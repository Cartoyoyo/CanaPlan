# -*- coding: utf-8 -*-
"""Réglages d'impression d'un plan, sous forme de bloc réutilisable.

Ces réglages vivent à deux endroits : dans la fenêtre d'export, où ils
accompagnent le choix des sorties, et dans PrintDialog, que l'outil de pose
rouvre quand on presse Échap pour changer d'échelle sans tout reprendre.
D'où ce widget commun plutôt qu'une copie de chaque côté.

Les explications de portée sont en infobulle : écrites en toutes lettres,
elles ajoutaient une centaine de pixels de hauteur à une fenêtre qui doit
déjà loger toutes les sorties.
"""
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QSpinBox,
    QLabel, QHBoxLayout, QRadioButton, QButtonGroup, QCheckBox,
)
from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject

from ..tools import i18n

FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# None = entrée personnalisée
SCALES = [150, 200, 250, 500, 1000, 2000, 5000, 10000, None]

# (clé du libellé, dpi ou None, clé de la note) — traduits à l'affichage
_DPI_PRESETS = [
    ('pd_dpi_legere',   96,   'pd_dpi_legere_note'),
    ('pd_dpi_standard', 150,  'pd_dpi_standard_note'),
    ('pd_dpi_bonne',    200,  'pd_dpi_bonne_note'),
    ('pd_dpi_haute',    300,  'pd_dpi_haute_note'),
    ('pd_dpi_perso',    None, 'pd_dpi_perso_note'),
]
_DPI_DEFAULT_IDX = 1   # 150 dpi par défaut


