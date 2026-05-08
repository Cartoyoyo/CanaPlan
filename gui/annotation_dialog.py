# gui/annotation_dialog.py

from qgis.core import QgsUnitTypes
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QFontComboBox, QDoubleSpinBox, QPushButton, QDialogButtonBox,
    QColorDialog, QToolButton, QButtonGroup, QFrame,
)
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtCore import Qt

_UNIT_PT  = QgsUnitTypes.RenderPoints
_UNIT_MAP = QgsUnitTypes.RenderMapUnits


class AnnotationDialog(QDialog):
    """Dialogue de création / édition d'une annotation texte."""

    def __init__(self, parent=None, text='', font_name='Arial',
                 size=2.0, size_unit=_UNIT_MAP, color=None,
                 bold=False, italic=False, underline=False,
                 alignment=Qt.AlignLeft):
        super().__init__(parent)
        self.setWindowTitle("Annotation")
        self.setMinimumWidth(400)
        self._color = QColor(color) if color else QColor(0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # ── Barre de mise en forme ──────────────────────────────────────
        toolbar = QHBoxLayout()
        toolbar.setSpacing(3)

        self.btn_bold = self._fmt_btn(
            "B", "Gras", bold, "font-weight:bold; font-size:13px;")
        self.btn_italic = self._fmt_btn(
            "I", "Italique", italic, "font-style:italic; font-size:13px;")
        self.btn_underline = self._fmt_btn(
            "S", "Souligné", underline, "text-decoration:underline; font-size:13px;")

        toolbar.addWidget(self.btn_bold)
        toolbar.addWidget(self.btn_italic)
        toolbar.addWidget(self.btn_underline)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setFixedWidth(10)
        toolbar.addWidget(sep)

        self._align_group = QButtonGroup(self)
        self._align_group.setExclusive(True)

        _align_id = {
            Qt.AlignLeft:    0,
            Qt.AlignHCenter: 1,
            Qt.AlignCenter:  1,
            Qt.AlignRight:   2,
        }.get(int(alignment), 0)

        self.btn_al = self._fmt_btn("G", "Aligner à gauche", _align_id == 0)
        self.btn_ac = self._fmt_btn("C", "Centrer",          _align_id == 1)
        self.btn_ar = self._fmt_btn("D", "Aligner à droite", _align_id == 2)

        self._align_group.addButton(self.btn_al, 0)
        self._align_group.addButton(self.btn_ac, 1)
        self._align_group.addButton(self.btn_ar, 2)

        toolbar.addWidget(self.btn_al)
        toolbar.addWidget(self.btn_ac)
        toolbar.addWidget(self.btn_ar)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── Zone de texte ───────────────────────────────────────────────
        layout.addWidget(QLabel("Texte :"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(90)
        layout.addWidget(self.text_edit)

        # ── Police ──────────────────────────────────────────────────────
        row_font = QHBoxLayout()
        row_font.addWidget(QLabel("Police :"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(font_name))
        row_font.addWidget(self.font_combo, 1)
        layout.addLayout(row_font)

        # ── Taille (m, suit le zoom) ────────────────────────────────────
        row_size = QHBoxLayout()
        row_size.addWidget(QLabel("Taille (m) :"))
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.1, 500.0)
        self.size_spin.setSingleStep(0.5)
        self.size_spin.setDecimals(2)
        init_size = size if 0.1 <= size <= 500 else 2.0
        self.size_spin.setValue(init_size)
        row_size.addWidget(self.size_spin)
        row_size.addStretch()
        layout.addLayout(row_size)

        # ── Couleur ─────────────────────────────────────────────────────
        row_color = QHBoxLayout()
        row_color.addWidget(QLabel("Couleur :"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedWidth(110)
        self._refresh_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        row_color.addWidget(self.color_btn)
        row_color.addStretch()
        layout.addLayout(row_color)

        # ── OK / Annuler ────────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Couleur ────────────────────────────────────────────────────────

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Couleur du texte")
        if c.isValid():
            self._color = c
            self._refresh_color_btn()

    def _refresh_color_btn(self):
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        fg = '#000000' if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else '#ffffff'
        self.color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {fg};")
        self.color_btn.setText(self._color.name().upper())

    # ── Boutons formatage ──────────────────────────────────────────────

    @staticmethod
    def _fmt_btn(label, tooltip, checked=False, extra_style=""):
        btn = QToolButton()
        btn.setText(label)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setFixedSize(28, 28)
        btn.setStyleSheet(
            f"QToolButton {{ {extra_style} }}"
            f"QToolButton:checked {{ {extra_style} background:#b8d4f0;"
            f" border:1px solid #5a8fc0; border-radius:3px; }}"
        )
        return btn

    # ── Résultat ───────────────────────────────────────────────────────

    def get_values(self):
        _align_map = {0: Qt.AlignLeft, 1: Qt.AlignHCenter, 2: Qt.AlignRight}
        return {
            'text':      self.text_edit.toPlainText().strip(),
            'font':      self.font_combo.currentFont().family(),
            'size':      self.size_spin.value(),
            'size_unit': _UNIT_MAP,
            'color':     QColor(self._color),
            'bold':      self.btn_bold.isChecked(),
            'italic':    self.btn_italic.isChecked(),
            'underline': self.btn_underline.isChecked(),
            'alignment': _align_map.get(self._align_group.checkedId(), Qt.AlignLeft),
        }
