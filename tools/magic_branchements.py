# tools/magic_branchements.py
"""Magic Box — branchements automatiques sur des tronçons choisis.

Trois modes, un branchement :
    parcelle : par parcelle riveraine (même non bâtie) ;
    bati     : par bâtiment riverain ;
    numero   : par adresse BAN riveraine.

Le calcul (`calculer`) ne touche à aucune couche : il rend des propositions
que l'interface affiche en aperçu. Seul `tracer` écrit, et il passe par
`DrawBranchementTool._finish`, comme le tracé à la main : tabouret, robinet
AEP, contrôle topologique et attributs restent ceux de l'outil.

Règles communes :
- le piquage est perpendiculaire à la conduite, au milieu du front de rue de
  la cible (parcelle, bâtiment) ou en face du numéro ;
- le branchement s'arrête sur la limite de parcelle côté rue, où se pose le
  tabouret ; en mode bâti sans parcelle, sur la façade ;
- les deux côtés de la rue sont raccordés, sauf choix d'un seul côté ;
- une cible déjà raccordée n'est pas touchée.

Les géométries et index viennent de `api`, qui porte la même logique pour
`creer_branchements` (tout le réseau, pilotage par script).
"""

from qgis.core import QgsFeatureRequest, QgsGeometry, QgsPointXY, QgsProject

from . import api
from . import territoire as terr

MODES = ('parcelle', 'bati', 'numero')
COTES = ('deux', 'gauche', 'droite')

COUCHE_BAN = "BAN Adresses"

FRONT_MIN = 1.0          # m : en deçà, la cible est après le bout du tronçon
ECART_MIN = 1.0          # m entre deux piquages
GARDE_REGARD = 0.5       # m : pas de piquage sur une chambre
SURFACE_MIN = 20.0       # m² : bandes et délaissés ne sont pas raccordés
TOL_FRONT = 3.0          # m : sommets de parcelle retenus comme front de rue
PORTEE_ADRESSE = 40.0    # m au-delà de distance_max pour chercher les numéros
TOL_DEJA = 5.0           # m le long de l'axe : numéro déjà raccordé
TOL_ADRESSE = 5.0        # m : point BAN « entrée » posé devant sa parcelle


# ── Accès aux couches ───────────────────────────────────────────────────────

def _couche(nom):
    if not nom:
        return None
    for c in QgsProject.instance().mapLayers().values():
        if c.name() == nom and hasattr(c, "getFeatures"):
            return c
    return None


def couches_manquantes(mode):
    """Noms des couches de fond nécessaires au mode et absentes du projet."""
    besoin = {
        'parcelle': [terr.couche_parcelles()],
        'bati': [terr.couche_bati()],
        'numero': [terr.couche_parcelles(), COUCHE_BAN],
    }[mode]
    return [n or "PCI - Parcelles" for n in besoin if not n or _couche(n) is None]


# ── Géométrie ───────────────────────────────────────────────────────────────

def _normale(axe, s):
    """Normale gauche unitaire de l'axe en s (sens de numérisation)."""
    tx, ty = api._tangente(axe, s)
    return -ty, tx


def _cote(axe, s, pa, cible_pt):
    """'gauche' ou 'droite' du point cible, dans le sens de l'axe."""
    nx, ny = _normale(axe, s)
    return 'gauche' if ((cible_pt.x() - pa.x()) * nx
                        + (cible_pt.y() - pa.y()) * ny) >= 0 else 'droite'


def _premier_croisement(pa, axe, s, vers_pt, surface, portee):
    """Premier point de la limite de `surface` sur le rayon perpendiculaire à
    l'axe issu de pa, tourné du côté de `vers_pt`."""
    nx, ny = _normale(axe, s)
    if (vers_pt.x() - pa.x()) * nx + (vers_pt.y() - pa.y()) * ny < 0:
        nx, ny = -nx, -ny
    rayon = QgsGeometry.fromPolylineXY(
        [pa, QgsPointXY(pa.x() + nx * portee, pa.y() + ny * portee)])
    bord = QgsGeometry(surface.constGet().boundary())
    touche = rayon.intersection(bord)
    if touche.isEmpty():
        return None
    pts = [QgsPointXY(v) for v in touche.vertices()]
    return min(pts, key=pa.distance) if pts else None


