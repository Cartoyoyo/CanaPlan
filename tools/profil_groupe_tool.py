# tools/profil_groupe_tool.py

import sip
from qgis.core import QgsPointXY, QgsGeometry, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QMessageBox
from ..gui.profil_dialog import ProfilOptionsDialog
from ..gui.profil_groupe_dialog import ProfilGroupeDialog

try:
    from qgis.core import NULL as QGIS_NULL
except ImportError:
    QGIS_NULL = None

BUFFER_DIST = 3.0  # mètres


def _to_float(val):
    if val is None or (QGIS_NULL is not None and val == QGIS_NULL):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


class ProfilGroupeTool(QgsMapTool):
    """
    Profil groupé : l'utilisateur trace un axe de référence → buffer 3 m →
    toutes les conduites EU + EP dans le buffer sont projetées sur l'axe et
    affichées superposées dans ProfilGroupeDialog.

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

        self._points  = []   # list of QgsPointXY
        self._band    = None

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CrossCursor)
        self.iface.messageBar().pushMessage(
            "Profil groupé",
            "Tracez l'axe de référence : clic gauche = ajouter un point  ·  "
            "Double-clic ou clic droit = terminer  ·  Échap = annuler",
            level=0, duration=0,
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
        if event.button() == Qt.LeftButton:
            self._points.append(self.toMapCoordinates(event.pos()))
            self._update_band(self.toMapCoordinates(event.pos()))
        elif event.button() == Qt.RightButton:
            if len(self._points) >= 2:
                self._compute_and_show()
            self._reset()

    def canvasDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            # canvasReleaseEvent a déjà ajouté le point — on déclenche le calcul
            if len(self._points) >= 2:
                self._compute_and_show()
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ rubberband

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
            QMessageBox.warning(None, "Profil groupé", "L'axe tracé est trop court.")
            return

        buffer_geom = ref_line.buffer(BUFFER_DIST, 8)

        # Table de lookup : QgsPointXY → {tn, fe_radier, nom}
        regard_lookup = []
        for couches in (self.couches_eu, self.couches_ep):
            rl = couches.get('regard')
            if rl is None or sip.isdeleted(rl):
                continue
            for feat in rl.getFeatures():
                g = feat.geometry()
                if g.isEmpty():
                    continue
                regard_lookup.append((
                    QgsPointXY(g.asPoint()),
                    {
                        'tn':        _to_float(feat['tn']),
                        'fe_radier': _to_float(feat['fe_radier']),
                        'nom':       (str(feat['nom'])
                                      if feat['nom'] and feat['nom'] != QGIS_NULL
                                      else '—'),
                    }
                ))

        def snap_regard(pt, tol=1.0):
            best, best_d = None, float('inf')
            for rpt, rdata in regard_lookup:
                d = pt.distance(rpt)
                if d < best_d:
                    best_d, best = d, rdata
            return best if best_d <= tol else None

        conduites_data = []

        for reseau, couches in (('EU', self.couches_eu), ('EP', self.couches_ep)):
            cl = couches.get('conduite')
            if cl is None or sip.isdeleted(cl):
                continue
            for feat in cl.getFeatures():
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

                x0 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt0))
                x1 = ref_line.lineLocatePoint(QgsGeometry.fromPointXY(pt1))

                r0 = snap_regard(pt0)
                r1 = snap_regard(pt1)

                # Oriente toujours x0 <= x1
                if x0 > x1:
                    x0, x1 = x1, x0
                    r0, r1 = r1, r0

                conduites_data.append({
                    'reseau': reseau,
                    'feat':   feat,
                    'x0':     x0,
                    'x1':     x1,
                    'fe0':    r0['fe_radier'] if r0 else None,
                    'fe1':    r1['fe_radier'] if r1 else None,
                    'tn0':    r0['tn']        if r0 else None,
                    'tn1':    r1['tn']        if r1 else None,
                    'nom_r0': r0['nom']       if r0 else '—',
                    'nom_r1': r1['nom']       if r1 else '—',
                })

        if not conduites_data:
            QMessageBox.warning(
                None, "Profil groupé",
                f"Aucune conduite EU ou EP trouvée dans le buffer de {BUFFER_DIST} m\n"
                "autour de l'axe tracé.")
            return

        # Piquages (branchements) — départ projeté sur l'axe de référence
        # Clé composite (reseau, feat_id) car EU et EP sont dans des couches
        # séparées et leurs feature IDs peuvent se chevaucher.
        cid_to_cdata = {(c['reseau'], c['feat'].id()): c for c in conduites_data}
        piquages = []

        for reseau, couches in (('EU', self.couches_eu), ('EP', self.couches_ep)):
            br_layer  = couches.get('branchement')
            tab_layer = couches.get('tabouret')
            if br_layer is None or sip.isdeleted(br_layer):
                continue

            # Pré-indexe les tabourets par position (extrémité aval du branchement)
            tab_by_pt = {}
            if tab_layer and not sip.isdeleted(tab_layer):
                for tf in tab_layer.getFeatures():
                    g = tf.geometry()
                    if g.isEmpty():
                        continue
                    tp = QgsPointXY(g.asPoint())
                    key = (round(tp.x(), 3), round(tp.y(), 3))
                    v = tf['nom']
                    tab_by_pt[key] = (
                        str(v) if v and (QGIS_NULL is None or v != QGIS_NULL) else '')

            for br in br_layer.getFeatures():
                g = br.geometry()
                if g.isEmpty():
                    continue
                line = g.asPolyline()
                if len(line) < 2:
                    continue

                start_pt = QgsPointXY(line[0])
                if not buffer_geom.contains(QgsGeometry.fromPointXY(start_pt)):
                    continue

                x_piq = ref_line.lineLocatePoint(
                    QgsGeometry.fromPointXY(start_pt))

                # Interpole FE depuis la conduite parente.
                # Priorité à la projection sur l'axe (alignement visuel avec
                # la ligne FE dessinée). Si les positions projetées dégénèrent
                # (x0 >= x1, conduite ~perpendiculaire à l'axe), fallback sur
                # pk_debut / longueur réelle.
                fe_piq = None
                parent = cid_to_cdata.get((reseau, br['id_conduite']))
                if not parent:
                    continue
                if parent:
                    x0, x1 = parent['x0'], parent['x1']
                    fe0, fe1 = parent['fe0'], parent['fe1']
                    if x1 > x0 and fe0 is not None and fe1 is not None:
                        t = max(0.0, min(1.0, (x_piq - x0) / (x1 - x0)))
                        fe_piq = fe0 + t * (fe1 - fe0)
                    else:
                        pk = _to_float(br['pk_debut']) or 0.0
                        parent_length = (_to_float(parent['feat']['longueur'])
                                         or parent['feat'].geometry().length())
                        if fe0 is not None and fe1 is not None and parent_length > 0:
                            t = max(0.0, min(1.0, pk / parent_length))
                            fe_piq = fe0 + t * (fe1 - fe0)
                        elif fe0 is not None:
                            fe_piq = fe0
                        elif fe1 is not None:
                            fe_piq = fe1

                end_pt = QgsPointXY(line[-1])
                nom_tab = tab_by_pt.get(
                    (round(end_pt.x(), 3), round(end_pt.y(), 3)), '')

                piquages.append({
                    'x':      x_piq,
                    'fe':     fe_piq,
                    'nom':    nom_tab,
                    'reseau': reseau,
                })

        opts_dlg = ProfilOptionsDialog(self.iface.mainWindow())
        if opts_dlg.exec_() != opts_dlg.Accepted:
            return

        dlg = ProfilGroupeDialog(
            {'conduites': conduites_data, 'ref_length': ref_len,
             'piquages':  piquages},
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
