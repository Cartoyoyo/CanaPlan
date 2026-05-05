# tools/projet_bet.py
import json
import os
import shutil
import tempfile
import zipfile
from datetime import date, datetime

from qgis.core import (QgsProject, QgsVectorLayer, QgsVectorFileWriter,
                       QgsRectangle, QgsCoordinateTransform,
                       QgsMemoryProviderUtils, QgsFeature, QgsLayerTreeGroup,
                       QgsUnitTypes)
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QProgressDialog, QApplication


def _copy_to_memory(layer):
    """Copie une couche vectorielle dans un provider mémoire (libère tout verrou fichier)."""
    mem = QgsMemoryProviderUtils.createMemoryLayer(
        layer.name(), layer.fields(), layer.wkbType(), layer.crs())
    mem.startEditing()
    for feat in layer.getFeatures():
        mem.addFeature(QgsFeature(feat))
    mem.commitChanges()
    return mem

_PREFIX = "BET_HUMIDE/"
_ROLES  = ('conduite', 'branchement', 'regard', 'tabouret')
_RESEAUX = ('EU', 'EP')


# ─────────────────────────────────────────────────────────────────────────────
#  Enregistrer
# ─────────────────────────────────────────────────────────────────────────────

_KEY_BET_PATH = _PREFIX + "current_bet_path"


def _read_label_size(project, s):
    """Lit la taille des étiquettes depuis la première couche disponible.
    Retourne un dict {'unit': 'points'|'map_units', 'value': float} ou None."""
    for reseau in _RESEAUX:
        key      = _PREFIX + f"couche_conduite_{reseau.lower()}"
        layer_id = s.value(key)
        layer    = project.mapLayer(layer_id) if layer_id else None
        if layer is None:
            continue
        labeling = layer.labeling()
        if labeling is None:
            continue
        fmt  = labeling.settings().format()
        unit = ('points' if fmt.sizeUnit() == QgsUnitTypes.RenderPoints
                else 'map_units')
        return {'unit': unit, 'value': fmt.size()}
    return None


def _get_or_create_group(project, reseau):
    """Retourne le groupe EU ou EP dans la légende (le crée en tête si absent)."""
    root = project.layerTreeRoot()
    group = root.findGroup(reseau)
    if group is None:
        group = root.insertGroup(0, reseau)
    return group


def project_dir():
    """Retourne le répertoire du projet BET courant, ou '' si aucun projet enregistré."""
    bet_path = QSettings().value(_KEY_BET_PATH, "")
    if bet_path:
        d = os.path.dirname(bet_path)
        if os.path.isdir(d):
            return d
    return ""


def _ask_bet_path(iface):
    """Demande dossier + nom et retourne (gpkg_temp_path, bet_path) ou (None, None)."""
    proj_dir = QFileDialog.getExistingDirectory(
        iface.mainWindow(),
        "Choisir le dossier de sauvegarde du projet",
        project_dir())
    if not proj_dir:
        return None, None

    default_name = os.path.basename(proj_dir) or "projet"
    proj_name, ok = QInputDialog.getText(
        iface.mainWindow(),
        "Nom du projet", "Nom :", text=default_name)
    if not ok or not proj_name.strip():
        return None, None

    proj_name = proj_name.strip()
    gpkg_temp = os.path.join(proj_dir, f"{proj_name}_tmp.gpkg")
    bet_path  = os.path.join(proj_dir, f"{proj_name}.bet")
    return gpkg_temp, bet_path


