from qgis.core import Qgis, QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor
from . import layer_ok as _ok
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QSpinBox, QDialogButtonBox, QLabel, QMessageBox,
)

from . import i18n

from .graph_utils import _to_float, build_graph, bfs
from .qt_exec import exec_dialog

_DEFAULTS = {
    'EU': {'regard': 'REU',  'tabouret': 'EU-BRCHT'},
    'EP': {'regard': 'REP',  'tabouret': 'EP-BRCHT'},
}


# ─────────────────────────────────────────────────────────────────────────────
#  Dialog de saisie des préfixes
# ─────────────────────────────────────────────────────────────────────────────

class _PrefixDialog(QDialog):

    def __init__(self, default_regard, default_tabouret, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('ot_renum_titre'))
        layout = QVBoxLayout(self)

        def _spinbox(default=1):
            sb = QSpinBox()
            sb.setMinimum(0)
            sb.setMaximum(9999)
            sb.setValue(default)
            return sb

        form = QFormLayout()
        self.ed_regard      = QLineEdit(default_regard)
        self.sb_start_reg   = _spinbox(1)
        self.ed_tabouret    = QLineEdit(default_tabouret)
        self.sb_start_tab   = _spinbox(1)

        form.addRow(i18n.tr('ot_lbl_prefixe_regards'),   self.ed_regard)
        form.addRow(i18n.tr('ot_lbl_depart_regards'),   self.sb_start_reg)
        form.addRow(i18n.tr('ot_lbl_prefixe_tabourets'), self.ed_tabouret)
        form.addRow(i18n.tr('ot_lbl_depart_tabourets'), self.sb_start_tab)
        layout.addLayout(form)

        note = QLabel(i18n.tr('ot_renum_exemple'))
        note.setWordWrap(True)
        layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @property
    def regard_prefix(self):
        return self.ed_regard.text().strip()

    @property
    def tabouret_prefix(self):
        return self.ed_tabouret.text().strip()

    @property
    def start_num_regard(self):
        return self.sb_start_reg.value()

    @property
    def start_num_tabouret(self):
        return self.sb_start_tab.value()


# ─────────────────────────────────────────────────────────────────────────────
#  Outil carte
# ─────────────────────────────────────────────────────────────────────────────

