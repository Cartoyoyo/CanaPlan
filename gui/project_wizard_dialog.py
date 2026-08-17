# -*- coding: utf-8 -*-
"""Assistant de création de projet (4 étapes) : adresse, fonds de plan,
configuration rapide, récapitulatif. Voir assistant_creation_projet.md à la
racine du plugin pour le plan complet."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QWidget, QCheckBox, QGroupBox, QToolBox, QTextEdit, QFrame,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
    QgsPointXY, QgsRasterLayer, QgsRectangle,
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsVertexMarker

from .ban_search_widget import BanSearchWidget
from .quick_config_widgets import (
    ReseauDefautWidget, CubatureConfigWidget, RemblaiConfigWidget,
)

CANVAS_CRS = QgsCoordinateReferenceSystem("EPSG:2154")
WGS84_CRS = QgsCoordinateReferenceSystem("EPSG:4326")

# Vichy, siège de l'utilisateur (Vichy Communauté) — vue par défaut de la
# mini-carte tant qu'aucune adresse n'a été recherchée.
DEFAULT_LON, DEFAULT_LAT = 3.4265, 46.1278
DEFAULT_HALF_EXTENT_M = 1500   # vue large ~3 km, ville entière
PICKED_HALF_EXTENT_M = 200     # vue rapprochée ~400 m, échelle de rue

STEP_TITLES = [
    "1. Localiser le projet",
    "2. Fonds de plan",
    "3. Configuration rapide",
    "4. Récapitulatif",
]


class _AddressPage(QWidget):
    """Étape 1 : recherche BAN + mini-carte OSM pour situer le projet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._address_label = ""
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "Entrez l'adresse du projet, puis ajustez la position en "
            "déplaçant/zoomant la carte si besoin."))

        self._search = BanSearchWidget()
        self._search.address_picked.connect(self._on_address_picked)
        layout.addWidget(self._search)

        self._canvas = QgsMapCanvas()
        self._canvas.setMinimumHeight(320)
        self._canvas.setDestinationCrs(CANVAS_CRS)
        self._canvas.setCanvasColor(QColor(235, 235, 230))

        osm = QgsRasterLayer(
            "type=xyz&url=https://tile.openstreetmap.org/%7Bz%7D/%7Bx%7D/%7By%7D.png"
            "&zmax=19&zmin=0&crs=EPSG3857",
            "OSM", "wms")
        self._osm_layer = osm
        if osm.isValid():
            self._canvas.setLayers([osm])

        self._canvas.setMapTool(QgsMapToolPan(self._canvas))
        layout.addWidget(self._canvas)

        # Vue par défaut : Vichy, tant qu'aucune adresse n'a été choisie.
        transform = QgsCoordinateTransform(WGS84_CRS, CANVAS_CRS, QgsProject.instance())
        default_point = transform.transform(QgsPointXY(DEFAULT_LON, DEFAULT_LAT))
        self._set_view(default_point, DEFAULT_HALF_EXTENT_M)

        self._marker = QgsVertexMarker(self._canvas)
        self._marker.setColor(QColor(220, 40, 40))
        self._marker.setIconType(QgsVertexMarker.ICON_CROSS)
        self._marker.setIconSize(14)
        self._marker.setPenWidth(3)
        self._marker.hide()

    def _set_view(self, point, half_extent_m):
        rect = QgsRectangle(
            point.x() - half_extent_m, point.y() - half_extent_m,
            point.x() + half_extent_m, point.y() + half_extent_m,
        )
        self._canvas.setExtent(rect)
        self._canvas.refresh()

    def _on_address_picked(self, lon, lat, label):
        self._address_label = label
        transform = QgsCoordinateTransform(WGS84_CRS, CANVAS_CRS, QgsProject.instance())
        point = transform.transform(QgsPointXY(lon, lat))
        self._set_view(point, PICKED_HALF_EXTENT_M)
        self._marker.setCenter(point)
        self._marker.show()
        self._canvas.refresh()

    def address_label(self):
        return self._address_label

    def extent(self):
        """Étendue courante de la mini-carte, en EPSG:2154."""
        return self._canvas.extent()


