# gui/stareau_export_dialog.py
"""Dialogue d'export StaR-Eau : saisie des metadonnees de chantier.

Le geostandard StaR-Eau impose une trentaine de colonnes NOT NULL a valeurs
controlees que le plugin ne stocke pas (maitre d'ouvrage, exploitant, mode de
circulation, type de pose, classe de precision...). Ces valeurs sont
constantes a l'echelle d'un chantier : on les saisit ici, une fois, au moment
de l'export.

Toutes les listes deroulantes sont alimentees par les listes de valeurs
officielles (tools/stareau_values.py) : il est structurellement impossible de
produire un code invalide.

Les valeurs saisies sont memorisees dans QgsSettings et reproposees au
chantier suivant.
"""

import os
from datetime import datetime

from qgis.PyQt.QtCore import QDate, QEvent, Qt, QTimer

from ..tools import i18n
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)
from qgis.core import QgsSettings

from ..tools import stareau_values as sv

_SETTINGS_PREFIX = "CanaPlan/stareau/"

# Valeur affichee dans la combo « contenu EP » pour laisser la colonne vide.
_EP_VIDE = 'se_ep_vide'

# Entree de tete de la combo « materiau des conduites » : le materiau du
# projet fait foi, et les objets sans materiau sortent en « non renseigne ».
_MAT_PROJET = 'se_mat_projet'

# Materiaux proposes en repli, « Non renseigne » exclu : c'est deja le sens
# de l'entree de tete, l'y laisser ferait deux choix pour un meme resultat.
_MATERIAUX_REPLI = tuple(
    (code, libelle) for code, libelle in sv.MATERIAUX_CONDUITE if code != "nr")


