# -*- coding: utf-8 -*-
import math
from collections import deque

from qgis.core import QgsPointXY

try:
    from qgis.core import NULL as QGIS_NULL
except ImportError:
    QGIS_NULL = None


def _to_float(val):
    if val is None or (QGIS_NULL is not None and val == QGIS_NULL):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ profondeurs


def _profondeur_regard(feat, ep_lit_pose):
    tn = _to_float(feat['tn'])
    fe = _to_float(feat['fe_radier'])
    if tn is None or fe is None:
        return None
    return tn - fe + ep_lit_pose


def _profondeur_tabouret(feat, ep_lit_pose):
    tn = _to_float(feat['tn'])
    fe = _to_float(feat['fe_entree'])
    if tn is None or fe is None:
        return None
    return tn - fe + ep_lit_pose


# ------------------------------------------------------------------ longueur 3D


def _longueur_3d(geom, z_start=None, z_end=None):
    l2d = geom.length()
    if not l2d or l2d <= 0:
        return 0.0
    if z_start is not None and z_end is not None:
        dz = z_end - z_start
        return (l2d ** 2 + dz ** 2) ** 0.5
    points = geom.asPolyline()
    if len(points) >= 2 and hasattr(points[0], 'z'):
        dz = points[-1].z() - points[0].z()
        return (l2d ** 2 + dz ** 2) ** 0.5
    return l2d


# ------------------------------------------------------------------ snapping


def _snap_regard(pt, regard_layer, tol=0.05):
    if regard_layer is None:
        return None
    best, best_d = None, float('inf')
    for feat in regard_layer.getFeatures():
        g = feat.geometry()
        if g.isEmpty():
            continue
        d = pt.distance(QgsPointXY(g.asPoint()))
        if d <= tol and d < best_d:
            best_d, best = d, feat
    return best


def _snap_tabouret(pt, tabouret_layer, tol=0.05):
    if tabouret_layer is None:
        return None
    best, best_d = None, float('inf')
    for feat in tabouret_layer.getFeatures():
        g = feat.geometry()
        if g.isEmpty():
            continue
        d = pt.distance(QgsPointXY(g.asPoint()))
        if d <= tol and d < best_d:
            best_d, best = d, feat
    return best


# ------------------------------------------------------------------ graph / BFS


def _build_graph(conduite_layer, regard_layer, tol=0.05):
    if regard_layer is None or conduite_layer is None:
        return {}, {}

    r_pts = [
        (feat.id(), QgsPointXY(feat.geometry().asPoint()))
        for feat in regard_layer.getFeatures()
        if not feat.geometry().isEmpty()
    ]

    def snap(pt):
        best_id, best_d = None, float('inf')
        for rid, rpt in r_pts:
            d = pt.distance(rpt)
            if d < best_d:
                best_d, best_id = d, rid
        return best_id if best_d <= tol else None

    # regard_id -> QgsFeature du regard (pour accéder aux attributs)
    regard_by_id = {}
    for feat in regard_layer.getFeatures():
        if not feat.geometry().isEmpty():
            regard_by_id[feat.id()] = feat

    graph = {}
    for feat in conduite_layer.getFeatures():
        g = feat.geometry()
        if g.isEmpty():
            continue
        line = g.asPolyline()
        r0 = snap(QgsPointXY(line[0]))
        r1 = snap(QgsPointXY(line[-1]))
        if r0 is None or r1 is None:
            continue
        graph.setdefault(r0, []).append((feat, r1))
        graph.setdefault(r1, []).append((feat, r0))

    return graph, regard_by_id


def _bfs(graph, start_id, end_id):
    queue = deque([(start_id, [start_id], [])])
    visited = {start_id}
    while queue:
        cur, r_path, c_path = queue.popleft()
        if cur == end_id:
            return r_path, c_path
        for c_feat, nb in graph.get(cur, []):
            if nb not in visited:
                visited.add(nb)
                queue.append((nb, r_path + [nb], c_path + [c_feat]))
    return None, None


# ------------------------------------------------------------------ calcul cubature


