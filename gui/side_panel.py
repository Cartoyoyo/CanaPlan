# -*- coding: utf-8 -*-
import os
from qgis.PyQt.QtCore import Qt, QEvent
from qgis.PyQt.QtGui import QIcon, QFont, QBrush, QColor
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTreeWidget, QTreeWidgetItem,
)

from ..tools import i18n
from ..tools import panneau_prefs as PP


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
        # Territoire du projet : entrées masquées, et libellés remplacés
        # (clé d'action -> clé i18n), voir main.appliquer_territoire.
        self._masquees = ()
        self._libelles_territoire = {}
        # Entrées masquées par l'utilisateur (onglet Interface).
        self._masques_utilisateur = set()
        # Entrée survolée et sa police d'origine (mise en gras au survol).
        self._survole = None
        self._police_origine = None
        self._build_ui()

    def _build_ui(self):
        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.itemClicked.connect(self._on_item_clicked)
        # Survol : l'entrée passe en gras, un rien plus grande, et reprend sa police quand la
        # souris la quitte ou sort du panneau.
        self.tree.setMouseTracking(True)
        self.tree.itemEntered.connect(self._survol)
        self.tree.viewport().installEventFilter(self)

        self._icon_dir = os.path.join(self.plugin.plugin_dir, "icon")
        self._peupler()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.tree)
        layout.addLayout(self._build_language_row())
        self.setWidget(container)

    # ── Contenu de l'arbre ──────────────────────────────────────────────

    def _peupler(self):
        """Construit l'arbre d'après STRUCTURE et les préférences Interface."""
        prefs = PP.charger()
        self._masques_utilisateur = set(prefs['masques'])
        self._i18n_items = []
        self._survole = None
        self.tree.clear()
        for noeud in PP.structure_ordonnee(prefs):
            self.tree.addTopLevelItem(self._construire(noeud, None))
        self.tree.expandAll()
        self._appliquer_couleurs()

    def _construire(self, noeud, parent):
        if 'dossier' in noeud:
            item = self._folder(noeud['dossier'], parent=parent)
            for enfant in noeud['enfants']:
                self._construire(enfant, item)
        else:
            item = self._item(parent, self._icon_dir, noeud['icone'],
                              noeud['action'], tr_key=noeud['tr'])
        return item

    def reconstruire(self):
        """Reconstruit l'arbre après un changement dans l'onglet Interface :
        ordre, entrées masquées, couleurs."""
        self._peupler()
        self.appliquer_territoire(self._masquees, self._libelles_territoire)

    def _appliquer_couleurs(self):
        """Interface colorée : bandeau de couleur sur chaque dossier, teinte
        légère sur ses entrées. Sinon, rendu standard de QGIS."""
        coloree = PP.interface_coloree()
        for i in range(self.tree.topLevelItemCount()):
            dossier = self.tree.topLevelItem(i)
            teinte = PP.COULEURS.get(self._cle_dossier(dossier))
            if coloree and teinte:
                fond = QColor(teinte)
                clair = QColor(fond)
                clair.setAlpha(28)
                self._colorer(dossier, QBrush(fond), QBrush(QColor('white')),
                              QBrush(clair))
            else:
                self._colorer(dossier, QBrush(), QBrush(), QBrush())

    def _colorer(self, dossier, fond, texte, fond_enfants):
        dossier.setBackground(0, fond)
        dossier.setForeground(0, texte)
        pile = [dossier.child(i) for i in range(dossier.childCount())]
        while pile:
            enfant = pile.pop()
            enfant.setBackground(0, fond_enfants)
            pile.extend(enfant.child(i) for i in range(enfant.childCount()))

    def _cle_dossier(self, item):
        for it, cle in self._i18n_items:
            if it is item:
                return cle
        return None

    # ── Mise en gras au survol, léger zoom ──────────────────────────────

    FACTEUR_ZOOM = 1.02

    def _survol(self, item, _colonne=0):
        if item is self._survole:
            return
        if self._survole is not None and self._police_origine is not None:
            self._survole.setFont(0, self._police_origine)
        self._survole, self._police_origine = None, None
        # Les titres de section sont déjà en gras : seules les entrées cliquables.
        if item is None or item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        self._police_origine = QFont(item.font(0))
        grasse = QFont(self._police_origine)
        base = grasse.pointSizeF() if grasse.pointSizeF() > 0 else self.tree.font().pointSizeF()
        grasse.setPointSizeF(base * self.FACTEUR_ZOOM)
        grasse.setBold(True)
        item.setFont(0, grasse)
        self._survole = item

    def eventFilter(self, objet, evenement):
        if objet is self.tree.viewport() and evenement.type() == QEvent.Type.Leave:
            self._survol(None)
        return super().eventFilter(objet, evenement)

    # ── Langue ──────────────────────────────────────────────────────────

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
            action = item.data(0, Qt.ItemDataRole.UserRole)
            item.setText(0, i18n.tr(self._libelles_territoire.get(action, cle)))
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

    # ── Territoire et masquage ──────────────────────────────────────────

    def appliquer_territoire(self, masquees, libelles):
        """Masque les entrées propres à la France et renomme celles qui
        changent de source à l'international. Les entrées masquées par
        l'utilisateur (onglet Interface) restent masquées."""
        self._masquees = tuple(masquees)
        self._libelles_territoire = dict(libelles)
        for item, cle in self._i18n_items:
            action = item.data(0, Qt.ItemDataRole.UserRole)
            if action is None:
                # Dossier masqué en entier par l'utilisateur.
                item.setHidden(cle in self._masques_utilisateur)
                continue
            item.setHidden(action in self._masquees
                           or action in self._masques_utilisateur)
            item.setText(0, i18n.tr(self._libelles_territoire.get(action, cle)))
        # Une section dont toutes les entrées sont masquées (Fond de plan
        # > France, à l'international) disparaît avec elles.
        for item, cle in self._i18n_items:
            if item.data(0, Qt.ItemDataRole.UserRole) is None:
                enfants = [item.child(i) for i in range(item.childCount())]
                item.setHidden(cle in self._masques_utilisateur
                               or (bool(enfants) and all(e.isHidden() for e in enfants)))

    # ── Fabriques ───────────────────────────────────────────────────────

    def _folder(self, tr_key, parent=None):
        """Dossier du panneau ; `parent` en fait une sous-section."""
        item = (QTreeWidgetItem(parent, [i18n.tr(tr_key)]) if parent is not None
                else QTreeWidgetItem([i18n.tr(tr_key)]))
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
