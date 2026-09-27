# tools/profil_batch.py
"""Export batch de profils en long — génère des PDF sans interaction carte."""

from collections import deque

from qgis.PyQt import sip
from qgis.core import QgsPointXY, QgsGeometry

from .graph_utils import _to_float, QGIS_NULL, build_graph, bfs


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

    # Le regard le plus profond doit toujours apparaître à gauche du
    # profil : si c'est celui de fin, on refait le même BFS dans l'autre
    # sens (et non une simple inversion des listes, pour ne pas décaler
    # les piquages qui restent mesurés depuis le début de leur conduite).
    prof_first = _fval(regards[0], 'profondeur')
    prof_last  = _fval(regards[-1], 'profondeur')
    if prof_last is not None and (prof_first is None or prof_last > prof_first):
        r_ids_rev, c_feats_rev = bfs(graph, r_ids[-1], r_ids[0])
        if r_ids_rev is not None:
            r_ids, c_feats = r_ids_rev, c_feats_rev
            regards = [regard_by_id[rid] for rid in r_ids if rid in regard_by_id]

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

def _robinets(couches):
    """AEP : fonction pt -> nom du robinet de branchement ; None en EU/EP,
    où le branchement prend le nom de son tabouret."""
    rl = couches.get('regard')
    if rl is None or sip.isdeleted(rl):
        return None
    from .aep_topo import noms_robinets
    return noms_robinets(rl)


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

    cl = couches.get('conduite')
    if cl is not None and not sip.isdeleted(cl):
        from .calc_pentes import rattacher_branchements
        rattacher_branchements(cl, br_layer)

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
    robinet_en = _robinets(couches)

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
                if robinet_en is not None:
                    nom = robinet_en(QgsPointXY(line[0]))
                else:
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
#  Export profil groupé EU / EP / AEP — axe = tronçon principal du réseau de référence
# ─────────────────────────────────────────────────────────────────────────────

_BUFFER_DIST = 3.0   # mètres autour de l'axe (idem ProfilGroupeTool)


def export_profils_groupe(couches_eu, couches_ep, paper_format, output_dir,
                          reseau_ref='EU', couches_aep=None):
    """
    Profil groupé EU + EP (+ AEP si `couches_aep`) avec axe = tronçon principal
    du réseau `reseau_ref`.
    Le nom de fichier enchaîne les 1ers/derniers regards de chaque réseau :
    {eu_dep}_{eu_arr}_{ep_dep}_{ep_arr}[_{aep_dep}_{aep_arr}]_PROFIL.pdf
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

    jeux = _jeux(couches_eu, couches_ep, couches_aep)
    ref_couches = dict(jeux).get(reseau_ref) or couches_eu
    regards, _ = _main_trunk_chain(ref_couches)
    if not regards:
        return False, None

    pts = _trunk_axis_points(regards)
    if len(pts) < 2:
        return False, None

    data = calculer_donnees_groupe(jeux, pts)
    if data is None or not data['conduites']:
        return False, None

    def _ends(reseau):
        c_list = [c for c in data['conduites'] if c['reseau'] == reseau]
        if not c_list:
            return None, None
        start_c = min(c_list, key=lambda c: c['x0'])
        end_c   = max(c_list, key=lambda c: c['x1'])
        return _safe_name(start_c.get('nom_r0')), _safe_name(end_c.get('nom_r1'))

    parts = []
    for reseau, _c in jeux:
        parts.extend(v for v in _ends(reseau) if v and v != '—')
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


def _jeux(couches_eu, couches_ep, couches_aep=None):
    """[(réseau, couches)] des réseaux fournis, dans l'ordre EU, EP, AEP."""
    jeux = [('EU', couches_eu), ('EP', couches_ep)]
    if couches_aep:
        jeux.append(('AEP', couches_aep))
    return [(r, c) for r, c in jeux if c]


# ─────────────────────────────────────────────────────────────────────────────
#  Calcul des données pour ProfilGroupeDialog (outil carte et export)
# ─────────────────────────────────────────────────────────────────────────────

def _nom(v):
    return str(v) if v and (QGIS_NULL is None or v != QGIS_NULL) else '—'


