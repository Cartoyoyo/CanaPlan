# gui/annotation_dialog.py

from qgis.core import QgsUnitTypes
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QFontComboBox, QDoubleSpinBox, QSpinBox, QComboBox, QPushButton,
    QDialogButtonBox, QColorDialog, QToolButton, QButtonGroup, QFrame,
    QCheckBox, QGroupBox, QGraphicsOpacityEffect,
)
from qgis.PyQt.QtGui import QColor, QFont, QTextCursor, QTextCharFormat
from qgis.PyQt.QtCore import Qt, pyqtSignal

from .etiquette_taille_dialog import _TARGET_MM, _SCALES

_UNIT_PT  = QgsUnitTypes.RenderPoints
_UNIT_MAP = QgsUnitTypes.RenderMapUnits


class AnnotationDialog(QDialog):
    """Dialogue de création / édition d'une annotation texte."""

    #: émis avec get_values() quand l'utilisateur clique sur « Appliquer »,
    #: pour prévisualiser/valider les changements sur la carte sans fermer.
    applied = pyqtSignal(dict)

    def __init__(self, parent=None, text='', font_name='Arial',
                 size=2.0, size_unit=_UNIT_MAP, color=None,
                 bold=False, italic=False, underline=False,
                 alignment=Qt.AlignLeft,
                 frame=False, frame_filled=True,
                 frame_fill_color=None, frame_border_color=None,
                 opacity=1.0):
        super().__init__(parent)
        self.setWindowTitle("Annotation")
        self.setMinimumWidth(560)
        self._color = QColor(color) if color else QColor(0, 0, 0)
        self._frame_fill_color = QColor(frame_fill_color) if frame_fill_color else QColor(255, 255, 255)
        self._frame_border_color = QColor(frame_border_color) if frame_border_color else QColor(0, 0, 0)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Mise en forme (gras/italique/souligné + alignement) ─────────
        grp_toolbar = QGroupBox("Mise en forme")
        toolbar = QHBoxLayout(grp_toolbar)
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
        layout.addWidget(grp_toolbar)

        # ── Zone de texte (sert aussi d'aperçu de la mise en forme) ─────
        layout.addWidget(QLabel("Texte :"))
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setMinimumHeight(90)
        self.text_edit.setPlaceholderText("Tapez votre texte…")
        layout.addWidget(self.text_edit)

        # ── Deux colonnes : Police/Taille  |  Couleur/Transparence/Cadre ──
        cols = QHBoxLayout()
        cols.setSpacing(10)

        # -- Colonne gauche : Police et taille
        grp_font = QGroupBox("Police et taille")
        v_font = QVBoxLayout(grp_font)

        row_font = QHBoxLayout()
        row_font.addWidget(QLabel("Police :"))
        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont(font_name))
        row_font.addWidget(self.font_combo, 1)
        v_font.addLayout(row_font)

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
        v_font.addLayout(row_size)

        row_scale = QHBoxLayout()
        row_scale.addWidget(QLabel("Échelle :"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Taille libre")
        for label, _scale in _SCALES:
            self.scale_combo.addItem(label)
        row_scale.addWidget(self.scale_combo, 1)
        v_font.addLayout(row_scale)

        self.custom_scale_spin = QSpinBox()
        self.custom_scale_spin.setRange(1, 1000000)
        self.custom_scale_spin.setValue(300)
        self.custom_scale_spin.setSingleStep(50)
        self.custom_scale_spin.setPrefix("1 / ")
        self.custom_scale_spin.setGroupSeparatorShown(True)
        self.custom_scale_spin.setVisible(False)
        v_font.addWidget(self.custom_scale_spin)

        note_scale = QLabel(
            "<i>Une échelle calcule la taille (m) avec la même formule "
            "que « Taille des étiquettes ».</i>")
        note_scale.setWordWrap(True)
        v_font.addWidget(note_scale)
        v_font.addStretch()

        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)
        self.custom_scale_spin.valueChanged.connect(self._apply_scale_size)

        cols.addWidget(grp_font, 1)

        # -- Colonne droite : Couleur, transparence, cadre
        col_right = QVBoxLayout()
        col_right.setSpacing(8)

        grp_color = QGroupBox("Couleur et transparence")
        v_color = QVBoxLayout(grp_color)

        row_color = QHBoxLayout()
        row_color.addWidget(QLabel("Couleur texte :"))
        self.color_btn = QPushButton()
        self.color_btn.setFixedWidth(100)
        self._refresh_color_btn()
        self.color_btn.clicked.connect(self._pick_color)
        row_color.addWidget(self.color_btn)
        row_color.addStretch()
        v_color.addLayout(row_color)

        row_opacity = QHBoxLayout()
        row_opacity.addWidget(QLabel("Transparence (%) :"))
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setValue(int(round((1.0 - opacity) * 100)))
        self.opacity_spin.setSuffix(" %")
        row_opacity.addWidget(self.opacity_spin)
        row_opacity.addStretch()
        v_color.addLayout(row_opacity)
        self.opacity_spin.valueChanged.connect(self._update_preview)

        col_right.addWidget(grp_color)

        grp_frame = QGroupBox("Cadre")
        v_frame = QVBoxLayout(grp_frame)

        row_frame1 = QHBoxLayout()
        self.chk_frame = QCheckBox("Afficher un cadre")
        self.chk_frame.setChecked(frame)
        row_frame1.addWidget(self.chk_frame)
        self.chk_frame_filled = QCheckBox("Fond rempli")
        self.chk_frame_filled.setChecked(frame_filled)
        row_frame1.addWidget(self.chk_frame_filled)
        row_frame1.addStretch()
        v_frame.addLayout(row_frame1)

        row_frame2 = QHBoxLayout()
        row_frame2.addWidget(QLabel("Fond :"))
        self.frame_fill_btn = QPushButton()
        self.frame_fill_btn.setFixedWidth(80)
        self.frame_fill_btn.clicked.connect(self._pick_frame_fill_color)
        row_frame2.addWidget(self.frame_fill_btn)

        row_frame2.addSpacing(8)
        row_frame2.addWidget(QLabel("Bordure :"))
        self.frame_border_btn = QPushButton()
        self.frame_border_btn.setFixedWidth(80)
        self.frame_border_btn.clicked.connect(self._pick_frame_border_color)
        row_frame2.addWidget(self.frame_border_btn)
        row_frame2.addStretch()
        v_frame.addLayout(row_frame2)
        v_frame.addStretch()

        col_right.addWidget(grp_frame)

        self._refresh_frame_buttons()
        self.chk_frame.toggled.connect(self._on_frame_toggled)
        self.chk_frame_filled.toggled.connect(self._on_frame_toggled)
        self._on_frame_toggled()

        cols.addLayout(col_right, 1)
        layout.addLayout(cols)

        self.text_edit.textChanged.connect(self._update_preview)
        self.font_combo.currentFontChanged.connect(self._update_preview)
        self.size_spin.valueChanged.connect(self._update_preview)
        self.btn_bold.toggled.connect(self._update_preview)
        self.btn_italic.toggled.connect(self._update_preview)
        self.btn_underline.toggled.connect(self._update_preview)
        self.btn_al.toggled.connect(self._update_preview)
        self.btn_ac.toggled.connect(self._update_preview)
        self.btn_ar.toggled.connect(self._update_preview)
        self.chk_frame.toggled.connect(self._update_preview)
        self.chk_frame_filled.toggled.connect(self._update_preview)
        self._update_preview()

        # ── Appliquer / OK / Annuler ─────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.Apply | QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Apply).clicked.connect(
            lambda: self.applied.emit(self.get_values()))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Échelle ────────────────────────────────────────────────────────

    def _on_scale_changed(self):
        is_custom = self.scale_combo.currentIndex() > 0 \
            and _SCALES[self.scale_combo.currentIndex() - 1][1] is None
        self.custom_scale_spin.setVisible(is_custom)
        self._apply_scale_size()

    def _apply_scale_size(self):
        idx = self.scale_combo.currentIndex()
        if idx == 0:
            return  # « Taille libre » : la taille reste éditable manuellement
        _, scale = _SCALES[idx - 1]
        if scale is None:
            scale = self.custom_scale_spin.value()
        self.size_spin.setValue(_TARGET_MM * scale / 1000.0)

    # ── Couleur ────────────────────────────────────────────────────────

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "Couleur du texte")
        if c.isValid():
            self._color = c
            self._refresh_color_btn()
            self._update_preview()

    def _refresh_color_btn(self):
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        fg = '#000000' if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else '#ffffff'
        self.color_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); color: {fg};")
        self.color_btn.setText(self._color.name().upper())

    # ── Cadre ──────────────────────────────────────────────────────────

    def _pick_frame_fill_color(self):
        c = QColorDialog.getColor(self._frame_fill_color, self, "Couleur du fond")
        if c.isValid():
            self._frame_fill_color = c
            self._refresh_frame_buttons()
            self._update_preview()

    def _pick_frame_border_color(self):
        c = QColorDialog.getColor(self._frame_border_color, self, "Couleur de la bordure")
        if c.isValid():
            self._frame_border_color = c
            self._refresh_frame_buttons()
            self._update_preview()

    def _refresh_frame_buttons(self):
        for btn, color in ((self.frame_fill_btn, self._frame_fill_color),
                            (self.frame_border_btn, self._frame_border_color)):
            r, g, b = color.red(), color.green(), color.blue()
            fg = '#000000' if (0.299 * r + 0.587 * g + 0.114 * b) > 128 else '#ffffff'
            btn.setStyleSheet(f"background-color: rgb({r},{g},{b}); color: {fg};")
            btn.setText(color.name().upper())

    def _on_frame_toggled(self):
        enabled = self.chk_frame.isChecked()
        self.chk_frame_filled.setEnabled(enabled)
        self.frame_fill_btn.setEnabled(enabled and self.chk_frame_filled.isChecked())
        self.frame_border_btn.setEnabled(enabled)

    # ── Aperçu (appliqué directement dans le champ de texte) ────────────

    def _update_preview(self):
        font = QFont(self.font_combo.currentFont().family())
        font.setBold(self.btn_bold.isChecked())
        font.setItalic(self.btn_italic.isChecked())
        font.setUnderline(self.btn_underline.isChecked())
        # Conversion approximative taille carte (m) → taille d'aperçu (pt),
        # juste pour rendre visible l'effet relatif du réglage de taille.
        pt = max(6.0, min(72.0, self.size_spin.value() * 4.0))
        font.setPointSizeF(pt)

        if self.btn_ac.isChecked():
            align = Qt.AlignHCenter
        elif self.btn_ar.isChecked():
            align = Qt.AlignRight
        else:
            align = Qt.AlignLeft

        # Applique police/couleur/alignement à tout le document sans
        # perturber la position du curseur de saisie de l'utilisateur.
        block_signals = self.text_edit.blockSignals(True)
        doc_cursor = QTextCursor(self.text_edit.document())
        doc_cursor.select(QTextCursor.Document)
        char_fmt = QTextCharFormat()
        char_fmt.setFont(font)
        char_fmt.setForeground(self._color)
        doc_cursor.mergeCharFormat(char_fmt)
        self.text_edit.setCurrentCharFormat(char_fmt)
        self.text_edit.setAlignment(align)
        self.text_edit.blockSignals(block_signals)

        if self.chk_frame.isChecked():
            bc = self._frame_border_color
            border_css = f"border: 2px solid rgb({bc.red()},{bc.green()},{bc.blue()});"
            if self.chk_frame_filled.isChecked():
                fc = self._frame_fill_color
                bg_css = f"background: rgb({fc.red()},{fc.green()},{fc.blue()});"
            else:
                bg_css = "background: white;"
        else:
            border_css = "border: 1px solid #b0b0b0;"
            bg_css = "background: white;"
        self.text_edit.setStyleSheet(f"QTextEdit {{ {bg_css} {border_css} }}")

        effect = QGraphicsOpacityEffect(self.text_edit)
        effect.setOpacity(1.0 - self.opacity_spin.value() / 100.0)
        self.text_edit.setGraphicsEffect(effect)

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
            'frame':               self.chk_frame.isChecked(),
            'frame_filled':        self.chk_frame_filled.isChecked(),
            'frame_fill_color':    QColor(self._frame_fill_color),
            'frame_border_color':  QColor(self._frame_border_color),
            'opacity':             1.0 - self.opacity_spin.value() / 100.0,
        }
