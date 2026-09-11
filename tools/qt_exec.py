# -*- coding: utf-8 -*-
"""Appel modal compatible PyQt5 et PyQt6.

PyQt5 5.15 expose bien `QDialog.exec`, mais l'entrée n'implémente pas le
protocole descripteur : sur une instance, `dlg.exec` rend la fonction NON liée
(`<built-in function exec>`), l'appel part donc sans `self` et PyQt lève

    TypeError: exec(self): first argument of unbound method must have type 'QDialog'

Seul `exec_()` est correctement lié sous PyQt5 — mais il a disparu de PyQt6.
Passer par `exec_dialog()` couvre les deux bindings sans présumer duquel on
dépend, y compris pour QMessageBox, QMenu et QWizard, qui souffrent du même
défaut de liaison.
"""

__all__ = ["exec_dialog"]


def exec_dialog(dialog):
    """Ouvre `dialog` en modal et rend son code de sortie.

    Sous PyQt5 on prend `exec_()`, le seul accesseur lié ; sous PyQt6, où
    `exec_` n'existe plus, on retombe sur `exec()`. Le dernier recours appelle
    la fonction non liée en lui passant `self` à la main, ce qui reste valable
    quel que soit le binding.
    """
    runner = getattr(dialog, "exec_", None)
    if runner is not None:
        return runner()
    runner = getattr(dialog, "exec", None)
    if runner is not None:
        try:
            return runner()
        except TypeError:
            # Entrée non liée : on fournit `self` explicitement.
            return type(dialog).exec(dialog)
    raise TypeError("objet non modal : %r" % (type(dialog).__name__,))
