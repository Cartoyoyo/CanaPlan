# tools/renseignement_tool.py

import math

from qgis.core import Qgis, QgsPointXY, QgsWkbTypes, QgsRectangle, QgsProject, QgsGeometry
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtGui import QColor, QCursor

from . import i18n
from . import layer_ok as _ok
from .spatial_utils import nearest_point_feature, nearest_line_feature


class RenseignementTool(QgsMapTool):
    """
    Survol (< 20 px) : mise en évidence orange de l'élément le plus proche.
    Clic gauche : ouvre le formulaire de saisie des attributs.
    Fonctionne aussi sur les annotations texte du calque d'annotations principal.
    """
    finished = pyqtSignal()

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {'EU': couches_eu, 'EP': couches_ep}
        self._hover = None            # (role, feat, layer, reseau)
        self._hover_band = None
        self._hover_annotation = None  # (item_id, item)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            "Renseigner",
            i18n.tr('ot_aide_renseignement'),
            level=Qgis.MessageLevel.Info, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._clear_hover()
        self._hover_annotation = None
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        self._update_hover(event.pos())

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._hover is None and self._hover_annotation is None:
            self._update_hover(event.pos())

        # Annotation prioritaire
        if self._hover_annotation is not None:
            item_id, item = self._hover_annotation
            fmt  = item.format()
            font = fmt.font()
            from ..gui.annotation_dialog import AnnotationDialog
            from .annotation_tool import make_text_format, _get_alignment, _set_alignment
            dlg = AnnotationDialog(
                None,
                text=item.text(),
                font_name=font.family(),
                size=fmt.size(),
                size_unit=fmt.sizeUnit(),
                color=fmt.color(),
                bold=font.bold(),
                italic=font.italic(),
                underline=font.underline(),
                alignment=_get_alignment(item),
            )
            pos = QCursor.pos()
            dlg.move(pos.x() + 20, pos.y() - 100)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                vals = dlg.get_values()
                from qgis.core import QgsProject, QgsAnnotationPointTextItem
                ann_layer = QgsProject.instance().mainAnnotationLayer()
                old_pt = item.point()
                ann_layer.removeItem(item_id)
                if vals['text']:
                    new_item = QgsAnnotationPointTextItem(vals['text'], old_pt)
                    new_item.setFormat(make_text_format(vals))
                    _set_alignment(new_item, vals['alignment'])
                    ann_layer.addItem(new_item)
                self.canvas.refresh()
            self._clear_hover()
            return

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
        pos = QCursor.pos()
        dlg.move(pos.x() + 20, pos.y() - 100)
        dlg.exec()
        self._clear_hover()

    # ------------------------------------------------------------------ survol

    def _update_hover(self, pixel_pos):
        click_pt = self.toMapCoordinates(pixel_pos)
        tol = 20 * self.canvas.mapUnitsPerPixel()

        # Passe 0 : annotations texte (priorité maximale)
        from .annotation_tool import find_annotation_at
        ann = find_annotation_at(self.canvas, click_pt)
        if ann is not None:
            if self._hover_annotation is None or self._hover_annotation[0] != ann[0]:
                self._clear_hover()
                self._hover_annotation = ann
                # Rubber band de mise en évidence
                pt = ann[1].point()
                geom = QgsGeometry.fromPointXY(QgsPointXY(pt.x(), pt.y()))
                rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PointGeometry)
                rb.setToGeometry(geom)
                rb.setColor(QColor(255, 165, 0))
                rb.setIconSize(14)
                rb.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
                self._hover_band = rb
            return
        elif self._hover_annotation is not None:
            self._clear_hover()

        # Passe 1 : regards et tabourets (prioritaires)
        best_pt = None
        for reseau, couches in self.couches.items():
            for role in ('regard', 'tabouret'):
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                feat, dist = nearest_point_feature(layer, click_pt, tol)
                if feat is not None and (best_pt is None or dist < best_pt[4]):
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
                    feat, _, dist = nearest_line_feature(layer, click_pt, tol)
                    if feat is not None and (best_line is None or dist < best_line[4]):
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
        if gtype == QgsWkbTypes.GeometryType.PointGeometry:
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PointGeometry)
            rb.setToGeometry(geom, layer)
            rb.setColor(QColor(255, 165, 0))
            rb.setIconSize(14)
            rb.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
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
        self._hover_annotation = None
