# tools/draw_conduite_tool.py

import math

from qgis.core import (
    Qgis,
    QgsPointXY, QgsGeometry, QgsFeature, QgsWkbTypes, QgsProject
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QMessageBox, QToolTip
from qgis.PyQt.QtGui import QColor, QCursor

from . import i18n

from .spatial_utils import nearest_point_feature, rect_request


class DrawConduiteTool(QgsMapToolEmitPoint):
    """
    Outil de dessin d'une conduite (EU ou EP).
    Chaque segment entre deux clics = un tronçon de conduite + un regard à chaque sommet.
    - Clic gauche : ajouter un regard et créer le tronçon depuis le regard précédent
    - Clic droit : ajouter le dernier regard + tronçon et terminer
    - Backspace : supprimer le dernier tronçon et son regard
    - Échap : annuler tout
    """
    finished = pyqtSignal()

    _TOPO_MIN_DIST_M = 0.5  # distance minimale entre deux regards (m)

    def __init__(self, canvas, reseau, couches):
        super().__init__(canvas)
        self.canvas = canvas
        self.reseau = reseau
        self.conduite_layer = couches['conduite']
        self.regard_layer = couches['regard']

        self.last_point = None       # dernier point posé
        self.points = []             # tous les sommets posés (pour calcul d'angle)
        self.regard_ids = []         # ids des regards créés (pour undo)
        self.conduite_ids = []       # ids des tronçons créés (pour undo)

        # Rubber band pour le segment en cours de tracé
        color = QColor(255, 0, 0) if reseau == "EU" else QColor(0, 0, 255)
        self.rubber = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
        self.rubber.setColor(color)
        self.rubber.setWidth(2)

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            f"Conduite {self.reseau}",
            i18n.tr('ot_aide_conduite'),
            level=Qgis.MessageLevel.Info, duration=0,
        )

    def deactivate(self):
        from qgis.utils import iface
        iface.messageBar().clearWidgets()
        QToolTip.hideText()
        self.rubber.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.last_point = None
        self.points = []
        self.regard_ids = []
        self.conduite_ids = []
        super().deactivate()

    def canvasMoveEvent(self, event):
        if self.last_point:
            point = self.toMapCoordinates(event.pos())
            self.rubber.setToGeometry(
                QgsGeometry.fromPolylineXY([self.last_point, point]), None)
            longueur = self.last_point.distance(point)
            texte = f"{longueur:.2f} m".replace('.', ',')
            if len(self.points) >= 2:
                angle = self._compute_angle(self.points[-2], self.points[-1], point)
                deviation = 180.0 - angle
                texte += f"  ·  {angle:.1f}° / {deviation:.1f}°".replace('.', ',')
            QToolTip.showText(QCursor.pos(), texte, self.canvas)
        else:
            QToolTip.hideText()

    @staticmethod
    def _compute_angle(p_prev, p_vertex, p_next):
        """Angle (en degrés) au sommet p_vertex entre les segments p_prev-p_vertex
        et p_vertex-p_next. 180° = alignement droit, 90° = angle droit."""
        ax = p_prev.x() - p_vertex.x()
        ay = p_prev.y() - p_vertex.y()
        bx = p_next.x() - p_vertex.x()
        by = p_next.y() - p_vertex.y()
        dot = ax * bx + ay * by
        det = ax * by - ay * bx
        return abs(math.degrees(math.atan2(det, dot)))

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            if self.last_point is None:
                return
            point = self.toMapCoordinates(event.pos())
            self._add_point(point)
            self._reset()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        point = self.toMapCoordinates(event.pos())
        self._add_point(point)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._reset()
        elif event.key() == Qt.Key.Key_Backspace:
            self._undo_last()

    def _add_point(self, point):
        """Ajoute un point : crée un regard et un tronçon si ce n'est pas le premier."""
        snapped = self._snap_to_regard(point)
        if snapped:
            point = snapped
        else:
            nearby = self._find_nearby_regard(point)
            if nearby:
                from qgis.utils import iface as _iface
                _iface.messageBar().pushMessage(
                    "Topologie",
                    i18n.tr('ot_regard_proche', distance=i18n.nombre(SNAP_WARN_M)),
                    level=Qgis.MessageLevel.Warning, duration=4,
                )
            regard_id = self._create_regard(point)
            self.regard_ids.append(regard_id)

        if self.last_point is not None:
            # Créer le tronçon entre le point précédent et celui-ci
            conduite_id = self._create_troncon(self.last_point, point)
            self.conduite_ids.append(conduite_id)

        self.last_point = point
        self.points.append(point)

    def _create_regard(self, point):
        """Crée un regard au point donné. Retourne l'id."""
        if not self.regard_layer.isEditable():
            self.regard_layer.startEditing()
        feat = QgsFeature(self.regard_layer.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(point))
        self.regard_layer.addFeature(feat)
        self.regard_layer.commitChanges()
        return feat.id()

    def _create_troncon(self, pt_from, pt_to):
        """Crée un tronçon de conduite entre deux points. Retourne l'id."""
        from ..config_dialog import get_default_params
        defaults = get_default_params()
        key = f"conduite_{self.reseau.lower()}"

        geom = QgsGeometry.fromPolylineXY([pt_from, pt_to])
        feat = QgsFeature(self.conduite_layer.fields())
        feat.setGeometry(geom)
        fields = self.conduite_layer.fields()
        feat.setAttribute('longueur', geom.length())
        if fields.indexOf('diametre') >= 0 and defaults[key]['diametre']:
            feat.setAttribute('diametre', defaults[key]['diametre'])
        if fields.indexOf('materiau') >= 0 and defaults[key]['materiau']:
            feat.setAttribute('materiau', defaults[key]['materiau'])

        if not self.conduite_layer.isEditable():
            self.conduite_layer.startEditing()
        self.conduite_layer.addFeature(feat)
        self.conduite_layer.commitChanges()
        return feat.id()

    def _undo_last(self):
        """Supprime le dernier tronçon et son regard."""
        if not self.conduite_ids:
            # Pas de tronçon, on est au premier point : supprimer le regard
            if self.regard_ids:
                rid = self.regard_ids.pop()
                if not self.regard_layer.isEditable():
                    self.regard_layer.startEditing()
                self.regard_layer.deleteFeature(rid)
                self.regard_layer.commitChanges()
            self.last_point = None
            self.points = []
            self.rubber.reset(QgsWkbTypes.GeometryType.LineGeometry)
            return

        # Supprimer le dernier tronçon
        cid = self.conduite_ids.pop()
        # Récupérer le point de départ de ce tronçon avant suppression
        conduite_feat = self.conduite_layer.getFeature(cid)
        prev_point = conduite_feat.geometry().asPolyline()[0]

        if not self.conduite_layer.isEditable():
            self.conduite_layer.startEditing()
        self.conduite_layer.deleteFeature(cid)
        self.conduite_layer.commitChanges()

        # Supprimer le regard du dernier point
        if self.regard_ids:
            rid = self.regard_ids.pop()
            if not self.regard_layer.isEditable():
                self.regard_layer.startEditing()
            self.regard_layer.deleteFeature(rid)
            self.regard_layer.commitChanges()

        if self.points:
            self.points.pop()
        self.last_point = QgsPointXY(prev_point)
        self.rubber.reset(QgsWkbTypes.GeometryType.LineGeometry)

    def _cancel(self):
        """Annule tout : supprime tous les tronçons et regards créés."""
        if self.conduite_ids:
            if not self.conduite_layer.isEditable():
                self.conduite_layer.startEditing()
            for cid in self.conduite_ids:
                self.conduite_layer.deleteFeature(cid)
            self.conduite_layer.commitChanges()

        if self.regard_ids:
            if not self.regard_layer.isEditable():
                self.regard_layer.startEditing()
            for rid in self.regard_ids:
                self.regard_layer.deleteFeature(rid)
            self.regard_layer.commitChanges()

        QToolTip.hideText()
        self.rubber.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.last_point = None
        self.points = []
        self.regard_ids = []
        self.conduite_ids = []

    def _reset(self):
        """Termine le tracé en cours, prêt pour un nouveau."""
        QToolTip.hideText()
        self.rubber.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.last_point = None
        self.points = []
        self.regard_ids = []
        self.conduite_ids = []

    def _find_nearby_regard(self, point):
        """Retourne le premier regard dans _TOPO_MIN_DIST_M, hors tolérance de snap."""
        for feat in self.regard_layer.getFeatures(
                rect_request(point, self._TOPO_MIN_DIST_M)):
            geom = feat.geometry()
            if geom.type() != QgsWkbTypes.GeometryType.PointGeometry:
                continue
            d = point.distance(QgsPointXY(geom.asPoint()))
            if 0 < d <= self._TOPO_MIN_DIST_M:
                return feat
        return None

    def _snap_to_regard(self, point):
        """Snap au regard le plus proche si dans la tolérance (30 px)."""
        tolerance = 30 * self.canvas.mapUnitsPerPixel()
        best_point = None
        best_dist = float('inf')

        feat, dist = nearest_point_feature(self.regard_layer, point, tolerance)
        if feat is not None:
            best_dist = dist
            best_point = feat.geometry().asPoint()

        if best_dist <= tolerance:
            return best_point
        return None
