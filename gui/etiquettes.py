# gui/etiquettes.py

from qgis.core import (
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBackgroundSettings,
    QgsVectorLayerSimpleLabeling,
    QgsProperty,
    QgsPropertyCollection,
    QgsField,
    QgsSimpleLineCallout,
    QgsLineSymbol,
    QgsUnitTypes,
    QgsProject,
)

# QgsLabelEngineSettings : nom variable selon la version de QGIS
try:
    from qgis.core import QgsLabelEngineSettings as _LabelEngineSettings
except ImportError:
    try:
        from qgis.core import QgsLabelingEngineSettings as _LabelEngineSettings
    except ImportError:
        _LabelEngineSettings = None
from qgis.PyQt.QtGui import QFont, QColor
from qgis.PyQt.QtCore import QSizeF, QVariant

try:
    from qgis.PyQt.QtCore import QMetaType
    _DOUBLE = QMetaType.Type.Double
    _INT = QMetaType.Type.Int
except (ImportError, AttributeError):
    _DOUBLE = QVariant.Double
    _INT = QVariant.Int

# Taille du texte en unités carte (mètres pour Lambert 93).
# À 1:500 → 4 mm, à 1:200 → 10 mm, à 1:1000 → 2 mm.
LABEL_SIZE_MAP_UNITS = 2.0
LABEL_PADDING_MAP_UNITS = 0.4

# Champs de position et de visibilité stockés dans la couche
LBL_X       = 'lbl_x'
LBL_Y       = 'lbl_y'
LBL_VISIBLE = 'lbl_visible'   # 1 = affichée, 0 = masquée

_POINT_ROLES = ('regard', 'tabouret')
_LINE_ROLES  = ('conduite', 'branchement')


def _ensure_label_fields(layer, role):
    """Ajoute lbl_x / lbl_y / lbl_visible (points) ou lbl_visible seul (lignes)."""
    fields = layer.fields()
    needed = [
        (LBL_X,       _DOUBLE),
        (LBL_Y,       _DOUBLE),
        (LBL_VISIBLE, _INT),
    ] if role in _POINT_ROLES else [
        (LBL_VISIBLE, _INT),
    ]
    missing = [(n, t) for n, t in needed if fields.indexFromName(n) < 0]
    if not missing:
        return
    if not layer.isEditable():
        layer.startEditing()
    for name, vtype in missing:
        layer.addAttribute(QgsField(name, vtype))
    layer.commitChanges()


def _reset_label_visibility(layer):
    """Remet lbl_visible à NULL pour toutes les features masquées (lbl_visible = 0)."""
    idx = layer.fields().indexFromName(LBL_VISIBLE)
    if idx < 0:
        return
    fids = [f.id() for f in layer.getFeatures()
            if f[LBL_VISIBLE] is not None and f[LBL_VISIBLE] == 0]
    if not fids:
        return
    if not layer.isEditable():
        layer.startEditing()
    for fid in fids:
        layer.changeAttributeValue(fid, idx, None)
    layer.commitChanges()


