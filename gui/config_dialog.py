# -*- coding: utf-8 -*-
from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QFormLayout,
    QComboBox, QDialogButtonBox, QTabWidget, QWidget,
)
from qgis.core import QgsProject, QgsWkbTypes

from ..tools import i18n

from .quick_config_widgets import (  # noqa: F401
    SKETCHES_PREFIX,
    SETTINGS_KEY,
    MATERIAUX,
    MATERIAUX_REMBLAI,
    INITIAL_DEFAULTS,
    get_default_params,
    get_cubature_config,
    TrenchSchemaWidget,
    CubatureSchemaWidget,
    NetworkSchemaWidget,
    ReseauDefautWidget,
    CubatureConfigWidget,
    RemblaiConfigWidget,
)

ROLES = {
    'conduite':    QgsWkbTypes.LineGeometry,
    'branchement': QgsWkbTypes.LineGeometry,
    'regard':      QgsWkbTypes.PointGeometry,
    'tabouret':    QgsWkbTypes.PointGeometry,
}

# Clés i18n, pas des libellés : traduire avec i18n.tr au moment de l'affichage.
LABELS = {
    'conduite':    'qc_conduites',
    'branchement': 'qc_branchements',
    'regard':      'qc_regards',
    'tabouret':    'qc_tabourets',
}


class ConfigDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.setWindowTitle(i18n.tr('panel_config'))
        self.setMinimumWidth(450)

        self.combos = {}
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # ── Onglet 1 : Réseau par défaut ────────────────────────────────
        self._reseau_widget = ReseauDefautWidget()
        tabs.addTab(self._reseau_widget, i18n.tr('wz_reseau_defaut'))

        # ── Onglet 2 : Couches ──────────────────────────────────────────
        tab_couches = QWidget()
        couches_layout = QVBoxLayout(tab_couches)

        for reseau in ("EU", "EP"):
            group = QGroupBox(i18n.tr('qc_reseau', code=reseau))
            form = QFormLayout()
            for role, geom_type in ROLES.items():
                combo = QComboBox()
                combo.addItem(i18n.tr('qc_non_configure'), None)
                self._populate_combo(combo, geom_type)
                key = f"{role}_{reseau.lower()}"
                self.combos[key] = combo
                form.addRow(i18n.tr('qc_couche_role',
                                    role=i18n.tr(LABELS[role])), combo)
            group.setLayout(form)
            couches_layout.addWidget(group)

        couches_layout.addStretch()
        tabs.addTab(tab_couches, i18n.tr('qc_couches'))

        # ── Onglet 3 : Cubature ──────────────────────────────────────────
        self._cubature_widget = CubatureConfigWidget()
        tabs.addTab(self._cubature_widget, i18n.tr('wz_cubature'))

        # ── Onglet 4 : Remblai ──────────────────────────────────────────
        self._remblai_widget = RemblaiConfigWidget()
        tabs.addTab(self._remblai_widget, i18n.tr('wz_remblai'))

        # Épaisseur de lit de pose partagée entre l'onglet Cubature et le
        # schéma de l'onglet Remblai.
        ep_lit_spin = self._cubature_widget._cub_widgets['ep_lit_pose']
        ep_lit_spin.valueChanged.connect(self._remblai_widget.set_ep_lit_pose)
        self._remblai_widget.set_ep_lit_pose(ep_lit_spin.value())

        main_layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _populate_combo(self, combo, geom_type):
        for layer in QgsProject.instance().mapLayers().values():
            if not hasattr(layer, 'geometryType'):
                continue
            if layer.geometryType() == geom_type:
                combo.addItem(layer.name(), layer.id())

    def _load_settings(self):
        s = QSettings()
        for key, combo in self.combos.items():
            saved_id = s.value(SKETCHES_PREFIX + f"couche_{key}")
            if saved_id:
                idx = combo.findData(saved_id)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
        # Les 3 widgets de config rapide chargent déjà leurs propres
        # réglages dans leur __init__.

    def _save_and_accept(self):
        s = QSettings()
        for key, combo in self.combos.items():
            layer_id = combo.currentData()
            if layer_id:
                s.setValue(SKETCHES_PREFIX + f"couche_{key}", layer_id)
            else:
                s.remove(SKETCHES_PREFIX + f"couche_{key}")

        self._reseau_widget.save_settings()
        self._cubature_widget.save_settings()
        self._remblai_widget.save_settings()

        self.accept()
