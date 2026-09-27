# tools/appareil_aep_tool.py
"""Outil « Poser un appareil AEP ».

- Clic sur un nœud AEP existant (coude, appareil…) : un menu propose le type
  à lui donner — le nœud reste en place, la topologie ne bouge pas.
- Clic sur une conduite AEP, loin de tout nœud : un nœud est inséré au point
  projeté, la conduite est coupée en deux (même mécanique que « Insérer un
  regard »), puis le menu propose le type.

Le robinet de branchement n'est pas proposé : il est posé par l'outil
branchement, au piquage.
"""
from qgis.core import Qgis, QgsPointXY, QgsGeometry, QgsFeature, QgsWkbTypes
from qgis.gui import QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QCursor
from qgis.PyQt.QtWidgets import QMenu

from . import i18n
from . import reseaux as R
from .insert_regard_tool import InsertRegardTool
from .spatial_utils import nearest_point_feature


class AppareilAepTool(InsertRegardTool):

    NOEUD_TOLERANCE_PX = 12

    def __init__(self, canvas, reseau, couches):
        # InsertRegardTool travaille sur un dict de réseaux : on ne lui laisse
        # que l'AEP, EU et EP restent hors d'atteinte de cet outil.
        super().__init__(canvas, {}, {})
        self.couches = {'AEP': couches}
        self.reseau = 'AEP'
        self.noeud_band = QgsRubberBand(canvas, QgsWkbTypes.GeometryType.PointGeometry)
        self.noeud_band.setColor(QColor(255, 140, 0))
        self.noeud_band.setIconSize(14)
        self.noeud_band.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)

    def activate(self):
        super(InsertRegardTool, self).activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        from qgis.utils import iface
        iface.messageBar().pushMessage(
            i18n.tr('appareil_aep'), i18n.tr('ot_aide_appareil_aep'),
            level=Qgis.MessageLevel.Info, duration=0)

    def deactivate(self):
        self.noeud_band.reset(QgsWkbTypes.GeometryType.PointGeometry)
        super().deactivate()

    # ------------------------------------------------------------------ survol

    def _noeud_sous(self, point):
        tol = self.NOEUD_TOLERANCE_PX * self.canvas.mapUnitsPerPixel()
        feat, _ = nearest_point_feature(self.couches['AEP']['regard'], point, tol)
        return feat

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.noeud_band.reset(QgsWkbTypes.GeometryType.PointGeometry)
        noeud = self._noeud_sous(point)
        if noeud is not None:
            self.snap_cross.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self.snap_line.reset(QgsWkbTypes.GeometryType.LineGeometry)
            self.noeud_band.addPoint(QgsPointXY(noeud.geometry().asPoint()))
            return
        super().canvasMoveEvent(event)

    # ------------------------------------------------------------------ clic

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = self.toMapCoordinates(event.pos())
        noeuds = self.couches['AEP']['regard']

        noeud = self._noeud_sous(point)
        if noeud is not None:
            code = self._choisir_type(noeud['type'])
            if code:
                self._ecrire_type(noeuds, noeud.id(), code)
            return

        result = self._find_closest_conduite(point)
        if not result:
            return
        code = self._choisir_type(None)
        if not code:
            return
        best_feat, best_proj, _ = result
        if not noeuds.isEditable():
            noeuds.startEditing()
        feat = QgsFeature(noeuds.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(best_proj))
        feat.setAttribute('type', code)
        noeuds.addFeature(feat)
        noeuds.commitChanges()
        self._split_conduite(self.couches['AEP']['conduite'], best_feat, best_proj,
                             self.couches['AEP'].get('branchement'))
        self.snap_cross.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.snap_line.reset(QgsWkbTypes.GeometryType.LineGeometry)
        self.canvas.refresh()

    def _choisir_type(self, actuel):
        menu = QMenu()
        actions = {}
        for code in R.AEP_NOEUD_TYPES_MANUELS:
            prefixe = R.aep_prefixe(code)
            libelle = R.libelle_type(code) + (f"  ({prefixe})" if prefixe else "")
            if not R.aep_dessine(code):
                libelle += "  — " + i18n.tr('aep_muet')
            act = menu.addAction(libelle)
            act.setCheckable(True)
            act.setChecked(code == actuel)
            actions[act] = code
        choisi = menu.exec(QCursor.pos())
        return actions.get(choisi)

    @staticmethod
    def _ecrire_type(layer, fid, code):
        idx = layer.fields().indexOf('type')
        if idx < 0:
            return
        if not layer.isEditable():
            layer.startEditing()
        layer.changeAttributeValue(fid, idx, code)
        layer.commitChanges()
        layer.triggerRepaint()