def _calc_remblai_volumes(largeur, l3d, diametre_mm, volume, config):
    """Retourne (vol_lit_pose, vol_conduite, vol_enrobage,
                 vol_chaussee_inf, vol_chaussee_sup, vol_remblai)."""
    if not l3d or largeur is None:
        return None, None, None, None, None, None

    ep_lit = config.get('ep_lit_pose', 0.10)
    ep_enr = config.get('ep_enrobage', 0.15)

    vol_lit_pose = largeur * l3d * ep_lit

    vol_conduite = None
    if diametre_mm:
        r_m = (diametre_mm / 1000.0) / 2.0
        vol_conduite = math.pi * r_m * r_m * l3d

    vol_enrobage = None
    if diametre_mm:
        d_m = diametre_mm / 1000.0
        vol_zone = largeur * l3d * (d_m + ep_enr)
        vol_enrobage = vol_zone - (vol_conduite or 0)

    ch_inf = config.get('chaussee_inf', False)
    ep_inf = config.get('ep_chaussee_inf', 0.20)
    vol_chaussee_inf = largeur * l3d * ep_inf if ch_inf else None

    ch_sup = config.get('chaussee_sup', False)
    ep_sup = config.get('ep_chaussee_sup', 0.08)
    vol_chaussee_sup = largeur * l3d * ep_sup if ch_sup else None

    vol_remblai = None
    if volume is not None:
        vol_remblai = volume
        for v in [vol_lit_pose, vol_enrobage, vol_conduite,
                   vol_chaussee_inf, vol_chaussee_sup]:
            if v is not None:
                vol_remblai -= v

    return vol_lit_pose, vol_conduite, vol_enrobage, \
        vol_chaussee_inf, vol_chaussee_sup, vol_remblai


def _make_result(id_, type_, reseau, nom_debut, nom_fin, l2d, l3d, pente_pct,
                 prof_debut, prof_fin, largeur, volume, materiau='', diametre=None,
                 err_debut=False, err_fin=False, vol_lit_pose=None,
                 vol_conduite=None, vol_enrobage=None, vol_chaussee_inf=None,
                 vol_chaussee_sup=None, vol_remblai=None):
    prof_moy = None
    if prof_debut is not None and prof_fin is not None:
        prof_moy = (prof_debut + prof_fin) / 2.0

    def _r(val, ndigits=2):
        return round(val, ndigits) if val is not None else None

    return {
        'id': id_,
        'type': type_,
        'reseau': reseau,
        'materiau': materiau or '',
        'diametre': round(diametre, 1) if diametre is not None else None,
        'nom_debut': nom_debut,
        'nom_fin': nom_fin,
        'l2d': round(l2d, 2) if l2d else 0.0,
        'l3d': round(l3d, 2) if l3d else 0.0,
        'pente_pct': round(pente_pct, 2) if pente_pct is not None else None,
        'prof_debut': round(prof_debut, 2) if prof_debut is not None else None,
        'prof_fin': round(prof_fin, 2) if prof_fin is not None else None,
        'prof_moy': round(prof_moy, 2) if prof_moy is not None else None,
        'largeur': largeur,
        'surface': round(largeur * l3d, 2) if (l3d and largeur is not None) else None,
        'volume': round(volume, 2) if volume is not None else None,
        'vol_lit_pose': _r(vol_lit_pose),
        'vol_conduite': _r(vol_conduite),
        'vol_enrobage': _r(vol_enrobage),
        'vol_chaussee_inf': _r(vol_chaussee_inf),
        'vol_chaussee_sup': _r(vol_chaussee_sup),
        'vol_remblai': _r(vol_remblai),
        'err_debut': err_debut,
        'err_fin': err_fin,
    }


def _nom_regard(feat):
    nom = feat['nom']
    if nom is not None and (QGIS_NULL is None or nom != QGIS_NULL):
        s = str(nom).strip()
        if s:
            return s
    return f"R{feat.id()}"


def _nom_tabouret(feat):
    nom = feat['nom']
    if nom is not None and (QGIS_NULL is None or nom != QGIS_NULL):
        s = str(nom).strip()
        if s:
            return s
    return f"T{feat.id()}"


