# tools/coupe_transversale_tool.py

from qgis.PyQt import sip
from qgis.core import Qgis, QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox

from . import i18n

from .graph_utils import _to_float, QGIS_NULL

_SNAP_TOL = 0.05


def _nom_regard(feat):
    if feat is None:
        return '?'
    v = feat['nom']
    if v and (QGIS_NULL is None or v != QGIS_NULL):
        s = str(v).strip()
        if s:
            return s
    return f"R{feat.id()}"


class CoupeTransversaleTool(QgsMapTool):
    """
    Coupe transversale : l'utilisateur trace un axe de coupe →
    toutes les conduites EU + EP croisées sont dessinées en coupe,
    avec TN et FE interpolés depuis les regards amont/aval.

    Clic gauche        : ajouter un point.
    Double-clic / droit : terminer et calculer.
    Échap              : annuler.
    """

    def __init__(self, canvas, iface, couches_eu, couches_ep):
        super().__init__(canvas)
        self.canvas     = canvas
        self.iface      = iface
        self.couches_eu = couches_eu
        self.couches_ep = couches_ep

        self._points = []
        self._band   = None

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.iface.messageBar().pushMessage(
            i18n.tr('coupe_transversale'),
            i18n.tr('ot_aide_coupe'),
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
            if len(self._points) >= 2:
                self._compute_and_show()
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ rubber band

    def _update_band(self, cursor_pt=None):
        if self._band is None:
            self._band = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.LineGeometry)
            self._band.setColor(QColor(200, 0, 200, 200))
            self._band.setWidth(2)
        self._band.reset(QgsWkbTypes.GeometryType.LineGeometry)
        for p in self._points:
            self._band.addPoint(p, False)
        if cursor_pt is not None:
            self._band.addPoint(cursor_pt, True)

    # ------------------------------------------------------------------ calcul

    def _compute_and_show(self):
        pts = [self._points[0]]
        for p in self._points[1:]:
            if p.distance(pts[-1]) > 0.001:
                pts.append(p)
        if len(pts) < 2:
            return

        cut_line = QgsGeometry.fromPolylineXY(pts)
        if cut_line.length() < 0.01:
            QMessageBox.warning(None, i18n.tr('coupe_transversale'), i18n.tr('po_axe_court'))
            return

        from ..config_dialog import get_cubature_config
        config = get_cubature_config()

        crossings = []
        warnings  = []

        for reseau, couches in (('EU', self.couches_eu), ('EP', self.couches_ep)):
            cl = couches.get('conduite')
            rl = couches.get('regard')
            if cl is None or sip.isdeleted(cl):
                continue
            if rl is None or sip.isdeleted(rl):
                continue

            regard_pts = [
                (QgsPointXY(f.geometry().asPoint()), f)
                for f in rl.getFeatures()
                if not f.geometry().isEmpty()
            ]

            def snap_regard(pt, rpts=regard_pts):
                best, best_d = None, float('inf')
                for rpt, rfeat in rpts:
                    d = pt.distance(rpt)
                    if d < best_d:
                        best_d, best = d, rfeat
                return best if best_d <= _SNAP_TOL else None

            for c_feat in cl.getFeatures():
                c_geom = c_feat.geometry()
                if c_geom.isEmpty():
                    continue
                line = c_geom.asPolyline()
                if len(line) < 2:
                    continue

                if not c_geom.intersects(cut_line):
                    continue

                inter_geom = c_geom.intersection(cut_line)
                if inter_geom.isEmpty():
                    continue
                # Ignore line/polygon intersections (parallel conduit)
                if inter_geom.type() != QgsWkbTypes.GeometryType.PointGeometry:
                    continue

                # Extract first intersection point
                inter_pt_xy = None
                for v in inter_geom.vertices():
                    inter_pt_xy = QgsPointXY(v.x(), v.y())
                    break
                if inter_pt_xy is None:
                    continue

                x_cut = cut_line.lineLocatePoint(QgsGeometry.fromPointXY(inter_pt_xy))

                c_len = c_geom.length()
                t = (c_geom.lineLocatePoint(QgsGeometry.fromPointXY(inter_pt_xy)) / c_len
                     if c_len > 0 else 0.5)

                r0 = snap_regard(QgsPointXY(line[0]))
                r1 = snap_regard(QgsPointXY(line[-1]))

                fe0 = _to_float(r0['fe_radier']) if r0 else None
                fe1 = _to_float(r1['fe_radier']) if r1 else None
                tn0 = _to_float(r0['tn'])        if r0 else None
                tn1 = _to_float(r1['tn'])        if r1 else None

                if fe0 is None and fe1 is None:
                    warnings.append(
                        i18n.tr('ct_sans_fe', id=c_feat.id(), reseau=reseau))
                    continue
                if tn0 is None and tn1 is None:
                    warnings.append(
                        i18n.tr('ct_sans_tn', id=c_feat.id(), reseau=reseau))
                    continue

                if fe0 is None: fe0 = fe1
                if fe1 is None: fe1 = fe0
                if tn0 is None: tn0 = tn1
                if tn1 is None: tn1 = tn0

                fe_inter = fe0 + t * (fe1 - fe0)
                tn_inter = tn0 + t * (tn1 - tn0)

                diam_mm  = _to_float(c_feat['diametre']) or 200.0
                diam_m   = diam_mm / 1000.0
                materiau = ''
                if c_feat['materiau'] and (QGIS_NULL is None or c_feat['materiau'] != QGIS_NULL):
                    materiau = str(c_feat['materiau'])

                width = config.get(f'largeur_conduite_{reseau.lower()}', 0.80)

                crossings.append({
                    'x':         x_cut,
                    'tn':        tn_inter,
                    'fe':        fe_inter,
                    'diam_m':    diam_m,
                    'materiau':  materiau,
                    'reseau':    reseau,
                    'width':     width,
                    'nom_amont': _nom_regard(r0),
                    'nom_aval':  _nom_regard(r1),
                })

        if warnings:
            self.iface.messageBar().pushMessage(
                i18n.tr('coupe_transversale'), "  ·  ".join(warnings),
                level=Qgis.MessageLevel.Warning, duration=10)

        if not crossings:
            QMessageBox.warning(
                None, i18n.tr('coupe_transversale'),
                i18n.tr('ot_aucune_conduite_coupe'))
            return

        crossings.sort(key=lambda c: c['x'])

        from ..gui.coupe_transversale_dialog import CoupeTransversaleDialog
        dlg = CoupeTransversaleDialog(crossings, config, self.iface.mainWindow(),
                                      cut_line_pts=pts)
        dlg.show()

    # ------------------------------------------------------------------ reset

    def _reset(self):
        self._points = []
        if self._band is not None:
            self.canvas.scene().removeItem(self._band)
            self._band = None


class CoupeTransversaleSingleTool(CoupeTransversaleTool):
    """Variante mono-réseau compatible avec _run_tool_single(needs_iface=True).

    Signature : (canvas, iface, reseau, couches)
    """

    _EMPTY = {'conduite': None, 'regard': None, 'branchement': None, 'tabouret': None}

    def __init__(self, canvas, iface, reseau, couches):
        if reseau == 'EU':
            super().__init__(canvas, iface, couches, self._EMPTY)
        else:
            super().__init__(canvas, iface, self._EMPTY, couches)
        self._reseau_label = reseau

    def activate(self):
        from qgis.gui import QgsMapTool as _Base
        _Base.activate(self)
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.iface.messageBar().pushMessage(
            "%s %s" % (i18n.tr('coupe_transversale'), self._reseau_label),
            i18n.tr('ot_aide_coupe'),
            level=Qgis.MessageLevel.Info, duration=0,
        )
