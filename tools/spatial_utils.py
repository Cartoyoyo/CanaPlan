# tools/spatial_utils.py
"""Recherches spatiales filtrées, partagées par les map tools.

Remplace les parcours linéaires complets (O(n) par événement souris) par des
QgsFeatureRequest.setFilterRect : seules les entités dont la bbox intersecte
la zone du clic sont désérialisées et testées.
"""
import math

from qgis.core import QgsFeatureRequest, QgsRectangle, QgsPointXY


def rect_request(pt, tol):
    """QgsFeatureRequest limité au carré de demi-côté tol autour de pt."""
    return QgsFeatureRequest().setFilterRect(QgsRectangle(
        pt.x() - tol, pt.y() - tol, pt.x() + tol, pt.y() + tol))


def nearest_point_feature(layer, pt, tol):
    """(feat, dist) de l'entité ponctuelle la plus proche de pt dans le
    rayon tol, sinon (None, inf)."""
    best, best_d = None, float('inf')
    for feat in layer.getFeatures(rect_request(pt, tol)):
        g = feat.geometry()
        if g.isEmpty():
            continue
        d = pt.distance(QgsPointXY(g.asPoint()))
        if d <= tol and d < best_d:
            best, best_d = feat, d
    return best, best_d


def nearest_line_feature(layer, pt, tol):
    """(feat, point_projeté, dist) de la ligne la plus proche de pt dans le
    rayon tol, sinon (None, None, inf)."""
    best, best_proj, best_d = None, None, float('inf')
    for feat in layer.getFeatures(rect_request(pt, tol)):
        g = feat.geometry()
        if g.isEmpty():
            continue
        sq, proj, _, _ = g.closestSegmentWithContext(pt)
        d = math.sqrt(sq)
        if d <= tol and d < best_d:
            best, best_proj, best_d = feat, QgsPointXY(proj), d
    return best, best_proj, best_d


class PointGrid:
    """Hash spatial simple pour une liste de (QgsPointXY, data).

    Remplace les scans linéaires sur des lookup-lists Python (profils) :
    nearest() ne visite que les cellules voisines du point cherché.
    """

    def __init__(self, items, cell=1.0):
        self.cell = cell
        self.grid = {}
        for pt, data in items:
            key = (int(pt.x() // cell), int(pt.y() // cell))
            self.grid.setdefault(key, []).append((pt, data))

    def nearest(self, pt, tol):
        """data du point le plus proche dans le rayon tol, sinon None."""
        cx, cy = int(pt.x() // self.cell), int(pt.y() // self.cell)
        r = int(tol // self.cell) + 1
        best, best_d = None, float('inf')
        for gx in range(cx - r, cx + r + 1):
            for gy in range(cy - r, cy + r + 1):
                for rpt, data in self.grid.get((gx, gy), ()):
                    d = pt.distance(rpt)
                    if d <= tol and d < best_d:
                        best_d, best = d, data
        return best


def nearest_line_feature_expanding(layer, pt, tols=(2.0, 20.0, 200.0)):
    """Comme nearest_line_feature, avec rayons croissants puis parcours
    complet en dernier recours (équivalent à l'ancien scan sans limite,
    mais quasi toujours résolu au premier rayon)."""
    for tol in tols:
        feat, proj, d = nearest_line_feature(layer, pt, tol)
        if feat is not None:
            return feat, proj, d
    best, best_proj, best_d = None, None, float('inf')
    for feat in layer.getFeatures():
        g = feat.geometry()
        if g.isEmpty():
            continue
        sq, proj, _, _ = g.closestSegmentWithContext(pt)
        d = math.sqrt(sq)
        if d < best_d:
            best, best_proj, best_d = feat, QgsPointXY(proj), d
    return best, best_proj, best_d
