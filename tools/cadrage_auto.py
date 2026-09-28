# tools/cadrage_auto.py
"""Cadrage automatique des planches d'impression.

À l'échelle demandée, on cherche à couvrir tout le réseau avec le moins de
planches possible. C'est un problème de couverture : on le traite par un
glouton, qui donne en pratique des résultats très proches de l'optimum sur
des réseaux d'assainissement — linéaires par nature, donc peu propices aux
cas pathologiques.

À chaque tour :

1. on part de l'élément non couvert le plus excentré (attaquer par le milieu
   gaspillerait des planches aux deux bouts) ;
2. on teste plusieurs orientations, dont l'axe principal du voisinage, et
   plusieurs décalages de la planche ;
3. on retient la combinaison qui couvre le plus d'éléments restants.

Chaque tour couvre au moins son point de départ : la terminaison est acquise.

Repère papier, identique à PrintTool._corners() :

    largeur -> ( cos θ, -sin θ)      hauteur -> ( sin θ, cos θ)

La zone carte n'est pas la feuille entière : le cartouche occupe le bas. Le
centre de la feuille est donc décalé d'un demi-cartouche par rapport au
centre de la zone carte, exactement comme dans _generate_pdf().
"""
import math

from qgis.PyQt import sip
from qgis.core import Qgis, QgsGeometry, QgsPointXY, QgsWkbTypes
from . import errlog

# Marge de sécurité autour du réseau, en MILLIMÈTRES PAPIER et non en
# pourcentage : ce qu'il faut protéger, ce sont les étiquettes (noms de
# regards, diamètres, cotes), et une étiquette occupe une taille fixe sur le
# papier quelle que soit l'échelle. Une marge en pourcentage aurait été
# généreuse à 1/1000 et insuffisante à 1/200, exactement l'inverse du besoin.
#
# 18 mm laissent la place à une étiquette de deux ou trois lignes débordant
# de son objet. La marge sert aussi de recouvrement entre planches voisines.
MARGE_MM = 18.0

# Une étiquette déborde de son point d'accroche d'environ six fois sa hauteur
# de texte (plusieurs lignes, plus le décalage d'ancrage). Ce repli ne sert
# que si le texte réel n'a pas pu être mesuré.
_DEBORD_ETIQUETTE = 6.0

# Largeur moyenne d'un caractère, en fraction de sa hauteur. Arial tourne
# autour de 0,5 ; on prend un peu large, une marge trop courte tronquant
# l'étiquette alors qu'une marge trop longue coûte au plus une planche.
_LARGEUR_CARACTERE = 0.60

# Au-delà, on cesse d'échantillonner : la plus longue étiquette est trouvée
# bien avant, et le calcul doit rester instantané sur un gros réseau.
_MAX_ETIQUETTES_MESUREES = 3000

# Plafond de la marge, en fraction de la plus petite dimension utile de la
# feuille. Sans lui, des étiquettes en unités carte à grande échelle
# réclameraient une marge si large qu'il ne resterait presque plus de zone
# cartographiée. Passé ce seuil on préfère une étiquette qui déborde à une
# planche qui ne montre plus rien.
_PLAFOND_MARGE = 0.20

# Plafond absolu de la marge, en mm papier. Les étiquettes mesurées à grande
# échelle (1/200) réclamaient jusqu'à 48 mm par côté : en A4 la moitié de la
# feuille partait en marge et le nombre de planches explosait. Une étiquette
# plus longue déborde un peu sur le bord de la feuille, c'est accepté.
MARGE_MAX_MM = 25.0

# Recouvrement entre planches voisines, en mm papier. Ce qui tombe dans la
# marge visible d'une planche compte comme couvert, sauf cette bande de bord :
# la planche suivante reprend donc le réseau RECOUVREMENT_MM avant la limite
# de la précédente, au lieu de toute la largeur de la marge.
RECOUVREMENT_MM = 8.0

# Orientations essayées, en degrés autour de l'axe principal du voisinage.
# Le balayage va jusqu'à 180° et non ±45° : une planche tournée de 90°
# échange sa largeur et sa hauteur, donc couvre une emprise différente. Sans
# ce quart de tour dans les candidats, un réseau linéaire imprimé en portrait
# ne pouvait jamais s'aligner sur la hauteur de la feuille — plus laid, et
# plus coûteux en planches.
_ECARTS_ANGLE = tuple(float(d) for d in range(0, 180, 15))

# Jeu autorisé autour de l'orientation flatteuse. Une planche dans cette
# fourchette est considérée comme alignée : parmi elles, c'est la couverture
# qui départage. Au-delà, la planche part de travers et n'est retenue que si
# aucune orientation alignée ne convient.
_TOLERANCE_ALIGNEMENT = math.radians(10.0)

