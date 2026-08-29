# -*- coding: utf-8 -*-
import json
import copy

from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QWidget,
    QScrollArea, QFormLayout, QGroupBox, QComboBox,
    QDoubleSpinBox, QCheckBox, QLabel, QRadioButton,
    QButtonGroup, QFileDialog, QMessageBox, QSizePolicy,
)
from qgis.core import QgsSettings, QgsMessageLog, Qgis

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.patches as mpatches
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ─── Constantes ───────────────────────────────────────────────────────────────

MATERIAUX_CONDUITE = ["PVC", "Fonte", "Béton", "PEHD", "Acier", "Grès", ""]
MATERIAUX_REMBLAI  = [
    "Sable", "2/6", "0/31.5", "Tout-venant",
    "GB (Grave bitume)", "GC (Grave ciment)", "Enrobé", "",
]

SETTINGS_KEY = "CanaPlan/coupe_tranchee_composee"

DEFAULT_TRANCHE = {
    'reseau':          'EU',
    'dn':              300,
    'materiau':        'PVC',
    'profondeur':      1.80,
    'espace_gauche':   0.50,
    'ecart_gauche':    0.40,
    'ecart_droit':     0.40,
    'ep_lit_pose':     0.10,
    'mat_lit_pose':    'Sable',
    'ep_enrobage':     0.15,
    'mat_enrobage':    'Sable',
    'mat_remblai':     '0/31.5',
    'chaussee_inf':    False,
    'ep_chaussee_inf': 0.20,
    'mat_chaussee_inf':'GB (Grave bitume)',
    'chaussee_sup':    False,
    'ep_chaussee_sup': 0.08,
    'mat_chaussee_sup':'Enrobé',
}

# ─── Helpers couleur ──────────────────────────────────────────────────────────

def _layer_color(mat):
    m = (mat or '').lower()
    if 'sable' in m:                        return '#F5EBB0'
    if '2/6' in m:                          return '#D5D5D5'
    if '0/31' in m or 'tout-venant' in m:  return '#AFAFAF'
    if 'gb' in m or 'bitume' in m:         return '#646464'
    if 'gc' in m or 'ciment' in m:         return '#B4B4B9'
    if 'enrobé' in m or 'enrobe' in m:     return '#323232'
    return '#DCDCDC'

def _pipe_color(reseau):
    # EU = brun/orange  (convention française eaux usées)
    # EP = bleu         (convention française eaux pluviales)
    # AEP = cyan        (convention française eau potable)
    if reseau == 'EU':  return '#C85A00'
    if reseau == 'AEP': return '#00BCD4'
    return '#1A6BBF'

def _luminance(hex_color):
    h = hex_color.lstrip('#')
    r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b

def _set_combo(combo, text):
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    else:
        combo.setCurrentText(text)


# ─── Dialog principal ─────────────────────────────────────────────────────────

class CoupeTrancheeComposeeDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('coupe_tranchee_composee'))
        self.setMinimumSize(1050, 680)
        self.resize(1300, 750)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._tranches = []
        self._current  = -1
        self._updating = False

        self._build_ui()
        self._load_settings()

        if not self._tranches:
            self._add_tranche()
        else:
            self._refresh_list()
            self._list.setCurrentRow(0)
            self._draw()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Horizontal)

        # ── Panneau gauche ───────────────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(270)
        left.setMaximumWidth(360)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(2, 2, 2, 2)
        ll.setSpacing(4)

        lbl = QLabel(i18n.tr('dt_tranches'))
        lbl.setFont(QFont("", -1, QFont.Bold))
        ll.addWidget(lbl)

        self._list = QListWidget()
        self._list.setMaximumHeight(160)
        self._list.currentRowChanged.connect(self._on_selection_changed)
        ll.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton(i18n.tr('dt_ajouter'))
        self._btn_del = QPushButton(i18n.tr('dt_supprimer'))
        self._btn_up  = QPushButton("↑")
        self._btn_dn  = QPushButton("↓")
        self._btn_up.setFixedWidth(28)
        self._btn_dn.setFixedWidth(28)
        self._btn_add.clicked.connect(self._add_tranche)
        self._btn_del.clicked.connect(self._remove_tranche)
        self._btn_up.clicked.connect(self._move_up)
        self._btn_dn.clicked.connect(self._move_down)
        for b in (self._btn_add, self._btn_del, self._btn_up, self._btn_dn):
            btn_row.addWidget(b)
        ll.addLayout(btn_row)

        # Formulaire scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._form_widget = QWidget()
        self._form_vbox   = QVBoxLayout(self._form_widget)
        self._form_vbox.setContentsMargins(2, 2, 2, 2)
        self._form_vbox.setSpacing(4)
        self._build_form()
        scroll.setWidget(self._form_widget)
        ll.addWidget(scroll, 1)

        # Boutons export / fermer
        exp_row = QHBoxLayout()
        self._btn_pdf   = QPushButton(i18n.tr('cb_export_pdf'))
        self._btn_png   = QPushButton(i18n.tr('ct_export_png').rstrip('…'))
        self._btn_close = QPushButton(i18n.tr('fermer'))
        self._btn_pdf.clicked.connect(lambda: self._export('pdf'))
        self._btn_png.clicked.connect(lambda: self._export('png'))
        self._btn_close.clicked.connect(self.close)
        for b in (self._btn_pdf, self._btn_png, self._btn_close):
            exp_row.addWidget(b)
        ll.addLayout(exp_row)

        splitter.addWidget(left)

        # ── Panneau droit : canvas matplotlib ───────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(2, 2, 2, 2)

        if HAS_MPL:
            self._fig    = Figure(facecolor='white')
            self._canvas = FigureCanvas(self._fig)
            self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            rl.addWidget(self._canvas)
        else:
            rl.addWidget(QLabel(i18n.tr('dt_matplotlib')))

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

    def _build_form(self):
        vb = self._form_vbox

        # ── Canalisation ─────────────────────────────────────────────────────
        grp1 = QGroupBox(i18n.tr('dt_canalisation'))
        f1   = QFormLayout(grp1)
        f1.setSpacing(4)

        rnet_row = QHBoxLayout()
        self._rb_eu  = QRadioButton("EU")
        self._rb_ep  = QRadioButton("EP")
        self._rb_aep = QRadioButton("AEP")
        self._rb_eu.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self._rb_eu)
        bg.addButton(self._rb_ep)
        bg.addButton(self._rb_aep)
        self._rb_eu.toggled.connect(self._on_field_changed)
        self._rb_aep.toggled.connect(self._on_field_changed)
        rnet_row.addWidget(self._rb_eu)
        rnet_row.addWidget(self._rb_ep)
        rnet_row.addWidget(self._rb_aep)
        rnet_row.addStretch()
        rw = QWidget(); rw.setLayout(rnet_row)
        f1.addRow(i18n.tr('dt_lbl_reseau'), rw)

        self._sp_dn = QDoubleSpinBox()
        self._sp_dn.setRange(60, 3000); self._sp_dn.setDecimals(0)
        self._sp_dn.setSuffix(" mm"); self._sp_dn.setSingleStep(50)
        self._sp_dn.valueChanged.connect(self._on_field_changed)
        f1.addRow(i18n.tr('dt_lbl_dn'), self._sp_dn)

        self._cb_mat = QComboBox(); self._cb_mat.setEditable(True)
        self._cb_mat.addItems(MATERIAUX_CONDUITE)
        self._cb_mat.currentTextChanged.connect(self._on_field_changed)
        f1.addRow(i18n.tr('dt_lbl_materiau'), self._cb_mat)

        self._sp_prof = QDoubleSpinBox()
        self._sp_prof.setRange(0.10, 10.0); self._sp_prof.setDecimals(2)
        self._sp_prof.setSuffix(" m"); self._sp_prof.setSingleStep(0.05)
        self._sp_prof.valueChanged.connect(self._on_field_changed)
        f1.addRow(i18n.tr('dt_lbl_prof_fe'), self._sp_prof)

        vb.addWidget(grp1)

        # ── Tranchée ─────────────────────────────────────────────────────────
        grp2 = QGroupBox(i18n.tr('dt_tranchee'))
        f2   = QFormLayout(grp2)
        f2.setSpacing(4)

        self._sp_esp_g = QDoubleSpinBox()
        self._sp_esp_g.setRange(0.0, 20.0); self._sp_esp_g.setDecimals(2)
        self._sp_esp_g.setSuffix(" m"); self._sp_esp_g.setSingleStep(0.10)
        self._sp_esp_g.valueChanged.connect(self._on_field_changed)
        f2.addRow(i18n.tr('dt_lbl_espace_gauche'), self._sp_esp_g)

        self._sp_ecg = QDoubleSpinBox()
        self._sp_ecg.setRange(0.05, 5.0); self._sp_ecg.setDecimals(2)
        self._sp_ecg.setSuffix(" m"); self._sp_ecg.setSingleStep(0.05)
        self._sp_ecg.valueChanged.connect(self._on_field_changed)
        f2.addRow(i18n.tr('dt_lbl_ecart_gauche'), self._sp_ecg)

        self._sp_ecd = QDoubleSpinBox()
        self._sp_ecd.setRange(0.05, 5.0); self._sp_ecd.setDecimals(2)
        self._sp_ecd.setSuffix(" m"); self._sp_ecd.setSingleStep(0.05)
        self._sp_ecd.valueChanged.connect(self._on_field_changed)
        f2.addRow(i18n.tr('dt_lbl_ecart_droit'), self._sp_ecd)

        vb.addWidget(grp2)

        # ── Remblai ───────────────────────────────────────────────────────────
        grp3 = QGroupBox(i18n.tr('dt_remblai'))
        f3   = QFormLayout(grp3)
        f3.setSpacing(4)

        self._sp_ep_lit = QDoubleSpinBox()
        self._sp_ep_lit.setRange(0.05, 0.50); self._sp_ep_lit.setDecimals(2)
        self._sp_ep_lit.setSuffix(" m"); self._sp_ep_lit.setSingleStep(0.05)
        self._sp_ep_lit.valueChanged.connect(self._on_field_changed)
        self._cb_mat_lit = QComboBox(); self._cb_mat_lit.setEditable(True)
        self._cb_mat_lit.addItems(MATERIAUX_REMBLAI)
        self._cb_mat_lit.currentTextChanged.connect(self._on_field_changed)
        row_lit = _hrow(self._sp_ep_lit, self._cb_mat_lit)
        f3.addRow(i18n.tr('dt_lbl_lit_pose'), row_lit)

        self._sp_ep_enr = QDoubleSpinBox()
        self._sp_ep_enr.setRange(0.05, 1.0); self._sp_ep_enr.setDecimals(2)
        self._sp_ep_enr.setSuffix(" m"); self._sp_ep_enr.setSingleStep(0.05)
        self._sp_ep_enr.valueChanged.connect(self._on_field_changed)
        self._cb_mat_enr = QComboBox(); self._cb_mat_enr.setEditable(True)
        self._cb_mat_enr.addItems(MATERIAUX_REMBLAI)
        self._cb_mat_enr.currentTextChanged.connect(self._on_field_changed)
        row_enr = _hrow(self._sp_ep_enr, self._cb_mat_enr)
        f3.addRow(i18n.tr('dt_lbl_enrobage'), row_enr)

        self._cb_mat_rem = QComboBox(); self._cb_mat_rem.setEditable(True)
        self._cb_mat_rem.addItems(MATERIAUX_REMBLAI)
        self._cb_mat_rem.currentTextChanged.connect(self._on_field_changed)
        f3.addRow(i18n.tr('dt_lbl_remblai'), self._cb_mat_rem)

        vb.addWidget(grp3)

        # ── Chaussée ──────────────────────────────────────────────────────────
        grp4 = QGroupBox(i18n.tr('dt_chaussee'))
        f4   = QFormLayout(grp4)
        f4.setSpacing(4)

        self._chk_inf = QCheckBox(i18n.tr('dt_chaussee_inf'))
        self._chk_inf.toggled.connect(self._on_field_changed)
        self._chk_inf.toggled.connect(self._update_ch_enabled)
        f4.addRow(self._chk_inf)

        self._sp_ep_ci = QDoubleSpinBox()
        self._sp_ep_ci.setRange(0.05, 1.0); self._sp_ep_ci.setDecimals(2)
        self._sp_ep_ci.setSuffix(" m"); self._sp_ep_ci.setSingleStep(0.05)
        self._sp_ep_ci.setEnabled(False)
        self._sp_ep_ci.valueChanged.connect(self._on_field_changed)
        self._cb_mat_ci = QComboBox(); self._cb_mat_ci.setEditable(True)
        self._cb_mat_ci.addItems(MATERIAUX_REMBLAI)
        self._cb_mat_ci.setEnabled(False)
        self._cb_mat_ci.currentTextChanged.connect(self._on_field_changed)
        f4.addRow(i18n.tr('dt_lbl_ep_mat'), _hrow(self._sp_ep_ci, self._cb_mat_ci))

        self._chk_sup = QCheckBox(i18n.tr('dt_chaussee_sup'))
        self._chk_sup.toggled.connect(self._on_field_changed)
        self._chk_sup.toggled.connect(self._update_ch_enabled)
        f4.addRow(self._chk_sup)

        self._sp_ep_cs = QDoubleSpinBox()
        self._sp_ep_cs.setRange(0.02, 0.30); self._sp_ep_cs.setDecimals(2)
        self._sp_ep_cs.setSuffix(" m"); self._sp_ep_cs.setSingleStep(0.01)
        self._sp_ep_cs.setEnabled(False)
        self._sp_ep_cs.valueChanged.connect(self._on_field_changed)
        self._cb_mat_cs = QComboBox(); self._cb_mat_cs.setEditable(True)
        self._cb_mat_cs.addItems(MATERIAUX_REMBLAI)
        self._cb_mat_cs.setEnabled(False)
        self._cb_mat_cs.currentTextChanged.connect(self._on_field_changed)
        f4.addRow(i18n.tr('dt_lbl_ep_mat'), _hrow(self._sp_ep_cs, self._cb_mat_cs))

        vb.addWidget(grp4)
        vb.addStretch()

    def _update_ch_enabled(self):
        self._sp_ep_ci.setEnabled(self._chk_inf.isChecked())
        self._cb_mat_ci.setEnabled(self._chk_inf.isChecked())
        self._sp_ep_cs.setEnabled(self._chk_sup.isChecked())
        self._cb_mat_cs.setEnabled(self._chk_sup.isChecked())

    # ── Gestion de la liste ───────────────────────────────────────────────────

    def _add_tranche(self):
        t = copy.deepcopy(DEFAULT_TRANCHE)
        # Les tranches suivantes sont collées (espace terrain = 0)
        if self._tranches:
            t['espace_gauche'] = 0.0
        # Pre-remplissage depuis la config de cubature. `t` part deja de
        # DEFAULT_TRANCHE : si la config manque ou est illisible, ces valeurs
        # restent en place et c'est le comportement voulu. On journalise
        # quand meme, sinon une cle renommee dans config_dialog ferait
        # silencieusement retomber toutes les tranches sur les defauts.
        try:
            from .config_dialog import get_cubature_config
            cfg = get_cubature_config()
            t['ep_lit_pose']     = cfg.get('ep_lit_pose', 0.10)
            t['ep_enrobage']     = cfg.get('ep_enrobage', 0.15)
            t['mat_lit_pose']    = cfg.get('materiau_lit_pose', 'Sable')
            t['mat_enrobage']    = cfg.get('materiau_enrobage', 'Sable')
            t['mat_remblai']     = cfg.get('materiau_remblai', '0/31.5')
            t['chaussee_inf']    = cfg.get('chaussee_inf', False)
            t['ep_chaussee_inf'] = cfg.get('ep_chaussee_inf', 0.20)
            t['mat_chaussee_inf']= cfg.get('materiau_chaussee_inf', 'GB (Grave bitume)')
            t['chaussee_sup']    = cfg.get('chaussee_sup', False)
            t['ep_chaussee_sup'] = cfg.get('ep_chaussee_sup', 0.08)
            t['mat_chaussee_sup']= cfg.get('materiau_chaussee_sup', 'Enrobé')
        except Exception as err:
            QgsMessageLog.logMessage(
                "Config de cubature illisible, tranche créée avec les valeurs "
                f"par défaut : {err}", "CanaPlan", Qgis.Warning)
        self._tranches.append(t)
        self._refresh_list()
        self._list.setCurrentRow(len(self._tranches) - 1)
        self._draw()

    def _remove_tranche(self):
        row = self._list.currentRow()
        if row < 0 or len(self._tranches) <= 1:
            return
        self._tranches.pop(row)
        self._refresh_list()
        self._list.setCurrentRow(min(row, len(self._tranches) - 1))
        self._draw()

    def _move_up(self):
        row = self._list.currentRow()
        if row <= 0:
            return
        self._tranches[row], self._tranches[row - 1] = (
            self._tranches[row - 1], self._tranches[row])
        self._refresh_list()
        self._list.setCurrentRow(row - 1)
        self._draw()

    def _move_down(self):
        row = self._list.currentRow()
        if row < 0 or row >= len(self._tranches) - 1:
            return
        self._tranches[row], self._tranches[row + 1] = (
            self._tranches[row + 1], self._tranches[row])
        self._refresh_list()
        self._list.setCurrentRow(row + 1)
        self._draw()

    def _refresh_list(self):
        self._list.blockSignals(True)
        cur = self._list.currentRow()
        self._list.clear()
        for i, t in enumerate(self._tranches):
            self._list.addItem(f"{i + 1} – {t['reseau']}  DN{int(t['dn'])}")
        self._list.blockSignals(False)
        if 0 <= cur < self._list.count():
            self._list.setCurrentRow(cur)

    def _on_selection_changed(self, row):
        if row < 0 or row >= len(self._tranches):
            self._current = -1
            return
        self._current = row
        self._populate_form(self._tranches[row])

    def _populate_form(self, t):
        self._updating = True
        try:
            self._rb_eu.setChecked(t.get('reseau', 'EU') == 'EU')
            self._rb_ep.setChecked(t.get('reseau', 'EU') == 'EP')
            self._rb_aep.setChecked(t.get('reseau', 'EU') == 'AEP')
            self._sp_dn.setValue(t.get('dn', 300))
            _set_combo(self._cb_mat, t.get('materiau', 'PVC'))
            self._sp_prof.setValue(t.get('profondeur', 1.80))
            self._sp_esp_g.setValue(t.get('espace_gauche', 0.50))
            self._sp_ecg.setValue(t.get('ecart_gauche', 0.40))
            self._sp_ecd.setValue(t.get('ecart_droit', 0.40))
            self._sp_ep_lit.setValue(t.get('ep_lit_pose', 0.10))
            _set_combo(self._cb_mat_lit, t.get('mat_lit_pose', 'Sable'))
            self._sp_ep_enr.setValue(t.get('ep_enrobage', 0.15))
            _set_combo(self._cb_mat_enr, t.get('mat_enrobage', 'Sable'))
            _set_combo(self._cb_mat_rem, t.get('mat_remblai', '0/31.5'))
            self._chk_inf.setChecked(t.get('chaussee_inf', False))
            self._sp_ep_ci.setValue(t.get('ep_chaussee_inf', 0.20))
            _set_combo(self._cb_mat_ci, t.get('mat_chaussee_inf', 'GB (Grave bitume)'))
            self._chk_sup.setChecked(t.get('chaussee_sup', False))
            self._sp_ep_cs.setValue(t.get('ep_chaussee_sup', 0.08))
            _set_combo(self._cb_mat_cs, t.get('mat_chaussee_sup', 'Enrobé'))
            self._update_ch_enabled()
        finally:
            self._updating = False

    def _on_field_changed(self, *_):
        if self._updating or self._current < 0:
            return
        t = self._tranches[self._current]
        if self._rb_eu.isChecked():
            t['reseau'] = 'EU'
        elif self._rb_aep.isChecked():
            t['reseau'] = 'AEP'
        else:
            t['reseau'] = 'EP'
        t['dn']              = self._sp_dn.value()
        t['materiau']        = self._cb_mat.currentText()
        t['profondeur']      = self._sp_prof.value()
        t['espace_gauche']   = self._sp_esp_g.value()
        t['ecart_gauche']    = self._sp_ecg.value()
        t['ecart_droit']     = self._sp_ecd.value()
        t['ep_lit_pose']     = self._sp_ep_lit.value()
        t['mat_lit_pose']    = self._cb_mat_lit.currentText()
        t['ep_enrobage']     = self._sp_ep_enr.value()
        t['mat_enrobage']    = self._cb_mat_enr.currentText()
        t['mat_remblai']     = self._cb_mat_rem.currentText()
        t['chaussee_inf']    = self._chk_inf.isChecked()
        t['ep_chaussee_inf'] = self._sp_ep_ci.value()
        t['mat_chaussee_inf']= self._cb_mat_ci.currentText()
        t['chaussee_sup']    = self._chk_sup.isChecked()
        t['ep_chaussee_sup'] = self._sp_ep_cs.value()
        t['mat_chaussee_sup']= self._cb_mat_cs.currentText()
        self._refresh_list()
        self._draw()

    # ── Dessin ────────────────────────────────────────────────────────────────

    def _draw(self):
        if not HAS_MPL or not self._tranches:
            return

        self._fig.clear()
        ax = self._fig.add_subplot(111)
        ax.set_aspect('equal')
        ax.axis('off')

        # ── Passe 1 : calcul géométrie de chaque tranche ─────────────────────
        tdata     = []
        x_cur     = 0.0
        max_above = 0.0
        max_below = 0.0

        for t in self._tranches:
            dn_m   = t.get('dn', 300) / 1000.0
            r      = dn_m / 2.0
            ecg    = t.get('ecart_gauche',  0.40)
            ecd    = t.get('ecart_droit',   0.40)
            esp    = t.get('espace_gauche', 0.0)
            h      = t.get('profondeur',    1.80)
            ep_lit = t.get('ep_lit_pose',   0.10)
            ep_enr = t.get('ep_enrobage',   0.15)
            ep_cs  = t.get('ep_chaussee_sup', 0.0) if t.get('chaussee_sup') else 0.0
            ep_ci  = t.get('ep_chaussee_inf', 0.0) if t.get('chaussee_inf') else 0.0

            x_cur  += esp
            xl      = x_cur
            xpl     = xl + ecg            # génératrice gauche du tuyau
            xpr     = xpl + dn_m          # génératrice droite
            xpc     = xpl + r             # centre du tuyau
            xr      = xpr + ecd
            w       = xr - xl
            x_cur   = xr

            y_fe      = -h                # fil d'eau (bas intérieur du tuyau)
            y_pc      = y_fe + r          # centre du tuyau
            y_lit_bot = y_fe - ep_lit     # fond de fouille
            y_enr_top = y_fe + dn_m + ep_enr  # haut de la zone d'enrobage
            y_rem_top = -(ep_cs + ep_ci)  # bas de la chaussée (ou TN si aucune)
            rem_h     = max(0.0, y_rem_top - y_enr_top)

            max_above = max(max_above, ep_cs + ep_ci)
            max_below = max(max_below, h + ep_lit)

            tdata.append(dict(
                t=t, xl=xl, xr=xr, xpl=xpl, xpr=xpr, xpc=xpc, w=w,
                dn_m=dn_m, r=r, ecg=ecg, ecd=ecd, esp=esp, h=h,
                ep_lit=ep_lit, ep_enr=ep_enr, ep_cs=ep_cs, ep_ci=ep_ci,
                y_fe=y_fe, y_pc=y_pc, y_lit_bot=y_lit_bot,
                y_enr_top=y_enr_top, y_rem_top=y_rem_top, rem_h=rem_h,
            ))

        total_w = x_cur

        # ── Passe 2 : dessin des couches et du tuyau ─────────────────────────
        margin_l = 0.55
        margin_r = 0.90   # plus large pour la colonne de cotes

        for d in tdata:
            t  = d['t']
            xl, xr, w = d['xl'], d['xr'], d['w']

            # Terrain entre tranches (bande claire)
            if d['esp'] > 1e-4:
                ax.add_patch(mpatches.Rectangle(
                    (xl - d['esp'], d['y_lit_bot']),
                    d['esp'], -d['y_lit_bot'],
                    facecolor='#EDEAD8', edgecolor='none', zorder=1))

            # Lit de pose
            _fill(ax, xl, d['y_lit_bot'], w, d['ep_lit'],
                  _layer_color(t['mat_lit_pose']),
                  t.get('mat_lit_pose', ''),
                  f"e={d['ep_lit']:.2f} m")

            # Enrobage (zone = DN + ep_enrobage au-dessus)
            _fill(ax, xl, d['y_fe'], w, d['dn_m'] + d['ep_enr'],
                  _layer_color(t['mat_enrobage']),
                  t.get('mat_enrobage', ''),
                  i18n.tr('dt_cote_enrobage',
                          valeur=f"{d['ep_enr']:.2f}"))

            # Remblai
            if d['rem_h'] > 1e-4:
                _fill(ax, xl, d['y_enr_top'], w, d['rem_h'],
                      _layer_color(t['mat_remblai']),
                      t.get('mat_remblai', ''),
                      f"e={d['rem_h']:.2f} m")

            # Chaussée inférieure
            if d['ep_ci'] > 1e-4:
                _fill(ax, xl, -(d['ep_cs'] + d['ep_ci']), w, d['ep_ci'],
                      _layer_color(t.get('mat_chaussee_inf', '')),
                      t.get('mat_chaussee_inf', ''),
                      f"e={d['ep_ci']:.2f} m")

            # Chaussée supérieure
            if d['ep_cs'] > 1e-4:
                _fill(ax, xl, -d['ep_cs'], w, d['ep_cs'],
                      _layer_color(t.get('mat_chaussee_sup', '')),
                      t.get('mat_chaussee_sup', ''),
                      f"e={d['ep_cs']:.2f} m")

            # Tuyau
            pc = _pipe_color(t['reseau'])
            ax.add_patch(mpatches.Circle(
                (d['xpc'], d['y_pc']), d['r'],
                facecolor='white', edgecolor=pc, linewidth=2.0, zorder=5))
            if d['r'] > 0.05:
                ax.text(d['xpc'], d['y_pc'],
                        f"{t['reseau']}\nDN{int(t['dn'])}",
                        ha='center', va='center', fontsize=7,
                        color=pc, fontweight='bold', zorder=6)
            elif d['r'] > 0.025:
                ax.text(d['xpc'], d['y_pc'], f"Φ{int(t['dn'])}",
                        ha='center', va='center', fontsize=5.5,
                        color=pc, fontweight='bold', zorder=6)

            # Parois tranchée (U)
            ax.plot([xl, xl, xr, xr],
                    [0.0, d['y_lit_bot'], d['y_lit_bot'], 0.0],
                    color='black', linewidth=1.5, zorder=7)

            # Cote enrobage : génératrice sup → limite haute zone enrobage
            y_gen_sup  = d['y_fe'] + d['dn_m']   # haut extérieur du tuyau
            y_enr_top  = d['y_enr_top']
            ep_enr     = d['ep_enr']
            if ep_enr > 0.02 and d['ecd'] > 0.12:
                x_ce = d['xpr'] + min(d['ecd'] * 0.35, 0.10)
                tick = 0.022
                for yy in (y_gen_sup, y_enr_top):
                    ax.plot([x_ce - tick, x_ce + tick], [yy, yy],
                            color='#555555', linewidth=0.7, zorder=8)
                ax.annotate('', xy=(x_ce, y_gen_sup), xytext=(x_ce, y_enr_top),
                            arrowprops=dict(arrowstyle='<->', color='#555555',
                                            lw=0.7, shrinkA=1, shrinkB=1))
                ax.text(x_ce + tick + 0.02, (y_gen_sup + y_enr_top) / 2,
                        f"{ep_enr:.2f} m",
                        ha='left', va='center', fontsize=6.0,
                        color='#333333', zorder=9)

        # ── TN ───────────────────────────────────────────────────────────────
        ax.plot([-margin_l, total_w + margin_l], [0.0, 0.0],
                color='#444444', linewidth=1.8, linestyle='--', zorder=8)
        ax.text(total_w + 0.08, 0.04, 'TN',
                va='bottom', ha='left', fontsize=9,
                color='#444444', fontweight='bold', zorder=9)

        # ── Colonne de cotes verticales (à droite du dernier tranche) ────────
        d_ref = tdata[-1]
        t_ref = d_ref['t']
        x_vc  = total_w + 0.22   # trait de cote vertical
        x_lbl = total_w + 0.30   # x de départ des labels

        # Segments (ybot, ytop, label_couche, ep)
        segs = []
        segs.append((d_ref['y_lit_bot'], d_ref['y_fe'],
                     i18n.tr('ct_couche_lit_pose'), d_ref['ep_lit']))
        segs.append((d_ref['y_fe'], d_ref['y_enr_top'],
                     i18n.tr('ct_couche_enrobage'), d_ref['ep_enr']))
        if d_ref['rem_h'] > 1e-4:
            segs.append((d_ref['y_enr_top'], d_ref['y_rem_top'],
                         i18n.tr('ct_couche_remblai'), d_ref['rem_h']))
        if d_ref['ep_ci'] > 1e-4:
            y_ci_bot = -(d_ref['ep_cs'] + d_ref['ep_ci'])
            segs.append((y_ci_bot, -d_ref['ep_cs'],
                         i18n.tr('ct_couche_chaussee_inf'), d_ref['ep_ci']))
        if d_ref['ep_cs'] > 1e-4:
            segs.append((-d_ref['ep_cs'], 0.0,
                         i18n.tr('ct_couche_chaussee_sup'), d_ref['ep_cs']))

        # Trait vertical + limites horizontales (witness)
        y_vc_bot = d_ref['y_lit_bot']
        y_vc_top = 0.0
        ax.plot([x_vc, x_vc], [y_vc_bot, y_vc_top],
                color='#AAAAAA', linewidth=0.7, zorder=6)

        # Witness lines horizontales depuis xr_last vers x_vc
        y_bounds = sorted({s[0] for s in segs} | {s[1] for s in segs})
        for yy in y_bounds:
            ax.plot([d_ref['xr'], x_vc], [yy, yy],
                    color='#CCCCCC', linewidth=0.4, linestyle=':', zorder=2)

        # Flèches + labels par segment
        tick = 0.025
        for (yb, yt, nom, ep) in segs:
            h_seg = abs(yt - yb)
            if h_seg < 1e-4:
                continue
            mid = (yb + yt) / 2
            # Ticks aux bornes
            for yy in (yb, yt):
                ax.plot([x_vc - tick, x_vc + tick], [yy, yy],
                        color='#888888', linewidth=0.7, zorder=7)
            # Double flèche verticale si assez haute
            if h_seg > 0.09:
                ax.annotate('', xy=(x_vc, yb), xytext=(x_vc, yt),
                            arrowprops=dict(arrowstyle='<->',
                                            color='#888888',
                                            lw=0.6,
                                            shrinkA=2, shrinkB=2))
            # Label : nom de la couche + épaisseur
            ax.text(x_lbl, mid,
                    f"{nom}\n{ep:.2f} m",
                    ha='left', va='center',
                    fontsize=6.0, color='#222222',
                    linespacing=1.3, zorder=8)

        # ── Passe 3 : annotations de cotes ───────────────────────────────────
        # 3 rangées sous les tranches, espacées de 0.22 m
        y1 = -(max_below + 0.18)   # rangée 1 : sous-cotes ecg | ΦDN | ecd
        y2 = -(max_below + 0.40)   # rangée 2 : largeur totale + espace terrain

        for i, d in enumerate(tdata):
            xl, xr = d['xl'], d['xr']
            xpl, xpr = d['xpl'], d['xpr']

            # ── Witness lines verticales (pointillés fins) ────────────────
            # Depuis le fond de fouille vers y1 (pour sous-cotes)
            for xw in (xl, xpl, xpr, xr):
                ax.plot([xw, xw], [d['y_lit_bot'], y1 + 0.03],
                        color='#BBBBBB', linewidth=0.5,
                        linestyle=':', zorder=2)

            # ── Rangée 1 : sous-cotes (texte AU-DESSUS des flèches) ───────
            _h_dim(ax, xl,  xpl, y1, f"{d['ecg']:.2f} m", text_above=True)
            # DN : label seulement si la flèche est assez large
            dn_lbl = f"Φ{int(d['t']['dn'])}" if d['dn_m'] >= 0.14 else ''
            _h_dim(ax, xpl, xpr, y1, dn_lbl,
                   color='#555555', text_above=True)
            _h_dim(ax, xpr, xr,  y1, f"{d['ecd']:.2f} m", text_above=True)

            # ── Rangée 2 : largeur totale (texte EN-DESSOUS) ──────────────
            # Witness lines depuis y1 vers y2 pour les bords xl et xr
            for xw in (xl, xr):
                ax.plot([xw, xw], [y1 - 0.03, y2 + 0.03],
                        color='#BBBBBB', linewidth=0.5,
                        linestyle=':', zorder=2)
            _h_dim(ax, xl, xr, y2, f"L = {d['w']:.2f} m")

            # Espace terrain entre cette tranche et la précédente
            if d['esp'] > 0.05 and i > 0:
                x_prev_r = tdata[i - 1]['xr']
                for xw in (x_prev_r, xl):
                    ax.plot([xw, xw], [y1 - 0.03, y2 + 0.03],
                            color='#CCCCCC', linewidth=0.4,
                            linestyle=':', zorder=2)
                _h_dim(ax, x_prev_r, xl, y2,
                       f"{d['esp']:.2f} m", color='#888888')


        # ── Limites axes ──────────────────────────────────────────────────────
        ax.set_xlim(-margin_l, total_w + margin_r)
        ax.set_ylim(-(max_below + 0.80), max_above + 0.25)

        self._fig.tight_layout(pad=0.4)
        self._canvas.draw()

    # ── Export ────────────────────────────────────────────────────────────────

    def _export(self, fmt):
        ext = fmt.lower()
        path, _ = QFileDialog.getSaveFileName(
            self, i18n.tr('dt_exporter_en', format=fmt.upper()), "",
            f"{fmt.upper()} (*.{ext})"
        )
        if not path:
            return
        if not path.lower().endswith(f'.{ext}'):
            path += f'.{ext}'
        try:
            self._fig.savefig(path, dpi=200, bbox_inches='tight',
                              facecolor='white')
        except Exception as e:
            QMessageBox.warning(self, i18n.tr('dt_erreur_export'), str(e))

    # ── Persistance ───────────────────────────────────────────────────────────

    def _load_settings(self):
        s = QgsSettings()
        raw = s.value(SETTINGS_KEY, None)
        if raw:
            try:
                self._tranches = json.loads(raw)
            except Exception:
                self._tranches = []

    def _save_settings(self):
        QgsSettings().setValue(SETTINGS_KEY, json.dumps(self._tranches))

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)


