# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon, QFont
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
)


class SidePanel(QDockWidget):

    def __init__(self, plugin, parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle("BET Humide")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._build_ui()

    def _build_ui(self):
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)

        icon_dir = os.path.join(self.plugin.plugin_dir, "icon")

        folder_general = self._folder("Général")
        self._item(folder_general, icon_dir, "renseignement.svg", "Renseigner un élément",          "renseignement")
        self._item(folder_general, icon_dir, "insert_regard.svg", "Insérer un regard sur conduite", "insert_regard")
        self._item(folder_general, icon_dir, "move.svg",          "Déplacer un ouvrage",            "move")
        self._item(folder_general, icon_dir, "copy_attrib.svg",   "Copier les attributs",           "copy_attributes")
        self._item(folder_general, icon_dir, "delete.svg",        "Effacer un élément",             "delete")
        self._item(folder_general, icon_dir, "config.svg",        "Configuration rapide",         "config")

        folder_eu = self._folder("EU – Eaux Usées")
        self._item(folder_eu, icon_dir, "conduite_eu.svg",    "Dessiner une conduite EU",        "conduite_eu")
        self._item(folder_eu, icon_dir, "branchement_eu.svg", "Dessiner un branchement EU",      "branchement_eu")
        self._item(folder_eu, icon_dir, "profil.svg",         "Profil en long EU",               "profil_eu")
        self._item(folder_eu, icon_dir, "profil.svg",         "Coupe transversale EU",           "coupe_eu")
        self._item(folder_eu, icon_dir, "renommer.svg",       "Renuméroter regards/tabourets EU", "renommer_eu")

        folder_ep = self._folder("EP – Eaux Pluviales")
        self._item(folder_ep, icon_dir, "conduite_ep.svg",    "Dessiner une conduite EP",        "conduite_ep")
        self._item(folder_ep, icon_dir, "branchement_ep.svg", "Dessiner un branchement EP",      "branchement_ep")
        self._item(folder_ep, icon_dir, "profil.svg",         "Profil en long EP",               "profil_ep")
        self._item(folder_ep, icon_dir, "profil.svg",         "Coupe transversale EP",           "coupe_ep")
        self._item(folder_ep, icon_dir, "renommer.svg",       "Renuméroter regards/tabourets EP", "renommer_ep")

        folder_etiquettes = self._folder("Étiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "Créer les étiquettes",              "creer_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes_toggle.svg", "Afficher / Masquer les étiquettes", "afficher_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "Taille des étiquettes",             "taille_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes_toggle.svg", "Forcer toutes les étiquettes visibles",   "forcer_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "Gestion de l'affichage des étiquettes",  "affichage_etiquettes")
        self._item(folder_etiquettes, icon_dir, "etiquettes.svg",        "Placer une annotation texte",            "annotation")

        folder_projet = self._folder("Projet")
        self._item(folder_projet, icon_dir, "config.svg", "Mise en place fond de projet", "fond_projet")
        self._item(folder_projet, icon_dir, "config.svg", "Enregistrer",                  "enregistrer_projet")
        self._item(folder_projet, icon_dir, "config.svg", "Enregistrer sous",             "enregistrer_projet_sous")
        self._item(folder_projet, icon_dir, "config.svg", "Charger un projet",            "charger_projet")
        self._item(folder_projet, icon_dir, "config.svg", "Importer DXF / DWG",           "import_dxf")
        self._item(folder_projet, icon_dir, "config.svg", "Importer Star-DT (GML)",     "import_star_dt")

        folder_impression = self._folder("Impression")
        self._item(folder_impression, icon_dir, "config.svg",
                   "Imprimer / Exporter PDF/DXF", "imprimer")
        self._item(folder_impression, icon_dir, "profil.svg",
                   "Profil groupé EU + EP", "profil_groupe")
        self._item(folder_impression, icon_dir, "profil.svg",
                   "Coupe transversale des tranchées", "coupe_transversale")
        self._item(folder_impression, icon_dir, "config.svg",
                   "Cubature tranchées", "cubature")
        self._item(folder_impression, icon_dir, "config.svg",
                   "Remblai tranchées", "remblai")
        self._item(folder_impression, icon_dir, "profil.svg",
                   "Dessinateur – Coupe de tranchées", "coupe_tranchee_composee")

        folder_fdc = self._folder("Fond de carte")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "Fond de projet (6 couches)", "fond_projet")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "OSM Desature", "osm_desature")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "Ortho 2022",  "ortho_2022")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "PCI Vecteur – Parcelles & Bâti (emprise)", "pci_emprise")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "BAN Adresses – vecteur (emprise)", "ban_vecteur")
        self._item(folder_fdc, icon_dir, "config.svg",
                   "Noms de rue BD TOPO (emprise)",    "nom_voie")

        for folder in (folder_projet, folder_general, folder_eu, folder_ep, folder_etiquettes, folder_impression, folder_fdc):
            self.tree.addTopLevelItem(folder)
        self.tree.expandAll()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tree)
        self.setWidget(container)

    def _folder(self, title):
        item = QTreeWidgetItem([title])
        font = QFont()
        font.setBold(True)
        item.setFont(0, font)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        return item

    def _item(self, parent, icon_dir, icon_name, label, key):
        item = QTreeWidgetItem(parent, [label])
        icon_path = os.path.join(icon_dir, icon_name)
        if os.path.exists(icon_path):
            item.setIcon(0, QIcon(icon_path))
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        return item

    def _on_item_clicked(self, item, column):
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key is None:
            return
        action = self.plugin.action_dict.get(key)
        if action is not None:
            action.trigger()
