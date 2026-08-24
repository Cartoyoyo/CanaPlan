# gui/etiquette_taille_dialog.py

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QSpinBox, QComboBox, QLabel, QDialogButtonBox, QFormLayout, QWidget,
    QCheckBox,
)
from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from qgis.PyQt.QtGui import QFont

# Taille cible sur papier : 2.5 mm — convertit en unités carte (mètres L93)
_TARGET_MM = 2.5
# None = entrée personnalisée
_SCALES = [
    ("1 / 150",   150),
    ("1 / 200",   200),
    ("1 / 250",   250),
    ("1 / 500",   500),
    ("1 / 1 000", 1000),
    ("1 / 2 000", 2000),
    (None, None),   # entrée personnalisée : libellé traduit à l'affichage
]


class EtiquetteTailleDialog(QDialog):

    def __init__(self, init_mode='map_units', init_value=None,
                 init_min_scale=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('taille_etiquettes'))
        self.setMinimumWidth(360)
        self._init_mode      = init_mode
        self._init_value     = init_value
        self._init_min_scale = init_min_scale
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel(i18n.tr('et_choix_mode'))
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # ── Mode 1 : taille de police fixe ───────────────────────────────
        grp_pt = QGroupBox(i18n.tr('et_police_fixe'))
        grp_pt.setCheckable(False)
        form_pt = QFormLayout(grp_pt)

        self.radio_pt = QRadioButton(i18n.tr('et_taille_points'))
        self.spin_pt  = QSpinBox()
        self.spin_pt.setRange(4, 30)
        init_pt = int(self._init_value) if self._init_mode == 'points' and self._init_value else 9
        self.spin_pt.setValue(init_pt)
        self.spin_pt.setSuffix(" pt")

        row_pt = QHBoxLayout()
        row_pt.addWidget(self.radio_pt)
        row_pt.addStretch()
        row_pt.addWidget(self.spin_pt)
        form_pt.addRow(row_pt)

        note_pt = QLabel(
            i18n.tr('et_aide_fixe'))
        note_pt.setWordWrap(True)
        form_pt.addRow(note_pt)
        layout.addWidget(grp_pt)

        # ── Mode 2 : adapté à l'échelle ───────────────────────────────────
        grp_sc = QGroupBox(i18n.tr('et_adapte_echelle'))
        form_sc = QFormLayout(grp_sc)

        self.radio_sc = QRadioButton(i18n.tr('et_echelle_cible'))
        self.combo_sc = QComboBox()
        for label, _ in _SCALES:
            self.combo_sc.addItem(label or i18n.tr('pd_echelle_perso'))
        self.combo_sc.setCurrentIndex(4)   # 1/1000 par défaut (surchargé ci-dessous si init)

        row_sc = QHBoxLayout()
        row_sc.addWidget(self.radio_sc)
        row_sc.addStretch()
        row_sc.addWidget(self.combo_sc)
        form_sc.addRow(row_sc)

        # Champ de saisie échelle personnalisée (masqué par défaut)
        self._custom_widget = QWidget()
        custom_row = QHBoxLayout(self._custom_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.addWidget(QLabel("1 /"))
        self._custom_spin = QSpinBox()
        self._custom_spin.setRange(1, 1000000)
        self._custom_spin.setValue(300)
        self._custom_spin.setSingleStep(50)
        self._custom_spin.setGroupSeparatorShown(True)
        custom_row.addWidget(self._custom_spin)
        self._custom_widget.setVisible(False)
        form_sc.addRow("", self._custom_widget)

        self.lbl_mu = QLabel()
        self.lbl_mu.setAlignment(Qt.AlignRight)
        form_sc.addRow(self.lbl_mu)

        note_sc = QLabel(
            i18n.tr('et_aide_echelle'))
        note_sc.setWordWrap(True)
        form_sc.addRow(note_sc)
        layout.addWidget(grp_sc)

        # ── Seuil de dézoom ───────────────────────────────────────────────
        grp_min = QGroupBox(i18n.tr('et_seuil'))
        form_min = QFormLayout(grp_min)

        self.chk_min = QCheckBox(i18n.tr('et_masquer_au_dela'))
        self.spin_min = QSpinBox()
        self.spin_min.setRange(100, 1000000)
        self.spin_min.setSingleStep(500)
        self.spin_min.setPrefix("1 / ")
        self.spin_min.setGroupSeparatorShown(True)

        row_min = QHBoxLayout()
        row_min.addWidget(self.chk_min)
        row_min.addStretch()
        row_min.addWidget(self.spin_min)
        form_min.addRow(row_min)

        note_min = QLabel(
            i18n.tr('et_aide_seuil'))
        note_min.setWordWrap(True)
        form_min.addRow(note_min)
        layout.addWidget(grp_min)

        # ── Boutons ───────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Connexions
        self.radio_pt.toggled.connect(self._on_mode_changed)
        self.combo_sc.currentIndexChanged.connect(self._on_scale_combo_changed)
        self._custom_spin.valueChanged.connect(self._update_map_units_label)
        self.chk_min.toggled.connect(self.spin_min.setEnabled)

        # État initial : restaure le dernier choix utilisateur
        if self._init_mode == 'points':
            self.radio_pt.setChecked(True)
        else:
            self.radio_sc.setChecked(True)
            if self._init_value is not None:
                self._restore_scale_combo(self._init_value)

        # 0 ou None = aucun seuil actif ; on garde une valeur plausible dans
        # le spin pour que cocher la case n'impose pas de la ressaisir.
        active = bool(self._init_min_scale)
        self.chk_min.setChecked(active)
        self.spin_min.setValue(int(self._init_min_scale) if active else 2000)
        self.spin_min.setEnabled(active)

        self._on_mode_changed()
        self._update_map_units_label()

    # ------------------------------------------------------------------ helpers

    def _restore_scale_combo(self, value_m):
        """Sélectionne dans la combo l'entrée correspondant à value_m (mètres)."""
        if _TARGET_MM <= 0:
            return
        scale = value_m * 1000.0 / _TARGET_MM
        for i, (_, s) in enumerate(_SCALES[:-1]):   # ignore 'Personnalisée'
            if s is not None and abs(s - scale) < 0.5:
                self.combo_sc.setCurrentIndex(i)
                return
        # Valeur personnalisée
        self.combo_sc.setCurrentIndex(len(_SCALES) - 1)
        self._custom_spin.setValue(int(round(scale)))

    # ------------------------------------------------------------------ slots

    def _on_mode_changed(self):
        pt_mode = self.radio_pt.isChecked()
        self.spin_pt.setEnabled(pt_mode)
        self.combo_sc.setEnabled(not pt_mode)
        if not pt_mode:
            self._on_scale_combo_changed()
        else:
            self._custom_widget.setVisible(False)

    def _on_scale_combo_changed(self):
        is_custom = _SCALES[self.combo_sc.currentIndex()][1] is None
        self._custom_widget.setVisible(is_custom)
        self._update_map_units_label()

    def _update_map_units_label(self):
        mu = self._current_map_units()
        self.lbl_mu.setText(
            i18n.tr('et_apercu', taille=i18n.nombre(mu),
                    mm=_TARGET_MM))

    def _current_map_units(self):
        _, scale = _SCALES[self.combo_sc.currentIndex()]
        if scale is None:
            scale = self._custom_spin.value()
        return _TARGET_MM * scale / 1000.0

    # ------------------------------------------------------------------ résultat

    def get_result(self):
        """Retourne (mode, value, min_scale) :
        - mode='points'     → value = taille en points (int)
        - mode='map_units'  → value = taille en mètres (float)
        - min_scale         → dénominateur du seuil de dézoom, 0 si désactivé
        """
        min_scale = self.spin_min.value() if self.chk_min.isChecked() else 0
        if self.radio_pt.isChecked():
            return ('points', self.spin_pt.value(), min_scale)
        return ('map_units', self._current_map_units(), min_scale)
