# gui/export_dialog.py

import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QFrame, QDialogButtonBox, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QWidget, QSizePolicy, QGridLayout,
)
from qgis.PyQt.QtCore import Qt

from ..tools import i18n
from .print_settings_widget import PrintSettingsWidget

_FORMATS = ['A4', 'A3', 'A2', 'A1', 'A0']

# Formats papier de la coupe type, alignés sur PAPER_SIZES du dialogue de coupe
_COUPE_PAPIERS = ['a4_paysage', 'a3_paysage', 'a4_portrait', 'a3_portrait']

# Retrait des réglages sous leur case maîtresse
_INDENT = 18


class ExportDialog(QDialog):
    """Dialogue de choix des exports : plan, profils, cubature, coupes types.

    Tout tient dans une seule fenêtre : l'utilisateur la parcourt de haut en
    bas et coche ce qu'il veut. Les explications de portée (ce que l'export
    groupé ne sait pas faire) sont en infobulle plutôt qu'en toutes lettres,
    pour que la fenêtre reste d'un seul tenant à l'écran.
    """

    def __init__(self, parent=None, default_dir=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr('exp_titre'))
        self.setMinimumWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        self._bloc_tout_en_un(layout)

        # Les réglages du plan sont montés avant le bloc Plan : leurs listes
        # se posent au bout de la case « Plan PDF ».
        self.reglages = PrintSettingsWidget(self, compact=True,
                                            disposition='inline')

        self._bloc_plan(layout)
        layout.addWidget(_hsep())
        self._bloc_profils(layout)
        layout.addWidget(_hsep())
        self._bloc_cubature(layout)
        layout.addWidget(_hsep())
        self._bloc_coupes(layout)
        layout.addWidget(_hsep())
        self._bloc_dossier(layout, default_dir)
        layout.addWidget(_hsep())

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(i18n.tr('exp_bouton'))
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ------------------------------------------------------------------ blocs

    def _bloc_plan(self, layout):
        layout.addWidget(_titre(i18n.tr('exp_plan_carto')))

        self.cb_pdf = QCheckBox(i18n.tr('exp_plan_pdf'))
        self.cb_pdf.setChecked(True)
        self.cb_dxf = QCheckBox(i18n.tr('exp_plan_dxf'))

        # Format, orientation, échelle et résolution au bout de la case, sans
        # libellés : chaque liste se lit d'elle-même et son infobulle la nomme.
        ligne = QHBoxLayout()
        ligne.setSpacing(8)
        ligne.addWidget(self.cb_pdf)
        ligne.addWidget(self.reglages.ligne_combos, 1)
        layout.addLayout(ligne)

        layout.addWidget(self.cb_dxf)

        # Titre du plan et mode de cadrage, en retrait sous les cases.
        retrait = QHBoxLayout()
        retrait.setContentsMargins(_INDENT, 0, 0, 0)
        retrait.addWidget(self.reglages)
        layout.addLayout(retrait)

        self.cb_pdf.toggled.connect(self._sync_impression)
        self.cb_dxf.toggled.connect(self._sync_impression)
        self._sync_impression()

    def _bloc_profils(self, layout):
        layout.addWidget(_titre(i18n.tr('exp_profils')))

        self.cb_eu,  self.fmt_eu  = self._profil_row(
            layout, i18n.tr('exp_profils_reseau', code="EU"))
        self.cb_ep,  self.fmt_ep  = self._profil_row(
            layout, i18n.tr('exp_profils_reseau', code="EP"))
        self.cb_grp, self.fmt_grp, self.ref_grp = self._profil_groupe_row(layout)

    def _bloc_cubature(self, layout):
        layout.addWidget(_titre(i18n.tr('exp_cubature_titre')))

        self.cb_cubature = QCheckBox(i18n.tr('exp_cub_inclure'))
        self.cb_cubature.setToolTip(i18n.tr('exp_cub_note'))
        layout.addWidget(self.cb_cubature)

        # Tous les réglages vivent dans ce conteneur : une seule connexion
        # suffit à les activer ou les griser avec la case maîtresse.
        self._cub_box = QWidget()
        box = QVBoxLayout(self._cub_box)
        box.setContentsMargins(_INDENT, 0, 0, 0)
        box.setSpacing(4)

        self.cub_perimetre = QComboBox()
        self.cub_perimetre.addItem(i18n.tr('cb_tout'),    'tout')
        self.cub_perimetre.addItem(i18n.tr('cb_eu_seul'), 'EU')
        self.cub_perimetre.addItem(i18n.tr('cb_ep_seul'), 'EP')

        self.cub_conduites = QCheckBox(i18n.tr('cb_conduites'))
        self.cub_conduites.setChecked(True)
        self.cub_branchements = QCheckBox(i18n.tr('cb_branchements'))
        self.cub_branchements.setChecked(True)

        box.addWidget(_hrow(
            QLabel(i18n.tr('exp_cub_perimetre')), self.cub_perimetre,
            self.cub_conduites, self.cub_branchements))

        self.cub_pdf = QCheckBox("PDF")
        self.cub_pdf.setChecked(True)
        self.cub_xlsx = QCheckBox("XLSX")
        self.cub_csv = QCheckBox("CSV")

        box.addWidget(_hrow(
            QLabel(i18n.tr('exp_cub_formats')),
            self.cub_pdf, self.cub_xlsx, self.cub_csv))

        self._cub_box.setEnabled(False)
        self.cb_cubature.toggled.connect(self._cub_box.setEnabled)
        layout.addWidget(self._cub_box)

    def _bloc_coupes(self, layout):
        layout.addWidget(_titre(i18n.tr('exp_coupes_titre')))

        self.cb_coupe_eu = QCheckBox(i18n.tr('exp_coupe_type', code="EU"))
        self.cb_coupe_ep = QCheckBox(i18n.tr('exp_coupe_type', code="EP"))
        for case in (self.cb_coupe_eu, self.cb_coupe_ep):
            case.setToolTip(i18n.tr('exp_coupe_note'))
        layout.addWidget(_hrow(self.cb_coupe_eu, self.cb_coupe_ep))

        self._coupe_box = QWidget()
        box = QHBoxLayout(self._coupe_box)
        box.setContentsMargins(_INDENT, 0, 0, 0)
        box.setSpacing(8)

        self.coupe_papier = QComboBox()
        for cle in _COUPE_PAPIERS:
            self.coupe_papier.addItem(_libelle_papier(cle), cle)
        self.coupe_fichier = QComboBox()
        self.coupe_fichier.addItems(['PDF', 'PNG'])
        self.coupe_fichier.setFixedWidth(70)

        box.addWidget(QLabel(i18n.tr('exp_coupe_format')))
        box.addWidget(self.coupe_papier)
        box.addWidget(self.coupe_fichier)
        box.addStretch()

        self._coupe_box.setEnabled(False)
        self.cb_coupe_eu.toggled.connect(self._sync_coupe_box)
        self.cb_coupe_ep.toggled.connect(self._sync_coupe_box)
        layout.addWidget(self._coupe_box)

    _STYLE_RACCOURCI = (
        "QPushButton {{"
        "  background-color: {fond}; color: #FFFFFF;"
        "  font-weight: bold; border: none; border-radius: 3px;"
        "  padding: 6px 14px;"
        "}}"
        "QPushButton:hover  {{ background-color: {survol}; }}"
        "QPushButton:pressed{{ background-color: {appui}; }}"
    )

    def _bloc_tout_en_un(self, layout):
        """Raccourcis « tout en un », dans le coin haut droit de la fenêtre.

        Ils ignorent délibérément les cases cochées plus bas : ce sont des
        boutons de sortie de secours, pas des options supplémentaires. Le
        coin, à l'écart de la colonne d'options, et la couleur pleine disent
        l'un comme l'autre qu'ils ne se combinent avec rien.

        Deux sorties pour le même contenu : l'archive ZIP garde les pièces
        séparées et rééditables (DXF, XLSX), le PDF complet les assemble en un
        seul document à faire circuler. Deux couleurs distinctes, parce que le
        résultat n'est pas du tout le même.
        """
        self._tout_en_un = False
        self._pdf_complet = False

        btn_pdf = QPushButton(i18n.tr('exp_pdf_complet'))
        btn_pdf.setToolTip("%s\n\n%s" % (i18n.tr('exp_pdf_complet_resume'),
                                         i18n.tr('exp_pdf_complet_note')))
        btn_pdf.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pdf.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_pdf.setStyleSheet(self._STYLE_RACCOURCI.format(
            fond="#6A1B9A", survol="#7E24B0", appui="#4E1273"))
        btn_pdf.clicked.connect(self._on_pdf_complet)

        btn_zip = QPushButton(i18n.tr('exp_tout_en_un'))
        # Le résumé d'abord : c'est ce qu'on veut lire en survolant, le détail
        # des cas particuliers vient après.
        btn_zip.setToolTip("%s\n\n%s" % (i18n.tr('exp_tout_en_un_resume'),
                                         i18n.tr('exp_tout_en_un_note')))
        btn_zip.setCursor(Qt.CursorShape.PointingHandCursor)
        # Le bouton garde la largeur de son libellé, quelle que soit la place
        # laissée par le ressort : dans un coin, un bouton étiré n'en est plus
        # un. La hauteur suit le thème, la traduction la largeur.
        btn_zip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn_zip.setStyleSheet(self._STYLE_RACCOURCI.format(
            fond="#CC0000", survol="#E01010", appui="#A30000"))
        btn_zip.clicked.connect(self._on_tout_en_un)

        coin = QHBoxLayout()
        coin.setContentsMargins(0, 0, 0, 0)
        coin.addStretch()          # pousse les boutons dans le coin droit
        coin.addWidget(btn_pdf)
        coin.addWidget(btn_zip)
        layout.addLayout(coin)

    def _sync_impression(self):
        """Les réglages ne valent que pour le plan : grisés sans lui.

        Grisés plutôt que masqués, pour que la fenêtre ne change pas de
        taille à chaque clic sur une case.
        """
        actif = self.cb_pdf.isChecked() or self.cb_dxf.isChecked()
        self.reglages.setEnabled(actif)
        self.reglages.ligne_combos.setEnabled(actif)

    def get_print_settings(self):
        """Réglages d'impression, au format attendu par PrintTool."""
        return self.reglages.get_settings()

    def _bloc_dossier(self, layout, default_dir):
        layout.addWidget(_titre(i18n.tr('exp_dossier')))

        dir_row = QHBoxLayout()
        self.dir_edit = QLineEdit(default_dir or os.path.expanduser("~"))
        self.dir_edit.setReadOnly(False)
        btn_browse = QPushButton(i18n.tr('parcourir'))
        btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_browse)
        layout.addLayout(dir_row)

    # ------------------------------------------------------------------ slots

    def _sync_coupe_box(self):
        self._coupe_box.setEnabled(
            self.cb_coupe_eu.isChecked() or self.cb_coupe_ep.isChecked())

    def _browse_dir(self):
        start = self.dir_edit.text().strip() or os.path.expanduser("~")
        if not os.path.isdir(start):
            start = os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, i18n.tr('exp_dossier_titre'), start)
        if path:
            self.dir_edit.setText(path)

    def _on_accept(self):
        """Valide le dossier puis ferme. Retourne False si le dossier cloche."""
        path = self.dir_edit.text().strip()
        if not path or not os.path.isdir(path):
            QMessageBox.warning(
                self, i18n.tr('exp_dossier_invalide'),
                i18n.tr('exp_dossier_absent'))
            return False
        self.accept()
        return True

    def _on_tout_en_un(self):
        # Le drapeau ne se lève que si le dossier est valide : sinon la
        # fenêtre reste ouverte et un nouveau clic sur Exporter ne doit pas
        # partir en mode tout en un.
        self._tout_en_un = self._on_accept()

    def _on_pdf_complet(self):
        # Même précaution que ci-dessus. Les deux raccourcis partagent la
        # chaîne de production : c'est le drapeau qui décide de la sortie.
        self._pdf_complet = self._on_accept()

    # ------------------------------------------------------------------ lignes

    def _profil_row(self, layout, label):
        row = QHBoxLayout()
        cb = QCheckBox(label)
        combo = QComboBox()
        combo.addItems(_FORMATS)
        combo.setCurrentText('A3')
        combo.setEnabled(False)
        combo.setFixedWidth(60)
        cb.toggled.connect(combo.setEnabled)
        row.addWidget(cb, 1)
        row.addWidget(combo)
        layout.addLayout(row)
        return cb, combo

    def _profil_groupe_row(self, layout):
        row = QHBoxLayout()
        cb = QCheckBox(i18n.tr('exp_profils_groupes'))

        ref_lbl = QLabel(i18n.tr('exp_ref'))
        ref_lbl.setEnabled(False)
        ref_combo = QComboBox()
        ref_combo.addItems(['EU', 'EP'])
        ref_combo.setFixedWidth(50)
        ref_combo.setEnabled(False)

        fmt_combo = QComboBox()
        fmt_combo.addItems(_FORMATS)
        fmt_combo.setCurrentText('A3')
        fmt_combo.setEnabled(False)
        fmt_combo.setFixedWidth(60)

        def _on_toggle(checked):
            ref_lbl.setEnabled(checked)
            ref_combo.setEnabled(checked)
            fmt_combo.setEnabled(checked)

        cb.toggled.connect(_on_toggle)

        row.addWidget(cb, 1)
        row.addWidget(ref_lbl)
        row.addWidget(ref_combo)
        row.addWidget(fmt_combo)
        layout.addLayout(row)
        return cb, fmt_combo, ref_combo

    # ------------------------------------------------------------------ résultat

    def get_choices(self):
        return {
            'plan_pdf':              self.cb_pdf.isChecked(),
            'plan_dxf':              self.cb_dxf.isChecked(),
            'profil_eu':             self.cb_eu.isChecked(),
            'profil_eu_format':      self.fmt_eu.currentText(),
            'profil_ep':             self.cb_ep.isChecked(),
            'profil_ep_format':      self.fmt_ep.currentText(),
            'profil_groupe':         self.cb_grp.isChecked(),
            'profil_groupe_format':  self.fmt_grp.currentText(),
            'profil_groupe_reseau':  self.ref_grp.currentText(),
            'cubature':              self.cb_cubature.isChecked(),
            'cubature_perimetre':    self.cub_perimetre.currentData(),
            'cubature_conduites':    self.cub_conduites.isChecked(),
            'cubature_branchements': self.cub_branchements.isChecked(),
            'cubature_pdf':          self.cub_pdf.isChecked(),
            'cubature_xlsx':         self.cub_xlsx.isChecked(),
            'cubature_csv':          self.cub_csv.isChecked(),
            'coupe_eu':              self.cb_coupe_eu.isChecked(),
            'coupe_ep':              self.cb_coupe_ep.isChecked(),
            'coupe_papier':          self.coupe_papier.currentData(),
            'coupe_fichier':         self.coupe_fichier.currentText().lower(),
            'tout_en_un':            self._tout_en_un,
            'pdf_complet':           self._pdf_complet,
            'output_dir':            self.dir_edit.text().strip(),
        }


# ─── Petits assembleurs de widgets ───────────────────────────────────────────

def _titre(texte):
    lbl = QLabel(texte)
    lbl.setStyleSheet("font-weight: bold;")
    return lbl


def _hrow(*widgets):
    """Widgets côte à côte, poussés à gauche."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(10)
    for ww in widgets:
        h.addWidget(ww)
    h.addStretch()
    return w


def _libelle_papier(cle):
    """« A4 paysage » depuis une clé de PAPER_SIZES, dans la langue courante."""
    format_court, orientation = cle.split('_')
    return f"{format_court.upper()} {i18n.tr('pd_' + orientation).lower()}"


def _vsep():
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep


def _hsep():
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Sunken)
    return sep
