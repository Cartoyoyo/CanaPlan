# -*- coding: utf-8 -*-
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QComboBox, QDialogButtonBox, QSpinBox, QLabel, QHBoxLayout, QWidget,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject

FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# None = entrée personnalisée
SCALES = [150, 200, 250, 500, 1000, 2000, 5000, 10000, None]

_CUSTOM_LABEL = "Personnalisée : 1 / …"

# (label affiché, dpi ou None, note)
_DPI_PRESETS = [
    ("Légère  –  96 dpi",          96,  "Fichier très léger, qualité réduite"),
    ("Standard  –  150 dpi",      150,  "Bon compromis taille / qualité (recommandé A1/A0)"),
    ("Bonne qualité  –  200 dpi",  200,  "Qualité correcte, fichier modéré"),
    ("Haute qualité  –  300 dpi",  300,  "Fichier lourd – à éviter en A1/A0"),
    ("Personnalisée…",            None,  "Saisissez la résolution souhaitée"),
]
_DPI_DEFAULT_IDX = 1   # 150 dpi par défaut


class PrintDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Paramètres d'impression")
        self.setMinimumWidth(360)

        default_title = QgsProject.instance().title() or "Plan de réseau"

        self.titre_edit = QLineEdit(default_title)

        self.format_combo = QComboBox()
        self.format_combo.addItems(list(FORMATS.keys()))
        self.format_combo.setCurrentText("A3")

        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["Paysage", "Portrait"])

        self.scale_combo = QComboBox()
        for s in SCALES:
            if s is None:
                self.scale_combo.addItem(_CUSTOM_LABEL, None)
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
        for label, dpi, note in _DPI_PRESETS:
            self.dpi_combo.addItem(label, dpi)
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
        form.addRow("Titre du plan :", self.titre_edit)
        form.addRow("Format :", self.format_combo)
        form.addRow("Orientation :", self.orient_combo)
        form.addRow("Échelle :", self.scale_combo)
        form.addRow("", self._custom_widget)
        form.addRow("Résolution PDF :", self.dpi_combo)
        form.addRow("", self._dpi_custom_widget)
        form.addRow("", self._dpi_note)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.Ok).setText("Placer les feuilles →")

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
            self._dpi_note.setText(_DPI_PRESETS[idx][2])
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
        if self.orient_combo.currentText() == "Portrait":
            w_mm, h_mm = h_mm, w_mm

        scale = self.scale_combo.currentData()
        if scale is None:
            scale = self._custom_spin.value()

        dpi = self.dpi_combo.currentData()
        if dpi is None:
            dpi = self._dpi_custom_spin.value()

        return {
            "titre":       self.titre_edit.text().strip() or "Plan de réseau",
            "format":      fmt,
            "orientation": self.orient_combo.currentText(),
            "w_mm":        float(w_mm),
            "h_mm":        float(h_mm),
            "echelle":     scale,
            "dpi":         dpi,
        }
