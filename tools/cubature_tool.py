# -*- coding: utf-8 -*-
import sip
from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox

BUFFER_DIST = 3.0  # mètres


class CubatureTool(QgsMapTool):
    """
    Mode BFS : 1er clic = regard départ (vert), 2e clic = regard arrivée → calcul.
    Mode Axe  : tracé d'une ligne de référence → buffer 3 m → toutes les conduites
                entièrement dans le buffer → calcul.
    Échap = reset (retour au dialogue d'accueil).
    """

    _SNAP_TOL_PX = 20

    def __init__(self, canvas, iface, couches_eu, couches_ep, opts, show_remblai=False):
        super().__init__(canvas)
        self.canvas = canvas
        self.iface = iface
        self.couches_eu = couches_eu
        self.couches_ep = couches_ep
        self.opts = opts
        self.show_remblai = show_remblai

        self._start = None
        self._reseau_start = None
        self._start_band = None
        self._hover_band = None
        self._dialog = None

        # Mode axe
        self._axe_mode = opts.get('axe', False)
        self._points = []   # list of QgsPointXY
        self._band = None   # QgsRubberBand pour le tracé

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        if self._axe_mode:
            self.iface.messageBar().pushMessage(
                "Cubature tranchées" if not self.show_remblai else "Remblai tranchées",
                "Tracez l'axe de référence : clic gauche = ajouter un point  ·  "
                "Double-clic ou clic droit = terminer  ·  Échap = annuler",
                level=0, duration=0,
            )
        else:
            self.iface.messageBar().pushMessage(
                "Cubature tranchées" if not self.show_remblai else "Remblai tranchées",
                "1er clic : regard départ (vert)  ·  2e clic : regard arrivée → calcul  ·  Échap : annuler",
                level=0, duration=0,
            )

    def deactivate(self):
        self.iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        if self._axe_mode:
            if self._points:
                self._update_band(self.toMapCoordinates(event.pos()))
            return

        feat, _, _ = self._nearest_regard_any(self.toMapCoordinates(event.pos()))
        if feat:
            layer = self._find_layer_for_feat(feat)
            if layer:
                if self._hover_band is None:
                    self._hover_band = self._make_pt_band(QColor(255, 165, 0))
                self._hover_band.setToGeometry(feat.geometry(), layer)
                return
        self._clear_band('_hover_band')

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._axe_mode:
                self._points.append(self.toMapCoordinates(event.pos()))
                self._update_band(self.toMapCoordinates(event.pos()))
                return
            else:
                feat, reseau, _ = self._nearest_regard_any(self.toMapCoordinates(event.pos()))
                if feat is None:
                    return

                if self._start is None:
                    self._start = feat
                    self._reseau_start = reseau
                    layer = self._find_layer_for_feat(feat)
                    self._start_band = self._make_pt_band(QColor(0, 200, 0))
                    self._start_band.setToGeometry(feat.geometry(), layer)
                else:
                    if feat.id() == self._start.id():
                        self._reset()
                        return
                    if reseau != self._reseau_start:
                        QMessageBox.warning(
                            None, "Cubature tranchées",
                            "Les deux regards doivent appartenir au même réseau.\n"
                            f"Départ : {self._reseau_start}, arrivée : {reseau}.")
                        self._reset()
                        return
                    self._compute_bfs(self._start, feat, reseau)
                    self._reset()

        elif event.button() == Qt.RightButton:
            if self._axe_mode and len(self._points) >= 2:
                self._compute_axe()
                self._reset()

    def canvasDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._axe_mode:
            if len(self._points) >= 2:
                self._compute_axe()
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ axe drawing

    def _update_band(self, cursor_pt=None):
        if self._band is None:
            self._band = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
            self._band.setColor(QColor(255, 120, 0, 200))
            self._band.setWidth(2)
        self._band.reset(QgsWkbTypes.LineGeometry)
        for p in self._points:
            self._band.addPoint(p, False)
        if cursor_pt is not None:
            self._band.addPoint(cursor_pt, True)

    # ------------------------------------------------------------------ calcul Axe

    def _compute_axe(self):
        pts = [self._points[0]]
        for p in self._points[1:]:
            if p.distance(pts[-1]) > 0.001:
                pts.append(p)

        if len(pts) < 2:
            return

        ref_line = QgsGeometry.fromPolylineXY(pts)
        ref_len = ref_line.length()
        if ref_len < 0.01:
            QMessageBox.warning(None, "Cubature tranchées",
                                "L'axe tracé est trop court.")
            return

        buffer_geom = ref_line.buffer(BUFFER_DIST, 8)

        from ..config_dialog import get_cubature_config
        from .calc_cubature import (
            calculer_cubature_troncon, calculer_cubature_branchement,
            _to_float, _nom_regard, _profondeur_regard,
        )

        config = get_cubature_config()
        results = []
        regard_name_to_point = {}  # nom -> QgsPointXY (pour construire le prefix axe)

        for reseau, couches in (('EU', self.couches_eu), ('EP', self.couches_ep)):
            if self.opts.get('perimetre', 'tout') not in ('tout', reseau):
                continue

            conduite_layer = couches.get('conduite')
            regard_layer = couches.get('regard')
            branchement_layer = couches.get('branchement')
            tabouret_layer = couches.get('tabouret')

            if conduite_layer is None or sip.isdeleted(conduite_layer):
                continue

            # Index regards par position
            regard_by_pos = {}
            if regard_layer and not sip.isdeleted(regard_layer):
                for feat in regard_layer.getFeatures():
                    g = feat.geometry()
                    if g.isEmpty():
                        continue
                    pt = QgsPointXY(g.asPoint())
                    key = (round(pt.x(), 3), round(pt.y(), 3))
                    regard_by_pos[key] = feat
                    regard_name_to_point[_nom_regard(feat)] = pt

            def snap_regard(pt, tol=1.0):
                best, best_d = None, float('inf')
                for rpt_key, rfeat in regard_by_pos.items():
                    d = pt.distance(QgsPointXY(rpt_key[0], rpt_key[1]))
                    if d < best_d:
                        best_d, best = d, rfeat
                return best if best_d <= tol else None

            if self.opts.get('conduites', True):
                for feat in conduite_layer.getFeatures():
                    g = feat.geometry()
                    if g.isEmpty():
                        continue
                    line = g.asPolyline()
                    if len(line) < 2:
                        continue

                    pt0 = QgsPointXY(line[0])
                    pt1 = QgsPointXY(line[-1])

                    # Les deux extrémités doivent être dans le buffer
                    if not (buffer_geom.contains(QgsGeometry.fromPointXY(pt0)) and
                            buffer_geom.contains(QgsGeometry.fromPointXY(pt1))):
                        continue

                    r_start = snap_regard(pt0)
                    r_end = snap_regard(pt1)
                    if r_start is None or r_end is None:
                        continue

                    res = calculer_cubature_troncon(
                        feat, r_start, r_end, config, reseau)
                    if res:
                        results.append(res)

            if self.opts.get('branchements', True) and branchement_layer and not sip.isdeleted(branchement_layer):
                # Conduite IDs capturées
                conduit_ids = {r['id'] for r in results if r.get('type') == 'Conduite'}

                # Index tabourets
                t_pts = {}
                if tabouret_layer and not sip.isdeleted(tabouret_layer):
                    for feat in tabouret_layer.getFeatures():
                        g = feat.geometry()
                        if not g.isEmpty():
                            t_pts[feat.id()] = (QgsPointXY(g.asPoint()), feat)

                for br_feat in branchement_layer.getFeatures():
                    id_cond = br_feat['id_conduite']
                    if id_cond is None:
                        continue
                    try:
                        id_cond_int = int(id_cond)
                    except (TypeError, ValueError):
                        continue
                    if id_cond_int not in conduit_ids:
                        continue
                    g = br_feat.geometry()
                    if g.isEmpty():
                        continue
                    line = g.asPolyline()
                    if len(line) < 2:
                        continue
                    pt_end = QgsPointXY(line[-1])
                    tabouret_feat = None
                    best_d = float('inf')
                    for tid, (tpt, tfeat) in t_pts.items():
                        d = pt_end.distance(tpt)
                        if d <= 0.05 and d < best_d:
                            best_d, tabouret_feat = d, tfeat
                    res = calculer_cubature_branchement(
                        br_feat, tabouret_feat, config, reseau,
                        regard_layer, conduite_layer,
                    )
                    if res:
                        results.append(res)

        if not results:
            QMessageBox.warning(
                None, "Cubature tranchées",
                f"Aucune conduite trouvée dans le buffer de {BUFFER_DIST} m\n"
                "autour de l'axe tracé.")
            return

        from ..gui.cubature_dialog import CubatureDialog
        if self._dialog is not None:
            try:
                self._dialog.close()
            except Exception:
                pass

        # Construire le prefix du fichier a partir des regards capturés par réseau
        axe_parts = []
        for reseau in ('EU', 'EP'):
            reseau_noms = set()
            for r in results:
                if r.get('reseau') == reseau:
                    reseau_noms.add(r['nom_debut'])
                    reseau_noms.add(r['nom_fin'])
            if len(reseau_noms) >= 2:
                # Trouver les 2 extrêmes projetés sur la ligne de référence
                best_start, best_end = None, None
                best_start_d, best_end_d = float('inf'), float('inf')
                start_pt, end_pt = pts[0], pts[-1]
                for nom in reseau_noms:
                    pt = regard_name_to_point.get(nom)
                    if pt is None:
                        continue
                    d_start = pt.distance(start_pt)
                    d_end = pt.distance(end_pt)
                    if d_start < best_start_d:
                        best_start_d, best_start = d_start, nom
                    if d_end < best_end_d:
                        best_end_d, best_end = d_end, nom
                if best_start and best_end:
                    axe_parts.append(f"{best_start}_{best_end}")
            elif len(reseau_noms) == 1:
                axe_parts.append(list(reseau_noms)[0])

        axe_prefix = "_".join(axe_parts) if axe_parts else None

        dlg = CubatureDialog(results, config, self.iface.mainWindow(),
                             bfs_prefix=axe_prefix, show_remblai=self.show_remblai)
        dlg.show()
        self._dialog = dlg

    # ------------------------------------------------------------------ calcul BFS

    def _compute_bfs(self, start_feat, end_feat, reseau):
        couches = self.couches_eu if reseau == 'EU' else self.couches_ep
        if couches is None:
            return

        from ..config_dialog import get_cubature_config
        from .calc_cubature import (
            calculer_cubature_bfs, calculer_cubature_branchement,
            _build_graph, _bfs, _snap_tabouret, _to_float,
        )

        config = get_cubature_config()

        conduite_layer = couches.get('conduite')
        regard_layer = couches.get('regard')

        if conduite_layer is None or regard_layer is None:
            return

        graph, regard_by_id = _build_graph(conduite_layer, regard_layer)
        r_ids, c_feats = _bfs(graph, start_feat.id(), end_feat.id())

        if r_ids is None:
            QMessageBox.warning(
                None, "Cubature tranchées",
                "Aucun chemin trouvé entre les deux regards sélectionnés.\n"
                "Vérifiez que le réseau est correctement connecté.")
            return

        results = []

        if self.opts.get('conduites', True):
            results.extend(calculer_cubature_bfs(
                start_feat, end_feat, couches, config, reseau))

        if self.opts.get('branchements', True):
            branchement_layer = couches.get('branchement')
            tabouret_layer = couches.get('tabouret')
            if branchement_layer:
                conduit_ids_on_path = {c.id() for c in c_feats}
                tol = 0.05
                # Index tabourets
                t_pts = {}
                if tabouret_layer:
                    for feat in tabouret_layer.getFeatures():
                        g = feat.geometry()
                        if not g.isEmpty():
                            t_pts[feat.id()] = (QgsPointXY(g.asPoint()), feat)
                for br_feat in branchement_layer.getFeatures():
                    id_cond = br_feat['id_conduite']
                    if id_cond is None:
                        continue
                    try:
                        id_cond_int = int(id_cond)
                    except (TypeError, ValueError):
                        continue
                    if id_cond_int not in conduit_ids_on_path:
                        continue
                    g = br_feat.geometry()
                    if g.isEmpty():
                        continue
                    line = g.asPolyline()
                    if len(line) < 2:
                        continue
                    pt_end = QgsPointXY(line[-1])
                    tabouret_feat = None
                    best_d = float('inf')
                    for tid, (tpt, tfeat) in t_pts.items():
                        d = pt_end.distance(tpt)
                        if d <= tol and d < best_d:
                            best_d, tabouret_feat = d, tfeat
                    res = calculer_cubature_branchement(
                        br_feat, tabouret_feat, config, reseau,
                        regard_layer, conduite_layer,
                    )
                    if res:
                        results.append(res)

        if not results:
            QMessageBox.information(
                None, "Cubature tranchées",
                "Aucun élément à afficher sur le chemin sélectionné.")
            return

        from ..gui.cubature_dialog import CubatureDialog
        if self._dialog is not None:
            try:
                self._dialog.close()
            except Exception:
                pass
        from .calc_cubature import _nom_regard
        bfs_prefix = f"{_nom_regard(start_feat)}_{_nom_regard(end_feat)}"
        dlg = CubatureDialog(results, config, self.iface.mainWindow(),
                             bfs_prefix=bfs_prefix, show_remblai=self.show_remblai)
        dlg.show()
        self._dialog = dlg

    # ------------------------------------------------------------------ snapping

    def _nearest_regard_any(self, point):
        tol = self._SNAP_TOL_PX * self.canvas.mapUnitsPerPixel()
        best, best_d, best_reseau, best_layer = None, float('inf'), None, None
        perimetre = self.opts.get('perimetre', 'tout')

        for name, couches in [('EU', self.couches_eu), ('EP', self.couches_ep)]:
            if perimetre not in ('tout', name):
                continue
            layer = couches.get('regard') if couches else None
            if layer is None or sip.isdeleted(layer):
                continue
            for feat in layer.getFeatures():
                g = feat.geometry()
                if g.isEmpty():
                    continue
                d = point.distance(QgsPointXY(g.asPoint()))
                if d <= tol and d < best_d:
                    best_d, best, best_reseau = d, feat, name
                    best_layer = layer

        return best, best_reseau, best_layer

    def _find_layer_for_feat(self, feat):
        for couches in [self.couches_eu, self.couches_ep]:
            if couches is None:
                continue
            layer = couches.get('regard')
            if layer is None or sip.isdeleted(layer):
                continue
            if feat.id() in [f.id() for f in layer.getFeatures()]:
                return layer
        return None

    # ------------------------------------------------------------------ helpers

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
        self._reseau_start = None
        self._clear_band('_start_band')
        self._clear_band('_hover_band')
        # Axe
        self._points = []
        if self._band is not None:
            self.canvas.scene().removeItem(self._band)
            self._band = None