# Décalages testés, en fraction de la planche. La planche doit contenir le
# point de départ : les décalages vont donc de « point au bord fin » à
# « point au bord début ».
_DECALAGES = (-0.98, -0.75, -0.5, -0.25, -0.02)


def marge_pour_etiquettes(label_size, echelle):
    """Marge en mm papier, tenant compte de la taille réelle des étiquettes.

    `label_size` est le dict rendu par projet_bet._read_label_size() :
    {'unit': 'points'|'map_units', 'value': float}. En unités carte, la
    taille du texte grandit au sol quand on dézoome : il faut la ramener au
    papier pour la comparer à une marge en millimètres.
    """
    marge = MARGE_MM
    if not label_size:
        return marge
    try:
        valeur = float(label_size.get('value') or 0)
        if valeur <= 0:
            return marge
        if label_size.get('unit') == 'points':
            hauteur_mm = valeur * 25.4 / 72.0
        else:
            # mètres -> millimètres papier à l'échelle demandée
            hauteur_mm = valeur * 1000.0 / float(echelle)
        return max(marge, _DEBORD_ETIQUETTE * hauteur_mm)
    except (TypeError, ValueError, ZeroDivisionError):
        return marge


def mesurer_etiquettes(couches, echelle):
    """Encombrement maximal des étiquettes, en millimètres papier.

    Retourne (largeur, hauteur). Le texte est réellement évalué : c'est sa
    largeur, et non la hauteur de la police, qui déborde des planches — une
    étiquette de regard tient facilement sur quarante millimètres.
    """
    from qgis.core import (QgsExpression, QgsExpressionContext,
                           QgsExpressionContextUtils)
    from ..gui.etiquettes import pal_settings

    larg_max = 0.0
    haut_max = 0.0

    for couche in _couches_valides(couches):
        try:
            pal = pal_settings(couche.labeling())
        except Exception:
            pal = None
        if pal is None:
            continue

        try:
            fmt = pal.format()
            if fmt.sizeUnit() == Qgis.RenderUnit.Points:
                haut_mm = fmt.size() * 25.4 / 72.0
            else:
                # Unités carte : la taille est au sol, on la ramène au papier.
                haut_mm = fmt.size() * 1000.0 / float(echelle)
        except Exception as _err:
            errlog.ignored(_err, "cadrage_auto.mesurer_etiquettes:139")
            continue
        if haut_mm <= 0:
            continue

        expression = None
        if getattr(pal, 'isExpression', False) and pal.fieldName:
            expression = QgsExpression(pal.fieldName)
            contexte = QgsExpressionContext()
            contexte.appendScopes(
                QgsExpressionContextUtils.globalProjectLayerScopes(couche))

        vus = 0
        for feat in couche.getFeatures():
            texte = None
            try:
                if expression is not None:
                    contexte.setFeature(feat)
                    texte = expression.evaluate(contexte)
                elif pal.fieldName:
                    texte = feat[pal.fieldName]
            except Exception:
                texte = None
            if texte in (None, ''):
                continue

            lignes = str(texte).splitlines() or [str(texte)]
            caracteres = max(len(ligne) for ligne in lignes)
            larg_max = max(larg_max,
                           caracteres * _LARGEUR_CARACTERE * haut_mm)
            haut_max = max(haut_max, len(lignes) * haut_mm * 1.25)

            vus += 1
            if vus >= _MAX_ETIQUETTES_MESUREES:
                break

    return larg_max, haut_max


def marge_depuis_couches(couches, echelle, label_size=None):
    """Marge en mm papier, déduite des étiquettes réellement affichées.

    Une étiquette est centrée sur son objet : elle déborde donc de la moitié
    de sa largeur. On ajoute sa hauteur pour les libellés multilignes et le
    décalage d'ancrage.
    """
    try:
        largeur, hauteur = mesurer_etiquettes(couches, echelle)
    except Exception:
        largeur = hauteur = 0.0
    if largeur <= 0:
        # Rien de mesurable : on retombe sur l'estimation par la police.
        return marge_pour_etiquettes(label_size, echelle)
    return max(MARGE_MM, largeur / 2.0 + hauteur)


def hauteur_cartouche_mm(h_mm):
    """Hauteur du cartouche, même formule que PrintTool et _generate_pdf."""
    return max(15.0, min(30.0, h_mm * 0.085))


def _couches_valides(couches):
    for couche in couches:
        if couche is not None and not sip.isdeleted(couche):
            yield couche