class RenommerTool(QgsMapTool):
    """
    1er clic = regard départ (vert), 2e clic = regard arrivée.
    BFS pour trouver le chemin, puis dialogue préfixes → renommage.
    """

    _SNAP_TOL_PX = 20
    _SNAP_TOL_M  = 0.05

    def __init__(self, canvas, iface, reseau, couches):
        super().__init__(canvas)
        self.canvas  = canvas
        self.iface   = iface
        self.reseau  = reseau
        self.couches = couches

        self._start      = None
        self._start_band = None
        self._hover_band = None

    # ------------------------------------------------------------------ cycle

    def activate(self):
        super().activate()
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        self.iface.messageBar().pushMessage(
            i18n.tr('ot_titre_renum', reseau=self.reseau),
            i18n.tr('ot_aide_renum'),
            level=Qgis.MessageLevel.Info, duration=0,
        )

    def deactivate(self):
        self.iface.messageBar().clearWidgets()
        self._reset()
        super().deactivate()

    # ------------------------------------------------------------------ events

    def canvasMoveEvent(self, event):
        feat = self._nearest_regard(self.toMapCoordinates(event.pos()))
        if feat:
            if self._hover_band is None:
                self._hover_band = self._make_pt_band(QColor(255, 165, 0))
            self._hover_band.setToGeometry(feat.geometry(), self.couches['regard'])
        else:
            self._clear_band('_hover_band')

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        feat = self._nearest_regard(self.toMapCoordinates(event.pos()))
        if feat is None:
            return

        if self._start is None:
            self._start = feat
            self._start_band = self._make_pt_band(QColor(0, 200, 0))
            self._start_band.setToGeometry(feat.geometry(), self.couches['regard'])
        else:
            if feat.id() != self._start.id():
                self._rename_path(self._start, feat)
            self._reset()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._reset()

    # ------------------------------------------------------------------ renommage

    def _rename_path(self, start, end):
        graph, regards = build_graph(self.couches['conduite'], self.couches['regard'],
                                     tol=self._SNAP_TOL_M)
        r_ids, c_feats = bfs(graph, start.id(), end.id())

        if r_ids is None:
            QMessageBox.warning(
                None, i18n.tr('ot_renumerotation'),
                i18n.tr('po_aucun_chemin'))
            return

        defaults = _DEFAULTS.get(self.reseau, _DEFAULTS['EU'])
        dlg = _PrefixDialog(defaults['regard'], defaults['tabouret'],
                            self.iface.mainWindow())
        if exec_dialog(dlg) != QDialog.DialogCode.Accepted:
            return

        reg_prefix  = dlg.regard_prefix
        tab_prefix  = dlg.tabouret_prefix
        n_reg       = dlg.start_num_regard
        n_tab_start = dlg.start_num_tabouret

        # ── Renommer les regards ─────────────────────────────────────────────
        regard_layer = self.couches['regard']
        nom_reg_idx  = regard_layer.fields().indexOf('nom')
        regard_layer.startEditing()
        for i, rid in enumerate(r_ids):
            regard_layer.changeAttributeValue(
                rid, nom_reg_idx, f"{reg_prefix}{n_reg + i:02d}")
        regard_layer.commitChanges()

        # ── Tabourets rattachés, ordonnés par abscisse depuis le départ ──────
        # `pk_debut` se mesure depuis le premier sommet de la conduite, qui
        # n'est pas son extrémité amont : la numérisation ne dit rien du sens
        # d'écoulement. Trier dessus numérotait les tabourets de l'aval vers
        # l'amont sur tout tronçon numérisé à rebours — invisible quand la rue
        # descend dans le sens où elle a été saisie, systématique sinon.
        #
        # Le sens, c'est `start` qui le donne : le regard de départ, choisi par
        # l'opérateur ou passé par la recette. On le suit. `c_feats[i]` relie
        # `r_ids[i]` à `r_ids[i+1]`, donc la conduite est parcourue à l'endroit
        # si son premier sommet touche `r_ids[i]`. De quoi convertir chaque
        # `pk_debut` en une **abscisse unique mesurée depuis le départ** : un
        # seul nombre à trier, et qui se lit — « ce branchement est à 137 m de
        # l'amont ».
        abscisses = {}          # {id_conduite: (origine, sens, longueur)}
        cumul = 0.0
        for i, c in enumerate(c_feats):
            line   = c.geometry().asPolyline()
            length = c.geometry().length()
            amont  = regards.get(r_ids[i])
            sens   = 1.0
            if line and amont is not None and not amont.geometry().isEmpty():
                pt = QgsPointXY(amont.geometry().asPoint())
                if pt.distance(QgsPointXY(line[0])) \
                        > pt.distance(QgsPointXY(line[-1])):
                    sens = -1.0
            abscisses[c.id()] = (cumul, sens, length)
            cumul += length

        br_on_path = []
        for br in self.couches['branchement'].getFeatures():
            repere = abscisses.get(br['id_conduite'])
            if repere is None:
                continue
            origine, sens, length = repere
            pk = _to_float(br['pk_debut']) or 0.0
            br_on_path.append(
                (origine + (pk if sens > 0 else length - pk), br))
        br_on_path.sort(key=lambda x: x[0])

        tabouret_layer = self.couches['tabouret']
        nom_tab_idx    = tabouret_layer.fields().indexOf('nom')

        tab_pts = {
            feat.id(): QgsPointXY(feat.geometry().asPoint())
            for feat in tabouret_layer.getFeatures()
            if not feat.geometry().isEmpty()
        }

        tabouret_layer.startEditing()
        tab_num = n_tab_start
        for _s, br in br_on_path:
            geom = br.geometry()
            if geom.isEmpty():
                continue
            line = geom.asPolyline()
            if not line:
                continue
            end_pt = QgsPointXY(line[-1])
            # Un tabouret déjà nommé sort du jeu : deux branchements arrivant au
            # même point rebaptisaient sinon le même tabouret deux fois, et son
            # voisin restait sans nom.
            proche = [fid for fid, rpt in tab_pts.items()
                      if end_pt.distance(rpt) <= self._SNAP_TOL_M]
            if not proche:
                continue
            fid = min(proche, key=lambda i: end_pt.distance(tab_pts[i]))
            tabouret_layer.changeAttributeValue(
                fid, nom_tab_idx, f"{tab_prefix}{tab_num:02d}")
            del tab_pts[fid]
            tab_num += 1
        tabouret_layer.commitChanges()

        from ..gui.etiquettes import sync_labels_after_rename
        sync_labels_after_rename(regard_layer,   'regard',   self.reseau)
        sync_labels_after_rename(tabouret_layer, 'tabouret', self.reseau)
        br_layer = self.couches.get('branchement')
        if br_layer and _ok(br_layer):
            sync_labels_after_rename(br_layer, 'branchement', self.reseau)

        self.iface.mapCanvas().refresh()

        nb_reg = len(r_ids)
        nb_tab = tab_num - n_tab_start
        msg = i18n.tr(
            'ot_renum_regards', nb=nb_reg,
            debut=f"{reg_prefix}{n_reg:02d}",
            fin=f"{reg_prefix}{n_reg + nb_reg - 1:02d}")
        if nb_tab:
            msg += "\n" + i18n.tr(
                'ot_renum_tabourets', nb=nb_tab,
                debut=f"{tab_prefix}{n_tab_start:02d}",
                fin=f"{tab_prefix}{tab_num - 1:02d}")
        else:
            msg += "\n" + i18n.tr('ot_renum_sans_tabouret')
        QMessageBox.information(None, i18n.tr('ot_renumerotation'), msg)

    # ------------------------------------------------------------------ helpers

    def _nearest_regard(self, point):
        tol = self._SNAP_TOL_PX * self.canvas.mapUnitsPerPixel()
        layer = self.couches.get('regard')
        if not _ok(layer):
            return None
        from .spatial_utils import nearest_point_feature
        best, _ = nearest_point_feature(layer, point, tol)
        return best

    def _make_pt_band(self, color):
        rb = QgsRubberBand(self.canvas, QgsWkbTypes.GeometryType.PointGeometry)
        rb.setColor(color)
        rb.setIconSize(14)
        rb.setIcon(QgsRubberBand.IconType.ICON_CIRCLE)
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
