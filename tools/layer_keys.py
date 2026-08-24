# tools/layer_keys.py
"""Persistance des IDs de couches BET (conduite/branchement/regard/tabouret).

Historiquement en QSettings *globales* (CanaPlan/couche_<role>_<reseau>),
donc partagées entre tous les projets QGIS : ouvrir le projet B après le
projet A faisait pointer les clés vers des couches inexistantes (couches
recréées vides), voire vers de mauvaises couches.

Désormais : le fichier de PROJET est la référence (writeEntry/readEntry),
les QSettings ne servent plus que de repli en lecture pour les projets
enregistrés avant cette version (et sont maintenues en écriture pour
rester compatibles avec une éventuelle session ancienne).
"""
from qgis.core import QgsProject
from qgis.PyQt.QtCore import QSettings

SCOPE = "CanaPlan"


def layer_key(role, reseau):
    return f"couche_{role}_{reseau.lower()}"


def get_layer_id(role, reseau):
    """ID de couche pour (role, reseau) : projet d'abord, QSettings en repli."""
    key = layer_key(role, reseau)
    val, ok = QgsProject.instance().readEntry(SCOPE, key)
    if ok and val:
        return val
    return QSettings().value(f"{SCOPE}/{key}")


def set_layer_id(role, reseau, layer_id):
    """Écrit l'ID dans le projet (référence) + QSettings (compatibilité)."""
    key = layer_key(role, reseau)
    QgsProject.instance().writeEntry(SCOPE, key, layer_id)
    QSettings().setValue(f"{SCOPE}/{key}", layer_id)
