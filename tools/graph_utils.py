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


def build_graph(conduite_layer, regard_layer, tol=0.05):
    """Construit le graphe regards↔conduites.

    Returns (graph, regard_by_id) :
    - graph         : {regard_id: [(conduite_feat, voisin_id), ...]}
    - regard_by_id  : {regard_id: QgsFeature}
    """
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

    regard_by_id = {
        feat.id(): feat
        for feat in regard_layer.getFeatures()
        if not feat.geometry().isEmpty()
    }

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


def bfs(graph, start_id, end_id):
    """BFS dans le graphe regards↔conduites.

    Returns (regard_ids, conduite_feats) ou (None, None) si pas de chemin.
    """
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