class StarEauExportDialog(QDialog):
    """Onglets Fichier / Chantier / Réseau / Ouvrages / Contrôle."""

    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.setWindowTitle(i18n.tr('se_titre'))
        self.setMinimumSize(720, 620)

        self._issues = []

        layout = QVBoxLayout(self)

        intro = QLabel(
            i18n.tr('se_intro'))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_fichier(),  i18n.tr('se_onglet_fichier'))
        self.tabs.addTab(self._tab_chantier(), i18n.tr('se_onglet_chantier'))
        self.tabs.addTab(self._tab_reseau(),   i18n.tr('se_onglet_reseau'))
        self.tabs.addTab(self._tab_ouvrages(), i18n.tr('se_onglet_ouvrages'))
        self.tabs.addTab(self._tab_controle(), i18n.tr('se_onglet_controle'))
        layout.addWidget(self.tabs)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(i18n.tr('exp_titre'))
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._restore()
        self._refresh_name()
        self._watch_layers()
        self.run_check()

    # ── Onglet Fichier ──────────────────────────────────────────────────────

    def _tab_fichier(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self.ed_code = QLineEdit()
        self.ed_code.setMaxLength(10)
        self.ed_code.setPlaceholderText(i18n.tr('se_code_chantier'))
        self.ed_code.textChanged.connect(self._refresh_name)
        form.addRow(i18n.tr('se_lbl_code'), self.ed_code)

        self.ed_siren = QLineEdit()
        self.ed_siren.setMaxLength(14)
        self.ed_siren.setPlaceholderText(i18n.tr('se_siren'))
        self.ed_siren.textChanged.connect(self._refresh_name)
        form.addRow(i18n.tr('se_lbl_siren'), self.ed_siren)

        self.cb_type_fichier = QComboBox()
        self.cb_type_fichier.addItems(["ASS", "EAU"])
        self.cb_type_fichier.currentIndexChanged.connect(self._refresh_name)
        form.addRow(i18n.tr('se_lbl_type_fichier'), self.cb_type_fichier)

        self.ed_date = QLineEdit(datetime.now().strftime("%Y-%m-%d"))
        self.ed_date.textChanged.connect(self._refresh_name)
        form.addRow(i18n.tr('se_lbl_date_export'), self.ed_date)

        layout.addLayout(form)

        out_group = QGroupBox(i18n.tr('se_fichier_sortie'))
        out_layout = QVBoxLayout(out_group)

        dir_row = QHBoxLayout()
        self.ed_dir = QLineEdit()
        self.ed_dir.setPlaceholderText(i18n.tr('se_dossier_dest'))
        btn_dir = QPushButton(i18n.tr('parcourir'))
        btn_dir.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.ed_dir)
        dir_row.addWidget(btn_dir)
        out_layout.addLayout(dir_row)

        self.lbl_name = QLabel()
        self.lbl_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_name.setWordWrap(True)
        font = QFont()
        font.setBold(True)
        self.lbl_name.setFont(font)
        out_layout.addWidget(self.lbl_name)

        hint = QLabel(
            i18n.tr('se_nommage'))
        hint.setWordWrap(True)
        out_layout.addWidget(hint)

        layout.addWidget(out_group)
        layout.addStretch()
        return page

    # ── Onglet Chantier ─────────────────────────────────────────────────────

    def _tab_chantier(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        note = QLabel(
            i18n.tr('se_champs_communs'))
        note.setWordWrap(True)
        layout.addWidget(note)

        form = QFormLayout()

        self.ed_insee = QLineEdit()
        self.ed_insee.setMaxLength(5)
        self.ed_insee.setPlaceholderText(i18n.tr('se_insee'))
        form.addRow(i18n.tr('se_lbl_insee'), self.ed_insee)

        self.ed_moa = QLineEdit()
        self.ed_moa.setPlaceholderText(i18n.tr('se_proprietaire'))
        form.addRow(i18n.tr('se_lbl_moa'), self.ed_moa)

        self.ed_exploitant = QLineEdit()
        form.addRow(i18n.tr('se_lbl_exploitant'), self.ed_exploitant)

        self.ed_entreprise = QLineEdit()
        self.ed_entreprise.setPlaceholderText(i18n.tr('se_facultatif'))
        form.addRow(i18n.tr('se_lbl_entreprise'), self.ed_entreprise)

        self.ed_localisation = QLineEdit()
        self.ed_localisation.setPlaceholderText(i18n.tr('se_rue'))
        form.addRow(i18n.tr('se_lbl_localisation'), self.ed_localisation)

        self.cb_etat = self._combo(sv.ETAT_SERVICE)
        form.addRow(i18n.tr('se_lbl_etat'), self.cb_etat)

        self.cb_prec_xy = self._combo(sv.PRECISION)
        form.addRow(i18n.tr('se_lbl_prec_xy'), self.cb_prec_xy)

        self.cb_prec_z = self._combo(sv.PRECISION)
        form.addRow(i18n.tr('se_lbl_prec_z'), self.cb_prec_z)

        year = datetime.now().year
        # Le geostandard ne stocke qu'une ANNEE de pose (domaine c_annee).
        # On saisit malgre tout la date complete : l'annee en est deduite
        # pour an_pose_sup, et le jour alimente les identifiants metier.
        self.de_pose = QDateEdit(QDate.currentDate())
        self.de_pose.setCalendarPopup(True)
        self.de_pose.setDisplayFormat("dd/MM/yyyy")
        self.de_pose.setDateRange(QDate(1800, 1, 1), QDate(2099, 12, 31))
        form.addRow(i18n.tr('se_lbl_date_pose'), self.de_pose)

        self.sp_service = QSpinBox()
        self.sp_service.setRange(1800, 2099)
        self.sp_service.setValue(year)
        form.addRow(i18n.tr('se_lbl_annee_service'), self.sp_service)

        self.cb_origine = self._combo(sv.ORIGINE)
        form.addRow(i18n.tr('se_lbl_origine'), self.cb_origine)

        layout.addLayout(form)

        self.ed_commentaire = QTextEdit()
        self.ed_commentaire.setMaximumHeight(70)
        layout.addWidget(QLabel(i18n.tr('se_commentaire')))
        layout.addWidget(self.ed_commentaire)

        layout.addStretch()
        return page

    # ── Onglet Réseau ───────────────────────────────────────────────────────

    def _tab_reseau(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()

        self.cb_type_eu = self._combo(sv.TYPE_RESEAU)
        self.cb_type_eu.setCurrentIndex(sv.index_of(sv.TYPE_RESEAU, "assaeu"))
        form.addRow(i18n.tr('se_lbl_type_eu'), self.cb_type_eu)

        self.cb_type_ep = self._combo(sv.TYPE_RESEAU)
        self.cb_type_ep.setCurrentIndex(sv.index_of(sv.TYPE_RESEAU, "assaep"))
        form.addRow(i18n.tr('se_lbl_type_ep'), self.cb_type_ep)

        self.cb_mode_circ = self._combo(sv.MODE_CIRCULATION)
        form.addRow(i18n.tr('se_lbl_mode_circ'), self.cb_mode_circ)

        self.cb_type_pose = self._combo(sv.TYPE_POSE)
        form.addRow(i18n.tr('se_lbl_type_pose'), self.cb_type_pose)

        self.cb_raison_pose = self._combo(sv.RAISON_POSE)
        form.addRow(i18n.tr('se_lbl_raison_pose'), self.cb_raison_pose)

        self.cb_revetement = self._combo(sv.REVETEMENT_INTERIEUR)
        form.addRow(i18n.tr('se_lbl_revetement'), self.cb_revetement)

        self.cb_fonction_cana = self._combo(sv.FONCTION_CANALISATION)
        form.addRow(i18n.tr('se_lbl_fonction_cana'), self.cb_fonction_cana)

        self.cb_fonction_brt = self._combo(sv.FONCTION_BRANCHEMENT)
        form.addRow(i18n.tr('se_lbl_fonction_brt'), self.cb_fonction_brt)

        # Les conduites et branchements portent deja un materiau saisi dans
        # le plugin : ce champ n'est qu'un repli. D'ou l'entree de tete, qui
        # dit explicitement que le projet fait foi — sans elle, « Non
        # renseigne » laisse croire que l'export ecraserait les materiaux.
        self.cb_materiau = QComboBox()
        self.cb_materiau.addItem(i18n.tr(_MAT_PROJET))
        self.cb_materiau.addItems(
            [libelle for _, libelle in _MATERIAUX_REPLI])
        form.addRow(i18n.tr('se_lbl_materiau_conduites'), self.cb_materiau)
        hint_mat = QLabel(
            i18n.tr('se_materiau_aide'))
        hint_mat.setWordWrap(True)
        form.addRow("", hint_mat)

        self.chk_sensible = QCheckBox(i18n.tr('se_sensible'))
        form.addRow("", self.chk_sensible)

        layout.addLayout(form)

        contenu_group = QGroupBox(i18n.tr('se_type_eau'))
        contenu_layout = QFormLayout(contenu_group)

        self.cb_contenu_eu = self._combo(sv.CONTENU_CANALISATION)
        contenu_layout.addRow(i18n.tr('se_lbl_contenu_eu'), self.cb_contenu_eu)

        self.cb_contenu_ep = QComboBox()
        self.cb_contenu_ep.addItem(i18n.tr(_EP_VIDE))
        self.cb_contenu_ep.addItems(sv.labels(sv.CONTENU_CANALISATION))
        contenu_layout.addRow(i18n.tr('se_lbl_contenu_ep'), self.cb_contenu_ep)

        warn = QLabel(
            i18n.tr('se_type_eau_aide'))
        warn.setWordWrap(True)
        contenu_layout.addRow(warn)

        layout.addWidget(contenu_group)
        layout.addStretch()
        return page

    # ── Onglet Ouvrages ─────────────────────────────────────────────────────

    def _tab_ouvrages(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        regard_group = QGroupBox(i18n.tr('se_regards'))
        regard_form = QFormLayout(regard_group)
        self.cb_type_regard = self._combo(sv.TYPE_REGARD)
        regard_form.addRow(i18n.tr('se_lbl_type_regard'), self.cb_type_regard)
        self.cb_position = self._combo(sv.POSITION_REGARD)
        regard_form.addRow(i18n.tr('se_lbl_position'), self.cb_position)
        self.cb_descente = self._combo(sv.TYPE_DESCENTE)
        regard_form.addRow(i18n.tr('se_lbl_descente'), self.cb_descente)
        self.cb_mat_regard = self._combo(sv.MATERIAUX_CONDUITE)
        self.cb_mat_regard.setCurrentIndex(
            sv.index_of(sv.MATERIAUX_CONDUITE, "beton"))
        regard_form.addRow(i18n.tr('dt_lbl_materiau'), self.cb_mat_regard)
        layout.addWidget(regard_group)

        tab_group = QGroupBox(i18n.tr('se_tabourets'))
        tab_form = QFormLayout(tab_group)
        self.cb_type_collecte = self._combo(sv.TYPE_POINT_COLLECTE)
        tab_form.addRow(i18n.tr('se_lbl_type_collecte'), self.cb_type_collecte)
        self.cb_usager = self._combo(sv.TYPE_USAGER)
        tab_form.addRow(i18n.tr('se_lbl_usager'), self.cb_usager)
        self.cb_mat_tabouret = self._combo(sv.MATERIAUX_CONDUITE)
        self.cb_mat_tabouret.setCurrentIndex(
            sv.index_of(sv.MATERIAUX_CONDUITE, "pvc"))
        tab_form.addRow(i18n.tr('dt_lbl_materiau'), self.cb_mat_tabouret)
        layout.addWidget(tab_group)

        rac_group = QGroupBox(i18n.tr('se_piquages'))
        rac_form = QFormLayout(rac_group)
        self.cb_type_raccord = self._combo(sv.TYPE_RACCORD)
        rac_form.addRow(i18n.tr('se_lbl_type_raccord'), self.cb_type_raccord)
        note = QLabel(
            i18n.tr('se_piquages_aide'))
        note.setWordWrap(True)
        rac_form.addRow(note)
        layout.addWidget(rac_group)

        layout.addStretch()
        return page

    # ── Onglet Contrôle ─────────────────────────────────────────────────────

    def _tab_controle(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.lbl_check = QLabel()
        self.lbl_check.setWordWrap(True)
        layout.addWidget(self.lbl_check)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([i18n.tr('se_niveau'), i18n.tr('se_objet'), i18n.tr('se_anomalie')])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemDoubleClicked.connect(self._zoom_to_issue)
        layout.addWidget(self.table)

        hint = QLabel(
            i18n.tr('se_controle_aide'))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        btn = QPushButton(i18n.tr('se_relancer'))
        btn.clicked.connect(self.run_check)
        layout.addWidget(btn)

        return page

    # ── Contrôle de conformité ──────────────────────────────────────────────

    def run_check(self):
        from ..tools.stareau_export import check_conformity
        try:
            self._issues = check_conformity()
        except Exception as exc:
            self._issues = []
            self.lbl_check.setText(i18n.tr('se_controle_echec', erreur=exc))
            return

        bloquants = [i for i in self._issues if i["niveau"] == "bloquant"]
        avertissements = [i for i in self._issues if i["niveau"] != "bloquant"]

        self.table.setRowCount(len(self._issues))
        ordered = bloquants + avertissements
        for row, issue in enumerate(ordered):
            niveau = QTableWidgetItem(
                "Bloquant" if issue["niveau"] == "bloquant" else "Avertissement")
            niveau.setForeground(
                QColor(180, 0, 0) if issue["niveau"] == "bloquant"
                else QColor(190, 120, 0))
            self.table.setItem(row, 0, niveau)
            self.table.setItem(row, 1, QTableWidgetItem(issue["objet"]))
            self.table.setItem(row, 2, QTableWidgetItem(issue["message"]))
        self._ordered_issues = ordered
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        if not self._issues:
            self.lbl_check.setText(i18n.tr('se_aucune_anomalie'))
        else:
            self.lbl_check.setText(
                i18n.tr('se_bilan', bloquants=len(bloquants),
                        avertissements=len(avertissements)))
        self.tabs.setTabText(
            4, i18n.tr('se_onglet_controle_nb', nb=len(self._issues))
            if self._issues else i18n.tr('se_onglet_controle'))

    # ── Reactualisation automatique ─────────────────────────────────────────

    def _watch_layers(self):
        """S'abonne aux modifications des couches BET.

        Le dialogue est non modal : l'utilisateur corrige un objet dans QGIS
        pendant qu'il est ouvert. Plutot que de compter sur le retour de
        focus — peu fiable, la fenetre pouvant rester au premier plan — on
        ecoute directement les couches. Les modifications arrivant en rafale
        (un trace pose plusieurs objets), un minuteur les regroupe.
        """
        from ..tools.stareau_export import source_layers

        self._check_timer = QTimer(self)
        self._check_timer.setSingleShot(True)
        self._check_timer.timeout.connect(self.run_check)

        self._watched = []
        for layer in source_layers().values():
            signals = []
            for name in ("featureAdded", "featuresDeleted", "geometryChanged",
                         "attributeValueChanged", "afterCommitChanges",
                         "editingStopped", "dataChanged"):
                signal = getattr(layer, name, None)
                if signal is None:
                    continue
                try:
                    signal.connect(self._schedule_check)
                    signals.append(signal)
                except Exception:
                    pass
            if signals:
                self._watched.append((layer, signals))

    def _schedule_check(self, *args):
        """Regroupe les modifications en rafale en un seul controle."""
        self._check_timer.start(400)

    def _unwatch_layers(self):
        from qgis.PyQt import sip
        for layer, signals in getattr(self, "_watched", []):
            if sip.isdeleted(layer):
                continue
            for signal in signals:
                try:
                    signal.disconnect(self._schedule_check)
                except (TypeError, RuntimeError):
                    pass
        self._watched = []

    def changeEvent(self, event):
        """Recontrole aussi au retour de focus, en complement de l'ecoute."""
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.run_check()

    def closeEvent(self, event):
        self._unwatch_layers()
        super().closeEvent(event)

    def _zoom_to_issue(self, item):
        from qgis.core import QgsProject
        issues = getattr(self, "_ordered_issues", [])
        if item.row() >= len(issues):
            return
        issue = issues[item.row()]
        layer = QgsProject.instance().mapLayer(issue["layer_id"])
        if layer is None or self.iface is None:
            return
        layer.selectByIds([issue["fid"]])
        self.iface.setActiveLayer(layer)
        self.iface.mapCanvas().zoomToSelected(layer)

    # ── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _combo(liste):
        combo = QComboBox()
        combo.addItems(sv.labels(liste))
        combo._stareau_liste = liste
        return combo

    @staticmethod
    def _code(combo):
        return sv.code_at(combo._stareau_liste, combo.currentIndex())

    def _browse_dir(self):
        start = self.ed_dir.text()
        if not start:
            try:
                from ..tools.projet_bet import project_dir
                start = project_dir()
            except Exception:
                start = ""
        chosen = QFileDialog.getExistingDirectory(
            self, i18n.tr('se_dossier_dest_titre'), start)
        if chosen:
            self.ed_dir.setText(chosen)
            self._refresh_name()

    def _refresh_name(self):
        from ..tools.stareau_export import file_name
        name = file_name(self._name_params())
        directory = self.ed_dir.text()
        self.lbl_name.setText(
            os.path.join(directory, name) if directory else name)

    def _name_params(self):
        return {
            "code_chantier": self.ed_code.text().strip(),
            "siren":         self.ed_siren.text().strip(),
            "type_fichier":  self.cb_type_fichier.currentText(),
            "date_export":   self.ed_date.text().strip(),
        }

    # ── Sortie ──────────────────────────────────────────────────────────────

    def output_path(self):
        from ..tools.stareau_export import file_name
        return os.path.join(self.ed_dir.text(), file_name(self._name_params()))

    def params(self):
        """Dictionnaire de parametres consomme par tools.stareau_export."""
        ep_index = self.cb_contenu_ep.currentIndex()
        contenu_ep = (None if ep_index == 0
                      else sv.code_at(sv.CONTENU_CANALISATION, ep_index - 1))

        # Index 0 = « Identique au projet » : les objets sans materiau
        # sortent en « nr », ceux qui en ont un gardent le leur de toute
        # facon, le repli n'etant consulte que sur un champ vide.
        mat_index = self.cb_materiau.currentIndex()
        materiau_defaut = ("nr" if mat_index == 0
                           else _MATERIAUX_REPLI[mat_index - 1][0])

        params = dict(self._name_params())
        params.update({
            "insee_commune":        self.ed_insee.text().strip(),
            "maitre_ouvrage":       self.ed_moa.text().strip(),
            "exploitant":           self.ed_exploitant.text().strip(),
            "entreprise_pose":      self.ed_entreprise.text().strip(),
            "localisation":         self.ed_localisation.text().strip(),
            "etat_service":         self._code(self.cb_etat),
            "precision_xy":         self._code(self.cb_prec_xy),
            "precision_z":          self._code(self.cb_prec_z),
            # Le standard ne veut que l'annee ; la date complete ne sert
            # qu'aux identifiants metier.
            "an_pose_sup":          self.de_pose.date().year(),
            "date_pose":            self.de_pose.date().toString("yyyyMMdd"),
            "an_service_sup":       self.sp_service.value(),
            "origine_creation":     self._code(self.cb_origine),
            "commentaire":          self.ed_commentaire.toPlainText().strip(),
            "type_reseau_eu":       self._code(self.cb_type_eu),
            "type_reseau_ep":       self._code(self.cb_type_ep),
            "mode_circulation":     self._code(self.cb_mode_circ),
            "type_pose":            self._code(self.cb_type_pose),
            "raison_pose":          self._code(self.cb_raison_pose),
            "revetement_interieur": self._code(self.cb_revetement),
            "fonction_canalisation": self._code(self.cb_fonction_cana),
            "fonction_branchement": self._code(self.cb_fonction_brt),
            "materiau_defaut":      materiau_defaut,
            "sensible":             self.chk_sensible.isChecked(),
            "contenu_eu":           self._code(self.cb_contenu_eu),
            "contenu_ep":           contenu_ep,
            "type_regard":          self._code(self.cb_type_regard),
            "position_regard":      self._code(self.cb_position),
            "type_descente":        self._code(self.cb_descente),
            "materiau_regard":      self._code(self.cb_mat_regard),
            "type_point_collecte":  self._code(self.cb_type_collecte),
            "type_usager":          self._code(self.cb_usager),
            "materiau_tabouret":    self._code(self.cb_mat_tabouret),
            "type_raccord":         self._code(self.cb_type_raccord),
        })
        return params

    def _on_accept(self):
        from qgis.PyQt.QtWidgets import QMessageBox

        missing = []
        if not self.ed_dir.text().strip():
            missing.append(i18n.tr('se_manque_dossier'))
        if not self.ed_insee.text().strip():
            missing.append(i18n.tr('se_manque_insee'))
        if not self.ed_moa.text().strip():
            missing.append(i18n.tr('se_manque_moa'))
        if not self.ed_exploitant.text().strip():
            missing.append(i18n.tr('se_manque_exploitant'))
        if missing:
            QMessageBox.warning(
                self, i18n.tr('se_champs_obligatoires'),
                i18n.tr('se_manque_intro') + "\n\n• "
                + "\n• ".join(missing))
            return

        bloquants = [i for i in self._issues if i["niveau"] == "bloquant"]
        if bloquants:
            answer = QMessageBox.question(
                self, i18n.tr('se_non_conformes'),
                i18n.tr('se_poursuivre', nb=len(bloquants)),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                self.tabs.setCurrentIndex(4)
                return

        self._save()
        self.accept()

    # ── Persistance ─────────────────────────────────────────────────────────

    def _widgets(self):
        """(cle de reglage, widget) de tout ce qui est memorise."""
        return (
            ("code_chantier", self.ed_code),
            ("siren",         self.ed_siren),
            ("dir",           self.ed_dir),
            ("insee",         self.ed_insee),
            ("moa",           self.ed_moa),
            ("exploitant",    self.ed_exploitant),
            ("entreprise",    self.ed_entreprise),
            ("localisation",  self.ed_localisation),
            ("type_fichier",  self.cb_type_fichier),
            ("etat",          self.cb_etat),
            ("prec_xy",       self.cb_prec_xy),
            ("prec_z",        self.cb_prec_z),
            ("origine",       self.cb_origine),
            ("type_eu",       self.cb_type_eu),
            ("type_ep",       self.cb_type_ep),
            ("mode_circ",     self.cb_mode_circ),
            ("type_pose",     self.cb_type_pose),
            ("raison_pose",   self.cb_raison_pose),
            ("revetement",    self.cb_revetement),
            ("fonction_cana", self.cb_fonction_cana),
            ("fonction_brt",  self.cb_fonction_brt),
            ("materiau",      self.cb_materiau),
            ("contenu_eu",    self.cb_contenu_eu),
            ("contenu_ep",    self.cb_contenu_ep),
            ("type_regard",   self.cb_type_regard),
            ("position",      self.cb_position),
            ("descente",      self.cb_descente),
            ("mat_regard",    self.cb_mat_regard),
            ("type_collecte", self.cb_type_collecte),
            ("usager",        self.cb_usager),
            ("mat_tabouret",  self.cb_mat_tabouret),
            ("type_raccord",  self.cb_type_raccord),
        )

    def _save(self):
        settings = QgsSettings()
        for key, widget in self._widgets():
            if isinstance(widget, QComboBox):
                # Memorise par LIBELLE et non par index : un index deviendrait
                # silencieusement faux des qu'une liste de valeurs change de
                # taille, et designerait un autre materiau ou un autre type.
                settings.setValue(_SETTINGS_PREFIX + key, widget.currentText())
            else:
                settings.setValue(_SETTINGS_PREFIX + key, widget.text())
        settings.setValue(_SETTINGS_PREFIX + "date_pose",
                          self.de_pose.date().toString("yyyy-MM-dd"))
        settings.setValue(_SETTINGS_PREFIX + "an_service", self.sp_service.value())
        settings.setValue(_SETTINGS_PREFIX + "sensible", self.chk_sensible.isChecked())

    def _restore(self):
        settings = QgsSettings()
        for key, widget in self._widgets():
            value = settings.value(_SETTINGS_PREFIX + key)
            if value in (None, ""):
                continue
            if isinstance(widget, QComboBox):
                index = widget.findText(str(value))
                # Introuvable : le libelle a disparu de la liste, on garde le
                # defaut du code plutot qu'une valeur arbitraire.
                if index >= 0:
                    widget.setCurrentIndex(index)
            else:
                widget.setText(str(value))

        stored_date = settings.value(_SETTINGS_PREFIX + "date_pose")
        if stored_date:
            date = QDate.fromString(str(stored_date), "yyyy-MM-dd")
            if date.isValid():
                self.de_pose.setDate(date)

        value = settings.value(_SETTINGS_PREFIX + "an_service")
        try:
            self.sp_service.setValue(int(value))
        except (TypeError, ValueError):
            pass

        sensible = settings.value(_SETTINGS_PREFIX + "sensible")
        self.chk_sensible.setChecked(str(sensible).lower() in ("true", "1"))

        if not self.ed_dir.text():
            try:
                from ..tools.projet_bet import project_dir
                self.ed_dir.setText(project_dir())
            except Exception:
                pass
