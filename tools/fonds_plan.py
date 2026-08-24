# tools/fonds_plan.py
"""Embarquement des couches de fond de plan dans l'archive .bet.

Le .bet ne contenait que les 8 couches métier (conduite / branchement /
regard / tabouret × EU / EP). Tout ce qui les entoure — fonds WMS, extraits
WFS, imports DXF ou Star-DT — était perdu à la réouverture.

Deux traitements selon la nature de la couche :

* raster de flux (WMS / WMTS / XYZ) : seule l'URI est mémorisée. Le flux est
  réinterrogé à l'ouverture, donc le fond reste à jour et l'archive ne
  grossit pas.
* vecteur (GeoJSON WFS, GPKG issu d'un DXF, GML Star-DT, couche mémoire) : le
  fichier source est copié dans l'archive. Indispensable pour les extraits
  WFS, écrits dans %TEMP%/canaplan/ que purge_temp_dir() vide à chaque
  démarrage du plugin, et pour les imports dont le fichier d'origine peut
  disparaître ou changer de poste.

Le style est enregistré en .qml à côté de chaque couche : les fonds WFS sont
mis en forme par du code au chargement, pas par un style de projet.
"""
import os

from . import i18n
from qgis.core import (QgsRasterLayer, QgsVectorLayer, QgsLayerTreeLayer,
                       QgsVectorFileWriter, QgsCoordinateTransformContext)

# Dossier des fonds à l'intérieur de l'archive .bet
ARCH_DIR = "fonds"

# Providers raster dont l'URI suffit à reconstruire la couche
_STREAM_PROVIDERS = ('wms', 'wmts', 'xyz', 'arcgismapserver')


def _safe_name(name):
    """Nom de fichier sûr pour une archive ZIP, dérivé du nom de couche."""
    keep = [c if (c.isalnum() or c in ' -_') else '_' for c in name]
    return ''.join(keep).strip().replace(' ', '_') or 'couche'


def _source_file(layer):
    """(chemin, nom_de_couche_interne) de la source d'un vecteur, ou (None, None).

    Les sources OGR portent parfois un suffixe — un GPKG s'écrit
    « chemin|layername=xxx » — qu'il faut séparer du chemin réel.
    """
    source = layer.source()
    if not source:
        return None, None
    morceaux = source.split('|')
    path = morceaux[0]
    layername = None
    for part in morceaux[1:]:
        if part.startswith('layername='):
            layername = part[len('layername='):]
    if not os.path.exists(path):
        return None, None
    return path, layername


def _capture_style(layer, qml_path):
    """Écrit le style de la couche en .qml. Retourne True si réussi."""
    try:
        layer.saveNamedStyle(qml_path)
    except Exception:
        return False
    return os.path.exists(qml_path)


def _read_opacity(layer):
    """Opacité de la couche (0.0 à 1.0), quel que soit son type."""
    try:
        if isinstance(layer, QgsRasterLayer):
            renderer = layer.renderer()
            return float(renderer.opacity()) if renderer is not None else 1.0
        return float(layer.opacity())
    except Exception:
        return 1.0


def _apply_opacity(layer, opacity):
    try:
        if isinstance(layer, QgsRasterLayer):
            renderer = layer.renderer()
            if renderer is not None:
                renderer.setOpacity(opacity)
        else:
            layer.setOpacity(opacity)
    except Exception:
        pass


