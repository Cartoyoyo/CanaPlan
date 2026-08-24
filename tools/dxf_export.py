# -*- coding: utf-8 -*-
"""Export DXF 2018 fidèle au plan QGIS.

Logique commune utilisée par main._export_dxf_direct (export sur l'emprise
du canvas) et PrintTool._export_dxf (export sur l'emprise des feuilles
posées). Suit à l'identique le pattern du Processing algorithm officiel
QGIS (cf. src/analysis/processing/qgsalgorithmdxfexport.cpp).

Pour les fonds + cadres + lignes de rappel des étiquettes regards/tabourets
— que QgsDxfExport ne sait pas exporter — un post-traitement avec ezdxf
est appliqué après l'écriture (voir tools.dxf_postprocess).
"""

import os
from qgis.PyQt.QtCore import Qt, QFile, QIODevice
from qgis.PyQt.QtWidgets import QApplication, QMessageBox
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsDxfExport, QgsMapSettings,
)

from . import i18n


# Préfixe des couches mémoire générées par le plugin (à exclure de l'export)
_INTERNAL_LAYER_PREFIX = '_bet_'


def collect_visible_vector_layers():
    """Retourne la liste des couches vectorielles visibles, hors couches
    internes du plugin, dans l'ordre d'affichage (haut de la légende d'abord).
    """
    root = QgsProject.instance().layerTreeRoot()
    layers = []
    for node in root.findLayers():
        if not node.isVisible():
            continue
        lyr = node.layer()
        if lyr is None or not isinstance(lyr, QgsVectorLayer):
            continue
        if lyr.name().startswith(_INTERNAL_LAYER_PREFIX):
            continue
        layers.append(lyr)
    return layers


def export_dxf(iface, dxf_path, extent, scale, *,
               force_2d=True, use_mtext=True,
               layer_title_as_name=False, encoding="CP1252"):
    """Écrit un DXF 2018 en suivant à l'identique le pattern de l'export
    natif QGIS (cf. src/analysis/processing/qgsalgorithmdxfexport.cpp).

    Points clés du pattern canonique :
      - Le QgsMapSettings est quasi vide : seul transformContext est défini.
        AUCUN setLayers / setExtent / setOutputSize / setOutputDpi /
        setDestinationCrs n'est appliqué dessus. C'est QgsDxfExport qui
        gère la liste des couches, l'extent et le CRS de destination
        directement, indépendamment du mapSettings.
      - Ordre des appels : setMapSettings → addLayers → setSymbologyScale
        → setSymbologyExport → setLayerTitleAsName → setDestinationCrs
        → setForce2d → setExtent (si non vide) → setFlags → writeToFile.
      - L'encoding par défaut est CP1252 (compatibilité AutoCAD).

    Args:
        iface: QgisInterface.
        dxf_path: chemin de sortie (.dxf).
        extent: QgsRectangle dans le CRS du projet, ou None pour exporter
            l'emprise complète des couches.
        scale: échelle cible (dénominateur, ex: 200.0 pour 1:200).
        force_2d: aplatit les géométries Z (recommandé pour AutoCAD).
        use_mtext: si True (défaut) utilise des entités MTEXT pour les
            étiquettes. Si False, simples TEXT (compat plus large).
        layer_title_as_name: si True, utilise le titre QGIS de la couche
            comme nom DXF ; sinon le nom QGIS de la couche.
        encoding: encodage DXF — CP1252 par défaut pour AutoCAD.

    Lève RuntimeError en cas d'échec d'écriture.
    """
    project = QgsProject.instance()
    project_crs = project.crs()

    vis_layers = collect_visible_vector_layers()
    if not vis_layers:
        raise RuntimeError(i18n.tr('dxf_aucune_couche'))

    # Ordre Z : top de la légende = dessiné en dernier. findLayers() renvoie
    # top→bottom ; on inverse pour bottom→top (ordre d'écriture DXF).
    all_layers = list(reversed(vis_layers))

    # ── QgsMapSettings minimaliste : uniquement le transformContext.
    # Aucun setLayers / setExtent / setOutputSize / setDestinationCrs ici —
    # exactement comme le fait QgsDxfExportAlgorithm en C++.
    ms = QgsMapSettings()
    ms.setTransformContext(project.transformContext())

    export = QgsDxfExport()
    export.setMapSettings(ms)
    export.addLayers([QgsDxfExport.DxfLayer(l) for l in all_layers])
    export.setSymbologyScale(float(scale))

    # Symbologie : SymbolLayerSymbology = fidélité maximale.
    _sym = (getattr(QgsDxfExport, 'SymbolLayerSymbology', None)
            or getattr(getattr(QgsDxfExport, 'SymbologyExport', None),
                       'SymbolLayerSymbology', None)
            or 2)
    export.setSymbologyExport(_sym)

    export.setLayerTitleAsName(bool(layer_title_as_name))
    export.setDestinationCrs(project_crs)
    if hasattr(export, 'setForce2d'):
        export.setForce2d(bool(force_2d))

    if extent is not None and not extent.isEmpty():
        export.setExtent(extent)

    # Flags : par défaut MText activé. FlagNoMText uniquement si désactivé.
    flags_cls = getattr(QgsDxfExport, 'Flags', None) or getattr(QgsDxfExport, 'Flag', None)
    flags = flags_cls() if flags_cls is not None else 0
    if not use_mtext:
        no_mtext = getattr(QgsDxfExport, 'FlagNoMText', None)
        if no_mtext is not None:
            flags = flags | no_mtext
    if hasattr(export, 'setFlags'):
        try:
            export.setFlags(flags)
        except (TypeError, ValueError):
            pass

    f = QFile(dxf_path)
    if not f.open(QIODevice.WriteOnly | QIODevice.Truncate):
        raise RuntimeError(i18n.tr('dxf_ouverture_impossible', chemin=dxf_path))
    try:
        result = export.writeToFile(f, encoding)
    finally:
        f.close()

    result_int = int(result) if not isinstance(result, int) else result
    if result_int != 0:
        raise RuntimeError(i18n.tr('dxf_code_retour', code=result_int))

    return len(vis_layers)


