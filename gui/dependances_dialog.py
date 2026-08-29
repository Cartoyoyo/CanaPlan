# gui/dependances_dialog.py
"""Fenêtre d'installation des bibliothèques nécessaires à l'export DXF.

Ouverte uniquement au moment où l'utilisateur demande une fonction qui en
dépend, jamais au démarrage. Voir tools/dependances.py.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QPlainTextEdit, QApplication,
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal

from ..tools import i18n
from ..tools import dependances


class _Installateur(QThread):
    """Lance pip hors du fil de l'interface.

    pip prend de dix secondes a plusieurs minutes selon la ligne : le faire
    dans le fil principal figerait QGIS entier, sans meme repeindre la barre
    de progression.
    """
    fini = pyqtSignal(bool, str)

    def __init__(self, paquets, parent=None):
        super().__init__(parent)
        self._paquets = paquets

    def run(self):
        ok, sortie = dependances.installer(self._paquets)
        self.fini.emit(ok, sortie)


class DependancesDialog(QDialog):
    def __init__(self, paquets, parent=None):
        super().__init__(parent)
        self._paquets = list(paquets)
        self._thread = None
        self.setWindowTitle(i18n.tr('dep_titre'))
        self.setMinimumWidth(560)

        vb = QVBoxLayout(self)

        self._msg = QLabel(i18n.tr('dep_explication',
                                   paquets=", ".join(self._paquets)))
        self._msg.setWordWrap(True)
        vb.addWidget(self._msg)

        self._dest = QLabel(i18n.tr('dep_destination',
                                    dossier=dependances.libs_dir()))
        self._dest.setWordWrap(True)
        self._dest.setStyleSheet("color: #666;")
        vb.addWidget(self._dest)

        self._barre = QProgressBar()
        self._barre.setRange(0, 0)          # indéterminée : pip ne dit rien
        self._barre.setVisible(False)
        vb.addWidget(self._barre)

        self._journal = QPlainTextEdit()
        self._journal.setReadOnly(True)
        self._journal.setVisible(False)
        self._journal.setMaximumHeight(180)
        vb.addWidget(self._journal)

        ligne = QHBoxLayout()
        ligne.addStretch()
        self._btn_annuler = QPushButton(i18n.tr('dep_plus_tard'))
        self._btn_annuler.clicked.connect(self.reject)
        ligne.addWidget(self._btn_annuler)
        self._btn_installer = QPushButton(i18n.tr('dep_installer'))
        self._btn_installer.setDefault(True)
        self._btn_installer.clicked.connect(self._lancer)
        ligne.addWidget(self._btn_installer)
        vb.addLayout(ligne)

    # ------------------------------------------------------------------

    def _lancer(self):
        self._btn_installer.setEnabled(False)
        self._btn_annuler.setEnabled(False)
        self._barre.setVisible(True)
        self._msg.setText(i18n.tr('dep_en_cours'))
        QApplication.processEvents()

        self._thread = _Installateur(self._paquets, self)
        self._thread.fini.connect(self._termine)
        self._thread.start()

    def _termine(self, ok, sortie):
        self._barre.setVisible(False)
        self._btn_annuler.setEnabled(True)

        if ok and dependances.tout_est_la():
            self._msg.setText(i18n.tr('dep_succes'))
            self._btn_annuler.setText(i18n.tr('dep_fermer'))
            self._btn_annuler.clicked.disconnect()
            self._btn_annuler.clicked.connect(self.accept)
            return

        # Echec : on montre la sortie de pip telle quelle, puis la commande a
        # rejouer a la main. C'est ce qui permet de debloquer un poste derriere
        # un proxy, ou de transmettre le probleme au service informatique.
        self._msg.setText(i18n.tr('dep_echec'))
        self._journal.setVisible(True)
        texte = (sortie or "").strip()
        if not ok and not dependances.tout_est_la() and not texte:
            texte = i18n.tr('dep_echec_sans_detail')
        self._journal.setPlainText(
            texte + "\n\n" + i18n.tr('dep_commande_manuelle') + "\n"
            + dependances.commande_manuelle(self._paquets))
        self._btn_installer.setEnabled(True)
        self._btn_installer.setText(i18n.tr('dep_reessayer'))
        self.adjustSize()

    def reject(self):
        if self._thread is not None and self._thread.isRunning():
            return                      # une installation en cours va au bout
        super().reject()
