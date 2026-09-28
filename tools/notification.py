# tools/notification.py
"""Compte rendu de fin d'export, sans fenêtre à valider.

Un export réussi n'a pas à bloquer l'utilisateur sur un « OK » : le compte
rendu part dans la barre de messages de QGIS, disparaît seul, et propose
d'ouvrir le dossier de sortie. Les détails (liste des fichiers, ordre des
pièces…) restent accessibles derrière un bouton, sans s'imposer.
"""

import os

from qgis.core import Qgis
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QPushButton

from . import i18n

DUREE_S = 15


def _barre():
    from qgis.utils import iface
    return iface.messageBar() if iface is not None else None


def ouvrir_dossier(chemin):
    """Ouvre dans l'explorateur le dossier `chemin` (ou celui du fichier)."""
    dossier = chemin if os.path.isdir(chemin) else os.path.dirname(os.path.abspath(chemin))
    QDesktopServices.openUrl(QUrl.fromLocalFile(dossier))


_visionneuses = []   # gardées en vie : la fenêtre est non modale


def _voir_details(titre, details):
    from qgis.gui import QgsMessageViewer
    from qgis.utils import iface
    v = QgsMessageViewer(iface.mainWindow() if iface else None)
    v.setWindowTitle(titre)
    v.setMessageAsPlainText(details)
    v.show()
    _visionneuses[:] = [w for w in _visionneuses if w.isVisible()] + [v]


def export_termine(titre, texte, chemin, details=None, niveau=Qgis.MessageLevel.Success):
    """Annonce un export terminé, avec un bouton « Ouvrir le dossier ».

    chemin  : fichier écrit ou dossier de sortie.
    details : texte long facultatif (plusieurs lignes), derrière « Plus ».
    """
    barre = _barre()
    if barre is None:
        return
    item = barre.createMessage(titre, texte)
    if details:
        bouton_details = QPushButton(i18n.tr('msg_details'))
        bouton_details.clicked.connect(lambda _=False: _voir_details(titre, details))
        item.layout().addWidget(bouton_details)
    if chemin:
        bouton = QPushButton("📂 " + i18n.tr('msg_ouvrir_dossier'))
        bouton.clicked.connect(lambda _=False, c=chemin: ouvrir_dossier(c))
        item.layout().addWidget(bouton)
    item.setLevel(niveau)
    item.setDuration(DUREE_S)
    barre.pushItem(item)
