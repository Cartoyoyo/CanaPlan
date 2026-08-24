# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QSpinBox, QLabel, QHBoxLayout, QWidget,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject

from ..tools import i18n

FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# None = entrée personnalisée
SCALES = [150, 200, 250, 500, 1000, 2000, 5000, 10000, None]

# (clé du libellé, dpi ou None, clé de la note) — traduits à l'affichage
_DPI_PRESETS = [
    ('pd_dpi_legere',   96,   'pd_dpi_legere_note'),
    ('pd_dpi_standard', 150,  'pd_dpi_standard_note'),
    ('pd_dpi_bonne',    200,  'pd_dpi_bonne_note'),
    ('pd_dpi_haute',    300,  'pd_dpi_haute_note'),
    ('pd_dpi_perso',    None, 'pd_dpi_perso_note'),
]
_DPI_DEFAULT_IDX = 1   # 150 dpi par défaut


class PrintDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('pd_titre'))
        self.setMinimumWidth(360)

        default_title = QgsProject.instance().title() or i18n.tr('pd_plan_reseau')

        self.titre_edit = QLineEdit(default_title)

        self.format_combo = QComboBox()
        self.format_combo.addItems(list(FORMATS.keys()))
        self.format_combo.setCurrentText("A3")

        self.orient_combo = QComboBox()
        # La valeur portée est le code ('paysage'/'portrait') : le texte
        # affiché suit la langue, le reste du code ne dépend pas de lui.
        self.orient_combo.addItem(i18n.tr('pd_paysage'), 'paysage')
        self.orient_combo.addItem(i18n.tr('pd_portrait'), 'portrait')

        self.scale_combo = QComboBox()
        for s in SCALES:
            if s is None:
                self.scale_combo.addItem(i18n.tr('pd_echelle_perso'), None)
            else:
                self.scale_combo.addItem(f"1 : {s:,}".replace(",", " "), s)
        self.scale_combo.setCurrentIndex(SCALES.index(1000))

        # Champ de saisie d'échelle personnalisée (masqué par défaut)
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

        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)

        # ── Résolution PDF ────────────────────────────────────────────────
        self.dpi_combo = QComboBox()
        for cle_label, dpi, _cle_note in _DPI_PRESETS:
            self.dpi_combo.addItem(i18n.tr(cle_label), dpi)
        self.dpi_combo.setCurrentIndex(_DPI_DEFAULT_IDX)

        # Champ DPI personnalisé (masqué par défaut)
        self._dpi_custom_widget = QWidget()
        dpi_custom_row = QHBoxLayout(self._dpi_custom_widget)
        dpi_custom_row.setContentsMargins(0, 0, 0, 0)
        self._dpi_custom_spin = QSpinBox()
        self._dpi_custom_spin.setRange(50, 300)
        self._dpi_custom_spin.setValue(150)
        self._dpi_custom_spin.setSingleStep(25)
        self._dpi_custom_spin.setSuffix(" dpi")
        dpi_custom_row.addWidget(self._dpi_custom_spin)
        dpi_custom_row.addStretch()
        self._dpi_custom_widget.setVisible(False)

        self._dpi_note = QLabel()
        self._dpi_note.setStyleSheet("color: #555; font-style: italic;")
        self._dpi_note.setWordWrap(True)
        self.dpi_combo.currentIndexChanged.connect(self._on_dpi_changed)
        self._on_dpi_changed()   # initialise la note

        # Met à jour la note DPI conseillée quand le format change
        self.format_combo.currentIndexChanged.connect(self._suggest_dpi)

        form = QFormLayout()
        form.addRow(i18n.tr('pd_titre_plan'), self.titre_edit)
        form.addRow(i18n.tr('pd_format'), self.format_combo)
        form.addRow(i18n.tr('pd_orientation'), self.orient_combo)
        form.addRow(i18n.tr('pd_echelle'), self.scale_combo)
        form.addRow("", self._custom_widget)
        form.addRow(i18n.tr('pd_resolution'), self.dpi_combo)
        form.addRow("", self._dpi_custom_widget)
        form.addRow("", self._dpi_note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Ok).setText(i18n.tr('pd_placer'))

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    # ------------------------------------------------------------------ slots

    def _on_scale_changed(self, index):
        is_custom = self.scale_combo.currentData() is None
        self._custom_widget.setVisible(is_custom)
        self.adjustSize()

    def _on_dpi_changed(self):
        idx = self.dpi_combo.currentIndex()
        if 0 <= idx < len(_DPI_PRESETS):
            self._dpi_note.setText(i18n.tr(_DPI_PRESETS[idx][2]))
        is_custom = self.dpi_combo.currentData() is None
        self._dpi_custom_widget.setVisible(is_custom)
        self.adjustSize()

    def _suggest_dpi(self):
        """Suggère automatiquement 150 dpi pour A1/A0, 200 pour A2/A3, 300 pour A4.
        N'écrase pas une saisie personnalisée déjà active."""
        if self.dpi_combo.currentData() is None:
            return   # l'utilisateur a choisi Personnalisée, on ne touche pas
        fmt = self.format_combo.currentText()
        suggested = {
            "A0": 1,   # index 1 = 150 dpi
            "A1": 1,
            "A2": 2,   # index 2 = 200 dpi
            "A3": 2,
            "A4": 3,   # index 3 = 300 dpi
        }.get(fmt, 1)
        self.dpi_combo.blockSignals(True)
        self.dpi_combo.setCurrentIndex(suggested)
        self.dpi_combo.blockSignals(False)
        self._on_dpi_changed()

    # ------------------------------------------------------------------ résultat

    def get_settings(self):
        fmt = self.format_combo.currentText()
        w_mm, h_mm = FORMATS[fmt]
        if self.orient_combo.currentData() == 'portrait':
            w_mm, h_mm = h_mm, w_mm

        scale = self.scale_combo.currentData()
        if scale is None:
            scale = self._custom_spin.value()

        dpi = self.dpi_combo.currentData()
        if dpi is None:
            dpi = self._dpi_custom_spin.value()

        return {
            "titre":       (self.titre_edit.text().strip()
                            or i18n.tr('pd_plan_reseau')),
            "format":      fmt,
            "orientation": self.orient_combo.currentData(),
            "w_mm":        float(w_mm),
            "h_mm":        float(h_mm),
            "echelle":     scale,
            "dpi":         dpi,
        }
