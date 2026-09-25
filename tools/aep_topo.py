# tools/aep_topo.py
"""Cohérence des robinets de branchement AEP, orientation des symboles AEP.

Le robinet de branchement (`robinet_branchement`) est un nœud posé sur la
conduite principale au point de piquage, sans couper la conduite — comme un
piquage EU/EP. Il n'est donc pas une extrémité de tronçon, et les outils qui
recalent les extrémités (déplacement d'un nœud, d'un piquage, suppression)
ne le voient pas.

`synchroniser_robinets` rétablit, après coup, la règle : un robinet au départ
de chaque branchement, et aucun robinet orphelin. Elle est idempotente et ne
touche à rien quand tout est déjà en place.
"""
import math

from qgis.core import NULL, QgsPointXY, QgsGeometry, QgsFeature, QgsSpatialIndex
from qgis.PyQt.QtCore import QTimer

from . import reseaux as R
from . import errlog

_TOL = 0.01          # m : robinet considéré au départ du branchement
_RAYON_APPARIEMENT = 25.0   # m : un robinet orphelin suit le branchement le plus proche


def _depart(feat):
    geom = feat.geometry()
    if geom is None or geom.isEmpty():
        return None
    line = geom.asPolyline()
    return QgsPointXY(line[0]) if line else None


def _extremites_conduites(conduite_layer):
    pts = []
    for f in conduite_layer.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        line = g.asPolyline()
        if len(line) >= 2:
            pts.append(QgsPointXY(line[0]))
            pts.append(QgsPointXY(line[-1]))
    return pts


def synchroniser_robinets(couches):
    """Recale les robinets de branchement AEP sur les départs de branchement.

    - branchement dont le départ porte déjà un nœud (robinet ou autre) : rien ;
    - sinon, le robinet orphelin le plus proche (25 m) y est déplacé — c'est le
      cas d'un piquage ou d'une conduite qu'on vient de déplacer ;
    - sinon un robinet est créé ;
    - les robinets restés orphelins sont supprimés, sauf s'ils sont aussi une
      extrémité de conduite (ils portent alors la topologie).

    Rend le nombre de robinets déplacés, créés et supprimés.
    """
    bilan = {'deplaces': 0, 'crees': 0, 'supprimes': 0}
    if not couches:
        return bilan
    noeuds = couches.get('regard')
    branchements = couches.get('branchement')
    conduites = couches.get('conduite')
    if noeuds is None or branchements is None:
        return bilan
    if noeuds.fields().indexOf('type') < 0:
        return bilan

    index = QgsSpatialIndex()
    pts = {}
    robinets = set()
    for f in noeuds.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        index.addFeature(f)
        pts[f.id()] = QgsPointXY(g.asPoint())
        if f['type'] == R.AEP_NOEUD_BRANCHEMENT:
            robinets.add(f.id())

    def noeud_en(pt):
        for fid in index.nearestNeighbor(pt, 1, _TOL):
            if pts[fid].distance(pt) <= _TOL:
                return fid
        return None

    departs_libres = []
    utilises = set()
    for br in branchements.getFeatures():
        pt = _depart(br)
        if pt is None:
            continue
        fid = noeud_en(pt)
        if fid is None:
            departs_libres.append(pt)
        else:
            utilises.add(fid)

    orphelins = [fid for fid in robinets if fid not in utilises]
    if not departs_libres and not orphelins:
        return bilan

    a_deplacer, a_creer = {}, []
    libres = set(orphelins)
    for pt in departs_libres:
        proche, d_min = None, _RAYON_APPARIEMENT
        for fid in libres:
            d = pts[fid].distance(pt)
            if d <= d_min:
                proche, d_min = fid, d
        if proche is not None:
            libres.discard(proche)
            a_deplacer[proche] = pt
        else:
            a_creer.append(pt)

    ext = _extremites_conduites(conduites) if (libres and conduites is not None) else []
    a_supprimer = [fid for fid in libres
                   if not any(pts[fid].distance(e) <= _TOL for e in ext)]

    if not (a_deplacer or a_creer or a_supprimer):
        return bilan

    etait_edite = noeuds.isEditable()
    if not etait_edite:
        noeuds.startEditing()
    try:
        for fid, pt in a_deplacer.items():
            noeuds.changeGeometry(fid, QgsGeometry.fromPointXY(pt))
        for pt in a_creer:
            feat = QgsFeature(noeuds.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(pt))
            feat.setAttribute('type', R.AEP_NOEUD_BRANCHEMENT)
            noeuds.addFeature(feat)
        for fid in a_supprimer:
            noeuds.deleteFeature(fid)
        if not etait_edite:
            noeuds.commitChanges()
    except Exception as err:        # la cohérence ne doit jamais bloquer l'outil appelant
        errlog.ignored(err, "aep_topo.synchroniser_robinets")
        if not etait_edite:
            noeuds.rollBack()
        return bilan

    bilan.update(deplaces=len(a_deplacer), crees=len(a_creer),
                 supprimes=len(a_supprimer))
    return bilan


# ─────────────────────────────────────────────────────────────────────────────
#  Orientation des symboles
# ─────────────────────────────────────────────────────────────────────────────
#
# Le style AEP lit l'orientation dans les champs sym_angle / sym_dir de la
# couche elle-même. Les calculer ici, en Python et dans le fil principal,
# évite que le rendu aille lire les couches conduite et branchement pendant
# qu'un outil les modifie — ce qui plantait QGIS (dessin d'un branchement).

