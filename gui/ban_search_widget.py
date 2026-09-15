# -*- coding: utf-8 -*-
"""Barre de recherche d'adresse avec suggestions, utilisée à l'étape 1
de l'assistant de création de projet.

La source dépend du territoire : Base Adresse Nationale en France, Photon
(OpenStreetMap) à l'international. Les deux fournisseurs émettent des
résultats au même format (label, city, postcode, lon, lat).

Implémentation en widget composite (QLineEdit + QListWidget empilés dans le
même layout), pas en popup flottant Qt.WindowType.Popup : un QListWidget top-level en
Qt.WindowType.Popup vole le focus du QLineEdit dès son affichage, ce qui déclenche
focusOutEvent et referme la liste avant que l'utilisateur ait pu la voir.
"""

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
)

from ..tools import i18n
from ..tools import territoire as terr
from ..tools.ban_search import BanSearchProvider
from ..tools.osm_services import PhotonSearchProvider


class BanSearchWidget(QWidget):
    """Champ de recherche d'adresse : suggestions affichées dans une
    liste sous le champ, au fil de la frappe (debounce 600 ms)."""

    address_picked = pyqtSignal(float, float, str)  # lon, lat, label

    def __init__(self, parent=None, territoire=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._edit = QLineEdit()
        self._edit.setClearButtonEnabled(True)
        layout.addWidget(self._edit)

        self._list = QListWidget()
        self._list.setMaximumHeight(140)
        self._list.hide()
        layout.addWidget(self._list)

        self._territoire = None
        self._provider = None
        self.set_territoire(territoire or terr.FRANCE)

        self._edit.textEdited.connect(self._on_text_edited)
        self._list.itemClicked.connect(self._on_item_clicked)

    def set_territoire(self, territoire):
        """Change de source de recherche ; la saisie en cours est effacée,
        une adresse française n'ayant pas de sens dans Photon et inversement."""
        if territoire == self._territoire:
            return
        if self._provider is not None:
            self._provider.cancel()
            self._provider.results_ready.disconnect(self._show_results)
            self._provider.deleteLater()
        self._territoire = territoire
        self._provider = (BanSearchProvider(self) if territoire == terr.FRANCE
                          else PhotonSearchProvider(self))
        self._provider.results_ready.connect(self._show_results)
        self._edit.setPlaceholderText(i18n.tr(
            'ban_rechercher' if territoire == terr.FRANCE else 'osm_rechercher'))
        self._edit.clear()
        self._list.clear()
        self._list.hide()

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
            # Le libellé Photon contient déjà la ville et le pays ; seul celui
            # de la BAN gagne à être complété par le code postal.
            if self._territoire == terr.FRANCE and res.get('postcode'):
                label = f"{label} ({res['postcode']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, res)
            self._list.addItem(item)

        self._list.show()

    def _on_item_clicked(self, item):
        res = item.data(Qt.ItemDataRole.UserRole)
        self._list.hide()
        self._edit.setText(res['label'])
        self.address_picked.emit(res['lon'], res['lat'], res['label'])

    def text(self):
        return self._edit.text()
