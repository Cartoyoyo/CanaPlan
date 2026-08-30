# -*- coding: utf-8 -*-
"""Fenêtre de réglages d'impression.

Les réglages eux-mêmes vivent dans PrintSettingsWidget, partagé avec la
fenêtre d'export. Cette fenêtre ne sert plus qu'à les présenter seuls, quand
l'outil de pose les rouvre : Échap pendant le placement des feuilles permet
de changer d'échelle ou de format sans reprendre la pose depuis le début.
"""
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox
from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from .print_settings_widget import PrintSettingsWidget, FORMATS, SCALES

__all__ = ['PrintDialog', 'PrintSettingsWidget', 'FORMATS', 'SCALES']


class PrintDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('pd_titre'))
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.reglages = PrintSettingsWidget(self)

        # Les appelants — _reopen_settings en tête — manipulent directement
        # ces widgets pour repartir des réglages courants : on les expose tels
        # quels plutôt que de leur imposer un détour.
        self.titre_edit   = self.reglages.titre_edit
        self.format_combo = self.reglages.format_combo
        self.orient_combo = self.reglages.orient_combo
        self.scale_combo  = self.reglages.scale_combo
        self.dpi_combo    = self.reglages.dpi_combo
        self.rb_manuel    = self.reglages.rb_manuel
        self.rb_auto      = self.reglages.rb_auto

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(i18n.tr('pd_placer'))

        layout = QVBoxLayout(self)
        layout.addWidget(self.reglages)
        layout.addWidget(btns)

    def get_settings(self):
        return self.reglages.get_settings()