def _axe_proche(axes, geom):
    return min(range(len(axes)), key=lambda k: axes[k].distance(geom))


def _front(axe, geom, tol=None):
    """(s_min, s_max) : projection sur l'axe des sommets de `geom` qui font
    face à la rue (à moins de tol de la distance minimale), tous si tol=None."""
    d0 = axe.distance(geom)
    bornes = []
    for v in geom.vertices():
        p = QgsGeometry.fromPointXY(QgsPointXY(v))
        if tol is None or axe.distance(p) <= d0 + tol:
            bornes.append(axe.lineLocatePoint(p))
    if not bornes:
        return None
    return min(bornes), max(bornes)


def _parcelle_de(parcelles, geom_pt):
    """(fid, géométrie) de la parcelle qui contient le point, sinon (None, None)."""
    if parcelles is None:
        return None, None
    index, geoms = parcelles
    for pid in index.intersects(geom_pt.boundingBox().buffered(0.5)):
        if geoms[pid].contains(geom_pt):
            return pid, geoms[pid]
    return None, None


# ── Branchements existants ──────────────────────────────────────────────────

def _existants(couche_branchement):
    """Départs (piquages) et arrivées (tabourets) des branchements en place."""
    departs, arrivees = [], []
    for f in couche_branchement.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        ligne = g.asPolyline() if not g.isMultipart() else \
            [p for part in g.asMultiPolyline() for p in part]
        if len(ligne) < 2:
            continue
        departs.append(QgsPointXY(ligne[0]))
        arrivees.append(QgsPointXY(ligne[-1]))
    return departs, arrivees


# ── Espacement des piquages ─────────────────────────────────────────────────

def _espacer(cibles, axes, couche_regard, departs_existants):
    """Comme api._espacer_piquages, en évitant aussi les piquages existants."""
    interdits = {i: [] for i in range(len(axes))}
    for f in couche_regard.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        i = _axe_proche(axes, g)
        if axes[i].distance(g) <= GARDE_REGARD:
            interdits[i].append((axes[i].lineLocatePoint(g), GARDE_REGARD))
    for p in departs_existants:
        g = QgsGeometry.fromPointXY(p)
        i = _axe_proche(axes, g)
        if axes[i].distance(g) <= 0.5:
            interdits[i].append((axes[i].lineLocatePoint(g), ECART_MIN))
    for i in interdits:
        interdits[i].sort()

    cibles.sort(key=lambda c: (c["axe"], c["s"]))
    precedent = {}
    for c in cibles:
        i, s = c["axe"], c["s"]
        if i in precedent:
            s = max(s, precedent[i] + ECART_MIN)
        for sr, garde in interdits[i]:
            if abs(s - sr) < garde:
                s = sr + garde
        s = min(max(s, 0.0), axes[i].length())
        c["s"] = s
        precedent[i] = s


# ── Collecte des cibles par mode ────────────────────────────────────────────

