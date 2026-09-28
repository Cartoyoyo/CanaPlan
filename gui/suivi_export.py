# -*- coding: utf-8 -*-
"""Fenêtre de suivi d'un export : tout ce qui va être fait, ce qui se fait,
ce qui est fait, avec le temps mesuré de chaque étape.

Toutes les sorties possibles sont listées, demandées ou non : on voit d'un
coup d'œil ce que l'export produira, et ce qu'il ne produira pas. La fenêtre
n'est pas modale — la carte reste utilisable, ce qui est indispensable
pendant la pose des planches — et reste ouverte à la fin, avec les temps,
jusqu'à ce que l'utilisateur la ferme.
"""

import time

from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtGui import QBrush, QColor, QFont
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from ..tools import i18n

# (clé, clé i18n du libellé) — ordre d'exécution de l'export.
ETAPES = (
    ('profil_eu',     'se_etape_profil_eu'),
    ('profil_ep',     'se_etape_profil_ep'),
    ('profil_aep',    'se_etape_profil_aep'),
    ('profil_groupe', 'se_etape_profil_groupe'),
    ('cubature',      'se_etape_cubature'),
    ('coupes',        'se_etape_coupes'),
    ('schemas',       'se_etape_schemas'),
    ('plan_pdf',      'se_etape_plan_pdf'),
    ('plan_dxf',      'se_etape_plan_dxf'),
    ('assemblage',    'se_etape_assemblage'),
    ('archive',       'se_etape_archive'),
)

_ICONES = {'non': "—", 'attente': "⏸", 'pose': "🖱", 'cours': "⏳",
           'fait': "✔", 'erreur': "✖", 'abandon': "⤫"}
_COULEURS = {'non': '#9E9E9E', 'attente': '#616161', 'pose': '#1565C0',
             'cours': '#E65100', 'fait': '#2E7D32', 'erreur': '#C62828',
             'abandon': '#757575'}

_ouverte = []   # la fenêtre non modale doit survivre à la fonction appelante


