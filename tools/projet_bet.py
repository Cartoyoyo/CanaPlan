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
                       )
from qgis.PyQt.QtCore import QSettings, Qt
from . import i18n
from qgis.PyQt.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QProgressDialog, QApplication
from . import errlog
from qgis.core import Qgis


def _copy_to_memory(layer):
    """Copie une couche vectorielle dans un provider mémoire (libère tout verrou fichier)."""
    mem = QgsMemoryProviderUtils.createMemoryLayer(
        layer.name(), layer.fields(), layer.wkbType(), layer.crs())
    mem.startEditing()
    for feat in layer.getFeatures():
        mem.addFeature(QgsFeature(feat))
    mem.commitChanges()
    return mem

_PREFIX = "CanaPlan/"
_ROLES  = ('conduite', 'branchement', 'regard', 'tabouret')
_RESEAUX = ('EU', 'EP')


# ─────────────────────────────────────────────────────────────────────────────
#  Enregistrer
# ─────────────────────────────────────────────────────────────────────────────

_KEY_BET_PATH = _PREFIX + "current_bet_path"

# ── Projets récents ──────────────────────────────────────────────────────────
_KEY_RECENT = _PREFIX + "recent_projects"
MAX_RECENT = 4


def _norm(path):
    """Clé de comparaison insensible à la casse et aux ../ (Windows)."""
    return os.path.normcase(os.path.abspath(path))


def recent_projects():
    """Retourne les .bet récemment ouverts, du plus récent au plus ancien.

    Purge au passage les doublons et les fichiers disparus (projet déplacé
    ou supprimé depuis), et plafonne à MAX_RECENT.
    """
    raw = QSettings().value(_KEY_RECENT, [])
    # QSettings rend une chaîne nue quand la liste stockée n'a qu'un élément.
    if isinstance(raw, str):
        raw = [raw] if raw else []
    paths, seen = [], set()
    for path in raw or []:
        if not path:
            continue
        key = _norm(path)
        if key in seen or not os.path.exists(path):
            continue
        seen.add(key)
        paths.append(path)
        if len(paths) >= MAX_RECENT:
            break
    return paths


def _push_recent(bet_path):
    """Place bet_path en tête de la liste des projets récents."""
    if not bet_path:
        return
    key = _norm(bet_path)
    kept = [p for p in recent_projects() if _norm(p) != key]
    QSettings().setValue(_KEY_RECENT, [bet_path] + kept[:MAX_RECENT - 1])


def _forget_recent(bet_path):
    """Retire bet_path des projets récents (fichier introuvable)."""
    key = _norm(bet_path)
    QSettings().setValue(
        _KEY_RECENT, [p for p in recent_projects() if _norm(p) != key])


def _set_current(bet_path):
    """Enregistre le projet courant et l'inscrit dans les récents."""
    QSettings().setValue(_KEY_BET_PATH, bet_path)
    _push_recent(bet_path)


def _read_label_size(project, s):
    """Lit la taille des étiquettes depuis la première couche disponible.
    Retourne un dict {'unit': 'points'|'map_units', 'value': float} ou None.

    Les conduites sont étiquetées en rule-based : la lecture passe
    obligatoirement par etiquettes.pal_settings(), qui descend dans la 1re
    règle. labeling.settings() renvoie ici un réglage PAR DÉFAUT (10 points,
    sans seuil) sans jamais lever — le lire directement faisait enregistrer
    10 pt dans le .bet, puis réappliquer cette taille à tout le projet à
    chaque enregistrement.
    """
    from .layer_keys import get_layer_id
    from ..gui.etiquettes import pal_settings
    for reseau in _RESEAUX:
        layer_id = get_layer_id('conduite', reseau)
        layer    = project.mapLayer(layer_id) if layer_id else None
        if layer is None:
            continue
        pal = pal_settings(layer.labeling())
        if pal is None:
            continue
        fmt  = pal.format()
        unit = ('points' if fmt.sizeUnit() == Qgis.RenderUnit.Points
                else 'map_units')
        # Seuil de dézoom : lu sur les mêmes settings (0 = pas de seuil).
        min_scale = int(pal.minimumScale) if pal.scaleVisibility else 0
        return {'unit': unit, 'value': fmt.size(), 'min_scale': min_scale}
    return None