def cleanup_plugin_resources(plugin):
    """Supprime le dossier temporaire d'extraction si présent. Appeler depuis unload()."""
    tmp_dir = getattr(plugin, '_bet_temp_dir', None)
    if tmp_dir and os.path.isdir(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
    plugin._bet_temp_dir = None


def _do_save(plugin, iface, gpkg_temp, bet_path):
    """Corps commun de la sauvegarde.
    gpkg_temp : chemin du GPKG intermédiaire (sera supprimé après archivage).
    bet_path  : chemin du fichier .bet final (archive ZIP).
    """
    plugin._cleanup_tools()

    s         = QSettings()
    project   = QgsProject.instance()
    ctx       = project.transformContext()
    crs       = project.crs()

    from ..gui.etiquettes import apply_etiquettes

    n_layers    = len(_ROLES) * len(_RESEAUX)
    total_steps = n_layers * 4 + 2   # copie + retrait + écriture + rechargement + zip + extrait

    progress = QProgressDialog("Sauvegarde en cours…", None, 0, total_steps,
                               iface.mainWindow())
    progress.setWindowTitle("Enregistrer le projet")
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setMinimumWidth(380)
    progress.setValue(0)
    QApplication.processEvents()

    def step(label):
        progress.setValue(progress.value() + 1)
        progress.setLabelText(label)
        QApplication.processEvents()

    # État des étiquettes avant de toucher aux couches
    labels_state = {}
    for reseau in _RESEAUX:
        key      = _PREFIX + f"couche_conduite_{reseau.lower()}"
        layer_id = s.value(key)
        layer    = project.mapLayer(layer_id) if layer_id else None
        labels_state[reseau] = bool(layer.labelsEnabled()) if layer else False

    # Phase 1 : copie en mémoire de toutes les couches
    to_save = []
    for reseau in _RESEAUX:
        for role in _ROLES:
            key      = _PREFIX + f"couche_{role}_{reseau.lower()}"
            layer_id = s.value(key)
            layer    = project.mapLayer(layer_id) if layer_id else None
            if layer is None:
                step(f"Préparation {role}_{reseau} (ignoré)")
                continue
            step(f"Copie mémoire : {role}_{reseau}")
            to_save.append((reseau, role, key, layer_id, _copy_to_memory(layer)))

    # Capture des préférences d'affichage
    label_size = _read_label_size(project, s)
    from ..gui.etiquettes import get_force_all_labels, get_label_display_prefs
    force_all_labels    = get_force_all_labels()
    label_display_prefs = getattr(plugin, '_label_display_prefs', None) or {
        'visibility': get_label_display_prefs(plugin),
        'fields':     None,
    }

    # Capture de la visibilité individuelle avant suppression
    visibility_state = {}
    for reseau, role, key, layer_id, _ in to_save:
        node = project.layerTreeRoot().findLayer(layer_id)
        visibility_state[f"{role}_{reseau}"] = node.isVisible() if node else True

    # Phase 2 : retrait des couches du projet
    for reseau, role, key, layer_id, _ in to_save:
        step(f"Libération : {role}_{reseau}")
        if project.mapLayer(layer_id):
            project.removeMapLayer(layer_id)

    # Phase 3 : écriture vers le GPKG temporaire
    for _ext in ('', '-wal', '-shm', '-journal'):
        _p = gpkg_temp + _ext
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except OSError:
                pass

    layers_meta = {r: {} for r in _RESEAUX}
    first  = True
    errors = []

    for reseau, role, key, layer_id, mem_layer in to_save:
        layer_name = f"{role}_{reseau}"
        step(f"Écriture GPKG : {layer_name}")
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = 'GPKG'
        opts.layerName  = layer_name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        first = False

        err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem_layer, gpkg_temp, ctx, opts)

        if err != QgsVectorFileWriter.NoError:
            errors.append(f"{layer_name} : {msg}")
        else:
            layers_meta[reseau][role] = layer_name

    # Capture visibilité des groupes EU/EP
    groups_visibility = {}
    for reseau in _RESEAUX:
        grp = project.layerTreeRoot().findGroup(reseau)
        groups_visibility[reseau] = grp.isVisible() if grp else True

    # Phase 4 : création de l'archive .bet (ZIP : metadata.json + data.gpkg)
    step("Compression de l'archive .bet…")

    bet_data = {
        "version":             "2.0",
        "plugin":              "BET_HUMIDE",
        "date":                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "crs":                 crs.authid() if crs.isValid() else "EPSG:2154",
        "gpkg":                "data.gpkg",
        "layers":              layers_meta,
        "labels":              labels_state,
        "visibility":          visibility_state,
        "groups_visibility":   groups_visibility,
        "label_size":          label_size,
        "force_all_labels":    force_all_labels,
        "label_display_prefs": label_display_prefs,
    }

    # Rotation des sauvegardes : bak1 → bak2, bet → bak1
    bak1_path = os.path.splitext(bet_path)[0] + ".bak1"
    bak2_path = os.path.splitext(bet_path)[0] + ".bak2"
    try:
        if os.path.exists(bak1_path):
            os.replace(bak1_path, bak2_path)
        if os.path.exists(bet_path):
            os.replace(bet_path, bak1_path)
    except OSError as e:
        progress.close()
        _remove_temp_gpkg(gpkg_temp)
        QMessageBox.critical(
            iface.mainWindow(), "Enregistrer le projet",
            f"Impossible de faire pivoter les sauvegardes :\n{e}\n\n"
            "Fermez tout logiciel qui pourrait avoir ouvert ces fichiers, puis réessayez.")
        return

    try:
        with zipfile.ZipFile(bet_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json",
                        json.dumps(bet_data, indent=2, ensure_ascii=False))
            if os.path.exists(gpkg_temp):
                zf.write(gpkg_temp, "data.gpkg")
    except Exception as e:
        progress.close()
        _remove_temp_gpkg(gpkg_temp)
        QMessageBox.critical(
            iface.mainWindow(), "Enregistrer le projet",
            f"Impossible de créer l'archive .bet :\n{e}")
        return

    _remove_temp_gpkg(gpkg_temp)

    # Phase 5 : extraction du GPKG dans un dossier temporaire persistant
    step("Extraction pour rechargement…")
    cleanup_plugin_resources(plugin)
    tmp_dir = tempfile.mkdtemp(prefix='bet_humide_')
    plugin._bet_temp_dir = tmp_dir
    extracted_gpkg = os.path.join(tmp_dir, "data.gpkg")

    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            zf.extract("data.gpkg", tmp_dir)
    except Exception as e:
        progress.close()
        QMessageBox.critical(
            iface.mainWindow(), "Enregistrer le projet",
            f"Impossible d'extraire le GPKG depuis l'archive :\n{e}")
        return

    # Phase 6 : rechargement depuis le dossier temporaire
    from ..gui.etiquettes import (apply_label_size_all, apply_label_fields,
                                   apply_label_display_prefs)
    from ..gui.etiquette_affichage_dialog import prefs_from_dict

    for reseau, role, key, layer_id, _ in to_save:
        layer_name = f"{role}_{reseau}"
        step(f"Rechargement : {layer_name}")
        if not layers_meta.get(reseau, {}).get(role):
            errors.append(f"{role}_{reseau} : couche introuvable, ignorée")
            continue
        new_layer = QgsVectorLayer(
            f"{extracted_gpkg}|layername={layer_name}", layer_name, "ogr")
        if new_layer.isValid():
            plugin._apply_style(new_layer, role, reseau)
            project.addMapLayer(new_layer, False)
            _get_or_create_group(project, reseau).addLayer(new_layer)
            s.setValue(key, new_layer.id())
            apply_etiquettes(new_layer, role, reseau)
            new_layer.setLabelsEnabled(labels_state.get(reseau, False))
            node = project.layerTreeRoot().findLayer(new_layer.id())
            if node:
                node.setItemVisibilityChecked(
                    visibility_state.get(layer_name, True))
        else:
            errors.append(f"{layer_name} : rechargement depuis archive échoué")

    # Réapplique taille, champs et visibilité sur les couches rechargées
    full_prefs = prefs_from_dict(label_display_prefs) if label_display_prefs else None
    if label_size:
        apply_label_size_all(plugin, label_size['unit'], label_size['value'])
    if full_prefs:
        apply_label_display_prefs(plugin, full_prefs['visibility'])
        if full_prefs.get('fields'):
            apply_label_fields(plugin, full_prefs['fields'])

    progress.setValue(total_steps)
    progress.close()

    QSettings().setValue(_KEY_BET_PATH, bet_path)
    iface.mapCanvas().refresh()

    if errors:
        QMessageBox.warning(
            iface.mainWindow(), "Enregistrer le projet",
            "Projet enregistré avec des avertissements :\n" + "\n".join(errors)
            + f"\n\nFichier : {bet_path}")
    else:
        QMessageBox.information(
            iface.mainWindow(), "Enregistrer le projet",
            f"Projet enregistré :\n{bet_path}")


