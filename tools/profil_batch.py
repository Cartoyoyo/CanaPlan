# tools/profil_batch.py
"""Export batch de profils en long — génère des PDF sans interaction carte."""

from collections import deque

import sip
from qgis.core import QgsPointXY, QgsGeometry

from .graph_utils import _to_float, QGIS_NULL, build_graph


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_name(s):
    if not s:
        return ''
    return ''.join(c for c in str(s) if c not in r'\/:*?"<>|').strip().replace(' ', '_')


def _regard_name(feat):
    if feat is None:
        return ''
    v = feat['nom']
    if v and (QGIS_NULL is None or v != QGIS_NULL):
        return _safe_name(v)
    return ''


def _fval(feat, key):
    v = feat[key]
    if v is None or (QGIS_NULL is not None and v == QGIS_NULL):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Tronçon principal — plus long chemin BFS, deux passes (diamètre d'arbre)
# ─────────────────────────────────────────────────────────────────────────────

def _main_trunk_chain(couches):
    """
    Retourne (regards, conduites) du tronçon principal du réseau,
    où regards est la liste ordonnée des QgsFeature regards et conduites
    la liste ordonnée des QgsFeature conduites entre eux.
    Retourne (None, None) si pas de chaîne exploitable.
    """
    conduite_layer = couches.get('conduite') if couches else None
    regard_layer   = couches.get('regard')   if couches else None
    if conduite_layer is None or regard_layer is None:
        return None, None
    if sip.isdeleted(conduite_layer) or sip.isdeleted(regard_layer):
        return None, None

    graph, regard_by_id = build_graph(conduite_layer, regard_layer)
    if not graph:
        return None, None

    def _bfs_farthest(start_id):
        queue   = deque([(start_id, [start_id], [], 0.0)])
        visited = {start_id}
        best    = (start_id, [start_id], [], 0.0)
        while queue:
            cur, r_path, c_path, length = queue.popleft()
            if length > best[3]:
                best = (cur, r_path, c_path, length)
            for c_feat, nb in graph.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    lng = _to_float(c_feat['longueur']) or c_feat.geometry().length() or 0.0
                    queue.append((nb, r_path + [nb], c_path + [c_feat], length + lng))
        return best

    # Passe 1 : extrémité du plus long chemin depuis un nœud quelconque
    any_id = next(iter(graph))
    end1, _, _, _ = _bfs_farthest(any_id)

    # Passe 2 : depuis end1, on récupère le chemin complet
    _, r_ids, c_feats, _ = _bfs_farthest(end1)

    regards = [regard_by_id[rid] for rid in r_ids if rid in regard_by_id]
    if len(regards) < 2 or not c_feats:
        return None, None
    return regards, c_feats


def _trunk_axis_points(regards):
    """Convertit la liste ordonnée de regards en liste de QgsPointXY."""
    pts = []
    for r in regards:
        g = r.geometry()
        if not g.isEmpty():
            pts.append(QgsPointXY(g.asPoint()))
    return pts


# ─────────────────────────────────────────────────────────────────────────────
#  Piquages le long du tronçon principal
# ─────────────────────────────────────────────────────────────────────────────

def _compute_piquages(conduites, abscisses, couches):
    """
    Pour chaque conduite du tronçon, retrouve les branchements raccordés et
    leur position absolue le long du profil.
    Retourne {idx_conduite: [{'abscisse': float, 'nom': str}, ...]}.
    """
    piquages = {}
    br_layer  = couches.get('branchement')
    tab_layer = couches.get('tabouret')
    if br_layer is None or sip.isdeleted(br_layer):
        return piquages

    # Index tabourets par position pour retrouver le nom
    tab_by_pt = {}
    if tab_layer and not sip.isdeleted(tab_layer):
        for tf in tab_layer.getFeatures():
            g = tf.geometry()
            if g.isEmpty():
                continue
            tp = QgsPointXY(g.asPoint())
            v = tf['nom']
            tab_by_pt[(round(tp.x(), 3), round(tp.y(), 3))] = (
                str(v) if v and (QGIS_NULL is None or v != QGIS_NULL) else '')

    cid_to_idx = {c.id(): i for i, c in enumerate(conduites)}

    for br in br_layer.getFeatures():
        idx = cid_to_idx.get(br['id_conduite'])
        if idx is None:
            continue
        pk = _to_float(br['pk_debut']) or 0.0

        nom = ''
        g = br.geometry()
        if not g.isEmpty():
            line = g.asPolyline()
            if len(line) >= 2:
                end_pt = QgsPointXY(line[-1])
                nom = tab_by_pt.get((round(end_pt.x(), 3), round(end_pt.y(), 3)), '')

        piquages.setdefault(idx, []).append({
            'abscisse': abscisses[idx] + pk,
            'nom':      nom,
        })
    return piquages


# ─────────────────────────────────────────────────────────────────────────────
#  Export profil EU ou EP — un seul profil = tronçon principal complet
# ─────────────────────────────────────────────────────────────────────────────

def export_profils_eu_ep(couches, reseau, paper_format, output_dir):
    """
    Profil du tronçon principal (plus long chemin BFS) → PDF une page.
    Le nom de fichier est construit à partir du 1er et dernier regard :
    {nom_dep}_{nom_arr}_PROFIL.pdf
    Retourne (n_ok, n_skip, output_path).
    """
    try:
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
    except ImportError:
        return 0, 0, None

    from ..gui.profil_dialog import ProfilDialog, _EXPORT_DPI
    import os

    regards, conduites = _main_trunk_chain(couches)
    if not regards or not conduites:
        return 0, 1, None

    nom_dep = _regard_name(regards[0]) or f'R{reseau}_DEP'
    nom_arr = _regard_name(regards[-1]) or f'R{reseau}_ARR'
    output_path = os.path.join(output_dir, f'{nom_dep}_{nom_arr}_PROFIL.pdf')

    abscisses = [0.0]
    for c in conduites:
        lng = _to_float(c['longueur']) or c.geometry().length() or 0.0
        abscisses.append(abscisses[-1] + lng)

    piquages = _compute_piquages(conduites, abscisses, couches)

    data = {
        'reseau':    reseau,
        'regards':   regards,
        'conduites': conduites,
        'abscisses': abscisses,
        'piquages':  piquages,
    }
    opts = {
        'cartouche':          True,
        'fleches_piquages':   True,
        'noms_piquages':      True,
        'distances_piquages': True,
        'format_papier':      paper_format,
    }
    dpi = _EXPORT_DPI.get(paper_format, 150)

    try:
        dlg = ProfilDialog(data, opts)
        with PdfPages(output_path) as pdf:
            pdf.savefig(dlg.figure, dpi=dpi)
        plt.close(dlg.figure)
        dlg.close()
        return 1, 0, output_path
    except Exception:
        return 0, 1, None


# ─────────────────────────────────────────────────────────────────────────────
#  Export profil groupé EU+EP — axe = tronçon principal du réseau de référence
# ─────────────────────────────────────────────────────────────────────────────

_BUFFER_DIST = 3.0   # mètres autour de l'axe (idem ProfilGroupeTool)


def export_profils_groupe(couches_eu, couches_ep, paper_format, output_dir,
                          reseau_ref='EU'):
    """
    Profil groupé EU+EP avec axe = tronçon principal du réseau reseau_ref.
    Le nom de fichier inclut les 1ers/derniers regards EU et EP :
    {eu_dep}_{eu_arr}_{ep_dep}_{ep_arr}_PROFIL.pdf
    Retourne (True, output_path) si réussi, sinon (False, None).
    """
    try:
        from matplotlib.backends.backend_pdf import PdfPages
        import matplotlib.pyplot as plt
    except ImportError:
        return False, None

    from ..gui.profil_groupe_dialog import ProfilGroupeDialog
    from ..gui.profil_dialog import _EXPORT_DPI
    import os

    ref_couches = couches_eu if reseau_ref == 'EU' else couches_ep
    regards, _ = _main_trunk_chain(ref_couches)
    if not regards:
        return False, None

    pts = _trunk_axis_points(regards)
    if len(pts) < 2:
        return False, None

    data = _compute_groupe_data(couches_eu, couches_ep, pts)
    if data is None or not data['conduites']:
        return False, None

    def _ends(reseau):
        c_list = [c for c in data['conduites'] if c['reseau'] == reseau]
        if not c_list:
            return None, None
        start_c = min(c_list, key=lambda c: c['x0'])
        end_c   = max(c_list, key=lambda c: c['x1'])
        return _safe_name(start_c.get('nom_r0')), _safe_name(end_c.get('nom_r1'))

    eu_s, eu_e = _ends('EU')
    ep_s, ep_e = _ends('EP')
    parts = [v for v in (eu_s, eu_e, ep_s, ep_e) if v]
    if not parts:
        parts = ['profil_groupe']
    output_path = os.path.join(output_dir, '_'.join(parts) + '_PROFIL.pdf')

    opts = {
        'cartouche':          True,
        'fleches_piquages':   True,
        'noms_piquages':      True,
        'distances_piquages': True,
        'format_papier':      paper_format,
    }
    dpi = _EXPORT_DPI.get(paper_format, 150)

    try:
        dlg = ProfilGroupeDialog(data, options=opts)
        with PdfPages(output_path) as pdf:
            pdf.savefig(dlg.figure, dpi=dpi)
        plt.close(dlg.figure)
        dlg.close()
        return True, output_path
    except Exception:
        return False, None


# ─────────────────────────────────────────────────────────────────────────────
#  Calcul des données pour ProfilGroupeDialog (miroir de ProfilGroupeTool)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_groupe_data(couches_eu, couches_ep, pts):
    ref_line = QgsGeometry.fromPolylineXY(pts)
    ref_len  = ref_line.length()
    if ref_len < 0.01:
        return None

    buffer_geom = ref_line.buffer(_BUFFER_DIST, 8)

    regard_lookup = []
    for couches in (couches_eu, couches_ep):
        if couches is None:
            continue
        rl = couches.get('regard')
        if rl is None or sip.isdeleted(rl):
            continue
        for feat in rl.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            v = feat['nom']
            regard_lookup.append((
                QgsPointXY(g.asPoint()),
                {
                    'tn':        _fval(feat, 'tn'),
                    'fe_radier': _fval(feat, 'fe_radier'),
                    'nom':       str(v) if v and (QGIS_NULL is None or v != QGIS_NULL) else '—',
                }
            ))

    def snap_regard(pt, tol=1.0):
        best, best_d = None, float('inf')
        for rpt, rdata in regard_lookup:
            d = pt.distance(rpt)
            if d < best_d:
                best_d, best = d, rdata
        return best if best_d <= tol else None

    conduites_data = []

    for reseau, couches in (('EU', couches_eu), ('EP', couches_ep)):
        if couches is None:
            continue
        cl = couches.get('conduite')
        if cl is None or sip.isdeleted(cl):
            continue
        for feat in cl.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue

            pt0, pt1 = QgsPointXY(line[0]), QgsPointXY(line[-1])
            if not (buffer_geom.contains(QgsGeometry.fromPointXY(pt0)) and
                    buffer_geom.contains(QgsGeometry.fromPointXY(pt1))):
                continue

            x0 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt0))
            x1 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt1))
            r0, r1 = snap_regard(pt0), snap_regard(pt1)

            if x0 > x1:
                x0, x1, r0, r1 = x1, x0, r1, r0

            conduites_data.append({
                'reseau': reseau,
                'feat':   feat,
                'x0':     x0,
                'x1':     x1,
                'fe0':    r0['fe_radier'] if r0 else None,
                'fe1':    r1['fe_radier'] if r1 else None,
                'tn0':    r0['tn']        if r0 else None,
                'tn1':    r1['tn']        if r1 else None,
                'nom_r0': r0['nom']       if r0 else '—',
                'nom_r1': r1['nom']       if r1 else '—',
            })

    # Piquages
    piquages = []
    cid_to_cdata = {(c['reseau'], c['feat'].id()): c for c in conduites_data}

    for reseau, couches in (('EU', couches_eu), ('EP', couches_ep)):
        if couches is None:
            continue
        br_layer  = couches.get('branchement')
        tab_layer = couches.get('tabouret')
        if br_layer is None or sip.isdeleted(br_layer):
            continue

        tab_by_pt = {}
        if tab_layer and not sip.isdeleted(tab_layer):
            for tf in tab_layer.getFeatures():
                g = tf.geometry()
                if g.isEmpty():
                    continue
                tp = QgsPointXY(g.asPoint())
                key = (round(tp.x(), 3), round(tp.y(), 3))
                v = tf['nom']
                tab_by_pt[key] = str(v) if v and (QGIS_NULL is None or v != QGIS_NULL) else ''

        for br in br_layer.getFeatures():
            g = br.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue
            start_pt = QgsPointXY(line[0])
            x_piq = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(start_pt))
            fe_piq = None
            parent = cid_to_cdata.get((reseau, br['id_conduite']))
            if parent:
                x0, x1 = parent['x0'], parent['x1']
                fe0, fe1 = parent['fe0'], parent['fe1']
                if x1 > x0 and fe0 is not None and fe1 is not None:
                    t = max(0.0, min(1.0, (x_piq - x0) / (x1 - x0)))
                    fe_piq = fe0 + t * (fe1 - fe0)
            end_pt = QgsPointXY(line[-1])
            nom_tab = tab_by_pt.get((round(end_pt.x(), 3), round(end_pt.y(), 3)), '')
            piquages.append({'x': x_piq, 'fe': fe_piq, 'nom': nom_tab, 'reseau': reseau})

    return {'conduites': conduites_data, 'ref_length': ref_len, 'piquages': piquages}