def collect(project, metier_ids, work_dir):
    """Décrit les fonds du projet et prépare les fichiers à archiver.

    metier_ids : ids des 8 couches métier, à exclure.
    work_dir   : dossier de travail pour les .qml et les exports mémoire.

    Retourne (entries, files, errors), où files liste des (arcname, chemin).
    """
    entries, files, errors = [], [], []
    rang = 0

    for node in project.layerTreeRoot().children():
        if not isinstance(node, QgsLayerTreeLayer):
            continue                    # groupes EU / EP : couches métier
        layer = node.layer()
        if layer is None or layer.id() in metier_ids:
            continue

        provider = layer.providerType()
        base = "%02d_%s" % (rang, _safe_name(layer.name()))
        entry = {
            "name":     layer.name(),
            "provider": provider,
            "visible":  node.isVisible(),
            "opacity":  _read_opacity(layer),
            "scale_visibility": {
                "enabled": bool(layer.hasScaleBasedVisibility()),
                "minimum": float(layer.minimumScale()),
                "maximum": float(layer.maximumScale()),
            },
        }

        if isinstance(layer, QgsRasterLayer):
            if provider not in _STREAM_PROVIDERS:
                errors.append(i18n.tr('fp_raster_local', couche=layer.name()))
                continue
            entry["kind"] = "raster"
            entry["source"] = layer.source()

        elif isinstance(layer, QgsVectorLayer):
            entry["kind"] = "vector"
            if provider == 'memory':
                # Couche volatile : on la matérialise en GPKG dans l'archive.
                dest = os.path.join(work_dir, base + ".gpkg")
                opts = QgsVectorFileWriter.SaveVectorOptions()
                opts.driverName = 'GPKG'
                opts.layerName = _safe_name(layer.name())
                err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
                    layer, dest, QgsCoordinateTransformContext(), opts)
                if err != QgsVectorFileWriter.NoError:
                    errors.append("%s : %s" % (layer.name(), msg))
                    continue
                entry["file"] = ARCH_DIR + "/" + base + ".gpkg"
                entry["layername"] = opts.layerName
                files.append((entry["file"], dest))
            else:
                path, layername = _source_file(layer)
                if path is None:
                    errors.append(i18n.tr('fp_source_introuvable',
                                          couche=layer.name()))
                    continue
                ext = os.path.splitext(path)[1] or ".dat"
                entry["file"] = ARCH_DIR + "/" + base + ext
                if layername:
                    entry["layername"] = layername
                files.append((entry["file"], path))
        else:
            continue                    # maillage, nuage de points : hors champ

        qml_local = os.path.join(work_dir, base + ".qml")
        if _capture_style(layer, qml_local):
            entry["qml"] = ARCH_DIR + "/" + base + ".qml"
            files.append((entry["qml"], qml_local))

        entries.append(entry)
        rang += 1

    return entries, files, errors


def restore(project, entries, base_dir):
    """Recrée les fonds sous les couches métier, dans l'ordre enregistré.

    base_dir : dossier où l'archive a été extraite.
    Retourne la liste des messages d'erreur.
    """
    errors = []
    root = project.layerTreeRoot()
    deja_presentes = {l.name() for l in project.mapLayers().values()}

    for entry in entries or []:
        name = entry.get("name") or "Fond de plan"
        if name in deja_presentes:
            continue                    # déjà chargée : on ne duplique pas

        if entry.get("kind") == "raster":
            layer = QgsRasterLayer(entry.get("source", ""), name,
                                   entry.get("provider", "wms"))
        else:
            rel = entry.get("file", "")
            path = os.path.join(base_dir, *rel.split("/")) if rel else ""
            if not path or not os.path.exists(path):
                errors.append(i18n.tr('fp_donnees_absentes', couche=name))
                continue
            uri = path
            if entry.get("layername"):
                uri = path + "|layername=" + entry["layername"]
            layer = QgsVectorLayer(uri, name, "ogr")

        if layer is None or not layer.isValid():
            errors.append(i18n.tr('fp_couche_invalide', couche=name))
            continue

        qml_rel = entry.get("qml")
        if qml_rel:
            qml_path = os.path.join(base_dir, *qml_rel.split("/"))
            if os.path.exists(qml_path):
                try:
                    layer.loadNamedStyle(qml_path)
                except Exception as exc:
                    errors.append(i18n.tr('fp_style_non_applique',
                                          couche=name, detail=exc))

        _apply_opacity(layer, entry.get("opacity", 1.0))

        scale = entry.get("scale_visibility") or {}
        if scale.get("enabled"):
            layer.setMinimumScale(scale.get("minimum", 0.0))
            layer.setMaximumScale(scale.get("maximum", 0.0))
            layer.setScaleBasedVisibility(True)

        project.addMapLayer(layer, False)
        node = QgsLayerTreeLayer(layer)
        node.setItemVisibilityChecked(bool(entry.get("visible", True)))
        # -1 : en bas de la légende, sous les groupes EU / EP restaurés avant.
        root.insertChildNode(-1, node)

    return errors


def extract_into(zf, base_dir):
    """Extrait le dossier des fonds de l'archive vers base_dir."""
    noms = [n for n in zf.namelist() if n.startswith(ARCH_DIR + "/")]
    for nom in noms:
        zf.extract(nom, base_dir)
    return bool(noms)