def _cibles_parcelles(axes, union, parcelles_couche, distance_max,
                      arrivees, ecartes):
    cibles = []
    zone = union.buffer(distance_max, 8).boundingBox()
    for f in parcelles_couche.getFeatures(QgsFeatureRequest(zone)):
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        nom = _libelle_parcelle(f)
        if g.distance(union) > distance_max:
            continue
        if g.area() < SURFACE_MIN:
            ecartes.append({"cible": nom, "cause": "parcelle trop petite"})
            continue
        if g.intersects(union):
            ecartes.append({"cible": nom,
                            "cause": "la conduite traverse la parcelle"})
            continue
        zone_deja = g.buffer(0.5, 4)
        if any(zone_deja.contains(QgsGeometry.fromPointXY(p)) for p in arrivees):
            ecartes.append({"cible": nom, "cause": "déjà raccordée"})
            continue
        i = _axe_proche(axes, g)
        front = _front(axes[i], g, TOL_FRONT)
        if front is None or front[1] - front[0] < FRONT_MIN:
            ecartes.append({"cible": nom, "cause": "sans front sur le tronçon"})
            continue
        cibles.append({"cible": nom, "geom": QgsGeometry(g), "axe": i,
                       "s": 0.5 * (front[0] + front[1]),
                       "vers": g.pointOnSurface().asPoint(),
                       "limite": QgsGeometry(g)})
    return cibles


def _cibles_bati(axes, union, bati_couche, parcelles, distance_max,
                 arrivees, ecartes):
    cibles = []
    zone = union.buffer(distance_max, 8).boundingBox()
    for f in bati_couche.getFeatures(QgsFeatureRequest(zone)):
        g = f.geometry()
        if g is None or g.isEmpty() or g.distance(union) > distance_max:
            continue
        nom = "bâtiment %s" % f.id()
        if api._vrai(f, "construction_legere"):
            ecartes.append({"cible": nom, "cause": "construction légère"})
            continue
        i = _axe_proche(axes, g)
        front = _front(axes[i], g)
        if front is None or front[1] - front[0] < FRONT_MIN:
            ecartes.append({"cible": nom, "cause": "sans front sur le tronçon"})
            continue
        _pid, parcelle = _parcelle_de(parcelles, g.centroid())
        if _deja_en_face(axes[i], front, parcelle, g, distance_max, arrivees):
            ecartes.append({"cible": nom, "cause": "déjà raccordé"})
            continue
        cibles.append({"cible": nom, "geom": QgsGeometry(g), "axe": i,
                       "s": 0.5 * (front[0] + front[1]),
                       "vers": g.centroid().asPoint(),
                       "limite": parcelle, "bati": QgsGeometry(g)})
    return cibles


def _deja_en_face(axe, front, parcelle, bati, distance_max, arrivees):
    """Un tabouret existant dans la parcelle (ou près du bâtiment), en face
    du front du bâtiment."""
    for p in arrivees:
        gp = QgsGeometry.fromPointXY(p)
        if parcelle is not None:
            if not parcelle.buffer(0.5, 4).contains(gp):
                continue
        elif gp.distance(bati) > distance_max:
            continue
        s = axe.lineLocatePoint(gp)
        if front[0] - 1.0 <= s <= front[1] + 1.0:
            return True
    return False


def _parcelle_adresse(f, parcelles, par_idu):
    """Parcelle d'une adresse BAN.

    Les points BAN sont souvent des « entrées », posés un à quelques mètres
    devant la limite, côté trottoir : ils ne tombent alors dans aucune
    parcelle. Ordre de recherche : le champ BAN `cad_parcelles` (identifiants
    cadastraux), la parcelle qui contient le point, la plus proche à moins de
    TOL_ADRESSE.
    """
    g = f.geometry()
    if "cad_parcelles" in f.fields().names() and not api._vide(f["cad_parcelles"]):
        for idu in str(f["cad_parcelles"]).replace(",", "|").split("|"):
            if idu.strip() in par_idu:
                return par_idu[idu.strip()]
    _pid, parcelle = _parcelle_de(parcelles, g)
    if parcelle is not None or parcelles is None:
        return parcelle
    index, geoms = parcelles
    proches = [geoms[pid] for pid in index.intersects(
        g.boundingBox().buffered(TOL_ADRESSE))
        if geoms[pid].distance(g) <= TOL_ADRESSE]
    return min(proches, key=lambda x: x.distance(g)) if proches else None


