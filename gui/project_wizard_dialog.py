# -*- coding: utf-8 -*-
"""Assistant de création de projet (4 étapes) : territoire et adresse, fonds
de plan, configuration rapide, récapitulatif. Voir assistant_creation_projet.md
à la racine du plugin pour le plan complet."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QWidget, QCheckBox, QGroupBox, QToolBox, QTextEdit, QFrame,
    QLineEdit, QFileDialog, QMessageBox, QScrollArea, QApplication,
    QRadioButton, QButtonGroup,
)
from qgis.PyQt.QtGui import QFont, QColor
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsProject,
    QgsPointXY, QgsRasterLayer, QgsRectangle,
)
from qgis.gui import (
    QgsMapCanvas, QgsMapToolPan, QgsVertexMarker, QgsProjectionSelectionWidget,
)

from ..tools import i18n
from ..tools import territoire as terr
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

# La mini-carte est en Web Mercator, le système natif des tuiles OSM : elles
# s'y affichent nettes partout dans le monde, là où Lambert 93 déformait tout
# ce qui sort de France. L'emprise est convertie dans le système du projet à
# la création.
CANVAS_CRS = QgsCoordinateReferenceSystem("EPSG:3857")
WGS84_CRS = QgsCoordinateReferenceSystem("EPSG:4326")

# Vue par défaut de la mini-carte tant qu'aucune adresse n'a été choisie :
# Vichy (Vichy Communauté) en France, l'Afrique de l'Ouest et centrale à
# l'international, où se trouvent la plupart des chantiers hors de France.
DEFAULT_VIEWS = {
    terr.FRANCE: (3.4265, 46.1278, 1500),         # ~3 km, ville entière
    terr.INTERNATIONAL: (8.0, 8.0, 3500000),      # ~7 000 km, continent
}
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
    """Étape 1 : territoire, recherche d'adresse, système de coordonnées et
    mini-carte OSM pour situer le projet."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._address_label = ""
        self._picked = None              # (lon, lat) de l'adresse choisie
        self._crs_manuel = False         # système choisi à la main : ne plus le proposer
        layout = QVBoxLayout(self)

        # ── Territoire ──────────────────────────────────────────────────
        ligne = QHBoxLayout()
        ligne.addWidget(QLabel(i18n.tr('wz_territoire')))
        self._radio_fr = QRadioButton(i18n.tr('wz_territoire_france'))
        self._radio_int = QRadioButton(i18n.tr('wz_territoire_international'))
        self._groupe = QButtonGroup(self)
        for radio in (self._radio_fr, self._radio_int):
            self._groupe.addButton(radio)
            ligne.addWidget(radio)
        ligne.addStretch()
        layout.addLayout(ligne)

        self._aide_int = QLabel(i18n.tr('wz_territoire_aide_int'))
        self._aide_int.setWordWrap(True)
        self._aide_int.setStyleSheet("color: #555;")
        layout.addWidget(self._aide_int)

        layout.addWidget(QLabel(i18n.tr('wz_adresse_aide')))

        self._search = BanSearchWidget()
        self._search.address_picked.connect(self._on_address_picked)
        layout.addWidget(self._search)

        # ── Système de coordonnées (international) ──────────────────────
        self._crs_box = QWidget()
        crs_layout = QVBoxLayout(self._crs_box)
        crs_layout.setContentsMargins(0, 0, 0, 0)
        crs_ligne = QHBoxLayout()
        crs_ligne.addWidget(QLabel(i18n.tr('wz_crs_label')))
        self._crs_widget = QgsProjectionSelectionWidget()
        self._crs_widget.crsChanged.connect(self._on_crs_changed)
        crs_ligne.addWidget(self._crs_widget, 1)
        crs_layout.addLayout(crs_ligne)
        crs_aide = QLabel(i18n.tr('wz_crs_aide'))
        crs_aide.setWordWrap(True)
        crs_aide.setStyleSheet("color: #555;")
        crs_layout.addWidget(crs_aide)
        layout.addWidget(self._crs_box)

        # ── Mini-carte ──────────────────────────────────────────────────
        self._canvas = QgsMapCanvas()
        self._canvas.setMinimumHeight(300)
        self._canvas.setDestinationCrs(CANVAS_CRS)
        self._canvas.setCanvasColor(QColor(235, 235, 230))

        osm = QgsRasterLayer(terr.URI_OSM, "OSM", "wms")
        self._osm_layer = osm
        if osm.isValid():
            self._canvas.setLayers([osm])

        self._canvas.setMapTool(QgsMapToolPan(self._canvas))
        layout.addWidget(self._canvas)

        self._marker = QgsVertexMarker(self._canvas)
        self._marker.setColor(QColor(220, 40, 40))
        self._marker.setIconType(QgsVertexMarker.IconType.ICON_CROSS)
        self._marker.setIconSize(14)
        self._marker.setPenWidth(3)
        self._marker.hide()

        # Le dernier territoire choisi est proposé : qui travaille en Afrique
        # n'a pas à rebasculer à chaque projet.
        (self._radio_int if terr.defaut() == terr.INTERNATIONAL
         else self._radio_fr).setChecked(True)
        self._groupe.buttonToggled.connect(self._on_territoire_toggled)
        self._appliquer_territoire()

    # ── Territoire ──────────────────────────────────────────────────────

    def territoire(self):
        return terr.INTERNATIONAL if self._radio_int.isChecked() else terr.FRANCE

    def _on_territoire_toggled(self, _button, checked):
        if checked:
            self._appliquer_territoire()

    def _appliquer_territoire(self):
        """Adapte recherche, système et vue au territoire. Une adresse choisie
        dans l'autre territoire est oubliée : elle n'y a plus de sens."""
        t = self.territoire()
        international = t == terr.INTERNATIONAL
        self._aide_int.setVisible(international)
        self._crs_box.setVisible(international)
        self._search.set_territoire(t)
        self._address_label = ""
        self._picked = None
        self._crs_manuel = False
        self._marker.hide()
        self._set_crs(terr.crs_propose(territoire=t) if not international else None)
        lon, lat, demi = DEFAULT_VIEWS[t]
        self._set_view(self._to_canvas(lon, lat), demi)

    # ── Système de coordonnées ──────────────────────────────────────────

    def _set_crs(self, crs):
        self._crs_programme = True
        try:
            self._crs_widget.setCrs(crs if crs is not None
                                    else QgsCoordinateReferenceSystem())
        finally:
            self._crs_programme = False

    def _on_crs_changed(self, _crs):
        if not getattr(self, '_crs_programme', False):
            self._crs_manuel = True

    def crs(self):
        """Système du projet : Lambert 93 en France, celui choisi ailleurs."""
        if self.territoire() == terr.FRANCE:
            return QgsCoordinateReferenceSystem(terr.L93)
        return self._crs_widget.crs()

    # ── Carte et adresse ────────────────────────────────────────────────

    def _to_canvas(self, lon, lat):
        transform = QgsCoordinateTransform(WGS84_CRS, CANVAS_CRS, QgsProject.instance())
        return transform.transform(QgsPointXY(lon, lat))

    def _set_view(self, point, half_extent_m):
        rect = QgsRectangle(
            point.x() - half_extent_m, point.y() - half_extent_m,
            point.x() + half_extent_m, point.y() + half_extent_m,
        )
        self._canvas.setExtent(rect)
        self._canvas.refresh()

    def _on_address_picked(self, lon, lat, label):
        self._address_label = label
        self._picked = (lon, lat)
        point = self._to_canvas(lon, lat)
        self._set_view(point, PICKED_HALF_EXTENT_M)
        self._marker.setCenter(point)
        self._marker.show()
        self._canvas.refresh()
        if self.territoire() == terr.INTERNATIONAL and not self._crs_manuel:
            self._set_crs(terr.crs_propose(lon, lat, terr.INTERNATIONAL))

    def address_label(self):
        return self._address_label

    def position(self):
        """(lon, lat) du chantier : l'adresse choisie, sinon le centre de la
        mini-carte — que l'utilisateur a pu déplacer après la recherche."""
        centre = self._canvas.extent().center()
        transform = QgsCoordinateTransform(CANVAS_CRS, WGS84_CRS, QgsProject.instance())
        p = transform.transform(centre)
        return p.x(), p.y()

    def extent_in(self, crs):
        """Étendue courante de la mini-carte, dans le système `crs`."""
        transform = QgsCoordinateTransform(CANVAS_CRS, crs, QgsProject.instance())
        return transform.transformBoundingBox(self._canvas.extent())

    def validate(self, parent):
        """Contrôle du système de coordonnées avant de quitter l'étape.

        Un système en degrés ou absent bloque. Un système qui déforme les
        longueurs au chantier (Lambert 93 à Dakar) est proposé à la
        correction, sans l'imposer : un bureau d'études peut avoir ses raisons.
        """
        lon, lat = self.position()
        crs = self.crs()
        if (self.territoire() == terr.INTERNATIONAL and not self._crs_manuel
                and not crs.isValid()):
            crs = terr.crs_propose(lon, lat, terr.INTERNATIONAL)
            self._set_crs(crs)
        diag = terr.diagnostic_crs(crs, lon, lat)
        if diag['ok']:
            return True
        message = terr.message_diagnostic(diag, lon, lat)
        if diag['motif'] in terr.MOTIFS_BLOQUANTS:
            QMessageBox.warning(parent, i18n.tr('wz_crs_titre'), message)
            return False
        reply = QMessageBox.question(
            parent, i18n.tr('wz_crs_titre'),
            i18n.tr('wz_crs_continuer', message=message),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes


class _BasemapsPage(QWidget):
    """Étape 2 : choix des fonds de plan à charger, selon le territoire."""

    # (clé run_fond_projet, clé i18n, coché par défaut)
    CHOIX = {
        terr.FRANCE: [
            ('osm', 'wz_fond_osm', True),
            ('ortho', 'wz_fond_ortho', True),
            ('ban', 'wz_fond_ban', False),
            ('noms_voie', 'wz_fond_noms_voie', False),
            ('pci_parcelles', 'wz_fond_parcelles', False),
            ('pci_bati', 'wz_fond_bati', False),
        ],
        # Le bâti est coché d'office à l'international : sans lui, pas de
        # branchements automatiques, et rien d'autre ne le remplace.
        terr.INTERNATIONAL: [
            ('osm', 'wz_fond_osm_int', True),
            ('ortho', 'wz_fond_esri', True),
            ('pci_bati', 'wz_fond_bati_osm', True),
        ],
    }
    RECAP = {
        terr.FRANCE: {
            'osm': 'wz_fond_osm_court', 'ortho': 'wz_fond_ortho',
            'ban': 'wz_fond_ban', 'noms_voie': 'wz_fond_noms_voie_court',
            'pci_parcelles': 'wz_fond_parcelles', 'pci_bati': 'wz_fond_bati',
        },
        terr.INTERNATIONAL: {
            'osm': 'wz_fond_osm_int', 'ortho': 'wz_fond_esri',
            'pci_bati': 'wz_fond_bati_osm',
        },
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n.tr('wz_fonds_aide')))

        self._group = QGroupBox(i18n.tr('wz_fonds_titre'))
        self._group_layout = QVBoxLayout()
        self._group.setLayout(self._group_layout)
        layout.addWidget(self._group)

        self._aide_int = QLabel(i18n.tr('wz_fond_aide_int'))
        self._aide_int.setWordWrap(True)
        self._aide_int.setStyleSheet("color: #555;")
        layout.addWidget(self._aide_int)
        layout.addStretch()

        self._territoire = None
        self._checks = {}
        self.set_territoire(terr.FRANCE)

    def set_territoire(self, territoire):
        if territoire == self._territoire:
            return
        self._territoire = territoire
        for cb in self._checks.values():
            self._group_layout.removeWidget(cb)
            cb.deleteLater()
        self._checks = {}
        for key, cle, checked in self.CHOIX[territoire]:
            cb = QCheckBox(i18n.tr(cle))
            cb.setChecked(checked)
            self._checks[key] = cb
            self._group_layout.addWidget(cb)
        self._aide_int.setVisible(territoire == terr.INTERNATIONAL)

    def options(self):
        return {key: cb.isChecked() for key, cb in self._checks.items()}

    def libelles(self):
        return {key: i18n.tr(cle) for key, cle in self.RECAP[self._territoire].items()}


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
        self._text.setMaximumHeight(120)
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

    def refresh(self, address_label, basemap_options, config_page,
                territoire_label="", crs_label="", basemap_labels=None):
        basemap_labels = basemap_labels or {}
        chosen = [basemap_labels.get(k, k) for k, v in basemap_options.items() if v]
        lines = [
            i18n.tr('wz_recap_territoire'),
            f"  {territoire_label} — {crs_label}",
            "",
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
        self.setMinimumSize(560, 560)

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
            t = self._address_page.territoire()
            crs = self._address_page.crs()
            self._recap_page.refresh(
                address_label,
                self._basemaps_page.options(),
                self._config_page,
                territoire_label=i18n.tr('wz_territoire_france' if t == terr.FRANCE
                                         else 'wz_territoire_international'),
                crs_label=(f"{crs.authid()} ({crs.description()})"
                           if crs.isValid() else "?"),
                basemap_labels=self._basemaps_page.libelles(),
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
        if self._current_index() == 0:
            if not self._address_page.validate(self):
                return
            self._basemaps_page.set_territoire(self._address_page.territoire())
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

        # Territoire et système du PROJET avant toute couche : _create_layer
        # en hérite, et les fonds téléchargés (bâti) sont écrits dedans.
        project = QgsProject.instance()
        crs = self._address_page.crs()
        terr.definir(self._address_page.territoire(), project)
        project.setCrs(crs)
        self._plugin.appliquer_territoire()

        canvas = self._iface.mapCanvas()
        canvas.setDestinationCrs(crs)
        canvas.setExtent(self._address_page.extent_in(crs))
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
