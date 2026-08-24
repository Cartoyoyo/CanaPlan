# -*- coding: utf-8 -*-
"""Barre de recherche d'adresse BAN avec suggestions, utilisée à l'étape 1
de l'assistant de création de projet.

Implémentation en widget composite (QLineEdit + QListWidget empilés dans le
même layout), pas en popup flottant Qt.Popup : un QListWidget top-level en
Qt.Popup vole le focus du QLineEdit dès son affichage, ce qui déclenche
focusOutEvent et referme la liste avant que l'utilisateur ait pu la voir.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
)

from ..tools import i18n
from ..tools.ban_search import BanSearchProvider


class BanSearchWidget(QWidget):
    """Champ de recherche d'adresse : suggestions BAN affichées dans une
    liste sous le champ, au fil de la frappe (debounce 600 ms)."""

    address_picked = pyqtSignal(float, float, str)  # lon, lat, label

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(i18n.tr('ban_rechercher'))
        self._edit.setClearButtonEnabled(True)
        layout.addWidget(self._edit)

        self._list = QListWidget()
        self._list.setMaximumHeight(140)
        self._list.hide()
        layout.addWidget(self._list)

        self._provider = BanSearchProvider(self)
        self._provider.results_ready.connect(self._show_results)

        self._edit.textEdited.connect(self._on_text_edited)
        self._list.itemClicked.connect(self._on_item_clicked)

    def _on_text_edited(self, text):
        text = text.strip()
        if len(text) < 3:
            self._provider.cancel()
            self._list.hide()
            return
        self._provider.search(text)

    def _show_results(self, results):
        self._list.clear()
        if not results:
            self._list.hide()
            return

        for res in results:
            label = res['label']
            if res.get('postcode'):
                label = f"{label} ({res['postcode']})"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, res)
            self._list.addItem(item)

        self._list.show()

    def _on_item_clicked(self, item):
        res = item.data(Qt.UserRole)
        self._list.hide()
        self._edit.setText(res['label'])
        self.address_picked.emit(res['lon'], res['lat'], res['label'])

    def text(self):
        return self._edit.text()