def _cibles_numeros(axes, union, ban_couche, parcelles, parcelles_couche,
                    distance_max, arrivees, ecartes):
    cibles = []
    par_idu = {}
    if parcelles_couche is not None and "idu" in parcelles_couche.fields().names():
        par_idu = {str(f["idu"]): QgsGeometry(f.geometry())
                   for f in parcelles_couche.getFeatures()
                   if not api._vide(f["idu"])}
    portee = distance_max + PORTEE_ADRESSE
    zone = union.buffer(portee, 8).boundingBox()
    for f in ban_couche.getFeatures(QgsFeatureRequest(zone)):
        g = f.geometry()
        if g is None or g.isEmpty() or g.distance(union) > portee:
            continue
        nom = _libelle_adresse(f)
        parcelle = _parcelle_adresse(f, parcelles, par_idu)
        if parcelle is None:
            ecartes.append({"cible": nom, "cause": "aucune parcelle sous le numéro"})
            continue
        if parcelle.distance(union) > distance_max:
            continue    # parcelle en second rang : pas riveraine
        if parcelle.intersects(union):
            ecartes.append({"cible": nom,
                            "cause": "la conduite traverse la parcelle"})
            continue
        i = _axe_proche(axes, g)
        axe = axes[i]
        s = axe.lineLocatePoint(g)
        if s <= 0.01 or s >= axe.length() - 0.01:
            ecartes.append({"cible": nom, "cause": "hors du tronçon"})
            continue
        zone_deja = parcelle.buffer(0.5, 4)
        if any(zone_deja.contains(QgsGeometry.fromPointXY(p))
               and abs(axe.lineLocatePoint(QgsGeometry.fromPointXY(p)) - s) <= TOL_DEJA
               for p in arrivees):
            ecartes.append({"cible": nom, "cause": "déjà raccordé"})
            continue
        cibles.append({"cible": nom, "geom": QgsGeometry(g), "axe": i, "s": s,
                       "vers": g.asPoint(), "limite": parcelle})
    return cibles


def _libelle_parcelle(f):
    noms = f.fields().names()
    if "section" in noms and "numero" in noms and not api._vide(f["numero"]):
        return "parcelle %s %s" % (f["section"], f["numero"])
    for champ in ("idu", "id"):
        if champ in noms and not api._vide(f[champ]):
            return "parcelle %s" % f[champ]
    return "parcelle %s" % f.id()


def _libelle_adresse(f):
    noms = f.fields().names()
    num = f["numero"] if "numero" in noms and not api._vide(f["numero"]) else "?"
    rep = f["rep"] if "rep" in noms and not api._vide(f["rep"]) else ""
    voie = ""
    for champ in ("nom_voie", "nom_afnor", "voie"):
        if champ in noms and not api._vide(f[champ]):
            voie = " " + str(f[champ])
            break
    return "n° %s%s%s" % (num, rep, voie)


# ── Calcul ──────────────────────────────────────────────────────────────────