def _get_or_create_group(project, reseau):
    """Retourne le groupe EU ou EP au premier niveau de la légende (le crée en tête si absent).
    Ne cherche PAS récursivement pour éviter de tomber sur un groupe homonyme imbriqué."""
    from qgis.core import QgsLayerTreeGroup
    root = project.layerTreeRoot()
    for child in root.children():
        if isinstance(child, QgsLayerTreeGroup) and child.name() == reseau:
            return child
    return root.insertGroup(0, reseau)


def project_dir():
    """Retourne le répertoire du projet BET courant, ou '' si aucun projet enregistré."""
    bet_path = QSettings().value(_KEY_BET_PATH, "")
    if bet_path:
        d = os.path.dirname(bet_path)
        if os.path.isdir(d):
            return d
    return ""


def current_bet_name():
    """Nom du projet CanaPlan courant, sans extension, ou '' si aucun.

    Sert d'identification de chantier en tête des rapports PDF.
    """
    bet_path = QSettings().value(_KEY_BET_PATH, "")
    if bet_path:
        return os.path.splitext(os.path.basename(bet_path))[0]
    return ""


def _ask_bet_path(iface):
    """Demande dossier + nom et retourne (gpkg_temp_path, bet_path) ou (None, None)."""
    proj_dir = QFileDialog.getExistingDirectory(
        iface.mainWindow(),
        i18n.tr('pb_dossier_sauvegarde'),
        project_dir())
    if not proj_dir:
        return None, None

    default_name = os.path.basename(proj_dir) or "projet"
    proj_name, ok = QInputDialog.getText(
        iface.mainWindow(),
        i18n.tr('pb_nom_projet'), i18n.tr('pb_nom'), text=default_name)
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

    progress = QProgressDialog(i18n.tr('bet_sauvegarde'), None, 0, total_steps,
                               iface.mainWindow())
    progress.setWindowTitle(i18n.tr('enregistrer_projet'))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setMinimumWidth(380)
    progress.setValue(0)
    QApplication.processEvents()

    def step(label):
        progress.setValue(progress.value() + 1)
        progress.setLabelText(label)
        QApplication.processEvents()

    # État des étiquettes avant de toucher aux couches
    from .layer_keys import get_layer_id, set_layer_id
    labels_state = {}
    for reseau in _RESEAUX:
        layer_id = get_layer_id('conduite', reseau)
        layer    = project.mapLayer(layer_id) if layer_id else None
        labels_state[reseau] = bool(layer.labelsEnabled()) if layer else False

    # Phase 1 : copie en mémoire de toutes les couches
    to_save = []
    for reseau in _RESEAUX:
        for role in _ROLES:
            layer_id = get_layer_id(role, reseau)
            layer    = project.mapLayer(layer_id) if layer_id else None
            if layer is None:
                step(i18n.tr('bet_preparation',
                             couche=f"{role}_{reseau}"))
                continue
            step(i18n.tr('bet_copie', couche=f"{role}_{reseau}"))
            to_save.append((reseau, role, layer_id, _copy_to_memory(layer)))

    # Capture des préférences d'affichage
    label_size = _read_label_size(project, s)
    if label_size is None:
        _mode  = s.value("CanaPlan/label_size_mode")
        _val   = s.value("CanaPlan/label_size_value")
        if _mode and _val is not None:
            try:
                label_size = {'unit': _mode, 'value': float(_val)}
            except (ValueError, TypeError) as _err:
                errlog.ignored(_err, "projet_bet._do_save:248")
    from ..gui.etiquettes import get_force_all_labels, get_label_display_prefs
    force_all_labels    = get_force_all_labels()
    label_display_prefs = getattr(plugin, '_label_display_prefs', None) or {
        'visibility': get_label_display_prefs(plugin),
        'fields':     None,
    }

    # Capture de la visibilité individuelle avant suppression
    visibility_state = {}
    for reseau, role, layer_id, _ in to_save:
        node = project.layerTreeRoot().findLayer(layer_id)
        visibility_state[f"{role}_{reseau}"] = node.isVisible() if node else True

    # Phase 2 : retrait des couches du projet
    for reseau, role, layer_id, _ in to_save:
        step(i18n.tr('bet_liberation', couche=f"{role}_{reseau}"))
        if project.mapLayer(layer_id):
            project.removeMapLayer(layer_id)

    # Phase 3 : écriture vers le GPKG temporaire
    for _ext in ('', '-wal', '-shm', '-journal'):
        _p = gpkg_temp + _ext
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except OSError as _err:
                errlog.ignored(_err, "projet_bet._do_save:275")

    layers_meta = {r: {} for r in _RESEAUX}
    first  = True
    errors = []

    for reseau, role, layer_id, mem_layer in to_save:
        layer_name = f"{role}_{reseau}"
        step(i18n.tr('bet_ecriture', couche=layer_name))
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = 'GPKG'
        opts.layerName  = layer_name
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer
        )
        first = False

        err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem_layer, gpkg_temp, ctx, opts)

        if err != QgsVectorFileWriter.WriterError.NoError:
            errors.append(f"{layer_name} : {msg}")
        else:
            layers_meta[reseau][role] = layer_name

    # Capture visibilité des groupes EU/EP
    groups_visibility = {}
    for reseau in _RESEAUX:
        grp = project.layerTreeRoot().findGroup(reseau)
        groups_visibility[reseau] = grp.isVisible() if grp else True

    # Phase 4 : création de l'archive .bet
    # (ZIP : metadata.json + data.gpkg + fonds/)
    step(i18n.tr('bet_compression'))

    # Fonds de plan : flux WMS par référence, vecteurs copiés dans l'archive.
    # Les .qml et les exports de couches mémoire transitent par un dossier
    # jetable, supprimé dès l'archive écrite.
    from . import fonds_plan
    fonds_work = tempfile.mkdtemp(prefix='canaplan_fonds_')
    try:
        metier_ids = {lid for _r, _ro, lid, _m in to_save}
        fonds_entries, fonds_files, fonds_errors = fonds_plan.collect(
            project, metier_ids, fonds_work)
    except Exception as exc:
        fonds_entries, fonds_files = [], []
        fonds_errors = [i18n.tr('bet_err_fonds_enreg', detail=exc)]
    errors.extend(fonds_errors)

    bet_data = {
        "version":             "2.0",
        "plugin":              "CanaPlan",
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
        "fonds":               fonds_entries,
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
            iface.mainWindow(), i18n.tr('enregistrer_projet'),
            fi18n.tr('pb_rotation_echec', erreur=e))
        return

    try:
        with zipfile.ZipFile(bet_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json",
                        json.dumps(bet_data, indent=2, ensure_ascii=False))
            if os.path.exists(gpkg_temp):
                zf.write(gpkg_temp, "data.gpkg")
            for arcname, src in fonds_files:
                if os.path.exists(src):
                    zf.write(src, arcname)
    except Exception as e:
        progress.close()
        _remove_temp_gpkg(gpkg_temp)
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('enregistrer_projet'),
            i18n.tr('pb_archive_echec', erreur=e))
        return

    _remove_temp_gpkg(gpkg_temp)
    shutil.rmtree(fonds_work, ignore_errors=True)

    # Phase 5 : extraction du GPKG dans un dossier temporaire persistant
    step(i18n.tr('bet_extraction'))
    cleanup_plugin_resources(plugin)
    tmp_dir = tempfile.mkdtemp(prefix='canaplan_')
    plugin._bet_temp_dir = tmp_dir
    extracted_gpkg = os.path.join(tmp_dir, "data.gpkg")

    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            zf.extract("data.gpkg", tmp_dir)
    except Exception as e:
        progress.close()
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('enregistrer_projet'),
            i18n.tr('pb_extraction_gpkg', erreur=e))
        return

    # Phase 6 : rechargement depuis le dossier temporaire
    from ..gui.etiquettes import (apply_label_size_all, apply_label_fields,
                                   apply_label_display_prefs)
    from ..gui.etiquette_affichage_dialog import prefs_from_dict

    for reseau, role, layer_id, _ in to_save:
        layer_name = f"{role}_{reseau}"
        step(i18n.tr('bet_rechargement', couche=layer_name))
        if not layers_meta.get(reseau, {}).get(role):
            errors.append(i18n.tr('bet_err_introuvable',
                                  couche=f"{role}_{reseau}"))
            continue
        new_layer = QgsVectorLayer(
            f"{extracted_gpkg}|layername={layer_name}", layer_name, "ogr")
        if new_layer.isValid():
            plugin._apply_style(new_layer, role, reseau)
            project.addMapLayer(new_layer, False)
            _get_or_create_group(project, reseau).addLayer(new_layer)
            set_layer_id(role, reseau, new_layer.id())
            apply_etiquettes(new_layer, role, reseau)
            new_layer.setLabelsEnabled(labels_state.get(reseau, False))
            node = project.layerTreeRoot().findLayer(new_layer.id())
            if node:
                node.setItemVisibilityChecked(
                    visibility_state.get(layer_name, True))
        else:
            errors.append(i18n.tr('bet_err_recharge', couche=layer_name))

    # Réapplique taille, champs et visibilité sur les couches rechargées
    full_prefs = prefs_from_dict(label_display_prefs) if label_display_prefs else None
    if label_size:
        apply_label_size_all(plugin, label_size['unit'], label_size['value'],
                             label_size.get('min_scale'))
    if full_prefs:
        apply_label_display_prefs(plugin, full_prefs['visibility'])
        if full_prefs.get('fields'):
            apply_label_fields(plugin, full_prefs['fields'])

    progress.setValue(total_steps)
    progress.close()

    _set_current(bet_path)
    iface.mapCanvas().refresh()

    if errors:
        QMessageBox.warning(
            iface.mainWindow(), i18n.tr('enregistrer_projet'),
            i18n.tr('pb_avertissements', details=chr(10).join(errors),
                    chemin=bet_path))
    else:
        QMessageBox.information(
            iface.mainWindow(), i18n.tr('enregistrer_projet'),
            i18n.tr('pb_enregistre', chemin=bet_path))


