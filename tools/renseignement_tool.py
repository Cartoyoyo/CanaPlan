# tools/renseignement_tool.py

import math

from qgis.core import QgsPointXY, QgsWkbTypes, QgsRectangle, QgsProject
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from . import layer_ok as _ok


class RenseignementTool(QgsMapTool):
    """
    Survol (< 20 px) : mise en évidence orange de l'élément le plus proche.
    Clic gauche : ouvre le formulaire de saisie des attributs.
    """
    finished = pyqtSignal()

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {'EU': couches_eu, 'EP': couches_ep}
        self._hover = None       # (role, feat, layer, reseau)
        self._hover_band = None

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.PointingHandCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            "Renseigner",
            "Survoler un élément pour le mettre en évidence  ·  Clic gauche : ouvrir le formulaire d'attributs",
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._clear_hover()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        self._update_hover(event.pos())

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self._hover is None:
            self._update_hover(event.pos())
        if self._hover is None:
            return
        role, feat, layer, reseau = self._hover
        # Recharger la feature depuis la couche pour éviter une ref obsolète
        fresh = layer.getFeature(feat.id())
        if fresh.isValid():
            feat = fresh
        from ..gui.renseignement_dialog import RenseignementDialog
        dlg = RenseignementDialog(role, feat, layer, reseau,
                                  couches=self.couches[reseau])
        # Positionner le dialogue à droite du clic pour ne pas masquer l'élément
        dlg.move(event.globalPos().x() + 20, event.globalPos().y() - 100)
        dlg.exec_()
        self._clear_hover()

    # ------------------------------------------------------------------ survol

    def _update_hover(self, pixel_pos):
        click_pt = self.toMapCoordinates(pixel_pos)
        tol = 20 * self.canvas.mapUnitsPerPixel()

        # Passe 1 : regards et tabourets (prioritaires)
        best_pt = None
        for reseau, couches in self.couches.items():
            for role in ('regard', 'tabouret'):
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if geom.isEmpty():
                        continue
                    dist = click_pt.distance(QgsPointXY(geom.asPoint()))
                    if dist <= tol and (best_pt is None or dist < best_pt[4]):
                        best_pt = (role, feat, layer, reseau, dist)

        # Passe 1b : étiquettes de regards/tabourets → renvoie l'objet associé
        if best_pt is None:
            lbl_match = self._find_label_feature(click_pt, tol)
            if lbl_match is not None:
                best_pt = lbl_match

        # Passe 2 : conduites et branchements, seulement si aucun point trouvé
        best_line = None
        if best_pt is None:
            for reseau, couches in self.couches.items():
                for role in ('branchement', 'conduite'):
                    layer = couches.get(role)
                    if not _ok(layer):
                        continue
                    for feat in layer.getFeatures():
                        geom = feat.geometry()
                        if geom.isEmpty():
                            continue
                        sq_d, _, _, _ = geom.closestSegmentWithContext(click_pt)
                        dist = math.sqrt(sq_d)
                        if dist <= tol and (best_line is None or dist < best_line[4]):
                            best_line = (role, feat, layer, reseau, dist)

        best = best_pt if best_pt is not None else best_line

        if best is None:
            if self._hover is not None:
                self._clear_hover()
            return

        role, feat, layer, reseau, _ = best
        if (self._hover is not None
                and self._hover[1].id() == feat.id()
                and self._hover[2] is layer):
            return

        self._clear_hover()
        self._hover = (role, feat, layer, reseau)
        self._hover_band = self._make_hover_band(feat, layer)

    def _find_label_feature(self, click_pt, tol):
        """Cherche une étiquette de regard/tabouret sous le curseur et
        renvoie le tuple (role, feat, layer, reseau, dist) de l'objet
        associé."""
        results = self.canvas.labelingResults()
        if results is None:
            return None

        layers_by_id = {}
        for reseau, couches in self.couches.items():
            for role in ('regard', 'tabouret'):
                lyr = couches.get(role)
                if _ok(lyr):
                    layers_by_id[lyr.id()] = (role, lyr, reseau)

        search = QgsRectangle(
            click_pt.x() - tol, click_pt.y() - tol,
            click_pt.x() + tol, click_pt.y() + tol,
        )

        best, best_dist = None, float('inf')
        for lbl in results.labelsWithinRect(search):
            info = layers_by_id.get(lbl.layerID)
            if info is None:
                continue
            cx = (lbl.labelRect.xMinimum() + lbl.labelRect.xMaximum()) / 2
            cy = (lbl.labelRect.yMinimum() + lbl.labelRect.yMaximum()) / 2
            dist = click_pt.distance(QgsPointXY(cx, cy))
            if dist < best_dist:
                best_dist = dist
                best = (info, lbl.featureId)

        if best is None:
            return None

        (role, layer, reseau), fid = best
        feat = layer.getFeature(fid)
        if not feat.isValid():
            return None
        return (role, feat, layer, reseau, best_dist)

    def _make_hover_band(self, feat, layer):
        geom = feat.geometry()
        gtype = layer.geometryType()
        if gtype == QgsWkbTypes.PointGeometry:
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
            rb.setToGeometry(geom, layer)
            rb.setColor(QColor(255, 165, 0))
            rb.setIconSize(14)
            rb.setIcon(QgsRubberBand.ICON_CIRCLE)
        else:
            rb = QgsRubberBand(self.canvas, gtype)
            rb.setToGeometry(geom, layer)
            rb.setColor(QColor(255, 165, 0, 200))
            rb.setWidth(5)
        return rb

    def _clear_hover(self):
        if self._hover_band is not None:
            self.canvas.scene().removeItem(self._hover_band)
            self._hover_band = None
        self._hover = None