def collecter_points(couches, pas):
    """Points du réseau à couvrir, en coordonnées monde.

    Les lignes sont densifiées : sans cela, une conduite plus longue qu'une
    planche serait jugée couverte dès que ses deux extrémités le sont, alors
    que son milieu sort de la feuille.
    """
    pts = []
    for couche in _couches_valides(couches):
        for feat in couche.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            if pas > 0 and geom.type() == QgsWkbTypes.GeometryType.LineGeometry:
                try:
                    geom = geom.densifyByDistance(pas)
                except Exception as _err:
                    errlog.ignored(_err, "cadrage_auto.collecter_points:223")
            for vertex in geom.vertices():
                pts.append((vertex.x(), vertex.y()))
    return pts


def normaliser(angle):
    """Ramène un angle dans [-90°, +90°].

    Une planche tournée de 180° a exactement la même empreinte : autant
    retenir celle qui garde le nord vers le haut plutôt que la tête en bas.
    """
    while angle > math.pi / 2:
        angle -= math.pi
    while angle < -math.pi / 2:
        angle += math.pi
    return angle


def _ecart_angulaire(a, b):
    """Écart entre deux orientations, dans [0, 90°].

    Des orientations de planche sont définies modulo 180° : 10° et 190°
    posent la même feuille.
    """
    return abs(normaliser(a - b))


def _axe_principal(points, cx, cy):
    """Angle papier de l'axe principal d'un nuage (composantes principales).

    Retourne un angle de rotation directement utilisable par PrintTool, ou
    None si le nuage n'a pas de direction franche.
    """
    sxx = syy = sxy = 0.0
    for x, y in points:
        dx, dy = x - cx, y - cy
        sxx += dx * dx
        syy += dy * dy
        sxy += dx * dy
    if sxx + syy <= 0:
        return None
    # Vecteur propre dominant de la matrice de covariance 2x2. L'angle
    # obtenu est trigonométrique, alors que la largeur du papier pointe vers
    # (cos θ, -sin θ) : d'où la négation, sans laquelle les planches se
    # posent en travers du tracé au lieu de le suivre.
    theta = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
    return normaliser(-theta)


def _compter(points_uv, a0, w_u, b0, h_u):
    """Nombre de points du nuage projeté tombant dans la planche."""
    a1 = a0 + w_u
    b1 = b0 + h_u
    n = 0
    for a, b in points_uv:
        if a0 <= a <= a1 and b0 <= b <= b1:
            n += 1
    return n


def _nombre(valeur):
    """Attribut numérique en float, ou None : un champ vide remonte un QVariant."""
    try:
        if valeur is None or (hasattr(valeur, "isNull") and valeur.isNull()):
            return None
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _collecteur(couches):
    """Le collecteur principal, orienté de l'AVAL vers l'AMONT.

    Un dossier de plans se lit dans le sens de l'écoulement inverse : on part
    du point de rejet et on remonte. L'orientation ne se devine pas de la
    géométrie — les tronçons sont tracés dans l'ordre où l'opérateur a
    cliqué — elle se lit dans les cotes : des deux extrémités, l'aval est
    celle dont le regard a le fil d'eau le plus bas.

    Rend `None` si le réseau n'est pas coté, ou si les conduites ne forment
    pas une chaîne : l'appelant retombe alors sur le cheminement géométrique.
    """
    conduites, regards = [], []
    for couche in _couches_valides(couches):
        nom = (couche.name() or "").lower()
        if nom.startswith("conduite") and couche.featureCount():
            conduites.append(couche)
        elif nom.startswith("regard") and couche.featureCount():
            regards.append(couche)
    if not conduites:
        return None
    # Un projet peut porter EU et EP : le collecteur de référence est l'EU,
    # sauf s'il n'y en a pas.
    conduites.sort(key=lambda c: 0 if (c.name() or "").upper().endswith("EU") else 1)
    couche = conduites[0]

    geoms = [f.geometry() for f in couche.getFeatures()
             if f.geometry() is not None and not f.geometry().isEmpty()]
    if not geoms:
        return None
    try:
        fusion = QgsGeometry.unaryUnion(geoms).mergeLines()
    except Exception as _err:
        errlog.ignored(_err, "cadrage_auto._collecteur:union")
        return None
    if fusion is None or fusion.isEmpty():
        return None
    # Un réseau ramifié rend plusieurs brins : le collecteur est le plus long.
    parties = fusion.asGeometryCollection() or [fusion]
    ligne = max(parties, key=lambda g: g.length())
    sommets = ligne.asPolyline()
    if len(sommets) < 2:
        return None

    depart, arrivee = QgsPointXY(sommets[0]), QgsPointXY(sommets[-1])
    fe_depart = fe_arrivee = None
    for couche_r in regards:
        for feat in couche_r.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            point = QgsPointXY(geom.asPoint())
            fe = _nombre(feat["fe_radier"]) if "fe_radier" in \
                [ch.name() for ch in couche_r.fields()] else None
            if fe is None:
                continue
            if point.distance(depart) < 0.5:
                fe_depart = fe
            elif point.distance(arrivee) < 0.5:
                fe_arrivee = fe
    if fe_depart is None or fe_arrivee is None:
        return None
    if fe_depart > fe_arrivee:
        # Le début de la géométrie est en amont : on retourne la ligne.
        ligne = QgsGeometry.fromPolylineXY([QgsPointXY(p) for p in reversed(sommets)])
    return ligne