def apply_etiquettes(layer, role, reseau=None):
    """Active les étiquettes sur la couche selon son rôle (point ou ligne).

    reseau : 'EU' → texte rouge, 'EP' → texte bleu (None = noir par défaut)
    """
    _ensure_label_fields(layer, role)
    _reset_label_visibility(layer)

    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = _expression(role)

    pc = QgsPropertyCollection()
    pc.setProperty(QgsPalLayerSettings.Show,
                   QgsProperty.fromExpression(f'coalesce("{LBL_VISIBLE}", 1)'))

    if role in _POINT_ROLES:
        pal.placement = QgsPalLayerSettings.AroundPoint
        pc.setProperty(QgsPalLayerSettings.PositionX, QgsProperty.fromField(LBL_X))
        pc.setProperty(QgsPalLayerSettings.PositionY, QgsProperty.fromField(LBL_Y))
        pc.setProperty(QgsPalLayerSettings.Hali, QgsProperty.fromValue('Center'))
        pc.setProperty(QgsPalLayerSettings.Vali, QgsProperty.fromValue('Half'))
    else:
        pal.placement = QgsPalLayerSettings.Curved
        pal.placementFlags = QgsPalLayerSettings.BelowLine | QgsPalLayerSettings.MapOrientation

    pal.setDataDefinedProperties(pc)

    # Couleur du texte selon le réseau
    TEXT_COLORS = {'EU': QColor(180, 0, 0), 'EP': QColor(0, 0, 180)}
    text_color = TEXT_COLORS.get(reseau, QColor(0, 0, 0))

    fmt = QgsTextFormat()
    fmt.setFont(QFont('Arial', 9))
    fmt.setSizeUnit(QgsUnitTypes.RenderMapUnits)
    fmt.setSize(LABEL_SIZE_MAP_UNITS)
    fmt.setColor(text_color)

    if role in _POINT_ROLES:
        bg = QgsTextBackgroundSettings()
        bg.setEnabled(True)
        bg.setType(QgsTextBackgroundSettings.ShapeRectangle)
        bg.setFillColor(QColor(255, 255, 255, 191))
        bg.setStrokeColor(QColor(80, 80, 80, 255))
        bg.setStrokeWidth(0.3)
        bg.setSizeType(QgsTextBackgroundSettings.SizeBuffer)
        bg.setSizeUnit(QgsUnitTypes.RenderMapUnits)
        bg.setSize(QSizeF(LABEL_PADDING_MAP_UNITS, LABEL_PADDING_MAP_UNITS))
        fmt.setBackground(bg)

    pal.setFormat(fmt)

    if role in _POINT_ROLES:
        callout = QgsSimpleLineCallout()
        callout.setEnabled(True)
        callout.setMinimumLength(0.0)
        line_symbol = QgsLineSymbol.createSimple({
            'line_color': '120,120,120,255',
            'line_width': '0.3',
            'line_width_unit': 'MM',
        })
        callout.setLineSymbol(line_symbol)
        pal.setCallout(callout)

    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def remove_etiquettes(layer):
    """Désactive les étiquettes sur la couche."""
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def set_force_all_labels(enabled: bool, canvas=None):
    """Active ou désactive l'affichage forcé de toutes les étiquettes.

    Quand activé : aucune étiquette n'est masquée — le moteur les décale
    automatiquement pour minimiser les chevauchements.
    Quand désactivé : comportement normal (certaines étiquettes peuvent être
    supprimées si elles se chevauchent trop).
    """
    if _LabelEngineSettings is None:
        return
    try:
        project  = QgsProject.instance()
        settings = project.labelingEngineSettings()
        settings.setFlag(_LabelEngineSettings.UseAllLabels, enabled)
        project.setLabelingEngineSettings(settings)
    except Exception:
        pass
    if canvas is not None:
        canvas.refresh()


def get_force_all_labels() -> bool:
    """Retourne l'état courant du flag UseAllLabels du projet."""
    if _LabelEngineSettings is None:
        return False
    try:
        settings = QgsProject.instance().labelingEngineSettings()
        return settings.testFlag(_LabelEngineSettings.UseAllLabels)
    except Exception:
        return False


def apply_label_display_prefs(plugin, visibility):
    """Applique la visibilité des étiquettes par réseau et par rôle.

    visibility : {reseau: {role: bool}}  — True = étiquettes activées
    """
    for reseau in ('EU', 'EP'):
        couches = plugin._get_couches(reseau)
        for role, layer in couches.items():
            enabled = visibility.get(reseau, {}).get(role, True)
            layer.setLabelsEnabled(enabled)
            layer.triggerRepaint()


def get_label_display_prefs(plugin):
    """Lit l'état courant des étiquettes, retourne {reseau: {role: bool}}."""
    prefs = {}
    for reseau in ('EU', 'EP'):
        couches = plugin._get_couches(reseau)
        prefs[reseau] = {role: layer.labelsEnabled()
                         for role, layer in couches.items()}
    return prefs


