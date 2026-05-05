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


def recalc_pentes(conduite_layer, regard_layer, tol=0.05,
                  branchement_layer=None, tabouret_layer=None):
    """Recalcule les pentes des conduites et les cotes de piquage / pentes des
    branchements à partir des FE radier des regards et des FE entrée des tabourets."""
    if conduite_layer is None or regard_layer is None:
        return

    # ── Index des regards : {id: (point, fe_radier)} ────────────────
    r_pts = {}
    for feat in regard_layer.getFeatures():
        g = feat.geometry()
        if not g.isEmpty():
            r_pts[feat.id()] = (QgsPointXY(g.asPoint()), _to_float(feat['fe_radier']))

    # ── 1. Pentes des conduites ─────────────────────────────────────
    pente_idx = conduite_layer.fields().indexOf('pente')
    if pente_idx >= 0:
        conduite_layer.startEditing()
        for feat in conduite_layer.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue

            pt0, pt1 = QgsPointXY(line[0]), QgsPointXY(line[-1])
            fe0 = fe1 = None
            for _rid, (rpt, fe) in r_pts.items():
                if pt0.distance(rpt) <= tol:
                    fe0 = fe
                if pt1.distance(rpt) <= tol:
                    fe1 = fe

            if fe0 is None or fe1 is None:
                continue

            longueur = _to_float(feat['longueur']) or g.length()
            if not longueur or longueur <= 0:
                continue

            pente = (fe0 - fe1) / longueur * 100
            conduite_layer.changeAttributeValue(feat.id(), pente_idx, round(pente, 3))
        conduite_layer.commitChanges()

    # ── 2. Cotes de piquage et pentes des branchements ──────────────
    if branchement_layer is None:
        return

    cp_idx = branchement_layer.fields().indexOf('cote_piquage')
    bp_idx = branchement_layer.fields().indexOf('pente')
    if cp_idx < 0 and bp_idx < 0:
        return

    # Index des tabourets : {id: (point, fe_entree)}
    t_pts = {}
    if tabouret_layer is not None:
        for feat in tabouret_layer.getFeatures():
            g = feat.geometry()
            if not g.isEmpty():
                t_pts[feat.id()] = (QgsPointXY(g.asPoint()), _to_float(feat['fe_entree']))

    branchement_layer.startEditing()
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
        pt_dep = QgsPointXY(cond_line[0])
        pt_arr = QgsPointXY(cond_line[-1])
        fe_dep = fe_arr = None
        for _rid, (rpt, fe) in r_pts.items():
            if pt_dep.distance(rpt) <= tol:
                fe_dep = fe
            if pt_arr.distance(rpt) <= tol:
                fe_arr = fe

        if fe_dep is None or fe_arr is None:
            continue

        # Cote piquage = interpolation linéaire
        pk = _to_float(feat['pk_debut'])
        if pk is None:
            continue

        cote_piquage = fe_dep + (fe_arr - fe_dep) * (pk / cond_len)

        if cp_idx >= 0:
            branchement_layer.changeAttributeValue(
                feat.id(), cp_idx, round(cote_piquage, 3))

        # Pente du branchement = (cote_piquage - fe_arrivee) / longueur * 100
        if bp_idx >= 0:
            br_geom = feat.geometry()
            if br_geom.isEmpty():
                continue
            br_line = br_geom.asPolyline()
            if len(br_line) < 2:
                continue

            longueur = _to_float(feat['longueur']) or br_geom.length()
            if not longueur or longueur <= 0:
                continue

            # Le dernier point du branchement arrive sur un tabouret ou un regard
            pt_arrivee = QgsPointXY(br_line[-1])
            fe_arrivee = None
            for _tid, (tpt, fe) in t_pts.items():
                if pt_arrivee.distance(tpt) <= tol:
                    fe_arrivee = fe
                    break

            if fe_arrivee is None:
                for _rid, (rpt, fe) in r_pts.items():
                    if pt_arrivee.distance(rpt) <= tol:
                        fe_arrivee = fe
                        break

            if fe_arrivee is not None:
                pente_br = (cote_piquage - fe_arrivee) / longueur * 100
                branchement_layer.changeAttributeValue(
                    feat.id(), bp_idx, round(pente_br, 3))

    branchement_layer.commitChanges()