def ordonner_planches(planches, collecteur=None):
    """Renumérote les planches dans l'ordre où on lit le dossier.

    Le glouton attaque à chaque tour par l'élément non couvert le plus
    excentré : excellent pour couvrir, mais l'ordre obtenu saute d'un bout du
    chantier à l'autre. Or les planches sont numérotées dans l'ordre de la
    liste.

    Avec `collecteur` — la conduite principale orientée de l'aval vers
    l'amont — chaque planche est classée sur son abscisse le long du réseau :
    la feuille 1 est celle du point de rejet, et les numéros remontent
    l'écoulement sans jamais revenir en arrière. C'est l'ordre dans lequel un
    dossier d'assainissement se lit et se vérifie sur le terrain.

    Sans collecteur — réseau non coté, conduites en plusieurs morceaux — on
    retombe sur le cheminement géométrique : la plus à l'ouest, puis de
    proche en proche.
    """
    if len(planches) < 2:
        return planches

    if collecteur is not None:
        try:
            classees = sorted(
                planches,
                key=lambda pl: collecteur.lineLocatePoint(
                    QgsGeometry.fromPointXY(pl[0])))
            return classees
        except Exception as _err:
            errlog.ignored(_err, "cadrage_auto.ordonner_planches:abscisse")

    if len(planches) < 3:
        return planches
    reste = list(planches)
    # La plus à l'ouest, et à égalité la plus au nord.
    depart = min(reste, key=lambda pl: (pl[0].x(), -pl[0].y()))
    reste.remove(depart)
    ordre = [depart]

    while reste:
        dernier = ordre[-1][0]
        suivant = min(reste, key=lambda pl: ((pl[0].x() - dernier.x()) ** 2
                                             + (pl[0].y() - dernier.y()) ** 2))
        reste.remove(suivant)
        ordre.append(suivant)
    return ordre


#: Rotation maximale d'une planche retournee pour suivre sa voisine. Au-dela
#: d'un quart de tour, le nord part vers le bas de la feuille : la carte se lit
#: tete en bas, textes compris. On tolere un peu plus de 90 degres pour que deux
#: planches jointives a +85 et -85 se lisent dans le meme sens.
_ROTATION_MAX = math.radians(115.0)


def _retourner(centre, theta, carto_h_m):
    """Meme emprise cartographiee, cartouche de l'autre cote.

    Seul le centre de la FEUILLE bouge, d'une hauteur de cartouche, puisque
    celui-ci passe de l'autre cote de la zone carte.
    """
    # Le haut du papier avant retournement, en coordonnees monde.
    vx, vy = math.sin(theta), math.cos(theta)
    return (QgsPointXY(centre.x() + carto_h_m * vx, centre.y() + carto_h_m * vy),
            _signe(theta + math.pi))


def _signe(theta):
    """Angle ramene dans ]-pi, pi]."""
    return (theta + math.pi) % (2 * math.pi) - math.pi


def harmoniser_orientations(planches, carto_h_m, voisinage=None):
    """Nord vers le haut, et cartouches des planches voisines du meme cote.

    Une planche tournee de 180 degres couvre exactement la meme emprise, mais
    son cartouche part a l'oppose. Chaque planche est d'abord ramenee dans
    [-90, +90] : le nord reste dans la moitie haute de la feuille.

    Deux planches jointives peuvent alors se retrouver a +85 et -85 : au sol
    elles s'alignent, mais l'une se lit a l'envers de l'autre. On retourne la
    seconde pour suivre la premiere, mais seulement si elle reste sous
    _ROTATION_MAX. L'ancienne version retournait sans limite, et les
    retournements s'enchainaient de proche en proche : sur un reseau en
    boucle, les planches finissaient a 180-250 degres, cartes tete en bas —
    et le secteur suivant heritait de l'inversion (constate le 27/09/2026).

    `voisinage` : distance maximale entre deux centres de feuille pour que la
    seconde suive la premiere. Au-dela, les planches ne se touchent pas (autre
    rue, autre secteur) et chacune garde son nord.
    """
    nord = []
    for centre, theta in planches:
        if abs(_signe(theta)) > math.pi / 2:
            centre, theta = _retourner(centre, theta, carto_h_m)
        nord.append((centre, theta))
    if len(nord) < 2:
        return nord

    harmonisees = [nord[0]]
    for centre, theta in nord[1:]:
        c_prec, precedent = harmonisees[-1]
        voisine = (voisinage is None
                   or math.hypot(centre.x() - c_prec.x(), centre.y() - c_prec.y()) <= voisinage)
        if voisine and abs(_signe(theta - precedent)) > math.pi / 2:
            c2, t2 = _retourner(centre, theta, carto_h_m)
            if abs(_signe(t2)) <= _ROTATION_MAX:
                centre, theta = c2, t2
        harmonisees.append((centre, theta))
    return harmonisees