def _remove_temp_gpkg(gpkg_path):
    """Supprime le GPKG temporaire et ses fichiers WAL/SHM."""
    for _ext in ('', '-wal', '-shm', '-journal'):
        _p = gpkg_path + _ext
        if os.path.exists(_p):
            try:
                os.remove(_p)
            except OSError as _err:
                errlog.ignored(_err, "projet_bet._remove_temp_gpkg:457")


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

def load_projet(plugin, iface, bet_path=None):
    """Charge un projet depuis un fichier .bet (v2 ZIP ou v1 JSON legacy).

    bet_path permet d'ouvrir directement un projet récent sans passer par le
    sélecteur de fichiers ; laissé à None, le dialogue habituel s'affiche.
    """
    if bet_path is None:
        bet_path, _ = QFileDialog.getOpenFileName(
            iface.mainWindow(),
            i18n.tr('ouvrir_projet_titre'),
            project_dir(), i18n.tr('filtre_projet'))
    if not bet_path:
        return

    # Un récent peut pointer sur un fichier déplacé ou supprimé entre-temps.
    if not os.path.exists(bet_path):
        _forget_recent(bet_path)
        QMessageBox.warning(
            iface.mainWindow(), i18n.tr('ouvrir_projet_titre'),
            i18n.tr('fichier_introuvable', path=bet_path))
        return

    _set_current(bet_path)

    # Détection du format : v2 = ZIP, v1 = JSON brut
    if zipfile.is_zipfile(bet_path):
        gpkg_path, bet_data = _load_v2(plugin, iface, bet_path)
    else:
        gpkg_path, bet_data = _load_v1(iface, bet_path)

    if gpkg_path is None:
        return

    plugin._cleanup_tools()

    from .layer_keys import get_layer_id, set_layer_id
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

            old_id = get_layer_id(role, reseau)
            if old_id and project.mapLayer(old_id):
                project.removeMapLayer(old_id)

            new_layer = QgsVectorLayer(
                f"{gpkg_path}|layername={layer_name}", layer_name, "ogr")
            if not new_layer.isValid():
                errors.append(i18n.tr('bet_err_invalide',
                                      couche=layer_name))
                continue

            plugin._apply_style(new_layer, role, reseau)
            try:
                apply_etiquettes(new_layer, role, reseau)
            except Exception as e:
                errors.append(i18n.tr('bet_err_etiquettes',
                                      couche=layer_name, detail=e))
            new_layer.setLabelsEnabled(labels_enabled)
            project.addMapLayer(new_layer, False)
            _get_or_create_group(project, reseau).addLayer(new_layer)
            set_layer_id(role, reseau, new_layer.id())

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
    try:
        from ..gui.etiquettes import (apply_label_size_all, set_force_all_labels,
                                       apply_label_display_prefs, apply_label_fields)
        from ..gui.etiquette_affichage_dialog import prefs_from_dict
        if label_size:
            apply_label_size_all(plugin, label_size['unit'], label_size['value'],
                                 label_size.get('min_scale'))
        # Le forçage doit passer APRES apply_label_size_all, qui reconstruit
        # les étiquetages : sinon displayAll serait écrasé par la valeur par
        # défaut de la reconstruction.
        set_force_all_labels(force_all_labels, plugin=plugin)
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
    except Exception as e:
        errors.append(i18n.tr('bet_err_prefs_etiquettes', detail=e))

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
        except Exception as _err:
            errlog.ignored(_err, "projet_bet.load_projet:616")
    if not combined.isNull():
        combined.grow(max(combined.width(), combined.height()) * 0.05)
        canvas.setExtent(combined)

    # Fonds de plan : après les couches métier, pour qu'ils se placent sous
    # les groupes EU / EP dans la légende.
    fonds_entries = bet_data.get('fonds')
    if fonds_entries:
        base_dir = getattr(plugin, '_bet_temp_dir', None) or os.path.dirname(bet_path)
        try:
            from . import fonds_plan
            errors.extend(fonds_plan.restore(project, fonds_entries, base_dir))
        except Exception as exc:
            errors.append(i18n.tr('bet_err_fonds_recharge', detail=exc))

    canvas.refresh()

    if errors:
        QMessageBox.warning(
            iface.mainWindow(), i18n.tr('pb_charger_titre'),
            i18n.tr('pb_couches_avertissements', nb=loaded,
                    details=chr(10).join(errors)))
    else:
        QMessageBox.information(
            iface.mainWindow(), i18n.tr('pb_charger_titre'),
            i18n.tr('pb_couches_chargees', nb=loaded, chemin=bet_path))