def calculer(couches, conduite_fids, mode, distance_max=10.0, cote='deux'):
    """Propositions de branchements pour les conduites choisies.

    couches : jeu de couches du réseau (plugin._get_couches).
    Rend {"propositions": [{cible, pa, pb, sur_parcelle}], "ecartes": [...]}.
    """
    if mode not in MODES:
        raise ValueError(mode)
    conduites = couches["conduite"]
    geoms = [f.geometry() for f in conduites.getFeatures(
        QgsFeatureRequest().setFilterFids(list(conduite_fids)))
        if not f.geometry().isEmpty()]
    if not geoms:
        return {"propositions": [], "ecartes": []}
    union = QgsGeometry.unaryUnion(geoms)
    axes = api._axes_continus(union)

    departs, arrivees = _existants(couches["branchement"])
    parcelles_couche = _couche(terr.couche_parcelles())
    parcelles = api._index_parcelles(terr.couche_parcelles())
    ecartes = []

    if mode == 'parcelle':
        cibles = _cibles_parcelles(axes, union, parcelles_couche, distance_max,
                                   arrivees, ecartes)
    elif mode == 'bati':
        cibles = _cibles_bati(axes, union, _couche(terr.couche_bati()),
                              parcelles, distance_max, arrivees, ecartes)
    else:
        cibles = _cibles_numeros(axes, union, _couche(COUCHE_BAN), parcelles,
                                 parcelles_couche, distance_max, arrivees,
                                 ecartes)

    # Côté de la rue, lu au milieu du front avant l'espacement.
    if cote != 'deux':
        gardees = []
        for c in cibles:
            axe = axes[c["axe"]]
            pa = QgsPointXY(axe.interpolate(c["s"]).asPoint())
            if _cote(axe, c["s"], pa, c["vers"]) == cote:
                gardees.append(c)
        cibles = gardees

    _espacer(cibles, axes, couches["regard"], departs)

    propositions = []
    for c in cibles:
        axe = axes[c["axe"]]
        pa = QgsPointXY(axe.interpolate(c["s"]).asPoint())
        if mode == 'bati':
            pb, sur_parcelle = api._arrivee_branchement(
                pa, axe, c["s"], c["bati"], parcelles, distance_max)
        else:
            if c["limite"].contains(QgsGeometry.fromPointXY(pa)):
                pb = None
            else:
                pb = _premier_croisement(pa, axe, c["s"], c["vers"],
                                         c["limite"], distance_max + 1.0)
            sur_parcelle = True
        if pb is None or pa.distance(pb) > distance_max or pa.distance(pb) < 0.1:
            ecartes.append({"cible": c["cible"],
                            "cause": "aucune limite à moins de %.1f m"
                                     % distance_max})
            continue
        propositions.append({"cible": c["cible"], "pa": pa, "pb": pb,
                             "sur_parcelle": sur_parcelle})
    return {"propositions": propositions, "ecartes": ecartes}


# ── Tracé ───────────────────────────────────────────────────────────────────

def tracer(canvas, reseau, couches, propositions, diametre=None, materiau=None):
    """Écrit les branchements proposés. Rend {"faits", "echecs", "messages"}."""
    from .draw_branchement_tool import DrawBranchementTool

    edition = [couches["tabouret"], couches["branchement"]]
    if reseau == 'AEP':
        edition.append(couches["regard"])   # robinet de branchement

    faits, echecs = 0, []
    with api._defauts_temporaires("branchement_%s" % reseau.lower(),
                                  diametre=diametre, materiau=materiau), \
            api.sans_fenetre() as sf, api._edition_groupee(*edition) as ed:
        for p in propositions:
            outil = DrawBranchementTool(canvas, reseau, couches,
                                        tol_m=api.TOL_SNAP_M,
                                        differer_ecriture=True)
            res = outil._snap_to_conduite(p["pa"])
            if not res:
                echecs.append({"cible": p["cible"], "cause": "piquage impossible"})
                continue
            outil.snapped_points = [res[0], p["pb"]]
            outil.points = [p["pa"], p["pb"]]
            outil.id_conduite, outil.pk_debut = res[1], res[2]
            avant = couches["branchement"].featureCount()
            outil._finish()
            if couches["branchement"].featureCount() > avant:
                faits += 1
            else:
                echecs.append({"cible": p["cible"], "cause": "refus topologique"})
    for err in ed.erreurs:
        echecs.append({"cible": None, "cause": "enregistrement refusé : %s" % err})
    return {"faits": faits, "echecs": echecs, "messages": sf.messages}


def defauts_branchement(reseau):
    """(diamètre, matériau) par défaut des branchements du réseau."""
    cle = "branchement_%s" % reseau.lower()
    try:
        d = api.config()["defauts"].get(cle, {})
    except Exception:
        d = {}
    if not d:
        from ..gui.quick_config_widgets import INITIAL_DEFAULTS
        diam, mat = INITIAL_DEFAULTS.get(cle, (160, "PVC"))
        return diam, mat
    return d.get("diametre"), d.get("materiau")
