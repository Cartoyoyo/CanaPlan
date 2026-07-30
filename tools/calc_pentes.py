from qgis.core import QgsPointXY, QgsSpatialIndex

from .graph_utils import _to_float


def _build_point_index(layer, fe_field):
    """Index spatial + {fid: (point, fe)} d'une couche de points.

    Retourne (QgsSpatialIndex, dict). Couche None → index vide.
    """
    pts = {}
    index = QgsSpatialIndex()
    if layer is None:
        return index, pts
    for feat in layer.getFeatures():
        g = feat.geometry()
        if not g.isEmpty():
            pts[feat.id()] = (QgsPointXY(g.asPoint()),
                              _to_float(feat[fe_field]))
            index.addFeature(feat)
    return index, pts


def _fe_at(index, pts, pt, tol):
    """FE de l'entité la plus proche de pt dans le rayon tol, sinon None."""
    for fid in index.nearestNeighbor(pt, 1, tol):
        rpt, fe = pts[fid]
        if pt.distance(rpt) <= tol:
            return fe
    return None


def recalc_pentes(conduite_layer, regard_layer, tol=0.05,
                  branchement_layer=None, tabouret_layer=None):
    """Recalcule les pentes des conduites et les cotes de piquage / pentes des
    branchements à partir des FE radier des regards et des FE entrée des tabourets.

    Recherches par index spatial (O(n log m)) et écritures batch via le
    dataProvider (un seul lot de signaux, pas de pile d'undo : recalcul
    automatique, pas une action utilisateur annulable)."""
    if conduite_layer is None or regard_layer is None:
        return

    r_index, r_pts = _build_point_index(regard_layer, 'fe_radier')

    # ── 1. Pentes des conduites ─────────────────────────────────────
    pente_idx = conduite_layer.fields().indexOf('pente')
    if pente_idx >= 0:
        amap = {}
        for feat in conduite_layer.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue

            pt0, pt1 = QgsPointXY(line[0]), QgsPointXY(line[-1])
            fe0 = _fe_at(r_index, r_pts, pt0, tol)
            fe1 = _fe_at(r_index, r_pts, pt1, tol)
            if fe0 is None or fe1 is None:
                continue

            longueur = _to_float(feat['longueur']) or g.length()
            if not longueur or longueur <= 0:
                continue

            pente = (fe0 - fe1) / longueur * 100
            amap[feat.id()] = {pente_idx: round(pente, 3)}

        if amap:
            conduite_layer.dataProvider().changeAttributeValues(amap)
            conduite_layer.triggerRepaint()

    # ── 2. Cotes de piquage et pentes des branchements ──────────────
    if branchement_layer is None:
        return

    cp_idx = branchement_layer.fields().indexOf('cote_piquage')
    bp_idx = branchement_layer.fields().indexOf('pente')
    if cp_idx < 0 and bp_idx < 0:
        return

    t_index, t_pts = _build_point_index(tabouret_layer, 'fe_entree')

    amap = {}
    for feat in branchement_layer.getFeatures():
        id_conduite = feat['id_conduite']
        if id_conduite is None:
            continue

        conduite_feat = conduite_layer.getFeature(int(id_conduite))
        if not conduite_feat.isValid():
            continue

        cond_geom = conduite_feat.geometry()
        if cond_geom.isEmpty():
            continue

        cond_line = cond_geom.asPolyline()
        if len(cond_line) < 2:
            continue

        cond_len = cond_geom.length()
        if cond_len <= 0:
            continue

        # FE amont / aval de la conduite
        fe_dep = _fe_at(r_index, r_pts, QgsPointXY(cond_line[0]), tol)
        fe_arr = _fe_at(r_index, r_pts, QgsPointXY(cond_line[-1]), tol)
        if fe_dep is None or fe_arr is None:
            continue

        # Cote piquage = interpolation linéaire
        pk = _to_float(feat['pk_debut'])
        if pk is None:
            continue

        cote_piquage = fe_dep + (fe_arr - fe_dep) * (pk / cond_len)

        changes = {}
        if cp_idx >= 0:
            changes[cp_idx] = round(cote_piquage, 3)

        # Pente du branchement = (cote_piquage - fe_arrivee) / longueur * 100
        if bp_idx >= 0:
            br_geom = feat.geometry()
            if not br_geom.isEmpty():
                br_line = br_geom.asPolyline()
                longueur = _to_float(feat['longueur']) or br_geom.length()
                if len(br_line) >= 2 and longueur and longueur > 0:
                    # Le dernier point arrive sur un tabouret ou un regard
                    pt_arrivee = QgsPointXY(br_line[-1])
                    fe_arrivee = _fe_at(t_index, t_pts, pt_arrivee, tol)
                    if fe_arrivee is None:
                        fe_arrivee = _fe_at(r_index, r_pts, pt_arrivee, tol)
                    if fe_arrivee is not None:
                        pente_br = (cote_piquage - fe_arrivee) / longueur * 100
                        changes[bp_idx] = round(pente_br, 3)

        if changes:
            amap[feat.id()] = changes

    if amap:
        branchement_layer.dataProvider().changeAttributeValues(amap)
        branchement_layer.triggerRepaint()
