# -*- coding: utf-8 -*-
"""Fenêtre de sélection d'un projet récent.

Un sous-menu déroulant obligeait à viser une entrée à l'aveugle, sans voir
d'où venait le projet ni de quand il datait. La fenêtre affiche les quatre
derniers projets avec leur dossier et leur date, et se referme sur le choix.
"""
import os
from datetime import datetime

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QDialogButtonBox,
)

from ..tools import i18n

_ROLE_PATH = Qt.ItemDataRole.UserRole


class RecentProjectsDialog(QDialog):
    """Liste les projets récents ; selected_path() donne le choix validé."""

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('recents_titre'))
        self.setMinimumWidth(520)
        self._paths = paths
        self._selected = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        titre = QLabel(i18n.tr('recents_invite'))
        police = QFont()
        police.setBold(True)
        titre.setFont(police)
        layout.addWidget(titre)

        self.liste = QListWidget()
        self.liste.setIconSize(QSize(24, 24))
        self.liste.setAlternatingRowColors(True)
        self.liste.itemDoubleClicked.connect(self._on_double_click)
        self.liste.currentItemChanged.connect(self._sync_bouton)
        layout.addWidget(self.liste)

        for path in self._paths:
            self.liste.addItem(self._make_item(path))

        if not self._paths:
            vide = QLabel(i18n.tr('recents_vide'))
            vide.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vide.setWordWrap(True)
            layout.addWidget(vide)
            self.liste.hide()

        boutons = QDialogButtonBox()
        self.bouton_ouvrir = QPushButton(i18n.tr('ouvrir'))
        self.bouton_ouvrir.setDefault(True)
        boutons.addButton(self.bouton_ouvrir,
                          QDialogButtonBox.ButtonRole.AcceptRole)
        boutons.addButton(QDialogButtonBox.StandardButton.Cancel)
        boutons.button(QDialogButtonBox.StandardButton.Cancel).setText(i18n.tr('annuler'))
        boutons.accepted.connect(self._on_accept)
        boutons.rejected.connect(self.reject)
        layout.addWidget(boutons)

        if self.liste.count():
            self.liste.setCurrentRow(0)
        self._sync_bouton()

    @staticmethod
    def _make_item(path):
        """Une ligne = nom du projet, puis dossier et date en infobulle."""
        nom = os.path.splitext(os.path.basename(path))[0]
        dossier = os.path.dirname(path)
        try:
            horodatage = datetime.fromtimestamp(os.path.getmtime(path))
            date = horodatage.strftime("%d/%m/%Y à %H:%M")
        except OSError:
            date = i18n.tr('recents_date_inconnue')
        item = QListWidgetItem(f"{nom}\n{dossier}   —   {date}")
        item.setData(_ROLE_PATH, path)
        item.setToolTip(path)
        return item

    def _sync_bouton(self, *_args):
        self.bouton_ouvrir.setEnabled(self.liste.currentItem() is not None)

    def _on_double_click(self, item):
        self._selected = item.data(_ROLE_PATH)
        self.accept()

    def _on_accept(self):
        item = self.liste.currentItem()
        if item is None:
            return
        self._selected = item.data(_ROLE_PATH)
        self.accept()

    def selected_path(self):
        """Chemin du projet choisi, ou None si la fenêtre a été annulée."""
        return self._selected
