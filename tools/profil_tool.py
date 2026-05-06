import sip
from qgis.core import QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox

from .graph_utils import _to_float, build_graph, bfs, QGIS_NULL


class ProfilTool(QgsMapTool):
    """
    Profil en long : 1er clic = regard départ (vert), 2e clic = regard arrivée.
    Recherche BFS dans le graphe conduite↔regard, puis ouvre ProfilDialog.
    Échap annule la saisie en cours.
    """

    _SNAP_TOL_PX = 20

    def __init__(self, canvas, iface, reseau, couches):
        super().__init__(canvas)
        self.canvas  = canvas
        self.iface   = iface
        self.reseau  = reseau
        self.couches = couches   # {'conduite', 'branchement', 'regard', 'tabouret'}

        self._start      = None   # QgsFeature regard départ
        self._start_band = None
        self._hover_band = None

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        self.iface.messageBar().pushMessage(
            f"Profil en long {self.reseau}",
            "1er clic : regard départ (vert)  ·  2e clic : regard arrivée → tracé du profil  ·  Échap : annuler",
            level=0, duration=0,
        )

    def deactivate(self):
        self.iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ helpers couche

    def _layer(self, role):
        """Retourne la couche si elle est encore valide, sinon None."""
        layer = self.couches.get(role)
        if layer is None or sip.isdeleted(layer):
            return None
        return layer

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        feat = self._nearest_regard(self.toMapCoordinates(event.pos()))
        if feat:
            layer = self._layer('regard')
            if layer is None:
                return
            if self._hover_band is None:
                self._hover_band = self._make_pt_band(QColor(255, 165, 0))
            self._hover_band.setToGeometry(feat.geometry(), layer)
        else:
            self._clear_band('_hover_band')

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        feat = self._nearest_regard(self.toMapCoordinates(event.pos()))
        if feat is None:
            return

        if self._start is None:
            self._start = feat
            self._start_band = self._make_pt_band(QColor(0, 200, 0))
            self._start_band.setToGeometry(feat.geometry(), self._layer('regard'))
        else:
            if feat.id() != self._start.id():
                self._compute_and_show(self._start, feat)
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ données

    def _compute_and_show(self, start, end):
        conduite_layer = self._layer('conduite')
        regard_layer   = self._layer('regard')
        if conduite_layer is None or regard_layer is None:
            return

        from .calc_pentes import recalc_pentes
        recalc_pentes(conduite_layer, regard_layer,
                      branchement_layer=self._layer('branchement'),
                      tabouret_layer=self._layer('tabouret'))

        graph, _       = build_graph(conduite_layer, regard_layer)
        r_ids, c_feats = bfs(graph, start.id(), end.id())

        if r_ids is None:
            QMessageBox.warning(
                None, "Profil en long",
                "Aucun chemin trouvé entre les deux regards sélectionnés.\n"
                "Vérifiez que le réseau est correctement connecté.")
            return
        regards      = [regard_layer.getFeature(rid) for rid in r_ids]

        # Abscisses cumulées
        abscisses = [0.0]
        for c in c_feats:
            lng = _to_float(c['longueur']) or c.geometry().length()
            abscisses.append(abscisses[-1] + lng)

        # Piquages par indice de conduite
        cid_to_idx = {c.id(): i for i, c in enumerate(c_feats)}
        piquages   = {}
        br_layer = self._layer('branchement')
        for br in (br_layer.getFeatures() if br_layer else []):
            idx = cid_to_idx.get(br['id_conduite'])
            if idx is None:
                continue
            pk  = _to_float(br['pk_debut']) or 0.0
            nom = self._tabouret_nom(br)
            piquages.setdefault(idx, []).append({
                'abscisse': abscisses[idx] + pk,
                'nom':      nom,
            })

        from ..gui.profil_dialog import ProfilDialog, ProfilOptionsDialog
        opts_dlg = ProfilOptionsDialog(self.iface.mainWindow())
        if opts_dlg.exec_() != opts_dlg.Accepted:
            return
        dlg = ProfilDialog(
            {
                'reseau':    self.reseau,
                'regards':   regards,
                'conduites': c_feats,
                'abscisses': abscisses,
                'piquages':  piquages,
            },
            opts_dlg.options(),
            self.iface.mainWindow(),
        )
        dlg.show()

    # ------------------------------------------------------------------ helpers

    def _nearest_regard(self, point):
        layer = self._layer('regard')
        if layer is None:
            return None
        tol = self._SNAP_TOL_PX * self.canvas.mapUnitsPerPixel()
        best, best_d = None, float('inf')
        for feat in layer.getFeatures():
            g = feat.geometry()
            if g.isEmpty():
                continue
            d = point.distance(QgsPointXY(g.asPoint()))
            if d <= tol and d < best_d:
                best_d, best = d, feat
        return best

    def _tabouret_nom(self, br_feat):
        """Retourne le nom du tabouret à l'extrémité finale du branchement."""
        geom = br_feat.geometry()
        if geom.isEmpty():
            return ''
        line = geom.asPolyline()
        if not line:
            return ''
        end_pt = QgsPointXY(line[-1])
        tol = 0.05
        tab_layer = self._layer('tabouret')
        for feat in (tab_layer.getFeatures() if tab_layer else []):
            g = feat.geometry()
            if g.isEmpty():
                continue
            if end_pt.distance(QgsPointXY(g.asPoint())) <= tol:
                v = feat['nom']
                if v and (QGIS_NULL is None or v != QGIS_NULL):
                    return str(v)
        return ''

    def _make_pt_band(self, color):
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        rb.setColor(color)
        rb.setIconSize(14)
        rb.setIcon(QgsRubberBand.ICON_CIRCLE)
        return rb

    def _clear_band(self, attr):
        band = getattr(self, attr, None)
        if band is not None:
            self.canvas.scene().removeItem(band)
            setattr(self, attr, None)

    def _reset(self):
        self._start = None
        self._clear_band('_start_band')
        self._clear_band('_hover_band')