_TOL_ORIENT = 0.05


def _azimut(p1, p2):
    """Azimut en degrés (0 = nord, sens horaire), comme azimuth() de QGIS."""
    return math.degrees(math.atan2(p2.x() - p1.x(), p2.y() - p1.y())) % 360.0


def _segment_sous(geom_line, pt):
    """(début, fin) du segment de `geom_line` le plus proche de `pt`."""
    line = geom_line.asPolyline()
    if len(line) < 2:
        return None
    _d, _proj, apres, _cote = geom_line.closestSegmentWithContext(pt)
    i = max(1, min(apres, len(line) - 1))
    return QgsPointXY(line[i - 1]), QgsPointXY(line[i])


def recalculer_orientations(couches):
    """Écrit sym_angle / sym_dir des nœuds et compteurs AEP.

    Écriture directe par le fournisseur, et seulement des valeurs qui
    changent : pas de session d'édition, pas d'entrée dans la pile
    d'annulation, pas de nouveau signal d'enregistrement (donc pas de
    boucle avec brancher_orientations).
    """
    if not couches:
        return
    noeuds = couches.get('regard')
    terminaux = couches.get('tabouret')
    conduites = couches.get('conduite')
    branchements = couches.get('branchement')
    if noeuds is None or conduites is None:
        return
    from .spatial_utils import nearest_line_feature

    def ecrire(couche, valeurs_par_fid):
        if not valeurs_par_fid:
            return
        couche.dataProvider().changeAttributeValues(valeurs_par_fid)
        couche.reload()
        couche.triggerRepaint()

    # Départs de branchement : direction du premier segment.
    departs = []
    arrivees = []
    for br in (branchements.getFeatures() if branchements else []):
        g = br.geometry()
        if g is None or g.isEmpty():
            continue
        line = g.asPolyline()
        if len(line) < 2:
            continue
        departs.append((QgsPointXY(line[0]), _azimut(QgsPointXY(line[0]), QgsPointXY(line[1]))))
        arrivees.append((QgsPointXY(line[-1]),
                         _azimut(QgsPointXY(line[-2]), QgsPointXY(line[-1]))))

    i_angle = noeuds.fields().indexOf('sym_angle')
    i_dir = noeuds.fields().indexOf('sym_dir')
    maj = {}
    if i_angle >= 0:
        for f in noeuds.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            pt = QgsPointXY(g.asPoint())
            angle = None
            cf, _p, _d = nearest_line_feature(conduites, pt, _TOL_ORIENT)
            if cf is not None:
                seg = _segment_sous(cf.geometry(), pt)
                if seg:
                    angle = round((_azimut(*seg) - 90.0) % 360.0, 2)
            direction = None
            for dp, az in departs:
                if dp.distance(pt) <= _TOL_ORIENT:
                    direction = round(az, 2)
                    break
            valeurs = {}
            if f.attribute(i_angle) != angle and not (angle is None and f.attribute(i_angle) in (None, NULL)):
                valeurs[i_angle] = angle
            if i_dir >= 0 and f.attribute(i_dir) != direction and not (direction is None and f.attribute(i_dir) in (None, NULL)):
                valeurs[i_dir] = direction
            if valeurs:
                maj[f.id()] = valeurs
    ecrire(noeuds, maj)

    if terminaux is not None and terminaux.fields().indexOf('sym_angle') >= 0:
        i_t = terminaux.fields().indexOf('sym_angle')
        maj_t = {}
        for f in terminaux.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            pt = QgsPointXY(g.asPoint())
            angle = None
            for ap, az in arrivees:
                if ap.distance(pt) <= _TOL_ORIENT:
                    angle = round((az + 90.0) % 360.0, 2)
                    break
            if f.attribute(i_t) != angle and not (angle is None and f.attribute(i_t) in (None, NULL)):
                maj_t[f.id()] = {i_t: angle}
        ecrire(terminaux, maj_t)


# Couches déjà branchées : {id de couche nœuds: minuteur}. Le minuteur regroupe
# les enregistrements successifs d'un même geste (conduite + nœud + robinet).
_BRANCHEES = {}


def brancher_orientations(couches):
    """Recalcule les orientations après chaque enregistrement d'une couche AEP.

    Idempotent : rappeler la fonction (à chaque _get_couches) ne double pas
    les connexions. Le recalcul est différé au retour dans la boucle
    d'événements, hors de la session d'édition qui vient de se fermer.
    """
    noeuds = couches.get('regard') if couches else None
    if noeuds is None:
        return
    cle = noeuds.id()
    if cle in _BRANCHEES:
        return
    minuteur = QTimer()
    minuteur.setSingleShot(True)
    minuteur.setInterval(0)

    def lancer():
        try:
            recalculer_orientations(couches)
        except RuntimeError as err:     # couche détruite entre-temps
            errlog.ignored(err, "aep_topo.recalculer_orientations")

    minuteur.timeout.connect(lancer)
    _BRANCHEES[cle] = minuteur
    for role in ('conduite', 'branchement', 'regard', 'tabouret'):
        couche = couches.get(role)
        if couche is not None:
            couche.afterCommitChanges.connect(minuteur.start)
            couche.willBeDeleted.connect(lambda c=cle: _BRANCHEES.pop(c, None))
    minuteur.start()
