# gui/etiquette_taille_dialog.py

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QRadioButton,
    QSpinBox, QComboBox, QLabel, QDialogButtonBox, QFormLayout, QWidget,
)
from qgis.PyQt.QtCore import Qt
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
    ("Personnalisée : 1 / …", None),
]


class EtiquetteTailleDialog(QDialog):

    def __init__(self, init_mode='map_units', init_value=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Taille des étiquettes")
        self.setMinimumWidth(340)
        self._init_mode  = init_mode
        self._init_value = init_value
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Choisissez le mode de dimensionnement des étiquettes")
        font = QFont()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # ── Mode 1 : taille de police fixe ───────────────────────────────
        grp_pt = QGroupBox("Taille de police fixe (points)")
        grp_pt.setCheckable(False)
        form_pt = QFormLayout(grp_pt)

        self.radio_pt = QRadioButton("Taille en points")
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
            "<i>Taille constante à l'écran, indépendante du zoom.</i>")
        note_pt.setWordWrap(True)
        form_pt.addRow(note_pt)
        layout.addWidget(grp_pt)

        # ── Mode 2 : adapté à l'échelle ───────────────────────────────────
        grp_sc = QGroupBox("Adapté à l'échelle d'impression")
        form_sc = QFormLayout(grp_sc)

        self.radio_sc = QRadioButton("Échelle cible")
        self.combo_sc = QComboBox()
        for label, _ in _SCALES:
            self.combo_sc.addItem(label)
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
            "<i>Taille proportionnelle au zoom — "
            "optimisée pour l'impression à l'échelle choisie.</i>")
        note_sc.setWordWrap(True)
        form_sc.addRow(note_sc)
        layout.addWidget(grp_sc)

        # ── Boutons ───────────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        # Connexions
        self.radio_pt.toggled.connect(self._on_mode_changed)
        self.combo_sc.currentIndexChanged.connect(self._on_scale_combo_changed)
        self._custom_spin.valueChanged.connect(self._update_map_units_label)

        # État initial : restaure le dernier choix utilisateur
        if self._init_mode == 'points':
            self.radio_pt.setChecked(True)
        else:
            self.radio_sc.setChecked(True)
            if self._init_value is not None:
                self._restore_scale_combo(self._init_value)
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
            f"→ {mu:.2f} m en unités carte  "
            f"({_TARGET_MM} mm sur papier)")

    def _current_map_units(self):
        _, scale = _SCALES[self.combo_sc.currentIndex()]
        if scale is None:
            scale = self._custom_spin.value()
        return _TARGET_MM * scale / 1000.0

    # ------------------------------------------------------------------ résultat

    def get_result(self):
        """Retourne (mode, value) :
        - mode='points'     → value = taille en points (int)
        - mode='map_units'  → value = taille en mètres (float)
        """
        if self.radio_pt.isChecked():
            return ('points', self.spin_pt.value())
        return ('map_units', self._current_map_units())