def _repere(centre, theta, carto_h_m):
    """(cx, cy, ux, uy, wx, wy) : centre de la zone carte et axes papier."""
    ux, uy = math.cos(theta), -math.sin(theta)
    wx, wy = math.sin(theta), math.cos(theta)
    return (centre.x() + (carto_h_m / 2.0) * wx,
            centre.y() + (carto_h_m / 2.0) * wy, ux, uy, wx, wy)


def repartir_planches(planches, points, w_u, h_u, debord_u, carto_h_m,
                      tours=20):
    """Répartit les planches le long du réseau, sans en changer le nombre.

    Le glouton place chaque planche pour avaler le plus de réseau restant :
    la première déborde souvent du bout du réseau, les dernières se
    recouvrent largement (rue de Grenoble, 27/09/2026 : une planche dépassait
    de 20 m l'extrémité sud, deux autres se superposaient aux trois quarts).

    Chaque tour attribue chaque point à la planche dont il est le plus proche
    du centre (distance rapportée aux dimensions utiles), puis recentre chaque
    planche sur l'emprise de ses points, orientation inchangée. Un tour n'est
    retenu que si tout le réseau reste couvert : sinon on garde le précédent.
    """
    if len(planches) < 2 or not points:
        return planches
    demi_w, demi_h = w_u / 2.0, h_u / 2.0

    def couvert(courantes):
        reperes = [_repere(c, t, carto_h_m) for c, t in courantes]
        for x, y in points:
            if not any(abs((x - cx) * ux + (y - cy) * uy) <= demi_w + debord_u
                       and abs((x - cx) * wx + (y - cy) * wy) <= demi_h + debord_u
                       for cx, cy, ux, uy, wx, wy in reperes):
                return False
        return True

    courantes = list(planches)
    for _tour in range(tours):
        reperes = [_repere(c, t, carto_h_m) for c, t in courantes]
        attribues = [[] for _ in courantes]
        for x, y in points:
            meilleur, k_min = None, 0
            for k, (cx, cy, ux, uy, wx, wy) in enumerate(reperes):
                a = (x - cx) * ux + (y - cy) * uy
                b = (x - cx) * wx + (y - cy) * wy
                d = max(abs(a) / demi_w, abs(b) / demi_h)
                if meilleur is None or d < meilleur:
                    meilleur, k_min = d, k
            attribues[k_min].append((x, y))

        nouvelles = []
        for (centre, theta), (cx, cy, ux, uy, wx, wy), pts in zip(
                courantes, reperes, attribues):
            if not pts:
                nouvelles.append((centre, theta))
                continue
            aa = [(x - cx) * ux + (y - cy) * uy for x, y in pts]
            bb = [(x - cx) * wx + (y - cy) * wy for x, y in pts]
            da = (min(aa) + max(aa)) / 2.0
            db = (min(bb) + max(bb)) / 2.0
            nouvelles.append((QgsPointXY(centre.x() + da * ux + db * wx,
                                         centre.y() + da * uy + db * wy), theta))

        deplacement = max(math.hypot(n[0].x() - c[0].x(), n[0].y() - c[0].y())
                          for n, c in zip(nouvelles, courantes))
        if not couvert(nouvelles):
            break
        courantes = nouvelles
        if deplacement < 0.05:
            break
    return courantes