def _remove_temp_gpkg(gpkg_path):
    """Supprime le GPKG temporaire et ses fichiers WAL/SHM."""
    for _ext in ('', '-wal', '-shm', '-journal'):
        _p = gpkg_path + _ext
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except OSError:
                pass


def save_projet(plugin, iface):
    """Enregistre dans le projet courant ; si aucun projet ouvert, bascule sur Enregistrer sous."""
    bet_path = QSettings().value(_KEY_BET_PATH, "")
    if bet_path and os.path.exists(bet_path):
        proj_dir   = os.path.dirname(bet_path)
        proj_name  = os.path.splitext(os.path.basename(bet_path))[0]
        gpkg_temp  = os.path.join(proj_dir, f"{proj_name}_tmp.gpkg")
    else:
        gpkg_temp, bet_path = _ask_bet_path(iface)
        if not bet_path:
            return
    _do_save(plugin, iface, gpkg_temp, bet_path)


def save_projet_sous(plugin, iface):
    """Enregistrer sous — demande toujours le dossier et le nom."""
    gpkg_temp, bet_path = _ask_bet_path(iface)
    if not bet_path:
        return
    _do_save(plugin, iface, gpkg_temp, bet_path)


# ─────────────────────────────────────────────────────────────────────────────
#  Charger
# ─────────────────────────────────────────────────────────────────────────────