def calculer_cubature_troncon(conduite_feat, regard_start, regard_end, config, reseau):
    geom = conduite_feat.geometry()
    if geom.isEmpty():
        return None

    l2d = geom.length()
    if not l2d or l2d <= 0:
        return None

    fe_start = _to_float(regard_start['fe_radier'])
    fe_end = _to_float(regard_end['fe_radier'])

    l3d = _longueur_3d(geom, fe_start, fe_end)

    prof_debut = _profondeur_regard(regard_start, config['ep_lit_pose'])
    prof_fin = _profondeur_regard(regard_end, config['ep_lit_pose'])

    err_debut = prof_debut is None
    err_fin = prof_fin is None

    largeur = config.get(f'largeur_conduite_{reseau.lower()}', 0.80)

    if err_debut and err_fin:
        volume = None
    else:
        if err_debut:
            prof_debut = prof_fin
        elif err_fin:
            prof_fin = prof_debut
        prof_moy = (prof_debut + prof_fin) / 2.0
        volume = largeur * l3d * prof_moy

    pente_pct = None
    if fe_start is not None and fe_end is not None and l2d > 0:
        pente_pct = (fe_start - fe_end) / l2d * 100

    diam = _to_float(conduite_feat['diametre'])
    v_lit, v_cond, v_enr, v_inf, v_sup, v_remb = \
        _calc_remblai_volumes(largeur, l3d, diam, volume, config)

    return _make_result(
        conduite_feat.id(), 'Conduite', reseau,
        _nom_regard(regard_start), _nom_regard(regard_end),
        l2d, l3d, pente_pct, prof_debut, prof_fin, largeur, volume,
        materiau=str(conduite_feat['materiau'] or '') if conduite_feat['materiau'] else '',
        diametre=diam,
        err_debut=err_debut, err_fin=err_fin,
        vol_lit_pose=v_lit, vol_conduite=v_cond, vol_enrobage=v_enr,
        vol_chaussee_inf=v_inf, vol_chaussee_sup=v_sup, vol_remblai=v_remb,
    )


def calculer_cubature_branchement(br_feat, tabouret_feat, config, reseau,
                                  regard_layer, conduite_layer):
    geom = br_feat.geometry()
    if geom.isEmpty():
        return None

    l2d = geom.length()
    if not l2d or l2d <= 0:
        return None

    # Profondeur au point de piquage (côté conduite mère)
    cote_piquage = _to_float(br_feat['cote_piquage'])

    # Snapper le premier point du branchement au regard le plus proche pour avoir le TN
    line = geom.asPolyline()
    if len(line) < 2:
        return None
    pt_start = QgsPointXY(line[0])
    regard_proche = _snap_regard(pt_start, regard_layer)
    prof_debut = None
    if regard_proche and cote_piquage is not None:
        tn_proche = _to_float(regard_proche['tn'])
        if tn_proche is not None:
            prof_debut = tn_proche - cote_piquage + config['ep_lit_pose']

    prof_fin = None
    if tabouret_feat:
        prof_fin = _profondeur_tabouret(tabouret_feat, config['ep_lit_pose'])

    err_debut = prof_debut is None
    err_fin = prof_fin is None

    # ΔZ pour L_3D : cote_piquage → fe_entree/fin
    z_end = None
    if tabouret_feat:
        z_end = _to_float(tabouret_feat['fe_entree'])
    l3d = _longueur_3d(geom, cote_piquage, z_end)

    largeur = config.get(f'largeur_branchement_{reseau.lower()}', 0.60)

    if err_debut and err_fin:
        volume = None
    else:
        if err_debut:
            prof_debut = prof_fin
        elif err_fin:
            prof_fin = prof_debut
        prof_moy = (prof_debut + prof_fin) / 2.0
        volume = largeur * l3d * prof_moy

    pente_pct = None
    if z_end is not None and cote_piquage is not None and l2d > 0:
        pente_pct = (cote_piquage - z_end) / l2d * 100

    nom_tab = _nom_tabouret(tabouret_feat) if tabouret_feat else ''
    diam = _to_float(br_feat['diametre'])
    v_lit, v_cond, v_enr, v_inf, v_sup, v_remb = \
        _calc_remblai_volumes(largeur, l3d, diam, volume, config)

    return _make_result(
        br_feat.id(), 'Branchement', reseau,
        f"C{br_feat['id_conduite'] or ''}", nom_tab,
        l2d, l3d, pente_pct, prof_debut, prof_fin, largeur, volume,
        materiau=str(br_feat['materiau'] or '') if br_feat['materiau'] else '',
        diametre=diam,
        err_debut=err_debut, err_fin=err_fin,
        vol_lit_pose=v_lit, vol_conduite=v_cond, vol_enrobage=v_enr,
        vol_chaussee_inf=v_inf, vol_chaussee_sup=v_sup, vol_remblai=v_remb,
    )