def _duree(s):
    return i18n.tr('se_duree', s=("%.1f" % s).replace('.', ',')) if s < 60 else \
        i18n.tr('se_duree_min', m=int(s // 60), s=int(s % 60))


class SuiviExport(QDialog):

    def __init__(self, titre, demandees, parent=None, masquees=()):
        """demandees : ensemble des clés d'ETAPES que l'export produira.
        masquees : étapes sans objet pour ce type d'export (non listées)."""
        super().__init__(parent)
        self.setWindowTitle(titre)
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(580)
        self._debut = time.monotonic()
        self._etat = {}         # clé -> [état, début, durée, détail]
        self._items = {}
        self._dossier = None

        layout = QVBoxLayout(self)
        self.arbre = QTreeWidget()
        self.arbre.setColumnCount(3)
        self.arbre.setHeaderLabels(["", i18n.tr('se_col_sortie'), i18n.tr('se_col_temps')])
        self.arbre.setRootIsDecorated(False)
        self.arbre.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        entete = self.arbre.header()
        entete.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        entete.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        entete.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for cle, cle_tr in ETAPES:
            if cle in masquees:
                continue
            item = QTreeWidgetItem(self.arbre, ["", i18n.tr(cle_tr), ""])
            self._items[cle] = item
            self._etat[cle] = ['attente' if cle in demandees else 'non', None, None, ""]
        layout.addWidget(self.arbre)

        self.total = QLabel()
        f = QFont(self.total.font())
        f.setBold(True)
        self.total.setFont(f)
        layout.addWidget(self.total)

        boutons = QHBoxLayout()
        self.btn_dossier = QPushButton("📂 " + i18n.tr('msg_ouvrir_dossier'))
        self.btn_dossier.setEnabled(False)
        self.btn_dossier.clicked.connect(self._ouvrir_dossier)
        fermer = QPushButton(i18n.tr('se_fermer'))
        fermer.clicked.connect(self.close)
        boutons.addStretch()
        boutons.addWidget(self.btn_dossier)
        boutons.addWidget(fermer)
        layout.addLayout(boutons)

        self._minuteur = QTimer(self)
        self._minuteur.timeout.connect(self._rafraichir)
        self._minuteur.start(250)
        self._termine = False
        self._rafraichir()
        # Hauteur ajustée aux lignes : pas de vide sous la liste.
        self.arbre.setFixedHeight(
            self.arbre.sizeHintForRow(0) * len(self._items)
            + self.arbre.header().sizeHint().height() + 6)
        self.adjustSize()
        _ouverte.append(self)
        self.show()
        QApplication.processEvents()

    # ── Pilotage ────────────────────────────────────────────────────────

    def _poser(self, cle, etat, detail=None):
        if cle not in self._etat:
            return
        e = self._etat[cle]
        maintenant = time.monotonic()
        if etat in ('cours', 'pose') and e[1] is None:
            e[1] = maintenant
        if etat in ('fait', 'erreur', 'abandon') and e[1] is not None and e[2] is None:
            e[2] = maintenant - e[1]
        e[0] = etat
        if detail is not None:
            e[3] = detail
        self._rafraichir()
        # Les étapes synchrones bloquent la boucle Qt : on laisse la fenêtre
        # se redessiner à chaque changement d'état.
        QApplication.processEvents()

    def demarrer(self, cle, detail=None):
        self._poser(cle, 'cours', detail)

    def poser_planches(self, cle):
        self._poser(cle, 'pose', i18n.tr('se_detail_pose'))

    def terminer(self, cle, ok=True, detail=None):
        self._poser(cle, 'fait' if ok else 'erreur', detail)

    def abandonner(self, cle):
        if self.est_en_attente(cle):
            self._poser(cle, 'abandon')

    def abandonner_restantes(self):
        """Étapes encore à faire ou en attente de pose : abandonnées."""
        for cle, e in self._etat.items():
            if e[0] in ('attente', 'pose', 'cours'):
                self._poser(cle, 'abandon')

    def est_en_attente(self, cle):
        return self._etat.get(cle, ['non'])[0] in ('attente', 'pose', 'cours')

    def fin(self, dossier=None):
        self._dossier = dossier
        self.btn_dossier.setEnabled(bool(dossier))
        self._termine = True
        self._total_final = time.monotonic() - self._debut
        self._rafraichir()
        self._minuteur.stop()

    # ── Affichage ───────────────────────────────────────────────────────

    def _rafraichir(self):
        maintenant = time.monotonic()
        for cle, item in self._items.items():
            etat, debut, duree, detail = self._etat[cle]
            item.setText(0, _ICONES[etat])
            if etat == 'non':
                temps = i18n.tr('se_non_demande')
            elif etat == 'attente':
                temps = i18n.tr('se_a_faire')
            elif duree is not None:
                temps = _duree(duree)
            elif debut is not None:
                temps = _duree(maintenant - debut)
            else:
                temps = ""
            item.setText(2, temps)
            item.setToolTip(1, detail or "")
            item.setText(1, self._libelle(cle) + (("  — " + detail) if detail and etat in ('pose', 'erreur') else ""))
            brosse = QBrush(QColor(_COULEURS[etat]))
            for col in range(3):
                item.setForeground(col, brosse)
            f = QFont(item.font(1))
            f.setBold(etat in ('cours', 'pose'))
            f.setItalic(etat == 'non')
            item.setFont(1, f)
        total = (self._total_final if self._termine else maintenant - self._debut)
        cle_total = 'se_total_fini' if self._termine else 'se_total_en_cours'
        self.total.setText(i18n.tr(cle_total, temps=_duree(total)))

    def _libelle(self, cle):
        return i18n.tr(dict(ETAPES)[cle])

    def _ouvrir_dossier(self):
        if self._dossier:
            from ..tools.notification import ouvrir_dossier
            ouvrir_dossier(self._dossier)

    def closeEvent(self, event):
        self._minuteur.stop()
        if self in _ouverte:
            _ouverte.remove(self)
        super().closeEvent(event)
