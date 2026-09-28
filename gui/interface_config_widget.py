# -*- coding: utf-8 -*-
"""Onglet Interface de la configuration rapide.

Langue du plugin, interface colorée, et contenu du panneau latéral : ordre
des sections et des entrées, entrées affichées ou non. Tout est gardé dans
QSettings (tools/panneau_prefs.py) et vaut pour les sessions suivantes.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QBrush, QColor, QFont, QIcon
from qgis.PyQt.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..tools import i18n
from ..tools import panneau_prefs as PP

_CLE = Qt.ItemDataRole.UserRole


class InterfaceConfigWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "icon")
        layout = QVBoxLayout(self)

        # ── Langue et couleurs ──────────────────────────────────────────
        general = QGroupBox(i18n.tr('qc_interface_general'))
        form = QFormLayout(general)
        self.combo_langue = QComboBox()
        for code, _libelle in i18n.CHOIX:
            self.combo_langue.addItem(i18n.libelle_choix(code), code)
        idx = self.combo_langue.findData(i18n.preference())
        if idx >= 0:
            self.combo_langue.setCurrentIndex(idx)
        form.addRow(i18n.tr('langue'), self.combo_langue)

        # Colorée par défaut ; « Classique » rend au panneau l'apparence
        # standard de QGIS. Le choix est gardé d'une session à l'autre.
        self.combo_apparence = QComboBox()
        self.combo_apparence.addItem(i18n.tr('qc_apparence_coloree'), True)
        self.combo_apparence.addItem(i18n.tr('qc_apparence_classique'), False)
        self.combo_apparence.setCurrentIndex(0 if PP.interface_coloree() else 1)
        self.combo_apparence.setToolTip(i18n.tr('qc_interface_coloree_tip'))
        self.combo_apparence.currentIndexChanged.connect(self._colorer_apercu)
        form.addRow(i18n.tr('qc_apparence'), self.combo_apparence)
        layout.addWidget(general)

        # ── Panneau latéral ─────────────────────────────────────────────
        panneau = QGroupBox(i18n.tr('qc_panneau'))
        vbox = QVBoxLayout(panneau)
        aide = QLabel(i18n.tr('qc_panneau_aide'))
        aide.setWordWrap(True)
        vbox.addWidget(aide)

        ligne = QHBoxLayout()
        self.arbre = QTreeWidget()
        self.arbre.setHeaderHidden(True)
        self.arbre.setIndentation(16)
        ligne.addWidget(self.arbre, 1)

        boutons = QVBoxLayout()
        self.btn_haut = QPushButton("▲ " + i18n.tr('qc_monter'))
        self.btn_bas = QPushButton("▼ " + i18n.tr('qc_descendre'))
        self.btn_defaut = QPushButton(i18n.tr('qc_reinitialiser'))
        self.btn_haut.clicked.connect(lambda: self._deplacer(-1))
        self.btn_bas.clicked.connect(lambda: self._deplacer(+1))
        self.btn_defaut.clicked.connect(self._par_defaut)
        for b in (self.btn_haut, self.btn_bas):
            boutons.addWidget(b)
        boutons.addStretch()
        boutons.addWidget(self.btn_defaut)
        ligne.addLayout(boutons)
        vbox.addLayout(ligne)
        layout.addWidget(panneau, 1)

        self._remplir(PP.charger())

    # ── Arbre d'édition ─────────────────────────────────────────────────

    def _remplir(self, prefs):
        self.arbre.clear()
        masques = prefs['masques']
        for noeud in PP.structure_ordonnee(prefs):
            self.arbre.addTopLevelItem(self._noeud(noeud, None, masques))
        self.arbre.expandAll()
        self._colorer_apercu()

    def _noeud(self, noeud, parent, masques):
        cle = PP.cle(noeud)
        if 'dossier' in noeud:
            texte, icone = i18n.tr(noeud['dossier']), None
        else:
            texte = i18n.tr(noeud['tr'] or noeud['action'])
            icone = os.path.join(self._icon_dir, noeud['icone'])
        item = (QTreeWidgetItem(parent, [texte]) if parent is not None
                else QTreeWidgetItem([texte]))
        item.setData(0, _CLE, cle)
        if icone and os.path.exists(icone):
            item.setIcon(0, QIcon(icone))
        if 'dossier' in noeud:
            f = QFont()
            f.setBold(True)
            item.setFont(0, f)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                      | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Unchecked if cle in masques
                           else Qt.CheckState.Checked)
        for enfant in noeud.get('enfants', ()):
            self._noeud(enfant, item, masques)
        return item

    def _deplacer(self, sens):
        """Monte ou descend l'élément choisi parmi ses frères."""
        item = self.arbre.currentItem()
        if item is None:
            return
        parent = item.parent()
        if parent is None:
            i = self.arbre.indexOfTopLevelItem(item)
            j = i + sens
            if not 0 <= j < self.arbre.topLevelItemCount():
                return
            deplie = item.isExpanded()
            self.arbre.takeTopLevelItem(i)
            self.arbre.insertTopLevelItem(j, item)
        else:
            i = parent.indexOfChild(item)
            j = i + sens
            if not 0 <= j < parent.childCount():
                return
            deplie = item.isExpanded()
            parent.takeChild(i)
            parent.insertChild(j, item)
        # Un élément retiré puis réinséré perd son dépliage et sa sélection.
        item.setExpanded(deplie)
        for k in range(item.childCount()):
            item.child(k).setExpanded(True)
        self.arbre.setCurrentItem(item)
        self._colorer_apercu()

    def _par_defaut(self):
        self._remplir({'ordre': {}, 'masques': set()})

    def _colorer_apercu(self, *_args):
        """L'arbre d'édition montre le rendu choisi pour le panneau."""
        coloree = bool(self.combo_apparence.currentData())
        for i in range(self.arbre.topLevelItemCount()):
            dossier = self.arbre.topLevelItem(i)
            teinte = PP.COULEURS.get(dossier.data(0, _CLE))
            if coloree and teinte:
                fond, clair = QColor(teinte), QColor(teinte)
                clair.setAlpha(28)
                brosses = (QBrush(fond), QBrush(QColor('white')), QBrush(clair))
            else:
                brosses = (QBrush(), QBrush(), QBrush())
            dossier.setBackground(0, brosses[0])
            dossier.setForeground(0, brosses[1])
            pile = [dossier.child(k) for k in range(dossier.childCount())]
            while pile:
                e = pile.pop()
                e.setBackground(0, brosses[2])
                pile.extend(e.child(k) for k in range(e.childCount()))

    # ── Enregistrement ──────────────────────────────────────────────────

    def preferences(self):
        """{"ordre": {parent: [clés]}, "masques": set()} lues dans l'arbre."""
        ordre, masques = {}, set()

        def parcourir(items, parent_cle):
            ordre[parent_cle] = [it.data(0, _CLE) for it in items]
            for it in items:
                if it.checkState(0) == Qt.CheckState.Unchecked:
                    masques.add(it.data(0, _CLE))
                enfants = [it.child(k) for k in range(it.childCount())]
                if enfants:
                    parcourir(enfants, it.data(0, _CLE))

        parcourir([self.arbre.topLevelItem(i)
                   for i in range(self.arbre.topLevelItemCount())], PP.RACINE)
        return {'ordre': ordre, 'masques': masques}

    def save_settings(self, plugin=None):
        PP.enregistrer(self.preferences())
        PP.definir_interface_coloree(bool(self.combo_apparence.currentData()))
        panneau = getattr(plugin, 'side_panel', None) if plugin else None
        if panneau is not None:
            panneau.reconstruire()
        code = self.combo_langue.currentData()
        if code != i18n.preference():
            # Retraduit tout le plugin, panneau compris (signal langue_changee).
            i18n.definir(code)
