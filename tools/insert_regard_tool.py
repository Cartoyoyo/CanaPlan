# tools/insert_regard_tool.py

import math

from qgis.core import (
    QgsPointXY, QgsGeometry, QgsFeature, QgsWkbTypes
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtGui import QColor

from . import i18n


class InsertRegardTool(QgsMapToolEmitPoint):
    """
    Outil d'insertion d'un regard sur une conduite existante.
    Projection automatique à 50 pixels de la conduite.
    Clic : le regard est créé au point projeté et la conduite est coupée.
    """
    finished = pyqtSignal()

    DETECT_TOLERANCE_PX = 50

    def __init__(self, canvas, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas = canvas
        self.couches = {
            'EU': couches_eu,
            'EP': couches_ep,
        }

        # Indicateur de snap (croix + trait de projection)
        self.snap_cross = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.snap_cross.setColor(QColor(0, 200, 0))
        self.snap_cross.setWidth(2)

        self.snap_line = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.snap_line.setColor(QColor(0, 200, 0))
        self.snap_line.setWidth(2)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            i18n.tr('insert_regard'),
            i18n.tr('ot_aide_insert_regard'),
            level=0, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_line.reset(QgsWkbTypes.LineGeometry)
        super().deactivate()

    def canvasMoveEvent(self, event):
        """Affiche l'indicateur de projection sur la conduite."""
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_line.reset(QgsWkbTypes.LineGeometry)

        cursor = self.toMapCoordinates(event.pos())
        result = self._find_closest_conduite(cursor)
        if not result:
            return

        proj_point = result[1]
        cross_size = 15 * self.canvas.mapUnitsPerPixel()

        # Trait de projection curseur → conduite
        self.snap_line.setToGeometry(
            QgsGeometry.fromPolylineXY([cursor, proj_point]), None)

        # Croix au point projeté
        cross_h = [
            QgsPointXY(proj_point.x() - cross_size, proj_point.y()),
            QgsPointXY(proj_point.x() + cross_size, proj_point.y()),
        ]
        cross_v = [
            QgsPointXY(proj_point.x(), proj_point.y() - cross_size),
            QgsPointXY(proj_point.x(), proj_point.y() + cross_size),
        ]
        self.snap_cross.setToGeometry(
            QgsGeometry.fromMultiPolylineXY([cross_h, cross_v]), None)

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        click_point = self.toMapCoordinates(event.pos())
        result = self._find_closest_conduite(click_point)
        if not result:
            return

        best_feat, best_proj, best_reseau = result
        couches = self.couches[best_reseau]
        conduite_layer = couches['conduite']
        regard_layer = couches['regard']

        # Créer le regard au point projeté (sans formulaire)
        if not regard_layer.isEditable():
            regard_layer.startEditing()
        regard_feat = QgsFeature(regard_layer.fields())
        regard_feat.setGeometry(QgsGeometry.fromPointXY(best_proj))
        regard_layer.addFeature(regard_feat)
        regard_layer.commitChanges()

        # Couper la conduite en deux
        self._split_conduite(conduite_layer, best_feat, best_proj)

        # Nettoyer l'indicateur
        self.snap_cross.reset(QgsWkbTypes.LineGeometry)
        self.snap_line.reset(QgsWkbTypes.LineGeometry)

        self.canvas.refresh()
        self.finished.emit()

    def _find_closest_conduite(self, point):
        """Cherche la conduite la plus proche dans la tolérance.
        Retourne (feat, proj_point, reseau) ou None."""
        tolerance = self.DETECT_TOLERANCE_PX * self.canvas.mapUnitsPerPixel()

        best_feat = None
        best_proj = None
        best_dist = float('inf')
        best_reseau = None

        from .spatial_utils import nearest_line_feature
        for reseau, couches in self.couches.items():
            layer = couches['conduite']
            feat, proj, dist = nearest_line_feature(layer, point, tolerance)
            if feat is not None and dist < best_dist:
                best_dist = dist
                best_feat = feat
                best_proj = proj
                best_reseau = reseau

        if best_feat is None or best_dist > tolerance:
            return None

        return (best_feat, best_proj, best_reseau)

    def _split_conduite(self, layer, feat, split_point):
        """Coupe une conduite en deux au point projeté."""
        geom = feat.geometry()
        line = geom.asPolyline()

        pk = geom.lineLocatePoint(QgsGeometry.fromPointXY(split_point))
        total_length = geom.length()

        if pk <= 0 or pk >= total_length:
            return

        split_pt = geom.interpolate(pk).asPoint()

        # Construire les deux sous-lignes
        line1 = []
        line2 = []
        inserted = False

        for i, vertex in enumerate(line):
            if not inserted:
                line1.append(vertex)
                if i < len(line) - 1:
                    seg = QgsGeometry.fromPolylineXY([vertex, line[i + 1]])
                    seg_pk = seg.lineLocatePoint(
                        QgsGeometry.fromPointXY(split_pt))
                    if 0 < seg_pk < seg.length():
                        line1.append(split_pt)
                        line2.append(split_pt)
                        inserted = True
            else:
                line2.append(vertex)

        if not inserted or len(line1) < 2 or len(line2) < 2:
            return

        if not layer.isEditable():
            layer.startEditing()

        layer.deleteFeature(feat.id())

        for sub_line in (line1, line2):
            new_geom = QgsGeometry.fromPolylineXY(sub_line)
            new_feat = QgsFeature(layer.fields())
            new_feat.setAttributes(feat.attributes())
            new_feat.setGeometry(new_geom)
            new_feat.setAttribute('longueur', new_geom.length())
            layer.addFeature(new_feat)

        layer.commitChanges()