def open_dxf_externally(dxf_path):
    """Ouvre le DXF avec l'application système associée, en isolant
    temporairement les variables d'environnement Qt de QGIS pour éviter que
    AutoCAD (qui utilise Qt depuis 2019) charge des DLL incompatibles.
    """
    saved = {}
    try:
        for key in list(os.environ):
            if key.startswith('QT_'):
                saved[key] = os.environ.pop(key)
        os.startfile(dxf_path)
    except Exception:
        pass
    finally:
        for key, val in saved.items():
            os.environ[key] = val


def run_export_dxf_with_ui(iface, dxf_path, extent, scale, *,
                           with_label_decorations=True, force_2d=True,
                           open_after=True):
    """Wrapper : exécute l'export avec gestion du curseur d'attente, post-
    traitement des étiquettes regards/tabourets (fond + cadre + callout via
    ezdxf), message bar et ouverture du fichier après écriture.

    Retourne True si l'export a réussi, False sinon.
    """
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        n_layers = export_dxf(
            iface, dxf_path, extent, scale, force_2d=force_2d)
    except Exception as exc:
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('pt_export_dxf'),
            i18n.tr('ot_erreur_dxf', erreur=exc))
        return False

    n_symbols = 0
    n_decorated = 0
    if with_label_decorations:
        try:
            from .dxf_postprocess import add_point_symbols, add_label_decorations
            # Symboles ponctuels d'abord (z-order inférieur aux étiquettes)
            n_symbols = add_point_symbols(dxf_path)
        except Exception as exc:
            iface.messageBar().pushMessage(
                i18n.tr('pt_export_dxf'),
                i18n.tr('ot_dxf_symboles', erreur=exc),
                level=1, duration=6,
            )
        try:
            from .dxf_postprocess import apply_ltscale
            apply_ltscale(dxf_path, scale)
        except Exception as exc:
            iface.messageBar().pushMessage(
                i18n.tr('pt_export_dxf'),
                i18n.tr('ot_dxf_ltscale', erreur=exc),
                level=1, duration=6,
            )
        try:
            from .dxf_postprocess import add_label_decorations
            n_decorated = add_label_decorations(dxf_path)
        except Exception as exc:
            # Le DXF est déjà écrit ; on ne bloque pas l'export pour autant
            iface.messageBar().pushMessage(
                i18n.tr('pt_export_dxf'),
                i18n.tr('ot_dxf_etiquettes', erreur=exc),
                level=1, duration=6,
            )
    QApplication.restoreOverrideCursor()

    suffix = (i18n.tr('dxf_etiquettes_decorees', nb=n_decorated)
              if n_decorated else "")
    iface.messageBar().pushMessage(
        i18n.tr('pt_export_dxf'),
        i18n.tr('ot_dxf_exporte', nb=str(n_layers) + suffix, chemin=dxf_path),
        level=0, duration=8,
    )
    if open_after:
        open_dxf_externally(dxf_path)
    return True
