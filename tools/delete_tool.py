# tools/delete_tool.py

import math

from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes, QgsRectangle, QgsProject
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox
from . import layer_ok as _ok


class DeleteTool(QgsMapTool):
    """
    Double comportement :
    - Survol (< 20 px) : pré-sélection orange de l'élément le plus proche
    - Clic gauche simple : suppression de l'élément pré-sélectionné (avec confirmation)
    - Clic gauche maintenu + glisser : lasso libre, accumule des éléments
    - Clic droit : supprime tous les éléments du lasso (avec confirmation)
    """
    finished = pyqtSignal()

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {'EU': couches_eu, 'EP': couches_ep}

        # --- lasso ---
        self._pending = []      # (role, feat, layer, reseau) accumulés
        self._highlights = []   # rubber bands sélection lasso
        self._lasso = None      # rubber band tracé en cours
        self._lasso_pts = []
        self._dragging = False
        self._press_px = None   # position pixel au moment du clic

        # --- survol géométrie ---
        self._hover = None      # (role, feat, layer, reseau) ou None
        self._hover_band = None

        # --- survol étiquette ---
        self._hover_label = None   # (feat, layer) ou None
        self._hover_label_band = None

        # --- survol annotation ---
        self._hover_annotation = None       # (item_id, item) ou None
        self._hover_annotation_band = None

    # ------------------------------------------------------------------ cycle de vie

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            "Effacer",
            "Clic : supprimer l'élément survolé  ·  Glisser : lasso multi-sélection + clic droit pour confirmer  ·  Clic droit sur étiquette : effacer l'étiquette",
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._clear_lasso()
        self._clear_highlights()
        self._clear_hover()
        self._clear_annotation_hover()
        self._pending.clear()
        self._lasso_pts.clear()
        super().deactivate()

    # ------------------------------------------------------------------ événements

    def canvasPressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self._press_px = event.pos()
        self._dragging = False

    def canvasMoveEvent(self, event):
        if self._press_px is not None:
            # Bouton gauche maintenu : vérifier si on dépasse le seuil de glissement
            dx = abs(event.pos().x() - self._press_px.x())
            dy = abs(event.pos().y() - self._press_px.y())
            if not self._dragging and (dx > 3 or dy > 3):
                self._dragging = True
                self._clear_hover()
                start = self.toMapCoordinates(self._press_px)
                self._lasso_pts = [start]
                self._clear_lasso()
                self._lasso = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
                self._lasso.setColor(QColor(30, 120, 255, 50))
                self._lasso.setStrokeColor(QColor(30, 120, 255, 200))
                self._lasso.setWidth(2)
                self._lasso.addPoint(start)
            if self._dragging and self._lasso is not None:
                pt = self.toMapCoordinates(event.pos())
                self._lasso_pts.append(pt)
                self._lasso.addPoint(pt)
        else:
            # Aucun bouton : mode survol
            self._update_hover(event.pos())

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._dragging:
                # Fin du lasso
                self._dragging = False
                self._clear_lasso()
                if len(self._lasso_pts) >= 3:
                    pts = self._lasso_pts + [self._lasso_pts[0]]
                    self._add_lasso_selection(QgsGeometry.fromPolygonXY([pts]))
                self._lasso_pts = []
            else:
                # Clic simple : supprimer l'élément, l'annotation ou l'étiquette
                if self._hover_annotation is not None:
                    self._delete_annotation()
                elif self._hover is not None:
                    self._delete_hovered()
                elif self._hover_label is not None:
                    self._erase_label()
            self._press_px = None

        elif event.button() == Qt.RightButton:
            self._confirm_and_delete_lasso()

    # ------------------------------------------------------------------ survol

    def _update_hover(self, pixel_pos):
        click_pt = self.toMapCoordinates(pixel_pos)
        tol = 20 * self.canvas.mapUnitsPerPixel()

        # Passe 0 : annotations (priorité maximale)
        from .annotation_tool import find_annotation_at
        ann = find_annotation_at(self.canvas, click_pt)
        if ann is not None:
            if (self._hover_annotation is None
                    or self._hover_annotation[0] != ann[0]):
                self._clear_annotation_hover()
                self._clear_hover()
                pt = ann[1].point()
                rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
                rb.setToGeometry(
                    QgsGeometry.fromPointXY(QgsPointXY(pt.x(), pt.y())), None)
                rb.setColor(QColor(255, 60, 60))
                rb.setIconSize(14)
                rb.setIcon(QgsRubberBand.ICON_CIRCLE)
                self._hover_annotation = ann
                self._hover_annotation_band = rb
            return
        elif self._hover_annotation is not None:
            self._clear_annotation_hover()

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

        if best is not None:
            self._clear_label_hover()
            role, feat, layer, reseau, _ = best
            if (self._hover is None
                    or self._hover[1].id() != feat.id()
                    or self._hover[2] is not layer):
                self._clear_hover()
                self._hover = (role, feat, layer, reseau)
                self._hover_band = self._make_hover_band(feat, layer)
            return

        self._clear_hover()

        # Passe 3 : étiquettes de regards/tabourets
        lbl_match = self._find_label_hover(click_pt, tol)
        if lbl_match is not None:
            feat, layer, label_rect = lbl_match
            if (self._hover_label is None
                    or self._hover_label[0].id() != feat.id()
                    or self._hover_label[1] is not layer):
                self._clear_label_hover()
                self._hover_label = (feat, layer)
                self._hover_label_band = self._make_label_band(label_rect)
        else:
            self._clear_label_hover()

    def _find_label_hover(self, click_pt, tol):
        """Retourne (feat, layer, labelRect) si une étiquette déplacée est proche."""
        results = self.canvas.labelingResults()
        if results is None:
            return None
        layers_by_id = {}
        for couches in self.couches.values():
            for role in ('regard', 'tabouret'):
                lyr = couches.get(role)
                if _ok(lyr):
                    layers_by_id[lyr.id()] = lyr
        search = QgsRectangle(
            click_pt.x() - tol, click_pt.y() - tol,
            click_pt.x() + tol, click_pt.y() + tol,
        )
        best, best_dist = None, float('inf')
        for lbl in results.labelsWithinRect(search):
            lyr = layers_by_id.get(lbl.layerID)
            if lyr is None:
                continue
            feat = lyr.getFeature(lbl.featureId)
            if not feat.isValid():
                continue
            cx = (lbl.labelRect.xMinimum() + lbl.labelRect.xMaximum()) / 2
            cy = (lbl.labelRect.yMinimum() + lbl.labelRect.yMaximum()) / 2
            dist = click_pt.distance(QgsPointXY(cx, cy))
            if dist < best_dist:
                best_dist = dist
                best = (feat, lyr, lbl.labelRect)
        return best

    def _make_label_band(self, label_rect):
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rb.setToGeometry(QgsGeometry.fromRect(label_rect), None)
        rb.setColor(QColor(255, 165, 0, 60))
        rb.setStrokeColor(QColor(255, 165, 0, 255))
        rb.setWidth(2)
        return rb

    def _clear_label_hover(self):
        if self._hover_label_band is not None:
            self.canvas.scene().removeItem(self._hover_label_band)
            self._hover_label_band = None
        self._hover_label = None

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
        self._clear_label_hover()

    # ------------------------------------------------------------------ effacement étiquette

    def _erase_label(self):
        feat, layer = self._hover_label
        nom = feat['nom'] if feat.fields().indexFromName('nom') >= 0 else str(feat.id())
        if QMessageBox.question(
                None, "Effacer l'étiquette",
                f"Supprimer l'étiquette de « {nom} » ?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        from ..gui.etiquettes import LBL_X, LBL_Y, LBL_VISIBLE
        fields = layer.fields()
        if not layer.isEditable():
            layer.startEditing()
        fid = feat.id()
        # Masque l'étiquette et efface sa position stockée
        for name, val in ((LBL_VISIBLE, 0), (LBL_X, None), (LBL_Y, None)):
            idx = fields.indexFromName(name)
            if idx >= 0:
                layer.changeAttributeValue(fid, idx, val)
        layer.commitChanges()
        self._clear_label_hover()
        self.canvas.refresh()

    # ------------------------------------------------------------------ clic simple

    def _delete_hovered(self):
        role, feat, layer, reseau = self._hover
        couches = self.couches[reseau]
        to_delete = {}

        def _add(lyr, f):
            lid = lyr.id()
            if lid not in to_delete:
                to_delete[lid] = (lyr, set())
            to_delete[lid][1].add(f.id())

        _add(layer, feat)

        if role == 'conduite':
            br_layer = couches['branchement']
            tab_layer = couches['tabouret']
            for br in br_layer.getFeatures():
                br_geom = br.geometry()
                if br_geom.isEmpty():
                    continue
                start_pt = QgsPointXY(br_geom.asPolyline()[0])
                sq_d, _, _, _ = feat.geometry().closestSegmentWithContext(start_pt)
                if math.sqrt(sq_d) < 0.01:
                    _add(br_layer, br)
                    end_pt = br_geom.asPolyline()[-1]
                    tab = self._find_point_at(tab_layer, end_pt)
                    if tab:
                        _add(tab_layer, tab)

        elif role == 'branchement':
            tab_layer = couches['tabouret']
            br_geom = feat.geometry()
            if not br_geom.isEmpty():
                end_pt = br_geom.asPolyline()[-1]
                tab = self._find_point_at(tab_layer, end_pt)
                if tab:
                    _add(tab_layer, tab)

        total = sum(len(fids) for _, fids in to_delete.values())
        noms = {'regard': 'regard', 'tabouret': 'tabouret',
                'conduite': 'conduite', 'branchement': 'branchement'}
        msg = f"Supprimer ce {noms.get(role, role)}"
        if total > 1:
            msg += f" et {total - 1} élément(s) associé(s) (cascade)"
        msg += " ?"

        if QMessageBox.question(None, "Confirmer la suppression", msg,
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        self._clear_hover()
        for lyr, fids in to_delete.values():
            if not lyr.isEditable():
                lyr.startEditing()
            for fid in fids:
                lyr.deleteFeature(fid)
            lyr.commitChanges()
        self.canvas.refresh()

    # ------------------------------------------------------------------ lasso

    def _add_lasso_selection(self, sel_geom):
        for reseau, couches in self.couches.items():
            for role in ('regard', 'tabouret', 'branchement', 'conduite'):
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                for feat in layer.getFeatures():
                    geom = feat.geometry()
                    if geom.isEmpty() or not sel_geom.intersects(geom):
                        continue
                    if any(f.id() == feat.id() and lyr is layer
                           for (_, f, lyr, _) in self._pending):
                        continue
                    self._pending.append((role, feat, layer, reseau))
                    self._highlight(feat, layer)
        self.canvas.update()

    def _highlight(self, feat, layer):
        rb = self._make_hover_band(feat, layer)
        self._highlights.append(rb)

    def _confirm_and_delete_lasso(self):
        if not self._pending:
            return

        to_delete = {}

        def _add(lyr, f):
            lid = lyr.id()
            if lid not in to_delete:
                to_delete[lid] = (lyr, set())
            to_delete[lid][1].add(f.id())

        for role, feat, layer, reseau in self._pending:
            _add(layer, feat)
            couches = self.couches[reseau]

            if role == 'conduite':
                br_layer = couches['branchement']
                tab_layer = couches['tabouret']
                for br in br_layer.getFeatures():
                    br_geom = br.geometry()
                    if br_geom.isEmpty():
                        continue
                    start_pt = QgsPointXY(br_geom.asPolyline()[0])
                    sq_d, _, _, _ = feat.geometry().closestSegmentWithContext(start_pt)
                    if math.sqrt(sq_d) < 0.01:
                        _add(br_layer, br)
                        end_pt = br_geom.asPolyline()[-1]
                        tab = self._find_point_at(tab_layer, end_pt)
                        if tab:
                            _add(tab_layer, tab)

            elif role == 'branchement':
                tab_layer = couches['tabouret']
                br_geom = feat.geometry()
                if not br_geom.isEmpty():
                    end_pt = br_geom.asPolyline()[-1]
                    tab = self._find_point_at(tab_layer, end_pt)
                    if tab:
                        _add(tab_layer, tab)

        total = sum(len(fids) for _, fids in to_delete.values())
        if QMessageBox.question(
                None, "Confirmer la suppression",
                f"Supprimer {total} élément(s) sélectionné(s) (cascade incluse) ?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return

        for lyr, fids in to_delete.values():
            if not lyr.isEditable():
                lyr.startEditing()
            for fid in fids:
                lyr.deleteFeature(fid)
            lyr.commitChanges()

        self._clear_highlights()
        self._pending.clear()
        self.canvas.refresh()

    # ------------------------------------------------------------------ effacement annotation

    def _clear_annotation_hover(self):
        if self._hover_annotation_band is not None:
            self.canvas.scene().removeItem(self._hover_annotation_band)
            self._hover_annotation_band = None
        self._hover_annotation = None

    def _delete_annotation(self):
        item_id, item = self._hover_annotation
        preview = item.text()[:40] + ('…' if len(item.text()) > 40 else '')
        if QMessageBox.question(
                None, "Effacer l'annotation",
                f"Supprimer l'annotation « {preview} » ?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        ann_layer = QgsProject.instance().mainAnnotationLayer()
        ann_layer.removeItem(item_id)
        self._clear_annotation_hover()
        self.canvas.refresh()

    # ------------------------------------------------------------------ helpers

    def _clear_lasso(self):
        if self._lasso is not None:
            self.canvas.scene().removeItem(self._lasso)
            self._lasso = None

    def _clear_highlights(self):
        for rb in self._highlights:
            self.canvas.scene().removeItem(rb)
        self._highlights.clear()

    def _find_point_at(self, layer, point):
        if not _ok(layer):
            return None
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            if QgsPointXY(point).distance(geom.asPoint()) <= 0.01:
                return feat
        return None
