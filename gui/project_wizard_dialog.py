# -*- coding: utf-8 -*-
"""Assistant de création de projet (4 étapes) : adresse, fonds de plan,
configuration rapide, récapitulatif. Voir assistant_creation_projet.md à la
racine du plugin pour le plan complet."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QWidget, QCheckBox, QGroupBox, QToolBox, QTextEdit, QFrame,
    QLineEdit, QFileDialog, QMessageBox, QScrollArea, QApplication,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
    QgsPointXY, QgsRasterLayer, QgsRectangle,
)
from qgis.gui import QgsMapCanvas, QgsMapToolPan, QgsVertexMarker

from ..tools import i18n
from .ban_search_widget import BanSearchWidget
from .quick_config_widgets import (
    ReseauDefautWidget, CubatureConfigWidget, RemblaiConfigWidget,
    NetworkSchemaWidget, CubatureSchemaWidget, TrenchSchemaWidget,
    network_group_stylesheet,
)

# Clés i18n des largeurs de tranchée affichées en aperçu au récapitulatif.
_CUBATURE_WIDTH_KEYS = {
    'larg_cond_eu': 'qc_conduite_eu', 'larg_cond_ep': 'qc_conduite_ep',
    'larg_branch_eu': 'qc_branch_court_eu', 'larg_branch_ep': 'qc_branch_court_ep',
}

CANVAS_CRS = QgsCoordinateReferenceSystem("EPSG:2154")
WGS84_CRS = QgsCoordinateReferenceSystem("EPSG:4326")

# Vichy, siège de l'utilisateur (Vichy Communauté) — vue par défaut de la
# mini-carte tant qu'aucune adresse n'a été recherchée.
DEFAULT_LON, DEFAULT_LAT = 3.4265, 46.1278
DEFAULT_HALF_EXTENT_M = 1500   # vue large ~3 km, ville entière
PICKED_HALF_EXTENT_M = 200     # vue rapprochée ~400 m, échelle de rue

# Ascenseur discret : pas de flèches, poignée translucide qui ne s'affirme
# qu'au survol. Appliqué à la barre seule et non au QScrollArea, pour ne pas
# cascader sur les QGroupBox enfants qui ont déjà leur propre feuille de style.
_SCROLLBAR_DISCRET_QSS = """
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: rgba(0, 0, 0, 55);
    min-height: 28px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(0, 0, 0, 110);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
"""

# Titres des étapes : traduits à l'affichage, pas au chargement du module.
STEP_TITLE_KEYS = ['wz_etape1', 'wz_etape2', 'wz_etape3', 'wz_etape4']


class _AddressPage(QWidget):
    """Étape 1 : recherche BAN + mini-carte OSM pour situer le projet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._address_label = ""
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            i18n.tr('wz_adresse_aide')))

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
        self._marker.setIconType(QgsVertexMarker.IconType.ICON_CROSS)
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
        layout.addWidget(QLabel(i18n.tr('wz_fonds_aide')))

        group = QGroupBox(i18n.tr('wz_fonds_titre'))
        group_layout = QVBoxLayout()

        self._checks = {}
        for key, cle, checked in [
            ('osm', 'wz_fond_osm', True),
            ('ortho', 'wz_fond_ortho', True),
            ('ban', 'wz_fond_ban', False),
            ('noms_voie', 'wz_fond_noms_voie', False),
            ('pci_parcelles', 'wz_fond_parcelles', False),
            ('pci_bati', 'wz_fond_bati', False),
        ]:
            cb = QCheckBox(i18n.tr(cle))
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
            i18n.tr('wz_config_aide')))

        box = QToolBox()

        self.reseau_widget = ReseauDefautWidget()
        box.addItem(self.reseau_widget, i18n.tr('wz_reseau_defaut'))

        self.cubature_widget = CubatureConfigWidget()
        box.addItem(self.cubature_widget, i18n.tr('wz_cubature'))

        self.remblai_widget = RemblaiConfigWidget()
        box.addItem(self.remblai_widget, i18n.tr('wz_remblai'))

        ep_lit_spin = self.cubature_widget._cub_widgets['ep_lit_pose']
        ep_lit_spin.valueChanged.connect(self.remblai_widget.set_ep_lit_pose)
        self.remblai_widget.set_ep_lit_pose(ep_lit_spin.value())

        layout.addWidget(box)

    def save_settings(self):
        self.reseau_widget.save_settings()
        self.cubature_widget.save_settings()
        self.remblai_widget.save_settings()

    def summary(self):
        return "\n\n".join((
            i18n.tr('wz_recap_reseau', texte=self.reseau_widget.summary()),
            i18n.tr('wz_recap_cubature', texte=self.cubature_widget.summary()),
            i18n.tr('wz_recap_remblai', texte=self.remblai_widget.summary()),
        ))