def apply_label_size_all(plugin, mode, value):
    """Applique la taille d'étiquette à toutes les couches EU et EP.

    mode  : 'points'    → taille fixe écran (QgsUnitTypes.RenderPoints)
            'map_units' → taille en mètres  (QgsUnitTypes.RenderMapUnits)
    value : float — taille dans l'unité correspondante
    """
    unit = (QgsUnitTypes.RenderPoints
            if mode == 'points'
            else QgsUnitTypes.RenderMapUnits)

    # Padding proportionnel (ratio identique à l'original)
    ratio_padding = LABEL_PADDING_MAP_UNITS / LABEL_SIZE_MAP_UNITS
    padding = value * ratio_padding

    for reseau in ('EU', 'EP'):
        couches = plugin._get_couches(reseau)
        for role, layer in couches.items():
            labeling = layer.labeling()
            if labeling is None:
                continue
            pal = labeling.settings()
            fmt = pal.format()
            fmt.setSize(value)
            fmt.setSizeUnit(unit)

            if role in _POINT_ROLES:
                bg = fmt.background()
                bg.setSize(QSizeF(padding, padding))
                bg.setSizeUnit(unit)
                fmt.setBackground(bg)

            pal.setFormat(fmt)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.triggerRepaint()


# Fragments d'expression par champ — (clé, fragment QGIS)
_FRAGMENTS = {
    'nom':         "coalesce(\"nom\", '-')",
    'tn':          "'TN   : ' || coalesce(format_number(\"tn\", 3), '-') || ' m'",
    'fe_radier':   "'FE rad.: ' || coalesce(format_number(\"fe_radier\", 3), '-') || ' m'",
    'fe_entree':   "'FE ent.: ' || coalesce(format_number(\"fe_entree\", 3), '-') || ' m'",
    'profondeur':  "'P      : ' || coalesce(format_number(\"profondeur\", 2), '-') || ' m'",
    'materiau':    "coalesce(\"materiau\", '-')",
    'diametre':    "coalesce(format_number(\"diametre\", 0), '-') || ' mm'",
    'longueur':    "coalesce(format_number(\"longueur\", 1), '-') || ' m'",
    'pente':       "coalesce(format_number(\"pente\", 1), '-') || '%'",
    'cote_piquage':"'Cote piq.: ' || coalesce(format_number(\"cote_piquage\", 3), '-') || ' m'",
}

# Ordre canonique des champs par rôle
_ROLE_FIELD_ORDER = {
    'regard':      ['nom', 'tn', 'fe_radier', 'profondeur'],
    'tabouret':    ['nom', 'tn', 'fe_entree', 'profondeur'],
    'conduite':    ['materiau', 'diametre', 'longueur', 'pente'],
    'branchement': ['materiau', 'diametre', 'longueur', 'pente', 'cote_piquage'],
}

# Séparateur entre champs selon le type
_SEP = {
    'regard':      "'\n'",
    'tabouret':    "'\n'",
    'conduite':    "' | '",
    'branchement': "' | '",
}


def build_expression(role, active_fields=None):
    """Construit l'expression QGIS pour les étiquettes du rôle donné.

    active_fields : dict {field: bool} ou None (→ tous actifs)
    """
    order = _ROLE_FIELD_ORDER.get(role, [])
    parts = []
    for f in order:
        if active_fields is None or active_fields.get(f, True):
            frag = _FRAGMENTS.get(f)
            if frag:
                parts.append(frag)

    if not parts:
        return "''"

    sep = _SEP.get(role, "' | '")
    joined = (', ' + sep + ', ').join(parts)
    return f"concat({joined})"


def _expression(role):
    """Expression par défaut (tous champs actifs)."""
    return build_expression(role, None)


def sync_labels_after_rename(layer, role, reseau=None):
    """Après un renommage : s'assure que le moteur d'étiquettes est actif.

    - Crée les champs lbl_* si absents (nouvelles features)
    - Configure apply_etiquettes si la couche n'a jamais été labellisée
    - Sinon déclenche uniquement un repaint (le texte suit le champ nom auto)
    Les positions lbl_x / lbl_y existantes ne sont PAS modifiées.
    """
    _ensure_label_fields(layer, role)
    if layer.labeling() is None or not layer.labelsEnabled():
        apply_etiquettes(layer, role, reseau)
    else:
        layer.triggerRepaint()


def apply_label_fields(plugin, fields_prefs):
    """Reconstruit les expressions d'étiquettes selon les champs sélectionnés."""
    for reseau in ('EU', 'EP'):
        couches = plugin._get_couches(reseau)
        for role, layer in couches.items():
            labeling = layer.labeling()
            if labeling is None:
                continue
            pal = labeling.settings()
            pal.fieldName   = build_expression(role, fields_prefs.get(role))
            pal.isExpression = True
            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.triggerRepaint()
