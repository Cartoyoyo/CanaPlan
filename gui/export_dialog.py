# gui/export_dialog.py

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QFrame, QDialogButtonBox, QLineEdit, QPushButton,
    QFileDialog, QMessageBox,
)
from qgis.PyQt.QtCore import Qt

from ..tools import i18n

_FORMATS = ['A4', 'A3', 'A2', 'A1', 'A0']


class ExportDialog(QDialog):
    """Dialogue de choix des exports : plan PDF/DXF et profils en long."""

    def __init__(self, parent=None, default_dir=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('exp_titre'))
        self.setMinimumWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Plan cartographique ───────────────────────────────────────────
        lbl_plan = QLabel(i18n.tr('exp_plan_carto'))
        lbl_plan.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_plan)

        self.cb_pdf = QCheckBox(i18n.tr('exp_plan_pdf'))
        self.cb_pdf.setChecked(True)
        self.cb_dxf = QCheckBox(i18n.tr('exp_plan_dxf'))
        layout.addWidget(self.cb_pdf)
        layout.addWidget(self.cb_dxf)

        layout.addWidget(_hsep())

        # ── Profils en long ───────────────────────────────────────────────
        lbl_profils = QLabel(i18n.tr('exp_profils'))
        lbl_profils.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_profils)

        self.cb_eu,  self.fmt_eu  = self._profil_row(
            layout, i18n.tr('exp_profils_reseau', code="EU"))
        self.cb_ep,  self.fmt_ep  = self._profil_row(
            layout, i18n.tr('exp_profils_reseau', code="EP"))
        self.cb_grp, self.fmt_grp, self.ref_grp = self._profil_groupe_row(layout)

        layout.addWidget(_hsep())

        # ── Dossier d'export ──────────────────────────────────────────────
        lbl_dir = QLabel(i18n.tr('exp_dossier'))
        lbl_dir.setStyleSheet("font-weight: bold;")
        layout.addWidget(lbl_dir)

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(default_dir or os.path.expanduser("~"))
        self.dir_edit.setReadOnly(False)
        btn_browse = QPushButton(i18n.tr('parcourir'))
        btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_browse)
        layout.addLayout(dir_row)

        layout.addWidget(_hsep())

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText(i18n.tr('exp_bouton'))
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse_dir(self):
        start = self.dir_edit.text().strip() or os.path.expanduser("~")
        if not os.path.isdir(start):
            start = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, i18n.tr('exp_dossier_titre'), start)
        if path:
            self.dir_edit.setText(path)

    def _on_accept(self):
        path = self.dir_edit.text().strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(
                self, i18n.tr('exp_dossier_invalide'),
                i18n.tr('exp_dossier_absent'))
            return
        self.accept()

    def _profil_row(self, layout, label):
        row = QHBoxLayout()
        cb = QCheckBox(label)
        combo = QComboBox()
        combo.addItems(_FORMATS)
        combo.setCurrentText('A3')
        combo.setEnabled(False)
        combo.setFixedWidth(60)
        cb.toggled.connect(combo.setEnabled)
        row.addWidget(cb, 1)
        row.addWidget(combo)
        layout.addLayout(row)
        return cb, combo

    def _profil_groupe_row(self, layout):
        row = QHBoxLayout()
        cb = QCheckBox(i18n.tr('exp_profils_groupes'))

        ref_lbl = QLabel(i18n.tr('exp_ref'))
        ref_lbl.setEnabled(False)
        ref_combo = QComboBox()
        ref_combo.addItems(['EU', 'EP'])
        ref_combo.setFixedWidth(50)
        ref_combo.setEnabled(False)

        fmt_combo = QComboBox()
        fmt_combo.addItems(_FORMATS)
        fmt_combo.setCurrentText('A3')
        fmt_combo.setEnabled(False)
        fmt_combo.setFixedWidth(60)

        def _on_toggle(checked):
            ref_lbl.setEnabled(checked)
            ref_combo.setEnabled(checked)
            fmt_combo.setEnabled(checked)

        cb.toggled.connect(_on_toggle)

        row.addWidget(cb, 1)
        row.addWidget(ref_lbl)
        row.addWidget(ref_combo)
        row.addWidget(fmt_combo)
        layout.addLayout(row)
        return cb, fmt_combo, ref_combo

    def get_choices(self):
        return {
            'plan_pdf':              self.cb_pdf.isChecked(),
            'plan_dxf':              self.cb_dxf.isChecked(),
            'profil_eu':             self.cb_eu.isChecked(),
            'profil_eu_format':      self.fmt_eu.currentText(),
            'profil_ep':             self.cb_ep.isChecked(),
            'profil_ep_format':      self.fmt_ep.currentText(),
            'profil_groupe':         self.cb_grp.isChecked(),
            'profil_groupe_format':  self.fmt_grp.currentText(),
            'profil_groupe_reseau':  self.ref_grp.currentText(),
            'output_dir':            self.dir_edit.text().strip(),
        }


def _hsep():
    sep = QFrame()
    sep.setFrameShape(QFrame.HLine)
    sep.setFrameShadow(QFrame.Sunken)
    return sep