def secteurs(points, distance):
    """Groupes de points séparés de plus de `distance` (union-find sur grille).

    Deux chantiers d'un même projet (deux rues éloignées) se cadrent chacun
    pour lui : aucune planche ne peut servir aux deux.
    """
    parent = list(range(len(points)))

    def racine(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cases = {}
    for i, (x, y) in enumerate(points):
        cases.setdefault((int(x // distance), int(y // distance)), []).append(i)
    for (cx, cy), membres in cases.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in cases.get((cx + dx, cy + dy), ()):
                    xj, yj = points[j]
                    for i in membres:
                        if i < j and (points[i][0] - xj) ** 2 + (points[i][1] - yj) ** 2 <= distance ** 2:
                            parent[racine(i)] = racine(j)
    groupes = {}
    for i in range(len(points)):
        groupes.setdefault(racine(i), []).append(points[i])
    return list(groupes.values())


def quadrillage(points, w_u, h_u, carto_h_m):
    """Planches nord en haut, posées en quadrillage sur l'emprise du réseau.

    Candidat de comparaison pour le glouton : sur un réseau maillé ou en
    boucle, les planches alignées tronçon par tronçon partent dans tous les
    sens et se recouvrent (8 planches là où un quadrillage en demande 4,
    27/09/2026). On essaie plusieurs calages de la grille et on garde celui
    qui touche le moins de cases occupées.
    """
    if not points:
        return []
    x0 = min(p[0] for p in points)
    y0 = min(p[1] for p in points)
    meilleure = None
    for fx in (0.0, 0.25, 0.5, 0.75):
        for fy in (0.0, 0.25, 0.5, 0.75):
            ox, oy = x0 - fx * w_u, y0 - fy * h_u
            cases = {(int((x - ox) // w_u), int((y - oy) // h_u)) for x, y in points}
            if meilleure is None or len(cases) < len(meilleure[0]):
                meilleure = (cases, ox, oy)
    cases, ox, oy = meilleure
    # Rotation nulle : le centre de la feuille est un demi-cartouche sous
    # celui de la zone carte.
    return [(QgsPointXY(ox + (i + 0.5) * w_u, oy + (j + 0.5) * h_u - carto_h_m / 2.0), 0.0)
            for i, j in sorted(cases)]


def _points_couverts(planche, points, w_u, h_u, debord_u, carto_h_m):
    """Points du réseau visibles sur la planche (zone utile + débord)."""
    cx, cy, ux, uy, wx, wy = _repere(planche[0], planche[1], carto_h_m)
    da, db = w_u / 2.0 + debord_u, h_u / 2.0 + debord_u
    return [(x, y) for x, y in points
            if abs((x - cx) * ux + (y - cy) * uy) <= da
            and abs((x - cx) * wx + (y - cy) * wy) <= db]


def elaguer_planches(planches, points, w_u, h_u, debord_u, carto_h_m):
    """Retire les planches dont tout le contenu figure deja sur les autres.

    Le glouton pose chaque planche pour couvrir le reste du reseau, sans
    revenir sur les precedentes : les derniers bouts de reseau donnent
    souvent une planche presque superposee a une voisine (mesure sur la rue
    de Grenoble : deux planches a 10 m l'une de l'autre). On retire d'abord
    celles qui montrent le moins, tant que chaque point reste sur au moins
    une planche.
    """
    if len(planches) < 2:
        return planches

    def couverts(centre, theta):
        ux, uy = math.cos(theta), -math.sin(theta)
        wx, wy = math.sin(theta), math.cos(theta)
        # Centre de la zone carte : un demi-cartouche au-dessus de la feuille.
        cx = centre.x() + (carto_h_m / 2.0) * wx
        cy = centre.y() + (carto_h_m / 2.0) * wy
        da, db = w_u / 2.0 + debord_u, h_u / 2.0 + debord_u
        return {i for i, (x, y) in enumerate(points)
                if abs((x - cx) * ux + (y - cy) * uy) <= da
                and abs((x - cx) * wx + (y - cy) * wy) <= db}

    ensembles = [couverts(c, t) for c, t in planches]
    gardees = list(range(len(planches)))
    for k in sorted(gardees, key=lambda i: len(ensembles[i])):
        autres = set()
        for j in gardees:
            if j != k:
                autres |= ensembles[j]
        if ensembles[k] <= autres:
            gardees.remove(k)
    return [planches[i] for i in gardees]


def calculer_planches(couches, w_mm, h_mm, echelle, max_planches=200,
                      marge_mm=None):
    """Planches couvrant le réseau à l'échelle donnée.

    Retourne une liste de (QgsPointXY centre_feuille, rotation_rad), prête à
    être passée à PrintTool. Liste vide si le réseau ne fournit aucun point.
    """
    facteur = echelle / 1000.0
    carto_mm = hauteur_cartouche_mm(h_mm)
    carto_h_m = carto_mm * facteur
    if marge_mm is None:
        marge_mm = MARGE_MM
    marge_mm = min(marge_mm, MARGE_MAX_MM,
                   _PLAFOND_MARGE * min(w_mm, h_mm - carto_mm))
    # Bande de marge considérée comme couverte (cf. RECOUVREMENT_MM).
    debord_u = max(0.0, marge_mm - RECOUVREMENT_MM) * facteur

    # Zone utile : la feuille, moins le cartouche, moins la marge à
    # étiquettes de chaque côté.
    w_u = (w_mm - 2 * marge_mm) * facteur
    h_u = (h_mm - carto_mm - 2 * marge_mm) * facteur
    if w_u <= 0 or h_u <= 0:
        return []

    pas = min(w_u, h_u) / 4.0
    points = collecter_points(couches, pas)
    if not points:
        return []

    # ── Cas d'une seule planche ──────────────────────────────────────────
    # À échelle large, tout le réseau tient sur une feuille. Le glouton la
    # poserait en partant d'une extrémité, ce qui collerait le chantier dans
    # un coin : ici on le veut au milieu de la carte, nord en haut.
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    if (max(xs) - min(xs)) <= w_u and (max(ys) - min(ys)) <= h_u:
        carte_x = (min(xs) + max(xs)) / 2.0
        carte_y = (min(ys) + max(ys)) / 2.0
        # Rotation nulle : la hauteur du papier pointe plein nord, le centre
        # de la feuille est donc un demi-cartouche sous le centre de la carte.
        return [(QgsPointXY(carte_x, carte_y - carto_h_m / 2.0), 0.0)]

    restants = list(dict.fromkeys(points))   # dédoublonne en gardant l'ordre
    rayon = math.hypot(w_u, h_u)
    planches = []

    while restants and len(planches) < max_planches:
        # ── 1. Point de départ : le plus excentré ────────────────────────
        gx = sum(p[0] for p in restants) / len(restants)
        gy = sum(p[1] for p in restants) / len(restants)
        px, py = max(restants, key=lambda p: (p[0] - gx) ** 2 + (p[1] - gy) ** 2)

        # ── 2. Voisinage utile : au-delà d'une diagonale, rien ne peut
        #       tomber sur la même planche que le point de départ.
        voisins = [p for p in restants
                   if abs(p[0] - px) <= rayon and abs(p[1] - py) <= rayon]

        vx = sum(p[0] for p in voisins) / len(voisins)
        vy = sum(p[1] for p in voisins) / len(voisins)
        axe = _axe_principal(voisins, vx, vy)

        angles = []
        if axe is not None:
            for ecart in _ECARTS_ANGLE:
                angles.append(normaliser(axe + math.radians(ecart)))
        angles.append(0.0)   # nord en haut, toujours dans les candidats

        # Orientation la plus flatteuse : la plus grande longueur du réseau
        # suit la plus grande dimension de la feuille, donc l'axe horizontal
        # médian en paysage et l'axe vertical médian en portrait. La largeur
        # du papier étant portée par u, l'axe du réseau doit tomber sur u en
        # paysage et sur v — soit un quart de tour — en portrait.
        if axe is None:
            ideal = 0.0
        elif w_mm >= h_mm:
            ideal = axe
        else:
            ideal = normaliser(axe + math.pi / 2.0)

        # Quelques orientations dans la tolérance, pour que la couverture ait
        # de quoi jouer sans que la planche parte de travers.
        for degres in (-10.0, -5.0, 5.0, 10.0):
            angles.append(normaliser(ideal + math.radians(degres)))
        angles.append(ideal)

        # ── 3. Meilleure orientation et meilleur décalage ─────────────────
        meilleur = None
        for angle in angles:
            # Repère papier : u = largeur, v = hauteur (cf. _corners).
            ct, st = math.cos(angle), math.sin(angle)
            ux, uy = ct, -st
            wx, wy = st, ct
            projetes = [((p[0] - px) * ux + (p[1] - py) * uy,
                         (p[0] - px) * wx + (p[1] - py) * wy)
                        for p in voisins]
            for fa in _DECALAGES:
                a0 = fa * w_u
                for fb in _DECALAGES:
                    b0 = fb * h_u
                    n = _compter(projetes, a0, w_u, b0, h_u)
                    # L'alignement prime sur la couverture : une planche
                    # penchée exploite sa diagonale et avale plus de linéaire,
                    # elle gagnerait donc toujours si on comptait d'abord les
                    # points — au prix d'un dossier de planches de travers.
                    # On préfère l'orientation flatteuse, quitte à une feuille
                    # de plus, et la couverture départage à l'intérieur de la
                    # tolérance.
                    ecart = _ecart_angulaire(angle, ideal)
                    aligne = 0 if ecart <= _TOLERANCE_ALIGNEMENT else 1
                    score = (-aligne, n, -ecart)
                    if meilleur is None or score > meilleur[0]:
                        meilleur = (score, angle, a0, b0, ux, uy, wx, wy)

        _score, angle, a0, b0, ux, uy, wx, wy = meilleur

        # ── 3 bis. Recentrer la planche sur ce qu'elle montre ─────────────
        # Le meilleur décalage vient d'une grille grossière : le réseau se
        # retrouve souvent contre un bord. On recentre sur l'emprise de tout
        # ce qui tombe dans la planche — y compris ce qu'une planche
        # précédente couvrait déjà, car le lecteur le voit aussi. Aucun point
        # ne peut en sortir : leur étendue tient déjà dans la planche.
        proches = [p for p in points
                   if abs(p[0] - px) <= rayon and abs(p[1] - py) <= rayon]
        couverts = [(a, b) for a, b in
                    (((p[0] - px) * ux + (p[1] - py) * uy,
                      (p[0] - px) * wx + (p[1] - py) * wy) for p in proches)
                    if a0 <= a <= a0 + w_u and b0 <= b <= b0 + h_u]
        if couverts:
            a_min = min(c[0] for c in couverts)
            a_max = max(c[0] for c in couverts)
            b_min = min(c[1] for c in couverts)
            b_max = max(c[1] for c in couverts)
            a0 = (a_min + a_max) / 2.0 - w_u / 2.0
            b0 = (b_min + b_max) / 2.0 - h_u / 2.0

        # ── 4. Centre de la zone carte, puis centre de la feuille ─────────
        ca = a0 + w_u / 2.0
        cb = b0 + h_u / 2.0
        carte_x = px + ca * ux + cb * wx
        carte_y = py + ca * uy + cb * wy
        # _generate_pdf remonte d'un demi-cartouche pour passer du centre
        # feuille au centre carte : on fait le chemin inverse.
        centre_x = carte_x - (carto_h_m / 2.0) * wx
        centre_y = carte_y - (carto_h_m / 2.0) * wy

        planches.append((QgsPointXY(centre_x, centre_y), angle))

        # ── 5. Retirer ce qui vient d'être couvert ───────────────────────
        # La marge est imprimée elle aussi : ce qui y tombe est visible sur
        # cette planche, à la bande de recouvrement près.
        a1, b1 = a0 + w_u + debord_u, b0 + h_u + debord_u
        a0, b0 = a0 - debord_u, b0 - debord_u
        avant = len(restants)
        reste = []
        for p in restants:
            a = (p[0] - px) * ux + (p[1] - py) * uy
            b = (p[0] - px) * wx + (p[1] - py) * wy
            if not (a0 <= a <= a1 and b0 <= b <= b1):
                reste.append(p)
        if len(reste) == avant:
            # Filet de sécurité : le point de départ est censé être couvert.
            # S'il ne l'est pas, on le retire pour ne pas boucler sans fin.
            reste = [p for p in restants if p != (px, py)]
        restants = reste

    def affiner(candidates, pts):
        # Planches superflues d'abord, puis répartition régulière, qui peut
        # en libérer une de plus.
        candidates = elaguer_planches(candidates, pts, w_u, h_u, debord_u, carto_h_m)
        candidates = repartir_planches(candidates, pts, w_u, h_u, debord_u, carto_h_m)
        return elaguer_planches(candidates, pts, w_u, h_u, debord_u, carto_h_m)

    planches = affiner(planches, points)

    # Secteur par secteur, le quadrillage nord en haut remplace les planches
    # du glouton s'il en économise au moins une : à nombre égal, les planches
    # alignées sur les rues se lisent mieux. Une rue droite presque nord-sud
    # tient en 3 planches quadrillées là où le glouton, qui l'attaque par un
    # bout, en pose 4 (rue de Grenoble, 27/09/2026) ; une boucle, à l'inverse,
    # se couvre mieux en suivant ses tronçons.
    finales = []
    for groupe in secteurs(points, rayon):
        dedans = set(groupe)
        a_lui = [pl for pl in planches
                 if any(p in dedans for p in _points_couverts(pl, points, w_u, h_u, debord_u, carto_h_m))]
        grille = affiner(quadrillage(groupe, w_u, h_u, carto_h_m), groupe)
        if grille and (not a_lui or len(grille) < len(a_lui)):
            a_lui = grille
        # Une planche à cheval sur deux secteurs ne doit pas sortir deux fois.
        finales.extend(pl for pl in a_lui if not any(pl is f for f in finales))
    planches = finales

    # L'ordre ensuite — il definit qui touche qui — puis le sens de lecture,
    # qui se propage de proche en proche le long de ce chemin. La numerotation
    # suit le collecteur, de l'aval vers l'amont, quand le reseau est cote.
    return harmoniser_orientations(
        ordonner_planches(planches, _collecteur(couches)), carto_h_m,
        voisinage=rayon)
