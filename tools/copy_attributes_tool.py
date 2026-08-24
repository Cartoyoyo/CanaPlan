# tools/copy_attributes_tool.py

import math

from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

from . import i18n
from . import layer_ok as _ok
from .spatial_utils import nearest_point_feature, nearest_line_feature

# Champs jamais copiés : identifiant, géométrie-dépendants, étiquettes, relations
_SKIP = frozenset({
    'nom', 'longueur', 'lbl_x', 'lbl_y', 'lbl_visible',
    'id_conduite', 'pk_debut', 'sens',
    'fid', 'id', 'ogc_fid', 'gid',
})


class CopyAttributesTool(QgsMapTool):
    """
    1er clic gauche  : copie les attributs de l'objet source (sauf nom/longueur/lbl_*)
                       → source surlignée en bleu
    Clics suivants   : accumule les cibles du même rôle → surlignées en vert
    Clic droit       : applique les attributs copiés aux cibles
    Échap            : annule
    """

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {'EU': couches_eu, 'EP': couches_ep}

        self._mode = None          # None | 'select'
        self._copied_role = None
        self._copied_attrs = {}    # {field_name: value}

        self._hover = None         # (role, feat, layer, reseau)
        self._hover_band = None    # orange – survol courant
        self._source_band = None   # bleu  – source copiée

        self._targets = []         # [(feat, layer)]
        self._highlights = []      # rubber bands verts

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            i18n.tr('copy_attributes'),
            i18n.tr('ot_aide_copy'),
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        self._update_hover(event.pos())

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._hover is None:
                return
            role, feat, layer, reseau = self._hover

            if self._mode is None:
                self._copy_source(role, feat, layer)
            else:
                if role != self._copied_role:
                    return
                if any(f.id() == feat.id() and lyr is layer
                       for f, lyr in self._targets):
                    return
                self._targets.append((feat, layer))
                self._highlights.append(
                    self._make_band(feat, layer, QColor(0, 180, 0, 200)))
                self._clear_hover_band()
                self.canvas.update()

        elif event.button() == Qt.RightButton:
            if self._mode == 'select' and self._targets:
                self._apply()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ copie source

    def _copy_source(self, role, feat, layer):
        fields = layer.fields()
        pk_indices = set(layer.primaryKeyAttributes())
        self._copied_attrs = {
            fields.field(i).name(): feat[fields.field(i).name()]
            for i in range(fields.count())
            if fields.field(i).name() not in _SKIP
            and i not in pk_indices
        }
        self._copied_role = role
        self._mode = 'select'
        # Remplace le hover orange par une band bleue fixe sur la source
        self._clear_hover_band()
        self._source_band = self._make_band(feat, layer, QColor(30, 120, 255, 220))

    # ------------------------------------------------------------------ application

    def _apply(self):
        for feat, layer in self._targets:
            if not layer.isEditable():
                layer.startEditing()
            fid = feat.id()
            fields = layer.fields()
            pk_indices = set(layer.primaryKeyAttributes())
            for name, val in self._copied_attrs.items():
                idx = fields.indexFromName(name)
                if idx >= 0 and idx not in pk_indices:
                    layer.changeAttributeValue(fid, idx, val)
            layer.commitChanges()
        self.canvas.refresh()
        self._reset()

    # ------------------------------------------------------------------ hover

    def _update_hover(self, pixel_pos):
        click_pt = self.toMapCoordinates(pixel_pos)
        tol = 20 * self.canvas.mapUnitsPerPixel()

        if self._mode is None:
            roles = ('regard', 'tabouret', 'conduite', 'branchement')
        else:
            roles = (self._copied_role,)

        best = self._find_best(click_pt, tol, roles)

        if best is not None:
            role, feat, layer, reseau, _ = best
            # Ne pas hoverer sur une cible déjà sélectionnée
            if any(f.id() == feat.id() and lyr is layer
                   for f, lyr in self._targets):
                self._clear_hover_band()
                return
            if (self._hover is None
                    or self._hover[1].id() != feat.id()
                    or self._hover[2] is not layer):
                self._clear_hover_band()
                self._hover = (role, feat, layer, reseau)
                self._hover_band = self._make_band(
                    feat, layer, QColor(255, 165, 0, 200))
        else:
            self._clear_hover_band()

    def _find_best(self, click_pt, tol, roles):
        point_roles = [r for r in roles if r in ('regard', 'tabouret')]
        line_roles  = [r for r in roles if r in ('conduite', 'branchement')]

        best_pt = None
        for reseau, couches in self.couches.items():
            for role in point_roles:
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                feat, dist = nearest_point_feature(layer, click_pt, tol)
                if feat is not None and (best_pt is None or dist < best_pt[4]):
                    best_pt = (role, feat, layer, reseau, dist)

        if best_pt is not None:
            return best_pt

        best_line = None
        for reseau, couches in self.couches.items():
            for role in line_roles:
                layer = couches.get(role)
                if not _ok(layer):
                    continue
                feat, _, dist = nearest_line_feature(layer, click_pt, tol)
                if feat is not None and (best_line is None or dist < best_line[4]):
                    best_line = (role, feat, layer, reseau, dist)
        return best_line

    # ------------------------------------------------------------------ helpers

    def _make_band(self, feat, layer, color):
        gtype = layer.geometryType()
        if gtype == QgsWkbTypes.PointGeometry:
            rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
            rb.setToGeometry(feat.geometry(), layer)
            rb.setColor(color)
            rb.setIconSize(16)
            rb.setIcon(QgsRubberBand.ICON_CIRCLE)
        else:
            rb = QgsRubberBand(self.canvas, gtype)
            rb.setToGeometry(feat.geometry(), layer)
            rb.setColor(color)
            rb.setWidth(5)
        return rb

    def _clear_hover_band(self):
        if self._hover_band is not None:
            self.canvas.scene().removeItem(self._hover_band)
            self._hover_band = None
        self._hover = None

    def _reset(self):
        self._clear_hover_band()
        if self._source_band is not None:
            self.canvas.scene().removeItem(self._source_band)
            self._source_band = None
        for rb in self._highlights:
            self.canvas.scene().removeItem(rb)
        self._highlights.clear()
        self._targets.clear()
        self._mode = None
        self._copied_role = None
        self._copied_attrs = {}
