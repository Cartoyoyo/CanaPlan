# -*- coding: utf-8 -*-
"""Avertissement d'usage : les résultats de CanaPlan sont indicatifs.

Métrés, cubatures, profils, cotes et pentes se vérifient par les moyens de
l'utilisateur ; le logiciel ne se substitue pas à une étude complète. La
licence GPL v3 exclut déjà toute garantie (articles 15 et 16), mais en anglais
et là où personne ne la lit : ce module rend l'avertissement visible là où
les chiffres servent.

Trois formes :

* une fenêtre à la **première utilisation d'une fonction** — pas au lancement
  de QGIS — que l'utilisateur ferme par « J'ai compris ». L'acceptation est
  mémorisée en QSettings et survit aux sessions : la fenêtre ne revient plus.
  Fermée autrement, la fonction ne se lance pas ;
* le texte complet dans « À propos » et en tête du rapport de cubature ;
* une mention courte dans les rapports de cubature : fenêtre de résultats,
  pied de page du PDF, classeur Excel, fin du CSV. Choix de l'utilisateur :
  **rien** sur les plans, profils et coupes, qui sont des pièces graphiques.

Le pilotage par script (`tools/api.py`) ne passe pas par les actions du menu :
il n'est jamais bloqué par la fenêtre.
"""
from qgis.PyQt.QtCore import QSettings

from . import i18n

_CLE = "CanaPlan/avertissement_compris"


def est_compris():
    valeur = QSettings().value(_CLE, False)
    return valeur in (True, 1, "1", "true", "True")


def marquer_compris():
    QSettings().setValue(_CLE, True)


def reinitialiser():
    """Fait réapparaître la fenêtre à la prochaine utilisation (tests, démo)."""
    QSettings().remove(_CLE)


def texte():
    """Texte complet, sans titre."""
    return i18n.tr('avert_texte')


def texte_court():
    """Mention d'une ligne pour le pied des documents produits."""
    return i18n.tr('avert_court')


def confirmer(parent=None):
    """Vrai si l'avertissement est accepté — déjà, ou à l'instant.

    Affiche la fenêtre tant que l'utilisateur n'a pas cliqué « J'ai compris ».
    """
    if est_compris():
        return True
    from qgis.PyQt.QtWidgets import QMessageBox
    from .qt_exec import exec_dialog

    boite = QMessageBox(parent)
    boite.setIcon(QMessageBox.Icon.Warning)
    boite.setWindowTitle("CanaPlan — %s" % i18n.tr('avert_titre'))
    boite.setText("<b>%s</b>" % i18n.tr('avert_titre'))
    boite.setInformativeText("%s\n\n%s" % (texte(), i18n.tr('avert_question')))
    compris = boite.addButton(i18n.tr('avert_compris'),
                              QMessageBox.ButtonRole.AcceptRole)
    boite.addButton(i18n.tr('annuler'), QMessageBox.ButtonRole.RejectRole)
    boite.setDefaultButton(compris)
    exec_dialog(boite)
    if boite.clickedButton() is compris:
        marquer_compris()
        return True
    return False