def load_projet(plugin, iface):
    """Charge un projet depuis un fichier .bet (v2 ZIP ou v1 JSON legacy)."""

    bet_path, _ = QFileDialog.getOpenFileName(
        iface.mainWindow(),
        "Ouvrir un projet BET Humide",
        project_dir(), "Projet BET Humide (*.bet)")
    if not bet_path:
        return

    QSettings().setValue(_KEY_BET_PATH, bet_path)

    # Détection du format : v2 = ZIP, v1 = JSON brut
    if zipfile.is_zipfile(bet_path):
        gpkg_path, bet_data = _load_v2(plugin, iface, bet_path)
    else:
        gpkg_path, bet_data = _load_v1(iface, bet_path)

    if gpkg_path is None:
        return

    plugin._cleanup_tools()

    s                 = QSettings()
    project           = QgsProject.instance()
    layers_meta       = bet_data.get('layers', {})
    labels_state      = bet_data.get('labels', {})
    visibility_state  = bet_data.get('visibility', {})
    groups_visibility = bet_data.get('groups_visibility', {})
    label_size          = bet_data.get('label_size')
    force_all_labels    = bet_data.get('force_all_labels', False)
    label_display_prefs = bet_data.get('label_display_prefs')
    errors            = []
    loaded            = 0

    from ..gui.etiquettes import apply_etiquettes

    for reseau in _RESEAUX:
        reseau_meta    = layers_meta.get(reseau, {})
        labels_enabled = labels_state.get(reseau, False)
        for role in _ROLES:
            layer_name = reseau_meta.get(role, f"{role}_{reseau}")
            key        = _PREFIX + f"couche_{role}_{reseau.lower()}"

            old_id = s.value(key)
            if old_id and project.mapLayer(old_id):
                project.removeMapLayer(old_id)

            new_layer = QgsVectorLayer(
                f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
            if not new_layer.isValid():
                errors.append(f"{layer_name} : couche invalide dans le GPKG")
                continue

            plugin._apply_style(new_layer, role, reseau)
            apply_etiquettes(new_layer, role, reseau)
            new_layer.setLabelsEnabled(labels_enabled)
            project.addMapLayer(new_layer, False)
            _get_or_create_group(project, reseau).addLayer(new_layer)
            s.setValue(key, new_layer.id())

            node = project.layerTreeRoot().findLayer(new_layer.id())
            if node:
                node.setItemVisibilityChecked(
                    visibility_state.get(layer_name, True))
            loaded += 1

    # Restaurer la visibilité des groupes EU/EP
    for reseau in _RESEAUX:
        grp = project.layerTreeRoot().findGroup(reseau)
        if grp:
            grp.setItemVisibilityChecked(groups_visibility.get(reseau, True))

    # Restaurer taille, flag et préférences d'affichage des étiquettes
    from ..gui.etiquettes import (apply_label_size_all, set_force_all_labels,
                                   apply_label_display_prefs, apply_label_fields)
    from ..gui.etiquette_affichage_dialog import prefs_from_dict
    if label_size:
        apply_label_size_all(plugin, label_size['unit'], label_size['value'])
    set_force_all_labels(force_all_labels)
    if label_display_prefs:
        full = prefs_from_dict(label_display_prefs)
        plugin._label_display_prefs = full
        apply_label_display_prefs(plugin, full['visibility'])
        if full.get('fields'):
            apply_label_fields(plugin, full['fields'])
    action_force = plugin.action_dict.get('forcer_etiquettes')
    if action_force is not None:
        action_force.blockSignals(True)
        action_force.setChecked(force_all_labels)
        action_force.blockSignals(False)

    # Centrer la vue sur l'étendue des couches chargées
    canvas     = iface.mapCanvas()
    canvas_crs = canvas.mapSettings().destinationCrs()
    combined   = QgsRectangle()
    for lyr in project.mapLayers().values():
        if not isinstance(lyr, QgsVectorLayer):
            continue
        try:
            ext = lyr.extent()
            if lyr.crs() != canvas_crs:
                tr  = QgsCoordinateTransform(lyr.crs(), canvas_crs, project)
                ext = tr.transformBoundingBox(ext)
            combined.combineExtentWith(ext)
        except Exception:
            pass
    if not combined.isNull():
        combined.grow(max(combined.width(), combined.height()) * 0.05)
        canvas.setExtent(combined)
    canvas.refresh()

    if errors:
        QMessageBox.warning(
            iface.mainWindow(), "Charger le projet",
            f"{loaded} couche(s) chargée(s).\nAvertissements :\n"
            + "\n".join(errors))
    else:
        QMessageBox.information(
            iface.mainWindow(), "Charger le projet",
            f"{loaded} couche(s) chargée(s) depuis :\n{bet_path}")


def _load_v2(plugin, iface, bet_path):
    """Charge un .bet v2 (archive ZIP). Retourne (gpkg_path, bet_data) ou (None, None)."""
    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            bet_data = json.loads(zf.read("metadata.json").decode('utf-8'))
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), "Erreur",
            f"Impossible de lire l'archive .bet :\n{e}")
        return None, None

    # Extraction du GPKG dans un dossier temporaire persistant
    cleanup_plugin_resources(plugin)
    tmp_dir = tempfile.mkdtemp(prefix='bet_humide_')
    plugin._bet_temp_dir = tmp_dir

    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            zf.extract("data.gpkg", tmp_dir)
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), "Erreur",
            f"Impossible d'extraire le GeoPackage depuis l'archive :\n{e}")
        cleanup_plugin_resources(plugin)
        return None, None

    gpkg_path = os.path.join(tmp_dir, "data.gpkg")
    return gpkg_path, bet_data


def _load_v1(iface, bet_path):
    """Charge un .bet v1 (JSON brut + .gpkg externe). Retourne (gpkg_path, bet_data) ou (None, None)."""
    try:
        with open(bet_path, 'r', encoding='utf-8') as f:
            bet_data = json.load(f)
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), "Erreur",
            f"Impossible de lire le fichier .bet :\n{e}")
        return None, None

    proj_dir  = os.path.dirname(bet_path)
    gpkg_name = bet_data.get('gpkg', '')
    gpkg_path = os.path.join(proj_dir, gpkg_name)

    if not os.path.exists(gpkg_path):
        QMessageBox.critical(
            iface.mainWindow(), "Erreur",
            f"GeoPackage introuvable :\n{gpkg_path}")
        return None, None

    return gpkg_path, bet_data