def _load_v2(plugin, iface, bet_path):
    """Charge un .bet v2 (archive ZIP). Retourne (gpkg_path, bet_data) ou (None, None)."""
    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            bet_data = json.loads(zf.read("metadata.json").decode('utf-8'))
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('erreur'),
            i18n.tr('pb_lecture_archive', erreur=e))
        return None, None

    # Extraction du GPKG dans un dossier temporaire persistant
    cleanup_plugin_resources(plugin)
    tmp_dir = tempfile.mkdtemp(prefix='canaplan_')
    plugin._bet_temp_dir = tmp_dir

    try:
        with zipfile.ZipFile(bet_path, 'r') as zf:
            zf.extract("data.gpkg", tmp_dir)
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('erreur'),
            i18n.tr('pb_extraction_geopackage', erreur=e))
        cleanup_plugin_resources(plugin)
        return None, None

    # Les fonds de plan vecteur vivent dans le même dossier temporaire que le
    # GPKG métier : ils doivent survivre aussi longtemps que le projet ouvert.
    try:
        from . import fonds_plan
        with zipfile.ZipFile(bet_path, 'r') as zf:
            fonds_plan.extract_into(zf, tmp_dir)
    except Exception as _err:
        errlog.ignored(_err, "projet_bet._load_v2:678")

    gpkg_path = os.path.join(tmp_dir, "data.gpkg")
    return gpkg_path, bet_data


def _load_v1(iface, bet_path):
    """Charge un .bet v1 (JSON brut + .gpkg externe). Retourne (gpkg_path, bet_data) ou (None, None)."""
    try:
        with open(bet_path, 'r', encoding='utf-8') as f:
            bet_data = json.load(f)
    except Exception as e:
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('erreur'),
            i18n.tr('pb_lecture_bet', erreur=e))
        return None, None

    proj_dir  = os.path.dirname(bet_path)
    gpkg_name = bet_data.get('gpkg', '')
    gpkg_path = os.path.join(proj_dir, gpkg_name)

    if not os.path.exists(gpkg_path):
        QMessageBox.critical(
            iface.mainWindow(), i18n.tr('erreur'),
            i18n.tr('pb_gpkg_introuvable', chemin=gpkg_path))
        return None, None

    return gpkg_path, bet_data
