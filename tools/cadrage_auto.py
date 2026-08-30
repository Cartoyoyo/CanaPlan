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
from qgis.core import Qgis, QgsPointXY, QgsWkbTypes
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


def ordonner_planches(planches):
    """Renumérote les planches selon un cheminement de proche en proche.

    Le glouton attaque à chaque tour par l'élément non couvert le plus
    excentré : excellent pour couvrir, mais l'ordre obtenu saute d'un bout du
    chantier à l'autre. Or les planches sont numérotées dans l'ordre de la
    liste, et on lit un dossier de plans en suivant le terrain.

    On repart donc de la planche la plus à l'ouest — le sens de lecture
    habituel — puis on enchaîne à chaque fois la plus proche encore libre.
    """
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


def harmoniser_orientations(planches, carto_h_m):
    """Met le cartouche des planches voisines du meme cote.

    Une planche tournee de 180 degres couvre exactement la meme emprise,
    mais son cartouche part a l'oppose. Comme les orientations sont ramenees
    dans [-90, +90], deux planches jointives peuvent se retrouver a +85 et
    -85 : au sol elles s'alignent, mais l'une se lit a l'envers de l'autre.

    On parcourt donc le cheminement en retournant une planche des qu'elle
    s'ecarte de plus d'un quart de tour de la precedente. Le retournement ne
    deplace pas la zone cartographiee : seul le centre de la FEUILLE bouge,
    d'une hauteur de cartouche, puisque celui-ci passe de l'autre cote.
    """
    if len(planches) < 2:
        return planches

    harmonisees = [planches[0]]
    for centre, theta in planches[1:]:
        precedent = harmonisees[-1][1]
        ecart = (theta - precedent + math.pi) % (2 * math.pi) - math.pi
        if abs(ecart) > math.pi / 2:
            # Le haut du papier avant retournement, en coordonnees monde.
            vx, vy = math.sin(theta), math.cos(theta)
            centre = QgsPointXY(centre.x() + carto_h_m * vx,
                                centre.y() + carto_h_m * vy)
            theta += math.pi
        harmonisees.append((centre, theta))
    return harmonisees


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
    marge_mm = min(marge_mm,
                   _PLAFOND_MARGE * min(w_mm, h_mm - carto_mm))

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
        a1, b1 = a0 + w_u, b0 + h_u
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

    # L'ordre d'abord — le cheminement definit qui touche qui — puis le sens
    # de lecture, qui se propage de proche en proche le long de ce chemin.
    return harmoniser_orientations(ordonner_planches(planches), carto_h_m)
