# -*- coding: utf-8 -*-
"""Liaison QGIS pour tools/altimetrie.py.

Le moteur d'échantillonnage ne connaît pas QGIS : il prend des points en
Lambert 93 et rend des altitudes. C'est ici qu'on lui donne les ouvrages du
projet, la transformation vers WGS84 dont a besoin le repli API REST, et le
rapport CSV qui tient lieu de traçabilité — le schéma des couches n'ayant pas
de champ de provenance, c'est ce fichier qui dit ce qui est levé et ce qui est
estimé.
"""

import csv
import os
from datetime import datetime

from qgis.core import (QgsCoordinateReferenceSystem, QgsCoordinateTransform,
                       QgsProject, NULL)

from . import altimetrie
from .projet_bet import project_dir

L93 = "EPSG:2154"
WGS84 = "EPSG:4326"

ROLES = ('regard', 'tabouret')
FE_FIELD = {'regard': 'fe_radier', 'tabouret': 'fe_entree'}


def _fnum(val):
    if val is None or val == NULL:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _sval(val, defaut=''):
    if val is None or val == NULL:
        return defaut
    return str(val).strip() or defaut


def collecter_points(couches, roles=ROLES):
    """Ouvrages ponctuels du réseau, prêts pour le moteur d'altimétrie.

    Retourne (points, infos) où `points` est la liste de ((role, fid), x, y)
    attendue par altimetrie.echantillonner et `infos` le détail de chaque
    ouvrage pour l'aperçu et le rapport."""
    points, infos = [], {}
    for role in roles:
        layer = couches.get(role)
        if layer is None:
            continue
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            pt = geom.asPoint()
            cle = (role, feat.id())
            points.append((cle, pt.x(), pt.y()))
            infos[cle] = {
                'role': role,
                'fid': feat.id(),
                'nom': _sval(feat['nom'], "#{}".format(feat.id())),
                'x': pt.x(), 'y': pt.y(),
                'tn': _fnum(feat['tn']),
            }
    return points, infos


def transformateur(crs_source=None):
    """Callable (x, y) -> (lon, lat) pour le repli API REST, ou None si la
    transformation n'est pas disponible."""
    src = crs_source or QgsCoordinateReferenceSystem(L93)
    if not src.isValid():
        return None
    tr = QgsCoordinateTransform(src, QgsCoordinateReferenceSystem(WGS84),
                                QgsProject.instance())

    def to_wgs84(x, y):
        pt = tr.transform(x, y)
        return pt.x(), pt.y()

    return to_wgs84


def crs_reseau(couches, roles=ROLES):
    """CRS des couches d'ouvrages, pour ne pas supposer le Lambert 93."""
    for role in roles:
        layer = couches.get(role)
        if layer is not None and layer.crs().isValid():
            return layer.crs()
    return QgsCoordinateReferenceSystem(L93)


def echantillonner_reseau(couches, roles=ROLES, log=None):
    """Collecte + échantillonnage. Retourne (infos, resultats)."""
    points, infos = collecter_points(couches, roles)
    if not points:
        return infos, {}
    resultats = altimetrie.echantillonner(
        points, to_wgs84=transformateur(crs_reseau(couches, roles)), log=log)
    return infos, resultats


# ────────────────────────────────────────────────────────── rapport

ENTETES = ["horodatage", "reseau", "type", "nom", "fid", "x_l93", "y_l93",
           "tn_avant", "tn_mnt", "ecart", "source", "applique"]


def ecrire_rapport(lignes, reseau, dossier=None):
    """Écrit le rapport CSV horodaté dans le dossier du projet.

    `lignes` : liste de dicts (cf. ENTETES, sans 'horodatage' ni 'reseau').
    Retourne le chemin écrit, ou '' si aucun dossier projet n'est connu.
    """
    dossier = dossier or project_dir()
    if not dossier or not os.path.isdir(dossier):
        return ''
    maintenant = datetime.now()
    chemin = os.path.join(
        dossier, "altimetrie_{}_{}.csv".format(
            reseau, maintenant.strftime("%Y%m%d_%H%M%S")))
    stamp = maintenant.strftime("%Y-%m-%d %H:%M:%S")
    with open(chemin, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(ENTETES)
        for l in lignes:
            w.writerow([
                stamp, reseau, l.get('type', ''), l.get('nom', ''),
                l.get('fid', ''),
                _csvnum(l.get('x')), _csvnum(l.get('y')),
                _csvnum(l.get('tn_avant'), 3), _csvnum(l.get('tn_mnt'), 3),
                _csvnum(l.get('ecart'), 3),
                l.get('source', ''),
                "oui" if l.get('applique') else "non",
            ])
    return chemin


def _csvnum(val, decimales=2):
    if val is None:
        return ''
    # Virgule décimale : le rapport est relu dans Excel en locale française.
    return ("{:." + str(decimales) + "f}").format(val).replace('.', ',')