class _RecapPage(QWidget):
    """Étape 4 : récapitulatif avant création."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # Le récapitulatif empile six blocs (aide, enregistrement, résumé,
        # réseau, largeurs, remblai) et dépasse la hauteur utile sur un écran
        # modeste. Tout passe donc dans une zone défilante : la page cesse
        # d'imposer sa hauteur au dialogue, et l'ascenseur n'apparaît que
        # lorsqu'il manque réellement de la place.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setStyleSheet(_SCROLLBAR_DISCRET_QSS)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)   # marge droite = place de l'ascenseur
        layout.addWidget(QLabel(
            i18n.tr('wz_recap_aide')))

        save_group = QGroupBox(i18n.tr('wz_enregistrement'))
        save_layout = QVBoxLayout()

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(i18n.tr('wz_nom_label')))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(i18n.tr('wz_nom_ph'))
        name_layout.addWidget(self._name_edit)
        save_layout.addLayout(name_layout)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(QLabel(i18n.tr('wz_dossier_label')))
        self._folder_edit = QLineEdit()
        self._folder_edit.setReadOnly(True)
        self._folder_edit.setPlaceholderText(i18n.tr('wz_choisir_dossier'))
        folder_layout.addWidget(self._folder_edit)
        btn_browse = QPushButton(i18n.tr('wz_parcourir'))
        btn_browse.clicked.connect(self._browse_folder)
        folder_layout.addWidget(btn_browse)
        save_layout.addLayout(folder_layout)

        save_group.setLayout(save_layout)
        layout.addWidget(save_group)

        from ..tools.projet_bet import project_dir
        default_dir = project_dir()
        if default_dir:
            self._folder_edit.setText(default_dir)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumHeight(90)
        layout.addWidget(self._text)

        # Aperçus schématiques (réseau, largeurs de tranchée, remblai),
        # compacts pour ne pas surcharger le récapitulatif.
        reseau_group = QGroupBox(i18n.tr('col_reseau'))
        reseau_layout = QHBoxLayout()
        self._network_eu = NetworkSchemaWidget()
        self._network_eu.setMinimumHeight(95)
        self._network_ep = NetworkSchemaWidget()
        self._network_ep.setMinimumHeight(95)
        for sub_title, widget in (("EU", self._network_eu), ("EP", self._network_ep)):
            sub_box = QGroupBox(sub_title)
            sub_box.setStyleSheet(network_group_stylesheet(sub_title))
            sub_layout = QVBoxLayout()
            sub_layout.addWidget(widget)
            sub_box.setLayout(sub_layout)
            reseau_layout.addWidget(sub_box)
        reseau_group.setLayout(reseau_layout)
        layout.addWidget(reseau_group)

        cubature_group = QGroupBox(i18n.tr('wz_cubature_largeurs'))
        cubature_layout = QHBoxLayout()
        self._cubature_widgets = {}
        for key in ('larg_cond_eu', 'larg_branch_eu', 'larg_cond_ep', 'larg_branch_ep'):
            w = CubatureSchemaWidget()
            w.setMinimumHeight(95)
            w.setMinimumWidth(110)
            self._cubature_widgets[key] = w
            sub_box = QGroupBox(i18n.tr(_CUBATURE_WIDTH_KEYS[key]))
            sub_reseau = "EU" if key.endswith("_eu") else "EP"
            sub_box.setStyleSheet(network_group_stylesheet(sub_reseau))
            sub_layout = QVBoxLayout()
            sub_layout.addWidget(w)
            sub_box.setLayout(sub_layout)
            cubature_layout.addWidget(sub_box)
        cubature_group.setLayout(cubature_layout)
        layout.addWidget(cubature_group)

        remblai_group = QGroupBox(i18n.tr('wz_remblai'))
        remblai_layout = QVBoxLayout()
        self._remblai_schema = TrenchSchemaWidget()
        self._remblai_schema.setMinimumHeight(150)
        remblai_layout.addWidget(self._remblai_schema)
        remblai_group.setLayout(remblai_layout)
        layout.addWidget(remblai_group)

        # Sans ressort final, les blocs se dilateraient pour remplir la zone
        # défilante dès qu'il reste de la place.
        layout.addStretch()

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, i18n.tr('wz_dossier_titre'),
            self._folder_edit.text())
        if folder:
            self._folder_edit.setText(folder)

    def project_name(self):
        return self._name_edit.text().strip()

    def project_folder(self):
        return self._folder_edit.text().strip()

    def set_default_name(self, name):
        if not self._name_edit.text().strip():
            self._name_edit.setText(name)

    def refresh(self, address_label, basemap_options, config_page):
        basemap_keys = {
            'osm': 'wz_fond_osm_court', 'ortho': 'wz_fond_ortho',
            'ban': 'wz_fond_ban', 'noms_voie': 'wz_fond_noms_voie_court',
            'pci_parcelles': 'wz_fond_parcelles', 'pci_bati': 'wz_fond_bati',
        }
        chosen = [i18n.tr(basemap_keys[k]) for k, v in basemap_options.items() if v]
        lines = [
            i18n.tr('wz_recap_adresse'),
            f"  {address_label or i18n.tr('wz_recap_sans_adresse')}",
            "",
            i18n.tr('wz_recap_fonds'),
            f"  {', '.join(chosen) if chosen else i18n.tr('wz_recap_aucun')}",
        ]
        self._text.setPlainText("\n".join(lines))

        self._network_eu.update_schema(config_page.reseau_widget.get_network_data("EU"))
        self._network_ep.update_schema(config_page.reseau_widget.get_network_data("EP"))

        for key, widget in self._cubature_widgets.items():
            width = config_page.cubature_widget.get_width(key)
            widget.update_schema(width, i18n.tr(_CUBATURE_WIDTH_KEYS[key]))

        self._remblai_schema.update_schema(config_page.remblai_widget.get_schema_data())


class ProjectWizardDialog(QDialog):
    """Assistant de création de projet en 4 étapes, navigable librement."""

    def __init__(self, plugin, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self._plugin = plugin
        self._iface = iface
        self._created = False

        self.setWindowTitle(i18n.tr('nouveau_projet_assistant'))
        self.setMinimumSize(560, 520)

        # Ouvrir assez grand pour que le récapitulatif (étape 4, la plus
        # dense) tienne d'un seul tenant quand l'écran le permet ; sinon on
        # s'arrête à la place disponible et son ascenseur prend le relais.
        ecran = QApplication.primaryScreen().availableGeometry()
        self.resize(min(700, ecran.width() - 80),
                    min(880, ecran.height() - 100))

        layout = QVBoxLayout(self)

        self._title_label = QLabel()
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self._title_label.setFont(font)
        layout.addWidget(self._title_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
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
        self._btn_prev = QPushButton(i18n.tr('wz_precedent'))
        self._btn_prev.clicked.connect(self._go_prev)
        nav_layout.addWidget(self._btn_prev)
        nav_layout.addStretch()
        self._btn_cancel = QPushButton(i18n.tr('annuler'))
        self._btn_cancel.clicked.connect(self.reject)
        nav_layout.addWidget(self._btn_cancel)
        self._btn_next = QPushButton(i18n.tr('wz_suivant'))
        self._btn_next.setDefault(True)
        self._btn_next.clicked.connect(self._go_next)
        nav_layout.addWidget(self._btn_next)
        layout.addLayout(nav_layout)

        self._update_nav()

    def _current_index(self):
        return self._stack.currentIndex()

    def _update_nav(self):
        idx = self._current_index()
        self._title_label.setText(i18n.tr(STEP_TITLE_KEYS[idx]))
        self._btn_prev.setEnabled(idx > 0)
        last = idx == self._stack.count() - 1
        self._btn_next.setText(
            i18n.tr('wz_creer') if last else i18n.tr('wz_suivant'))
        if last:
            address_label = self._address_page.address_label()
            self._recap_page.refresh(
                address_label,
                self._basemaps_page.options(),
                self._config_page,
            )
            if address_label:
                self._recap_page.set_default_name(
                    i18n.tr('wz_projet_nomme', nom=address_label))

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
        import os
        from ..tools.projet_bet import _do_save

        proj_name = self._recap_page.project_name()
        proj_folder = self._recap_page.project_folder()
        if not proj_name or not proj_folder:
            QMessageBox.warning(
                self, i18n.tr('nouveau_projet_assistant'),
                i18n.tr('wz_err_champs'))
            return

        bet_path = os.path.join(proj_folder, f"{proj_name}.bet")
        if os.path.exists(bet_path):
            reply = QMessageBox.question(
                self, i18n.tr('nouveau_projet_assistant'),
                i18n.tr('wz_ecraser', nom=proj_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        gpkg_temp = os.path.join(proj_folder, f"{proj_name}_tmp.gpkg")

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
        _do_save(self._plugin, self._iface, gpkg_temp, bet_path)
        self.accept()

    def project_created(self):
        return self._created
