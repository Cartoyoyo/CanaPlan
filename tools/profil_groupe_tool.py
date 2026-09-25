# tools/profil_groupe_tool.py

from qgis.core import Qgis, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt

from . import i18n
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QDialog, QMessageBox
from ..gui.profil_dialog import ProfilOptionsDialog
from ..gui.profil_groupe_dialog import ProfilGroupeDialog

from .qt_exec import exec_dialog

BUFFER_DIST = 3.0  # mètres


class ProfilGroupeTool(QgsMapTool):
    """
    Profil groupé : l'utilisateur trace un axe de référence → buffer 3 m →
    toutes les conduites EU + EP (+ AEP) dans le buffer sont projetées sur l'axe et
    affichées superposées dans ProfilGroupeDialog.

    Clic gauche        : ajouter un point.
    Double-clic / droit : terminer et calculer.
    Échap              : annuler.
    """

    def __init__(self, canvas, iface, couches_eu, couches_ep, couches_aep=None):
        super().__init__(canvas)
        self.canvas     = canvas
        self.iface      = iface
        self.couches_eu = couches_eu
        self.couches_ep = couches_ep
        self.couches_aep = couches_aep

        self._points  = []   # list of QgsPointXY
        self._band    = None

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.iface.messageBar().pushMessage(
            i18n.tr('po_profil_groupe'),
            i18n.tr('po_aide_axe'),
            level=Qgis.MessageLevel.Info, duration=0,
        )

    def deactivate(self):
        self.iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        if not self._points:
            return
        self._update_band(self.toMapCoordinates(event.pos()))

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._points.append(self.toMapCoordinates(event.pos()))
            self._update_band(self.toMapCoordinates(event.pos()))
        elif event.button() == Qt.MouseButton.RightButton:
            if len(self._points) >= 2:
                self._compute_and_show()
            self._reset()

    def canvasDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # canvasReleaseEvent a déjà ajouté le point — on déclenche le calcul
            if len(self._points) >= 2:
                self._compute_and_show()
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ rubberband

    def _update_band(self, cursor_pt=None):
        if self._band is None:
            self._band = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
            self._band.setColor(QColor(255, 120, 0, 200))
            self._band.setWidth(2)
        self._band.reset(QgsWkbTypes.GeometryType.LineGeometry)
        for p in self._points:
            self._band.addPoint(p, False)
        if cursor_pt is not None:
            self._band.addPoint(cursor_pt, True)

    # ------------------------------------------------------------------ calcul

    def _compute_and_show(self):
        # Déduplique les points consécutifs identiques (résidu du double-clic)
        pts = [self._points[0]]
        for p in self._points[1:]:
            if p.distance(pts[-1]) > 0.001:
                pts.append(p)

        if len(pts) < 2:
            return

        ref_line = QgsGeometry.fromPolylineXY(pts)
        ref_len  = ref_line.length()
        if ref_len < 0.01:
            QMessageBox.warning(None, i18n.tr('po_profil_groupe'), i18n.tr('po_axe_court'))
            return

        from .profil_batch import calculer_donnees_groupe
        jeux = [('EU', self.couches_eu), ('EP', self.couches_ep)]
        if self.couches_aep:
            jeux.append(('AEP', self.couches_aep))
        data = calculer_donnees_groupe(jeux, pts, BUFFER_DIST)
        if not data or not data['conduites']:
            QMessageBox.warning(
                None, i18n.tr('po_profil_groupe'),
                i18n.tr('po_aucune_conduite', rayon=BUFFER_DIST))
            return

        opts_dlg = ProfilOptionsDialog(self.iface.mainWindow())
        if exec_dialog(opts_dlg) != QDialog.DialogCode.Accepted:
            return

        dlg = ProfilGroupeDialog(
            data,
            self.iface.mainWindow(),
            options=opts_dlg.options(),
        )
        dlg.show()

    # ------------------------------------------------------------------ reset

    def _reset(self):
        self._points = []
        if self._band is not None:
            self.canvas.scene().removeItem(self._band)
            self._band = None
