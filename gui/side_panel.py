# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTreeWidget, QTreeWidgetItem,
)

from ..tools import i18n


class SidePanel(QDockWidget):

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("CanaPlan")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        # (item, clé i18n) : les libellés sont reposés à chaque changement
        # de langue, sans reconstruire l'arbre ni perdre son état déplié.
        self._i18n_items = []
        self._build_ui()

    def _build_ui(self):
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)

        icon_dir = os.path.join(self.plugin.plugin_dir, "icon")

        folder_general = self._folder("grp_general")
        self._item(folder_general, icon_dir, "renseignement.svg", "renseignement")
        self._item(folder_general, icon_dir, "config.svg",        "tableau_saisie")
        self._item(folder_general, icon_dir, "insert_regard.svg", "insert_regard")
        self._item(folder_general, icon_dir, "move.svg",          "move")
        self._item(folder_general, icon_dir, "copy_attrib.svg",   "copy_attributes")
        self._item(folder_general, icon_dir, "delete.svg",        "delete")
        self._item(folder_general, icon_dir, "config.svg",        "config",
                   tr_key="panel_config")

        folder_eu = self._folder("grp_eu")
        self._item(folder_eu, icon_dir, "conduite_eu.svg",    "conduite_eu")
        self._item(folder_eu, icon_dir, "branchement_eu.svg", "branchement_eu")
        self._item(folder_eu, icon_dir, "profil.svg",         "profil_eu")
        self._item(folder_eu, icon_dir, "profil.svg",         "coupe_eu")
        self._item(folder_eu, icon_dir, "renommer.svg",       "renommer_eu")

        folder_ep = self._folder("grp_ep")
        self._item(folder_ep, icon_dir, "conduite_ep.svg",    "conduite_ep")
        self._item(folder_ep, icon_dir, "branchement_ep.svg", "branchement_ep")
        self._item(folder_ep, icon_dir, "profil.svg",         "profil_ep")
        self._item(folder_ep, icon_dir, "profil.svg",         "coupe_ep")
        self._item(folder_ep, icon_dir, "renommer.svg",       "renommer_ep")

        folder_etiquettes = self._folder("grp_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "creer_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes_toggle.svg", "afficher_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "taille_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes_toggle.svg", "forcer_etiquettes",
                   tr_key="panel_forcer_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "affichage_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "annotation")

        folder_projet = self._folder("grp_projet")
        self._item(folder_projet, icon_dir, "config.svg", "nouveau_projet_assistant")
        self._item(folder_projet, icon_dir, "config.svg", "projets_recents")
        self._item(folder_projet, icon_dir, "config.svg", "enregistrer_projet",
                   tr_key="panel_enregistrer_projet")
        self._item(folder_projet, icon_dir, "config.svg", "enregistrer_projet_sous")
        self._item(folder_projet, icon_dir, "config.svg", "charger_projet")
        self._item(folder_projet, icon_dir, "config.svg", "import_dxf")
        self._item(folder_projet, icon_dir, "config.svg", "import_star_dt")

        folder_impression = self._folder("grp_sorties")
        self._item(folder_impression, icon_dir, "config.svg", "imprimer")
        self._item(folder_impression, icon_dir, "profil.svg", "profil_groupe")
        self._item(folder_impression, icon_dir, "profil.svg", "coupe_transversale")
        self._item(folder_impression, icon_dir, "config.svg", "cubature")
        self._item(folder_impression, icon_dir, "profil.svg", "coupe_tranchee_composee",
                   tr_key="panel_coupe_tranchee_composee")
        self._item(folder_impression, icon_dir, "config.svg", "export_stareau",
                   tr_key="panel_export_stareau")

        folder_fdc = self._folder("grp_fond")
        self._item(folder_fdc, icon_dir, "config.svg", "fond_projet",
                   tr_key="panel_fond_projet")
        self._item(folder_fdc, icon_dir, "config.svg", "osm_desature")
        self._item(folder_fdc, icon_dir, "config.svg", "ortho_ign")
        self._item(folder_fdc, icon_dir, "config.svg", "pci_parcelles")
        self._item(folder_fdc, icon_dir, "config.svg", "pci_bati")
        self._item(folder_fdc, icon_dir, "config.svg", "ban_vecteur",
                   tr_key="panel_ban_vecteur")
        self._item(folder_fdc, icon_dir, "config.svg", "nom_voie")

        for folder in (folder_projet, folder_general, folder_eu, folder_ep,
                       folder_etiquettes, folder_impression, folder_fdc):
            self.tree.addTopLevelItem(folder)
        self.tree.expandAll()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tree)
        layout.addLayout(self._build_language_row())
        self.setWidget(container)

    def _build_language_row(self):
        """Sélecteur de langue en pied de panneau, synchronisé avec le menu."""
        ligne = QHBoxLayout()
        self.label_langue = QLabel(i18n.tr('langue'))
        ligne.addWidget(self.label_langue)

        self.combo_langue = QComboBox()
        for code, _libelle in i18n.CHOIX:
            self.combo_langue.addItem(i18n.libelle_choix(code), code)
        index = self.combo_langue.findData(i18n.preference())
        if index >= 0:
            self.combo_langue.setCurrentIndex(index)
        self.combo_langue.currentIndexChanged.connect(self._on_langue_choisie)
        ligne.addWidget(self.combo_langue, 1)
        return ligne

    def _on_langue_choisie(self, _index):
        i18n.definir(self.combo_langue.currentData())

    def retranslate(self):
        """Repose les libellés de l'arbre et du sélecteur."""
        for item, cle in self._i18n_items:
            item.setText(0, i18n.tr(cle))
        self.label_langue.setText(i18n.tr('langue'))
        # Le signal est coupé le temps de réécrire les entrées : les
        # renommer déclenche currentIndexChanged et rappellerait definir().
        self.combo_langue.blockSignals(True)
        for position, (code, _libelle) in enumerate(i18n.CHOIX):
            self.combo_langue.setItemText(position, i18n.libelle_choix(code))
        index = self.combo_langue.findData(i18n.preference())
        if index >= 0:
            self.combo_langue.setCurrentIndex(index)
        self.combo_langue.blockSignals(False)

    def _folder(self, tr_key):
        item = QTreeWidgetItem([i18n.tr(tr_key)])
        font = QFont()
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self._i18n_items.append((item, tr_key))
        return item

    def _item(self, parent, icon_dir, icon_name, key, tr_key=None):
        """Entrée cliquable. tr_key permet un libellé propre au panneau,
        plus court que celui de l'action (« Enregistrer » vs « Enregistrer
        le projet »)."""
        tr_key = tr_key or key
        item = QTreeWidgetItem(parent, [i18n.tr(tr_key)])
        icon_path = os.path.join(icon_dir, icon_name)
        if os.path.exists(icon_path):
            item.setIcon(0, QIcon(icon_path))
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        self._i18n_items.append((item, tr_key))
        return item

    def _on_item_clicked(self, item, column):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return
        action = self.plugin.action_dict.get(key)
        if action is not None:
            action.trigger()