def calculer_cubature_reseau(couches, config, reseau):
    """Calcule la cubature pour toutes les conduites et branchements d'un réseau.

    couches: dict {'conduite', 'branchement', 'regard', 'tabouret'}
    config: dict avec ep_lit_pose, largeur_conduite_xx, largeur_branchement_xx
    reseau: 'EU' ou 'EP'
    Retourne list[dict].
    """
    results = []
    conduite_layer = couches.get('conduite')
    branchement_layer = couches.get('branchement')
    regard_layer = couches.get('regard')
    tabouret_layer = couches.get('tabouret')

    if conduite_layer is None or regard_layer is None:
        return results

    tol = 0.05

    # Indexer les tabourets pour les branchements
    t_pts = {}
    if tabouret_layer:
        for feat in tabouret_layer.getFeatures():
            g = feat.geometry()
            if not g.isEmpty():
                t_pts[feat.id()] = (QgsPointXY(g.asPoint()), feat)

    # ── Conduites ──────────────────────────────────────────────
    for c_feat in conduite_layer.getFeatures():
        g = c_feat.geometry()
        if g.isEmpty():
            continue
        line = g.asPolyline()
        if len(line) < 2:
            continue

        pt0, pt1 = QgsPointXY(line[0]), QgsPointXY(line[-1])
        r0 = _snap_regard(pt0, regard_layer, tol)
        r1 = _snap_regard(pt1, regard_layer, tol)
        if r0 is None or r1 is None:
            continue

        res = calculer_cubature_troncon(c_feat, r0, r1, config, reseau)
        if res:
            results.append(res)

    # ── Branchements ───────────────────────────────────────────
    if branchement_layer:
        for br_feat in branchement_layer.getFeatures():
            g = br_feat.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue

            # Chercher le tabouret à l'extrémité
            pt_end = QgsPointXY(line[-1])
            tabouret_feat = None
            best_d = float('inf')
            for tid, (tpt, tfeat) in t_pts.items():
                d = pt_end.distance(tpt)
                if d <= tol and d < best_d:
                    best_d, tabouret_feat = d, tfeat

            res = calculer_cubature_branchement(
                br_feat, tabouret_feat, config, reseau,
                regard_layer, conduite_layer,
            )
            if res:
                results.append(res)

    return results


def calculer_cubature_bfs(start_regard, end_regard, couches, config, reseau):
    """Calcule la cubature le long d'un chemin BFS entre deux regards.

    Retourne list[dict] pour chaque tronçon de conduite sur le chemin.
    """
    conduite_layer = couches.get('conduite')
    regard_layer = couches.get('regard')

    if conduite_layer is None or regard_layer is None:
        return []

    graph, regard_by_id = _build_graph(conduite_layer, regard_layer)
    r_ids, c_feats = _bfs(graph, start_regard.id(), end_regard.id())

    if r_ids is None:
        return []

    results = []
    for i, c_feat in enumerate(c_feats):
        r_start = regard_by_id.get(r_ids[i])
        r_end = regard_by_id.get(r_ids[i + 1])
        if r_start is None or r_end is None:
            continue
        res = calculer_cubature_troncon(c_feat, r_start, r_end, config, reseau)
        if res:
            results.append(res)

    return results
