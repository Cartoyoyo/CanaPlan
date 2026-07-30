# tools/move_tool.py

import math

from qgis.core import (
    QgsPointXY, QgsGeometry, QgsRectangle, QgsWkbTypes, QgsProject
)
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QColor
from . import layer_ok as _ok
from .spatial_utils import (
    rect_request, nearest_point_feature,
    nearest_line_feature, nearest_line_feature_expanding,
)


class MoveTool(QgsMapTool):
    """
    Déplacement de regards/tabourets et de leurs étiquettes.
    - Survol géométrie (< 20 px) : cercle orange
    - Survol étiquette (dans la boîte + 20 px, si pas de géométrie proche) : boîte orange
    - 1er clic : sélectionne l'élément ou l'étiquette
    - Déplacer la souris : prévisualisation
    - 2e clic : pose à la nouvelle position
    - Échap : annule
    """
    finished = pyqtSignal()

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {'EU': couches_eu, 'EP': couches_ep}

        # Mode actif : None | 'geom' | 'label'
        self._mode = None

        # Survol géométrie
        self._hover = None         # (role, feat, layer, reseau)
        self._hover_band = None

        # Survol étiquette
        self._label_hover = None   # QgsLabelPosition
        self._label_hover_band = None

        # Déplacement géométrie
        self._sel_feat = None
        self._sel_layer = None
        self._sel_reseau = None
        self._sel_role = None
        self._orig_pt = None

        # Déplacement étiquette
        self._sel_label = None     # QgsLabelPosition
        self._label_w = 0.0
        self._label_h = 0.0
        self._label_hidden = False  # True si l'étiquette est temporairement masquée

        # Survol annotation
        self._hover_annotation = None       # (item_id, item)
        self._hover_annotation_band = None

        # Déplacement annotation
        self._sel_ann_id = None
        self._sel_ann_text = None
        self._sel_ann_fmt = None
        self._sel_ann_alignment = None
        self._sel_ann_orig_pt = None        # QgsPointXY original

        # Rubber band de prévisualisation
        self._preview = None
        # Prévisualisations des conduites/branchements connectés (mode 'geom')
        self._line_previews = []

        # ── Mode 'piquage' : déplacement du point de piquage d'un branchement ──
        self._hover_piquage      = None   # (feat, br_layer, reseau, cond_layer, reg_layer)
        self._hover_piquage_band = None
        self._piquage_feat       = None
        self._piquage_layer      = None
        self._piquage_reseau     = None
        self._piquage_cond_layer = None
        self._piquage_reg_layer  = None
        self._piquage_snap_pt    = None   # QgsPointXY courant snappé
        self._piquage_snap_cond  = None   # QgsFeature conduite snappée
        self._piquage_snap_band  = None   # croix verte indicateur
        self._piquage_line_prev  = None   # prévisualisation branchement

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            "Déplacer",
            "Clic gauche sur un ouvrage, un piquage de branchement ou une étiquette  ·  2e clic : poser  ·  Échap : annuler",
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        if self._mode == 'annotation':
            pt = self.toMapCoordinates(event.pos())
            if self._preview is not None:
                self._preview.setToGeometry(QgsGeometry.fromPointXY(pt), None)

        elif self._mode == 'piquage':
            self._update_piquage_snap(self.toMapCoordinates(event.pos()))

        elif self._mode == 'geom':
            pt = self.toMapCoordinates(event.pos())
            if self._preview is not None:
                self._preview.setToGeometry(QgsGeometry.fromPointXY(pt), None)
            for item in self._line_previews:
                new_line = list(item['line'])
                for idx in item['endpoints']:
                    new_line[idx] = pt
                item['rb'].setToGeometry(
                    QgsGeometry.fromPolylineXY(new_line), None)

        elif self._mode == 'label':
            pt = self.toMapCoordinates(event.pos())
            if self._preview is not None:
                hw, hh = self._label_w / 2, self._label_h / 2
                self._preview.setToGeometry(
                    QgsGeometry.fromRect(QgsRectangle(
                        pt.x() - hw, pt.y() - hh,
                        pt.x() + hw, pt.y() + hh
                    )), None
                )
        else:
            self._update_hover(event.pos())

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        pt = self.toMapCoordinates(event.pos())

        if self._mode == 'annotation':
            self._apply_annotation_move(pt)
        elif self._mode == 'piquage':
            self._apply_piquage_move()
        elif self._mode == 'geom':
            self._apply_geom_move(pt)
        elif self._mode == 'label':
            self._apply_label_move(pt)
        else:
            if self._hover_annotation is not None:
                self._start_annotation_move()
            elif self._hover is not None:
                self._start_geom_move()
            elif self._hover_piquage is not None:
                self._start_piquage_move()
            elif self._label_hover is not None:
                self._start_label_move()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ hover

    def _update_hover(self, pixel_pos):
        click_pt = self.toMapCoordinates(pixel_pos)
        tol = 20 * self.canvas.mapUnitsPerPixel()

        # Passe 0 : annotations texte (priorité maximale)
        from .annotation_tool import find_annotation_at
        ann = find_annotation_at(self.canvas, click_pt)
        if ann is not None:
            if (self._hover_annotation is None
                    or self._hover_annotation[0] != ann[0]):
                self._clear_annotation_hover()
                self._clear_geom_hover()
                self._clear_label_hover()
                self._hover_annotation = ann
                self._hover_annotation_band = self._make_ann_band(ann[1])
            return
        elif self._hover_annotation is not None:
            self._clear_annotation_hover()

        # Passe 1 : regards et tabourets (prioritaires) — requête filtrée
        best_pt = None
        for reseau, couches in self.couches.items():
            for role in ('regard', 'tabouret'):
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                feat, dist = nearest_point_feature(layer, click_pt, tol)
                if feat is not None and (best_pt is None or dist < best_pt[4]):
                    best_pt = (role, feat, layer, reseau, dist)

        if best_pt is not None:
            self._clear_label_hover()
            role, feat, layer, reseau, _ = best_pt
            if (self._hover is None
                    or self._hover[1].id() != feat.id()
                    or self._hover[2] is not layer):
                self._clear_geom_hover()
                self._hover = (role, feat, layer, reseau)
                self._hover_band = self._make_geom_band(feat, layer)
            return

        self._clear_geom_hover()

        # Passe 1b : piquage de branchement (point[0] d'un branchement)
        piq = self._find_piquage_near(click_pt, tol)
        if piq is not None:
            self._clear_label_hover()
            if (self._hover_piquage is None
                    or self._hover_piquage[0].id() != piq[0].id()):
                self._clear_piquage_hover()
                self._hover_piquage = piq
                pt0 = QgsPointXY(piq[0].geometry().asPolyline()[0])
                self._hover_piquage_band = QgsRubberBand(
                    self.canvas, QgsWkbTypes.PointGeometry)
                self._hover_piquage_band.setColor(QColor(255, 165, 0))
                self._hover_piquage_band.setIconSize(16)
                self._hover_piquage_band.setIcon(QgsRubberBand.ICON_X)
                self._hover_piquage_band.setToGeometry(
                    QgsGeometry.fromPointXY(pt0), None)
            return
        else:
            self._clear_piquage_hover()

        # Passe 2 : étiquettes (uniquement si aucune géométrie proche)
        lbl = self._find_label_near(click_pt, tol)
        if lbl is not None:
            if (self._label_hover is None
                    or self._label_hover.featureId != lbl.featureId
                    or self._label_hover.layerID != lbl.layerID):
                self._clear_label_hover()
                self._label_hover = lbl
                self._label_hover_band = self._make_label_band(lbl)
        else:
            self._clear_label_hover()

    def _find_label_near(self, click_pt, tol):
        """Cherche l'étiquette (regard/tabouret) la plus proche."""
        results = self.canvas.labelingResults()
        if results is None:
            return None

        valid_ids = {
            couches[role].id()
            for couches in self.couches.values()
            for role in ('regard', 'tabouret', 'conduite')
            if _ok(couches.get(role))
        }

        search = QgsRectangle(
            click_pt.x() - tol, click_pt.y() - tol,
            click_pt.x() + tol, click_pt.y() + tol
        )

        best, best_dist = None, float('inf')
        for lbl in results.labelsWithinRect(search):
            if lbl.layerID not in valid_ids:
                continue
            cx = (lbl.labelRect.xMinimum() + lbl.labelRect.xMaximum()) / 2
            cy = (lbl.labelRect.yMinimum() + lbl.labelRect.yMaximum()) / 2
            dist = click_pt.distance(QgsPointXY(cx, cy))
            if dist < best_dist:
                best_dist = dist
                best = lbl
        return best

    def _make_geom_band(self, feat, layer):
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        rb.setToGeometry(feat.geometry(), layer)
        rb.setColor(QColor(255, 165, 0))
        rb.setIconSize(14)
        rb.setIcon(QgsRubberBand.ICON_CIRCLE)
        return rb

    def _make_label_band(self, lbl):
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        rb.setToGeometry(QgsGeometry.fromRect(lbl.labelRect), None)
        rb.setColor(QColor(255, 165, 0, 60))
        rb.setStrokeColor(QColor(255, 165, 0, 255))
        rb.setWidth(2)
        return rb

    def _clear_geom_hover(self):
        if self._hover_band is not None:
            self.canvas.scene().removeItem(self._hover_band)
            self._hover_band = None
        self._hover = None

    def _clear_label_hover(self):
        if self._label_hover_band is not None:
            self.canvas.scene().removeItem(self._label_hover_band)
            self._label_hover_band = None
        self._label_hover = None

    # ------------------------------------------------------------------ déplacement géométrie

    def _start_geom_move(self):
        role, feat, layer, reseau = self._hover
        self._sel_feat = feat
        self._sel_layer = layer
        self._sel_reseau = reseau
        self._sel_role = role
        self._orig_pt = feat.geometry().asPoint()
        self._mode = 'geom'
        self._clear_geom_hover()

        self._preview = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self._preview.setColor(QColor(0, 200, 0))
        self._preview.setIconSize(12)
        self._preview.setIcon(QgsRubberBand.ICON_CIRCLE)
        self._preview.setToGeometry(
            QgsGeometry.fromPointXY(QgsPointXY(self._orig_pt)), None)

        # Prévisualise en orange les lignes directement connectées
        couches = self.couches[self._sel_reseau]
        if role == 'regard':
            self._collect_line_previews(couches['conduite'])
            self._collect_line_previews(couches['branchement'])
        elif role == 'tabouret':
            self._collect_line_previews(couches['branchement'], translate_all=True)

    def _collect_line_previews(self, line_layer, translate_all=False):
        """Collecte les rubber bands de prévisualisation des lignes connectées.
        translate_all=True : tous les sommets suivent le déplacement (tabouret).
        translate_all=False : seul le sommet coïncident suit (regard).
        """
        tolerance = 0.05
        old_point = QgsPointXY(self._orig_pt)
        for feat in line_layer.getFeatures(rect_request(old_point, tolerance)):
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            line = geom.asPolyline()
            if translate_all:
                # Branchement de tabouret : l'extrémité finale doit coïncider
                if QgsPointXY(line[-1]).distance(old_point) > tolerance:
                    continue
                endpoints = list(range(len(line)))   # tous les indices
            else:
                endpoints = []
                if QgsPointXY(line[0]).distance(old_point) <= tolerance:
                    endpoints.append(0)
                if QgsPointXY(line[-1]).distance(old_point) <= tolerance:
                    endpoints.append(len(line) - 1)
                if not endpoints:
                    continue
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
            rb.setColor(QColor(255, 165, 0, 220))
            rb.setWidth(2)
            rb.setToGeometry(QgsGeometry.fromPolylineXY(line), None)
            self._line_previews.append({
                'rb':          rb,
                'line':        [QgsPointXY(p) for p in line],
                'endpoints':   endpoints,
            })

    def _apply_geom_move(self, new_point):
        old_point = QgsPointXY(self._orig_pt)
        couches = self.couches[self._sel_reseau]

        if not self._sel_layer.isEditable():
            self._sel_layer.startEditing()
        self._sel_layer.changeGeometry(
            self._sel_feat.id(), QgsGeometry.fromPointXY(new_point))
        self._sel_layer.commitChanges()

        if self._sel_role == 'regard':
            self._update_connected_lines(couches['conduite'], old_point, new_point)
            self._reproject_branchements(couches['branchement'], couches['conduite'])
            self._update_connected_lines(couches['branchement'], old_point, new_point)
        elif self._sel_role == 'tabouret':
            self._translate_branchements(couches['branchement'], couches['conduite'],
                                         old_point, new_point)

        self._reset()
        self.canvas.refresh()

    # ------------------------------------------------------------------ déplacement étiquette

    def _start_label_move(self):
        lbl = self._label_hover
        self._sel_label = lbl
        self._label_w = lbl.labelRect.width()
        self._label_h = lbl.labelRect.height()
        self._mode = 'label'
        self._clear_label_hover()

        hw, hh = self._label_w / 2, self._label_h / 2
        cx = (lbl.labelRect.xMinimum() + lbl.labelRect.xMaximum()) / 2
        cy = (lbl.labelRect.yMinimum() + lbl.labelRect.yMaximum()) / 2

        self._preview = QgsRubberBand(self.canvas, QgsWkbTypes.PolygonGeometry)
        self._preview.setToGeometry(
            QgsGeometry.fromRect(
                QgsRectangle(cx - hw, cy - hh, cx + hw, cy + hh)), None)
        self._preview.setColor(QColor(255, 165, 0, 60))
        self._preview.setStrokeColor(QColor(255, 165, 0, 200))
        self._preview.setWidth(2)

        self._set_label_hidden(lbl, True)

    def _set_label_hidden(self, lbl, hidden):
        """Masque (hidden=True) ou restaure (hidden=False) l'étiquette via lbl_visible."""
        layer = QgsProject.instance().mapLayer(lbl.layerID)
        if layer is None:
            return
        from ..gui.etiquettes import LBL_VISIBLE
        idx = layer.fields().indexFromName(LBL_VISIBLE)
        if idx < 0:
            return
        val = 0 if hidden else None
        if not layer.isEditable():
            layer.startEditing()
        layer.changeAttributeValue(lbl.featureId, idx, val)
        layer.commitChanges()
        self._label_hidden = hidden
        self.canvas.refresh()

    @staticmethod
    def _conduite_angle_at(geom, pt):
        """Valeur de LBL_ROT (degrés) pour aligner l'étiquette épinglée sur la
        conduite au point pt.

        L'angle lisible de la conduite est normalisé dans [-90, 90], puis
        décalé de -90° : le placement OverPoint de QGIS ajoute +90° à la
        rotation data-defined (sinon le texte sort perpendiculaire à la
        conduite). affiché = (angle-90) + 90 = angle."""
        try:
            if geom is None or geom.isEmpty():
                return -90.0
            _, _, after, _ = geom.closestSegmentWithContext(pt)
            line = geom.asPolyline()
            if len(line) < 2:
                return -90.0
            i = max(1, min(after, len(line) - 1))
            p1, p2 = line[i - 1], line[i]
            angle = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
            if angle > 90:
                angle -= 180
            elif angle < -90:
                angle += 180
            return round(angle - 90, 2)
        except Exception:
            return -90.0

    def _apply_label_move(self, new_point):
        lbl = self._sel_label
        layer = QgsProject.instance().mapLayer(lbl.layerID)
        if layer is None:
            self._reset()
            return

        from ..gui.etiquettes import LBL_X, LBL_Y
        fields = layer.fields()
        idx_x = fields.indexFromName(LBL_X)
        idx_y = fields.indexFromName(LBL_Y)

        if idx_x < 0 or idx_y < 0:
            self._reset()
            return

        # On translate l'ancrage stocké du même vecteur que le centre
        # rendu vers le point cliqué : indépendant du coin que QGIS
        # utilise pour interpréter PositionX/PositionY.
        cur_cx = (lbl.labelRect.xMinimum() + lbl.labelRect.xMaximum()) / 2
        cur_cy = (lbl.labelRect.yMinimum() + lbl.labelRect.yMaximum()) / 2
        dx = new_point.x() - cur_cx
        dy = new_point.y() - cur_cy

        def _to_float(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        feat = layer.getFeature(lbl.featureId)
        cur_anchor_x = _to_float(feat[LBL_X]) if feat.isValid() else None
        cur_anchor_y = _to_float(feat[LBL_Y]) if feat.isValid() else None

        if cur_anchor_x is None or cur_anchor_y is None:
            # Premier déplacement : l'ancrage stocké est le centre
            # (cohérent avec Hali=Center / Vali=Half dans etiquettes.py).
            cur_anchor_x = cur_cx
            cur_anchor_y = cur_cy

        new_x = cur_anchor_x + dx
        new_y = cur_anchor_y + dy

        from ..gui.etiquettes import LBL_VISIBLE, LBL_ROT
        idx_v = fields.indexFromName(LBL_VISIBLE)
        idx_r = fields.indexFromName(LBL_ROT)

        if not layer.isEditable():
            layer.startEditing()
        layer.changeAttributeValue(lbl.featureId, idx_x, new_x)
        layer.changeAttributeValue(lbl.featureId, idx_y, new_y)
        if idx_v >= 0:
            layer.changeAttributeValue(lbl.featureId, idx_v, None)
        # Conduites : fige l'orientation = angle de la conduite au point d'origine
        if idx_r >= 0:
            rot_deg = self._conduite_angle_at(
                feat.geometry(), QgsPointXY(cur_cx, cur_cy))
            layer.changeAttributeValue(lbl.featureId, idx_r, rot_deg)
        layer.commitChanges()
        self._label_hidden = False

        self._reset()
        self.canvas.refresh()

    # ------------------------------------------------------------------ déplacement annotation

    def _make_ann_band(self, item):
        pt = item.point()
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        rb.setToGeometry(QgsGeometry.fromPointXY(QgsPointXY(pt.x(), pt.y())), None)
        rb.setColor(QColor(255, 165, 0))
        rb.setIconSize(14)
        rb.setIcon(QgsRubberBand.ICON_CIRCLE)
        return rb

    def _clear_annotation_hover(self):
        if self._hover_annotation_band is not None:
            self.canvas.scene().removeItem(self._hover_annotation_band)
            self._hover_annotation_band = None
        self._hover_annotation = None

    def _start_annotation_move(self):
        item_id, item = self._hover_annotation
        pt = item.point()
        # Copie des données avant tout removeItem
        self._sel_ann_id = item_id
        self._sel_ann_text = item.text()
        self._sel_ann_fmt = item.format()
        from .annotation_tool import _get_alignment
        self._sel_ann_alignment = _get_alignment(item)
        self._sel_ann_orig_pt = QgsPointXY(pt.x(), pt.y())
        self._mode = 'annotation'
        self._clear_annotation_hover()

        self._preview = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self._preview.setColor(QColor(0, 200, 0))
        self._preview.setIconSize(12)
        self._preview.setIcon(QgsRubberBand.ICON_CIRCLE)
        self._preview.setToGeometry(
            QgsGeometry.fromPointXY(self._sel_ann_orig_pt), None)

    def _apply_annotation_move(self, new_point):
        from qgis.core import QgsAnnotationPointTextItem
        from .annotation_tool import _set_alignment

        ann_layer = QgsProject.instance().mainAnnotationLayer()
        ann_layer.removeItem(self._sel_ann_id)

        new_item = QgsAnnotationPointTextItem(self._sel_ann_text, new_point)
        new_item.setFormat(self._sel_ann_fmt)
        _set_alignment(new_item, self._sel_ann_alignment)
        ann_layer.addItem(new_item)

        self._reset()
        self.canvas.refresh()

    # ------------------------------------------------------------------ reset

    def _reset(self):
        if self._label_hidden and self._sel_label is not None:
            self._set_label_hidden(self._sel_label, False)
        self._clear_geom_hover()
        self._clear_label_hover()
        self._clear_annotation_hover()
        self._clear_piquage_hover()
        if self._preview is not None:
            self.canvas.scene().removeItem(self._preview)
            self._preview = None
        for item in self._line_previews:
            self.canvas.scene().removeItem(item['rb'])
        self._line_previews = []
        # piquage rubber bands
        for rb in (self._piquage_snap_band, self._piquage_line_prev):
            if rb is not None:
                self.canvas.scene().removeItem(rb)
        self._piquage_snap_band = None
        self._piquage_line_prev = None
        self._piquage_feat      = None
        self._piquage_layer     = None
        self._piquage_reseau    = None
        self._piquage_cond_layer= None
        self._piquage_reg_layer = None
        self._piquage_snap_pt   = None
        self._piquage_snap_cond = None
        self._mode = None
        self._sel_feat = None
        self._sel_layer = None
        self._sel_reseau = None
        self._sel_role = None
        self._orig_pt = None
        self._sel_label = None
        self._label_hidden = False
        self._sel_ann_id = None
        self._sel_ann_text = None
        self._sel_ann_fmt = None
        self._sel_ann_alignment = None
        self._sel_ann_orig_pt = None

    # ------------------------------------------------------------------ helpers géométrie

    def _update_connected_lines(self, line_layer, old_point, new_point):
        tolerance = 0.001
        if not line_layer.isEditable():
            line_layer.startEditing()
        modified = False
        for feat in line_layer.getFeatures(rect_request(old_point, tolerance)):
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            line = geom.asPolyline()
            changed = False
            if QgsPointXY(line[0]).distance(old_point) <= tolerance:
                line[0] = new_point
                changed = True
            if QgsPointXY(line[-1]).distance(old_point) <= tolerance:
                line[-1] = new_point
                changed = True
            if changed:
                new_geom = QgsGeometry.fromPolylineXY(line)
                line_layer.changeGeometry(feat.id(), new_geom)
                idx = line_layer.fields().indexOf('longueur')
                if idx >= 0:
                    line_layer.changeAttributeValue(
                        feat.id(), idx, new_geom.length())
                modified = True
        if modified:
            line_layer.commitChanges()
        else:
            line_layer.rollBack()

    def _translate_branchements(self, branchement_layer, conduite_layer,
                                 old_point, new_point):
        """Translate tout le branchement connecté au tabouret (rigide),
        puis re-projette le point de piquage sur la conduite la plus proche."""
        tolerance = 0.05
        dx = new_point.x() - old_point.x()
        dy = new_point.y() - old_point.y()

        if not branchement_layer.isEditable():
            branchement_layer.startEditing()
        modified = False

        for feat in branchement_layer.getFeatures(
                rect_request(old_point, tolerance)):
            geom = feat.geometry()
            if geom.isEmpty():
                continue
            line = geom.asPolyline()

            # Le tabouret est l'extrémité finale du branchement
            if QgsPointXY(line[-1]).distance(old_point) > tolerance:
                continue

            # Translate tous les sommets
            new_line = [QgsPointXY(p.x() + dx, p.y() + dy) for p in line]

            # Re-projette le point de piquage (premier sommet) sur la conduite
            _, best_proj, _ = nearest_line_feature_expanding(
                conduite_layer, new_line[0])

            if best_proj is not None:
                new_line[0] = best_proj

            new_geom = QgsGeometry.fromPolylineXY(new_line)
            branchement_layer.changeGeometry(feat.id(), new_geom)

            idx = branchement_layer.fields().indexOf('longueur')
            if idx >= 0:
                branchement_layer.changeAttributeValue(
                    feat.id(), idx, round(new_geom.length(), 2))
            modified = True

        if modified:
            branchement_layer.commitChanges()
        else:
            branchement_layer.rollBack()

    def _reproject_branchements(self, branchement_layer, conduite_layer):
        if not branchement_layer.isEditable():
            branchement_layer.startEditing()
        modified = False
        for br_feat in branchement_layer.getFeatures():
            br_geom = br_feat.geometry()
            if br_geom.isEmpty():
                continue
            br_line = br_geom.asPolyline()
            start_pt = QgsPointXY(br_line[0])
            _, best_proj, best_dist = nearest_line_feature_expanding(
                conduite_layer, start_pt)
            if best_proj is None or best_dist <= 0.0001:
                continue
            br_line[0] = best_proj
            new_geom = QgsGeometry.fromPolylineXY(br_line)
            branchement_layer.changeGeometry(br_feat.id(), new_geom)
            idx = branchement_layer.fields().indexOf('longueur')
            if idx >= 0:
                branchement_layer.changeAttributeValue(
                    br_feat.id(), idx, new_geom.length())
            modified = True
        if modified:
            branchement_layer.commitChanges()
        else:
            branchement_layer.rollBack()

    # ------------------------------------------------------------------ piquage

    def _find_piquage_near(self, click_pt, tol):
        """Retourne (feat, br_layer, reseau, cond_layer, reg_layer) ou None."""
        best, best_d = None, float('inf')
        for reseau, couches in self.couches.items():
            br_layer = couches.get('branchement')
            if not _ok(br_layer):
                continue
            for feat in br_layer.getFeatures(rect_request(click_pt, tol)):
                geom = feat.geometry()
                if geom.isEmpty():
                    continue
                line = geom.asPolyline()
                if not line:
                    continue
                d = click_pt.distance(QgsPointXY(line[0]))
                if d <= tol and d < best_d:
                    best_d = d
                    best = (feat, br_layer, reseau,
                            couches.get('conduite'), couches.get('regard'))
        return best

    def _clear_piquage_hover(self):
        if self._hover_piquage_band is not None:
            self.canvas.scene().removeItem(self._hover_piquage_band)
            self._hover_piquage_band = None
        self._hover_piquage = None

    def _start_piquage_move(self):
        feat, br_layer, reseau, cond_layer, reg_layer = self._hover_piquage
        self._piquage_feat       = feat
        self._piquage_layer      = br_layer
        self._piquage_reseau     = reseau
        self._piquage_cond_layer = cond_layer
        self._piquage_reg_layer  = reg_layer
        self._mode = 'piquage'
        self._clear_piquage_hover()

        self._piquage_snap_band = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self._piquage_snap_band.setColor(QColor(0, 200, 0))
        self._piquage_snap_band.setWidth(2)

        self._piquage_line_prev = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        col = QColor(200, 80, 0) if reseau == 'EU' else QColor(0, 80, 200)
        self._piquage_line_prev.setColor(col)
        self._piquage_line_prev.setWidth(2)
        self._piquage_line_prev.setLineStyle(Qt.DotLine)

        from qgis.utils import iface
        iface.messageBar().pushMessage(
            f"Déplacer piquage {reseau}",
            "Déplacer vers la conduite ou un regard  ·  Clic : confirmer  ·  Échap : annuler",
            level=0, duration=0,
        )

    def _update_piquage_snap(self, cursor_pt):
        """Snap curseur → regard ou conduite du même réseau."""
        cond_layer = self._piquage_cond_layer
        if not _ok(cond_layer):
            return

        self._piquage_snap_band.reset(QgsWkbTypes.LineGeometry)
        snap_pt   = None
        snap_cond = None

        # Priorité 1 : regard proche (10 px)
        reg_layer = self._piquage_reg_layer
        if _ok(reg_layer):
            reg_tol = 10 * self.canvas.mapUnitsPerPixel()
            r_feat, _ = nearest_point_feature(reg_layer, cursor_pt, reg_tol)
            if r_feat is not None:
                snap_pt = QgsPointXY(r_feat.geometry().asPoint())
                snap_cond, _, _ = nearest_line_feature_expanding(
                    cond_layer, snap_pt)

        # Priorité 2 : projection sur conduite
        if snap_pt is None:
            cond_tol = 200 * self.canvas.mapUnitsPerPixel()
            best_cf, best_proj, _ = nearest_line_feature(
                cond_layer, cursor_pt, cond_tol)
            if best_cf is not None:
                snap_pt   = best_proj
                snap_cond = best_cf

        self._piquage_snap_pt   = snap_pt
        self._piquage_snap_cond = snap_cond

        if snap_pt is None:
            if self._piquage_line_prev:
                self._piquage_line_prev.reset(QgsWkbTypes.LineGeometry)
            return

        # Croix verte au point snappé
        cs = 15 * self.canvas.mapUnitsPerPixel()
        cross = QgsGeometry.fromMultiPolylineXY([
            [QgsPointXY(snap_pt.x() - cs, snap_pt.y()),
             QgsPointXY(snap_pt.x() + cs, snap_pt.y())],
            [QgsPointXY(snap_pt.x(), snap_pt.y() - cs),
             QgsPointXY(snap_pt.x(), snap_pt.y() + cs)],
        ])
        self._piquage_snap_band.setToGeometry(cross, None)

        # Prévisualisation branchement
        old_line = self._piquage_feat.geometry().asPolyline()
        new_line = [snap_pt] + [QgsPointXY(p) for p in old_line[1:]]
        self._piquage_line_prev.setToGeometry(
            QgsGeometry.fromPolylineXY(new_line), None)

    def _apply_piquage_move(self):
        """Confirme le déplacement du piquage et met à jour tous les attributs."""
        snap_pt   = self._piquage_snap_pt
        snap_cond = self._piquage_snap_cond
        if snap_pt is None or snap_cond is None:
            self._reset()
            return

        feat  = self._piquage_feat
        layer = self._piquage_layer

        old_line = feat.geometry().asPolyline()
        new_line = [snap_pt] + [QgsPointXY(p) for p in old_line[1:]]
        new_geom = QgsGeometry.fromPolylineXY(new_line)

        cond_geom = snap_cond.geometry()
        new_pk  = round(cond_geom.lineLocatePoint(
                        QgsGeometry.fromPointXY(snap_pt)), 3)
        new_lon = round(new_geom.length(), 2)

        fields = layer.fields()
        if not layer.isEditable():
            layer.startEditing()

        layer.changeGeometry(feat.id(), new_geom)

        for attr, val in (('pk_debut',    new_pk),
                          ('id_conduite', snap_cond.id()),
                          ('longueur',    new_lon)):
            idx = fields.indexOf(attr)
            if idx >= 0:
                layer.changeAttributeValue(feat.id(), idx, val)

        idx_cote = fields.indexOf('cote_piquage')
        if idx_cote >= 0 and _ok(self._piquage_reg_layer):
            cote = self._interp_cote_piquage(snap_cond, new_pk)
            if cote is not None:
                layer.changeAttributeValue(feat.id(), idx_cote, round(cote, 3))

        layer.commitChanges()
        self._reset()
        self.canvas.refresh()

    def _interp_cote_piquage(self, cond_feat, pk):
        """Interpolation linéaire FE_dep → FE_arr au PK donné sur la conduite."""
        cond_geom = cond_feat.geometry()
        if cond_geom.isEmpty():
            return None
        cond_len = cond_geom.length()
        if cond_len <= 0:
            return None
        line   = cond_geom.asPolyline()
        tol    = 0.05

        def _fe_at(pt):
            r, _ = nearest_point_feature(self._piquage_reg_layer, pt, tol)
            if r is None:
                return None
            try:
                return float(r['fe_radier'])
            except (TypeError, ValueError):
                return None

        fe_dep = _fe_at(QgsPointXY(line[0]))
        fe_arr = _fe_at(QgsPointXY(line[-1]))
        if fe_dep is None or fe_arr is None:
            return None
        return fe_dep + (fe_arr - fe_dep) * (pk / cond_len)