# ─── Fonctions de dessin ──────────────────────────────────────────────────────

def _hrow(*widgets):
    """Retourne un QWidget contenant les widgets côte à côte."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    for ww in widgets:
        h.addWidget(ww)
    return w


def _fill(ax, x, y_bottom, width, height, color, mat='', ep=''):
    """Rectangle rempli : label matériau + cote épaisseur centrés."""
    rect = mpatches.Rectangle(
        (x, y_bottom), width, height,
        facecolor=color, edgecolor='#666666', linewidth=0.5, zorder=3)
    ax.add_patch(rect)
    if height < 0.04 or width < 0.12:
        return
    lum = _luminance(color)
    tc  = 'black' if lum > 0.40 else 'white'
    fs  = 6.5 if height > 0.20 else 5.5
    lines = [l for l in (mat, ep) if l]
    if not lines:
        return
    ax.text(x + width / 2, y_bottom + height / 2,
            '\n'.join(lines),
            ha='center', va='center', fontsize=fs,
            color=tc, zorder=4, clip_on=True, linespacing=1.2)


def _h_dim(ax, x1, x2, y, label, color='#333333', text_above=False):
    """Flèche de cote horizontale ↔ avec label au-dessus ou en-dessous."""
    if abs(x2 - x1) < 1e-6:
        return
    ax.annotate('', xy=(x2, y), xytext=(x1, y),
                arrowprops=dict(arrowstyle='<->', color=color,
                                lw=0.7, shrinkA=0, shrinkB=0))
    if label:
        dy = 0.055 if text_above else -0.055
        va = 'bottom' if text_above else 'top'
        ax.text((x1 + x2) / 2, y + dy, label,
                ha='center', va=va, fontsize=6.5, color=color)