def calculer_donnees_groupe(jeux, pts, buffer_dist=_BUFFER_DIST):
    """Conduites et piquages des réseaux `jeux` projetés sur l'axe `pts`.

    jeux : [(réseau, couches)], réseaux EU, EP et/ou AEP.

    Une conduite n'entre que si ses deux extrémités sont à moins de
    `buffer_dist` de l'axe ; un piquage, que si sa conduite mère est entrée.
    Chaque réseau a sa propre table de regards : sans cela, un nœud AEP posé
    à moins d'un mètre d'un regard EU (réseaux parallèles dans la même rue)
    lui prenait son TN et son fil d'eau.

    AEP : `muet0` / `muet1` signalent les nœuds sans appareil (coudes, tés…),
    que le dessin ne représente ni en cheminée ni dans le cartouche.
    """
    from .spatial_utils import PointGrid
    from . import reseaux as R

    ref_line = QgsGeometry.fromPolylineXY(pts)
    ref_len  = ref_line.length()
    if ref_len < 0.01:
        return None
    buffer_geom = ref_line.buffer(buffer_dist, 8)

    def dedans(pt):
        return buffer_geom.contains(QgsGeometry.fromPointXY(pt))

    conduites_data = []
    piquages = []
    for reseau, couches in jeux:
        rl = couches.get('regard')
        cl = couches.get('conduite')
        if rl is None or sip.isdeleted(rl) or cl is None or sip.isdeleted(cl):
            continue
        aep = R.est_aep(reseau) and rl.fields().indexOf('type') >= 0

        lookup = []
        for feat in rl.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            code = feat['type'] if aep else None
            lookup.append((QgsPointXY(g.asPoint()), {
                'tn':        _fval(feat, 'tn'),
                'fe_radier': _fval(feat, 'fe_radier'),
                'nom':       _nom(feat['nom']),
                'type':      code,
                'muet':      aep and not R.aep_dessine(code),
            }))
        grille = PointGrid(lookup)

        cdata_reseau = {}
        for feat in cl.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue
            pt0, pt1 = QgsPointXY(line[0]), QgsPointXY(line[-1])
            if not (dedans(pt0) and dedans(pt1)):
                continue
            x0 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt0))
            x1 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt1))
            r0, r1 = grille.nearest(pt0, 1.0), grille.nearest(pt1, 1.0)
            if x0 > x1:
                x0, x1, r0, r1 = x1, x0, r1, r0
            c = {
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
                'muet0':  bool(r0 and r0['muet']),
                'muet1':  bool(r1 and r1['muet']),
            }
            conduites_data.append(c)
            cdata_reseau[feat.id()] = c

        br_layer  = couches.get('branchement')
        tab_layer = couches.get('tabouret')
        if br_layer is None or sip.isdeleted(br_layer):
            continue
        cl = couches.get('conduite')
        if cl is not None and not sip.isdeleted(cl):
            from .calc_pentes import rattacher_branchements
            rattacher_branchements(cl, br_layer)
        tab_by_pt = {}
        if tab_layer and not sip.isdeleted(tab_layer):
            for tf in tab_layer.getFeatures():
                g = tf.geometry()
                if g.isEmpty():
                    continue
                tp = QgsPointXY(g.asPoint())
                v = _nom(tf['nom'])
                tab_by_pt[(round(tp.x(), 3), round(tp.y(), 3))] = '' if v == '—' else v

        robinet_en = _robinets(couches)
        for br in br_layer.getFeatures():
            g = br.geometry()
            if g.isEmpty():
                continue
            line = g.asPolyline()
            if len(line) < 2:
                continue
            start_pt = QgsPointXY(line[0])
            if not dedans(start_pt):
                continue
            parent = cdata_reseau.get(br['id_conduite'])
            if not parent:
                continue
            x_piq = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(start_pt))
            # FE interpolé sur la conduite mère. Priorité à la projection sur
            # l'axe (alignement visuel avec la ligne FE dessinée) ; si elle
            # dégénère (conduite ~perpendiculaire à l'axe), repli sur
            # pk_debut / longueur réelle.
            x0, x1 = parent['x0'], parent['x1']
            fe0, fe1 = parent['fe0'], parent['fe1']
            if x1 > x0 and fe0 is not None and fe1 is not None:
                t = max(0.0, min(1.0, (x_piq - x0) / (x1 - x0)))
                fe_piq = fe0 + t * (fe1 - fe0)
            else:
                pk = _to_float(br['pk_debut']) or 0.0
                longueur = (_to_float(parent['feat']['longueur'])
                            or parent['feat'].geometry().length())
                if fe0 is not None and fe1 is not None and longueur > 0:
                    t = max(0.0, min(1.0, pk / longueur))
                    fe_piq = fe0 + t * (fe1 - fe0)
                else:
                    fe_piq = fe0 if fe0 is not None else fe1
            end_pt = QgsPointXY(line[-1])
            piquages.append({
                'x':      x_piq,
                'fe':     fe_piq,
                'nom':    (robinet_en(start_pt) if robinet_en is not None
                           else tab_by_pt.get((round(end_pt.x(), 3), round(end_pt.y(), 3)), '')),
                'reseau': reseau,
            })

    return {'conduites': conduites_data, 'ref_length': ref_len, 'piquages': piquages}


def _compute_groupe_data(couches_eu, couches_ep, pts, couches_aep=None):
    """Compatibilité : ancienne signature EU/EP."""
    return calculer_donnees_groupe(_jeux(couches_eu, couches_ep, couches_aep), pts)