class PrintSettingsWidget(QWidget):
    """Titre, format, orientation, échelle, résolution et mode de cadrage."""

    def __init__(self, parent=None, compact=False, disposition='formulaire'):
        super().__init__(parent)
        self._disposition = disposition

        default_title = QgsProject.instance().title() or i18n.tr('pd_plan_reseau')
        self.titre_edit = QLineEdit(default_title)

        self.format_combo = QComboBox()
        self.format_combo.addItems(list(FORMATS.keys()))
        self.format_combo.setCurrentText("A3")
        self.format_combo.setToolTip(i18n.tr('pd_format'))

        self.orient_combo = QComboBox()
        # La valeur portée est le code ('paysage'/'portrait') : le texte
        # affiché suit la langue, le reste du code ne dépend pas de lui.
        self.orient_combo.addItem(i18n.tr('pd_paysage'), 'paysage')
        self.orient_combo.addItem(i18n.tr('pd_portrait'), 'portrait')
        self.orient_combo.setToolTip(i18n.tr('pd_orientation'))

        self.scale_combo = QComboBox()
        for s in SCALES:
            if s is None:
                self.scale_combo.addItem(i18n.tr('pd_echelle_perso'), None)
            else:
                self.scale_combo.addItem(f"1 : {s:,}".replace(",", " "), s)
        self.scale_combo.setCurrentIndex(SCALES.index(1000))
        self.scale_combo.setToolTip(i18n.tr('pd_echelle'))

        # Champ de saisie d'échelle personnalisée (masqué par défaut)
        self._custom_widget = QWidget()
        custom_row = QHBoxLayout(self._custom_widget)
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.addWidget(QLabel("1 /"))
        self._custom_spin = QSpinBox()
        self._custom_spin.setRange(1, 1000000)
        self._custom_spin.setValue(300)
        self._custom_spin.setSingleStep(50)
        self._custom_spin.setGroupSeparatorShown(True)
        custom_row.addWidget(self._custom_spin)
        self._custom_widget.setVisible(False)
        self.scale_combo.currentIndexChanged.connect(self._on_scale_changed)

        # ── Résolution PDF ────────────────────────────────────────────────
        self.dpi_combo = QComboBox()
        for cle_label, dpi, _cle_note in _DPI_PRESETS:
            self.dpi_combo.addItem(i18n.tr(cle_label), dpi)
        self.dpi_combo.setCurrentIndex(_DPI_DEFAULT_IDX)

        self._dpi_custom_widget = QWidget()
        dpi_custom_row = QHBoxLayout(self._dpi_custom_widget)
        dpi_custom_row.setContentsMargins(0, 0, 0, 0)
        self._dpi_custom_spin = QSpinBox()
        self._dpi_custom_spin.setRange(50, 300)
        self._dpi_custom_spin.setValue(150)
        self._dpi_custom_spin.setSingleStep(25)
        self._dpi_custom_spin.setSuffix(" dpi")
        dpi_custom_row.addWidget(self._dpi_custom_spin)
        dpi_custom_row.addStretch()
        self._dpi_custom_widget.setVisible(False)

        # En mode compact la note du DPI passe en infobulle ; sinon elle
        # reste écrite, PrintDialog ayant la place.
        self._compact = compact
        self._dpi_note = QLabel()
        self._dpi_note.setStyleSheet("color: #555; font-style: italic;")
        self._dpi_note.setWordWrap(True)
        self._dpi_note.setVisible(not compact)
        self.dpi_combo.currentIndexChanged.connect(self._on_dpi_changed)

        self.format_combo.currentIndexChanged.connect(self._suggest_dpi)

        # ── Cadrage des planches ──────────────────────────────────────────
        self.rb_manuel = QRadioButton(i18n.tr('pd_cadrage_manuel'))
        self.rb_auto = QRadioButton(i18n.tr('pd_cadrage_auto'))
        # Le cadrage automatique est le défaut : il couvre tout le réseau
        # sans intervention, la pose manuelle restant là pour les cas où l'on
        # veut choisir soi-même ses planches.
        self.rb_auto.setChecked(True)
        self._grp_cadrage = QButtonGroup(self)
        self._grp_cadrage.addButton(self.rb_manuel)
        self._grp_cadrage.addButton(self.rb_auto)
        self.rb_manuel.setToolTip(i18n.tr('pd_cadrage_note_manuel'))
        self.rb_auto.setToolTip(i18n.tr('pd_cadrage_note_auto'))

        self._cadrage_note = QLabel()
        self._cadrage_note.setStyleSheet("color: #555; font-style: italic;")
        self._cadrage_note.setWordWrap(True)
        self._cadrage_note.setVisible(not compact)
        self.rb_manuel.toggled.connect(self._on_cadrage_changed)

        # ── Plan d'ensemble ───────────────────────────────────────────────
        # Coché par défaut : une planche seule ne dit pas où elle se situe, et
        # c'était jusqu'ici une question posée au milieu de l'export.
        self.cb_ensemble = QCheckBox(i18n.tr('pd_plan_ensemble_case'))
        self.cb_ensemble.setChecked(True)
        self.cb_ensemble.setToolTip(i18n.tr('pd_plan_ensemble_note'))

        self._on_dpi_changed()
        self._on_cadrage_changed()

        # ── Mise en page ──────────────────────────────────────────────────
        if disposition == 'inline':
            self._monter_en_ligne()
            return

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow(i18n.tr('pd_titre_plan'), self.titre_edit)
        if compact:
            # Format et orientation sur une seule ligne : deux listes courtes
            # côte à côte valent mieux que deux lignes de formulaire.
            paire = QWidget()
            ligne = QHBoxLayout(paire)
            ligne.setContentsMargins(0, 0, 0, 0)
            ligne.setSpacing(6)
            ligne.addWidget(self.format_combo)
            ligne.addWidget(self.orient_combo, 1)
            form.addRow(i18n.tr('pd_format'), paire)
        else:
            form.addRow(i18n.tr('pd_format'), self.format_combo)
            form.addRow(i18n.tr('pd_orientation'), self.orient_combo)
        form.addRow(i18n.tr('pd_echelle'), self.scale_combo)
        form.addRow("", self._custom_widget)
        form.addRow(i18n.tr('pd_resolution'), self.dpi_combo)
        form.addRow("", self._dpi_custom_widget)
        form.addRow("", self._dpi_note)
        form.addRow(i18n.tr('pd_cadrage'), self.rb_manuel)
        form.addRow("", self.rb_auto)
        form.addRow("", self._cadrage_note)
        form.addRow("", self.cb_ensemble)

    # ------------------------------------------------------------------ inline

    def _monter_en_ligne(self):
        """Réglages tassés : les listes nues sur une ligne, le reste dessous.

        `ligne_combos` est exposé pour que l'appelant le pose où il veut —
        en pratique au bout de la case « Plan PDF ». Les listes n'ont plus de
        libellé : leur contenu se lit tout seul (A3, Paysage, 1 : 1000) et
        l'infobulle nomme le réglage.
        """
        self.ligne_combos = QWidget()
        ligne = QHBoxLayout(self.ligne_combos)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(4)
        for widget in (self.format_combo, self.orient_combo, self.scale_combo,
                       self._custom_widget, self.dpi_combo,
                       self._dpi_custom_widget):
            ligne.addWidget(widget)
        ligne.addStretch()

        # Le titre et le mode de cadrage ne tiennent pas sur la même ligne :
        # ils forment le corps du widget, que l'appelant place en dessous.
        corps = QFormLayout(self)
        corps.setContentsMargins(0, 0, 0, 0)
        corps.setSpacing(4)
        corps.addRow(i18n.tr('pd_titre_plan'), self.titre_edit)
        corps.addRow(i18n.tr('pd_cadrage'), self.rb_manuel)
        corps.addRow("", self.rb_auto)
        corps.addRow("", self.cb_ensemble)

    # ------------------------------------------------------------------ slots

    def _on_scale_changed(self, index=0):
        self._custom_widget.setVisible(self.scale_combo.currentData() is None)

    def _on_dpi_changed(self):
        idx = self.dpi_combo.currentIndex()
        if 0 <= idx < len(_DPI_PRESETS):
            note = i18n.tr(_DPI_PRESETS[idx][2])
            self._dpi_note.setText(note)
            self.dpi_combo.setToolTip(note)
        self._dpi_custom_widget.setVisible(self.dpi_combo.currentData() is None)

    def _on_cadrage_changed(self):
        self._cadrage_note.setText(
            i18n.tr('pd_cadrage_note_manuel') if self.rb_manuel.isChecked()
            else i18n.tr('pd_cadrage_note_auto'))

    def _suggest_dpi(self):
        """Suggère 150 dpi pour A1/A0, 200 pour A2/A3, 300 pour A4.
        N'écrase pas une saisie personnalisée déjà active."""
        if self.dpi_combo.currentData() is None:
            return
        suggested = {"A0": 1, "A1": 1, "A2": 2, "A3": 2, "A4": 3}.get(
            self.format_combo.currentText(), 1)
        self.dpi_combo.blockSignals(True)
        self.dpi_combo.setCurrentIndex(suggested)
        self.dpi_combo.blockSignals(False)
        self._on_dpi_changed()

    # ------------------------------------------------------------------ résultat

    def get_settings(self):
        fmt = self.format_combo.currentText()
        w_mm, h_mm = FORMATS[fmt]
        if self.orient_combo.currentData() == 'portrait':
            w_mm, h_mm = h_mm, w_mm

        scale = self.scale_combo.currentData()
        if scale is None:
            scale = self._custom_spin.value()

        dpi = self.dpi_combo.currentData()
        if dpi is None:
            dpi = self._dpi_custom_spin.value()

        return {
            "titre":        (self.titre_edit.text().strip()
                             or i18n.tr('pd_plan_reseau')),
            "format":       fmt,
            "orientation":  self.orient_combo.currentData(),
            "w_mm":         float(w_mm),
            "h_mm":         float(h_mm),
            "echelle":      scale,
            "dpi":          dpi,
            "cadrage_auto":  self.rb_auto.isChecked(),
            "plan_ensemble": self.cb_ensemble.isChecked(),
        }