class _BasemapsPage(QWidget):
    """Étape 2 : choix des fonds de plan à charger."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Fonds de plan à charger dans le nouveau projet :"))

        group = QGroupBox("Fonds de plan")
        group_layout = QVBoxLayout()

        self._checks = {}
        for key, text, checked in [
            ('osm', "Fond OSM désaturé", True),
            ('ortho', "Orthophoto IGN", True),
            ('ban', "Adresses BAN", False),
            ('noms_voie', "Noms de voie (BD TOPO)", False),
            ('pci_parcelles', "PCI Vecteur Parcelles", False),
            ('pci_bati', "PCI Vecteur Bâti", False),
        ]:
            cb = QCheckBox(text)
            cb.setChecked(checked)
            self._checks[key] = cb
            group_layout.addWidget(cb)

        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()

    def options(self):
        return {key: cb.isChecked() for key, cb in self._checks.items()}


class _QuickConfigPage(QWidget):
    """Étape 3 : réseau par défaut / cubature / remblai, en accordéons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Configuration rapide du projet (modifiable plus tard depuis "
            "le menu Configuration) :"))

        box = QToolBox()

        self.reseau_widget = ReseauDefautWidget()
        box.addItem(self.reseau_widget, "Réseau par défaut")

        self.cubature_widget = CubatureConfigWidget()
        box.addItem(self.cubature_widget, "Cubature")

        self.remblai_widget = RemblaiConfigWidget()
        box.addItem(self.remblai_widget, "Remblai")

        ep_lit_spin = self.cubature_widget._cub_widgets['ep_lit_pose']
        ep_lit_spin.valueChanged.connect(self.remblai_widget.set_ep_lit_pose)
        self.remblai_widget.set_ep_lit_pose(ep_lit_spin.value())

        layout.addWidget(box)

    def save_settings(self):
        self.reseau_widget.save_settings()
        self.cubature_widget.save_settings()
        self.remblai_widget.save_settings()

    def summary(self):
        return (
            f"Réseau : {self.reseau_widget.summary()}\n\n"
            f"Cubature : {self.cubature_widget.summary()}\n\n"
            f"Remblai : {self.remblai_widget.summary()}"
        )


class _RecapPage(QWidget):
    """Étape 4 : récapitulatif avant création."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Vérifiez les informations ci-dessous, ou revenez en arrière "
            "pour les modifier, puis cliquez sur « Créer »."))

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        layout.addWidget(self._text)

    def refresh(self, address_label, basemap_options, config_summary):
        basemap_labels = {
            'osm': "OSM désaturé", 'ortho': "Orthophoto IGN",
            'ban': "Adresses BAN", 'noms_voie': "Noms de voie",
            'pci_parcelles': "PCI Vecteur Parcelles", 'pci_bati': "PCI Vecteur Bâti",
        }
        chosen = [basemap_labels[k] for k, v in basemap_options.items() if v]
        lines = [
            "Adresse du projet :",
            f"  {address_label or '(non renseignée — position de la mini-carte utilisée)'}",
            "",
            "Fonds de plan :",
            f"  {', '.join(chosen) if chosen else '(aucun)'}",
            "",
            config_summary,
        ]
        self._text.setPlainText("\n".join(lines))


class ProjectWizardDialog(QDialog):
    """Assistant de création de projet en 4 étapes, navigable librement."""

    def __init__(self, plugin, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self._plugin = plugin
        self._iface = iface
        self._created = False

        self.setWindowTitle("Créer un projet avec l'assistant")
        self.setMinimumSize(560, 520)

        layout = QVBoxLayout(self)

        self._title_label = QLabel()
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self._title_label.setFont(font)
        layout.addWidget(self._title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._stack = QStackedWidget()
        self._address_page = _AddressPage()
        self._basemaps_page = _BasemapsPage()
        self._config_page = _QuickConfigPage()
        self._recap_page = _RecapPage()
        for page in (self._address_page, self._basemaps_page,
                     self._config_page, self._recap_page):
            self._stack.addWidget(page)
        layout.addWidget(self._stack)

        nav_layout = QHBoxLayout()
        self._btn_prev = QPushButton("< Précédent")
        self._btn_prev.clicked.connect(self._go_prev)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addStretch()
        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.clicked.connect(self.reject)
        nav_layout.addWidget(self._btn_cancel)
        self._btn_next = QPushButton("Suivant >")
        self._btn_next.setDefault(True)
        self._btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self._btn_next)
        layout.addLayout(nav_layout)

        self._update_nav()

    def _current_index(self):
        return self._stack.currentIndex()

    def _update_nav(self):
        idx = self._current_index()
        self._title_label.setText(STEP_TITLES[idx])
        self._btn_prev.setEnabled(idx > 0)
        last = idx == self._stack.count() - 1
        self._btn_next.setText("Créer" if last else "Suivant >")
        if last:
            self._recap_page.refresh(
                self._address_page.address_label(),
                self._basemaps_page.options(),
                self._config_page.summary(),
            )

    def _go_prev(self):
        self._stack.setCurrentIndex(self._current_index() - 1)
        self._update_nav()

    def _go_next(self):
        if self._current_index() == self._stack.count() - 1:
            self._create_project()
            return
        self._stack.setCurrentIndex(self._current_index() + 1)
        self._update_nav()

    def _create_project(self):
        from ..tools.projet_bet import save_projet_sous

        canvas = self._iface.mapCanvas()
        canvas.setDestinationCrs(CANVAS_CRS)
        canvas.setExtent(self._address_page.extent())
        canvas.refresh()

        self._plugin.run_fond_projet(self._basemaps_page.options())
        self._config_page.save_settings()

        # Les couches EU/EP doivent exister avant l'enregistrement : sans
        # elles, l'archive .bet écrite est vide (pas de data.gpkg) et
        # l'extraction qui suit l'écriture échoue.
        self._plugin._get_couches("EU")
        self._plugin._get_couches("EP")

        self._created = True
        save_projet_sous(self._plugin, self._iface)
        self.accept()

    def project_created(self):
        return self._created
