# gui/etiquettes.py

from qgis.core import (
    Qgis,
    QgsPalLayerSettings,
    QgsTextFormat,
    QgsTextBackgroundSettings,
    QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
    QgsRuleBasedLabeling,
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
LBL_ROT     = 'lbl_rot'       # rotation en degrés (conduites déplacées)

_POINT_ROLES = ('regard', 'tabouret')
_LINE_ROLES  = ('conduite', 'branchement')


def _ensure_label_fields(layer, role):
    """Ajoute lbl_x / lbl_y / lbl_visible selon le rôle.

    Points (regard, tabouret) et conduites : lbl_x + lbl_y + lbl_visible.
    Branchements et autres lignes : lbl_visible seul.
    """
    fields = layer.fields()
    if role == 'conduite':
        needed = [
            (LBL_X,       _DOUBLE),
            (LBL_Y,       _DOUBLE),
            (LBL_ROT,     _DOUBLE),
            (LBL_VISIBLE, _INT),
        ]
    elif role in _POINT_ROLES:
        needed = [
            (LBL_X,       _DOUBLE),
            (LBL_Y,       _DOUBLE),
            (LBL_VISIBLE, _INT),
        ]
    else:
        needed = [
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


_TEXT_COLORS = {'EU': QColor(180, 0, 0), 'EP': QColor(0, 0, 180)}


def _conduite_text_format(color, size=LABEL_SIZE_MAP_UNITS,
                          unit=QgsUnitTypes.RenderMapUnits,
                          bold=False, buffer_mm=0.8):
    """Format texte des conduites (buffer blanc)."""
    fmt = QgsTextFormat()
    font = QFont('Arial', 9)
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSizeUnit(unit)
    fmt.setSize(size)
    fmt.setColor(color)
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(buffer_mm)
    buf.setSizeUnit(QgsUnitTypes.RenderMillimeters)
    buf.setColor(QColor(255, 255, 255))
    buf.setOpacity(0.9)
    fmt.setBuffer(buf)
    return fmt


def _make_conduite_labeling(reseau, expression, size=LABEL_SIZE_MAP_UNITS,
                            unit=QgsUnitTypes.RenderMapUnits):
    """Rule-based labeling pour conduites :
      - règle 1 (lbl_x IS NULL)     : Curved auto, le texte suit la conduite.
      - règle 2 (lbl_x IS NOT NULL) : OverPoint épinglé à lbl_x/lbl_y avec
        l'orientation figée lbl_rot (conserve l'angle de la conduite) + callout.
    """
    fmt  = _conduite_text_format(_TEXT_COLORS.get(reseau, QColor(0, 0, 0)),
                                 size, unit,
                                 bold=reseau == 'EP',
                                 buffer_mm=1.4 if reseau == 'EP' else 0.8)
    show = QgsProperty.fromExpression(f'coalesce("{LBL_VISIBLE}", 1)')

    def _base():
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = True
        pal.fieldName = expression
        pal.setFormat(fmt)
        return pal

    # ── Règle 1 : curviligne automatique ─────────────────────────────────
    pal_auto = _base()
    pal_auto.placement = QgsPalLayerSettings.Curved
    pal_auto.placementFlags = (QgsPalLayerSettings.BelowLine |
                               QgsPalLayerSettings.MapOrientation)
    pc1 = QgsPropertyCollection()
    pc1.setProperty(QgsPalLayerSettings.Show, show)
    pal_auto.setDataDefinedProperties(pc1)
    rule_auto = QgsRuleBasedLabeling.Rule(pal_auto)
    rule_auto.setFilterExpression(f'"{LBL_X}" IS NULL')
    rule_auto.setDescription('Conduite – auto')

    # ── Règle 2 : épinglée, orientation conservée ────────────────────────
    pal_pin = _base()
    # OverPoint entre en collision avec un autre enum sous QgsPalLayerSettings
    # en QGIS 3.44 : on passe par Qgis.LabelPlacement.
    try:
        pal_pin.placement = Qgis.LabelPlacement.OverPoint
    except AttributeError:
        pal_pin.placement = QgsPalLayerSettings.OverPoint
    pc2 = QgsPropertyCollection()
    pc2.setProperty(QgsPalLayerSettings.Show, show)
    pc2.setProperty(QgsPalLayerSettings.PositionX, QgsProperty.fromField(LBL_X))
    pc2.setProperty(QgsPalLayerSettings.PositionY, QgsProperty.fromField(LBL_Y))
    pc2.setProperty(QgsPalLayerSettings.Hali, QgsProperty.fromValue('Center'))
    pc2.setProperty(QgsPalLayerSettings.Vali, QgsProperty.fromValue('Half'))
    pc2.setProperty(QgsPalLayerSettings.LabelRotation,
                    QgsProperty.fromField(LBL_ROT))
    pal_pin.setDataDefinedProperties(pc2)
    try:
        callout = QgsSimpleLineCallout()
        callout.setEnabled(True)
        callout.setMinimumLength(5.0)
        callout.setMinimumLengthUnit(QgsUnitTypes.RenderMapUnits)
        callout.setLineSymbol(QgsLineSymbol.createSimple({
            'line_color': '100,100,100,200',
            'line_width': '0.3',
            'line_width_unit': 'MM',
            'line_style': 'dash',
        }))
        pal_pin.setCallout(callout)
    except Exception:
        pass
    rule_pin = QgsRuleBasedLabeling.Rule(pal_pin)
    rule_pin.setFilterExpression(f'"{LBL_X}" IS NOT NULL')
    rule_pin.setDescription('Conduite – épinglée')

    root = QgsRuleBasedLabeling.Rule(None)
    root.appendChild(rule_auto)
    root.appendChild(rule_pin)
    return QgsRuleBasedLabeling(root)


def _conduite_current_settings(labeling):
    """Extrait (expression, size, unit) de la 1re règle d'un labeling conduite."""
    try:
        rules = labeling.rootRule().children()
        if rules:
            s = rules[0].settings()
            return s.fieldName, s.format().size(), s.format().sizeUnit()
    except Exception:
        pass
    return None


def apply_etiquettes(layer, role, reseau=None):
    """Active les étiquettes sur la couche selon son rôle (point ou ligne).

    reseau : 'EU' → texte rouge, 'EP' → texte bleu (None = noir par défaut)
    """
    _ensure_label_fields(layer, role)
    _reset_label_visibility(layer)

    # ── Conduites : rule-based (auto curviligne / épinglée orientée) ──────
    if role == 'conduite':
        layer.setLabeling(_make_conduite_labeling(reseau, _expression('conduite')))
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()
        return

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
    text_color = _TEXT_COLORS.get(reseau, QColor(0, 0, 0))

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
    else:
        buf = QgsTextBufferSettings()
        buf.setEnabled(True)
        buf.setSize(0.8)
        buf.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        buf.setColor(QColor(255, 255, 255))
        buf.setOpacity(0.9)
        fmt.setBuffer(buf)

    pal.setFormat(fmt)

    if role in _POINT_ROLES:
        callout = QgsSimpleLineCallout()
        callout.setEnabled(True)
        callout.setMinimumLength(0.0)
        callout.setLineSymbol(QgsLineSymbol.createSimple({
            'line_color': '120,120,120,255',
            'line_width': '0.3',
            'line_width_unit': 'MM',
        }))
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

            # Conduites : rule-based → reconstruire avec la nouvelle taille
            if role == 'conduite' or isinstance(labeling, QgsRuleBasedLabeling):
                cur = _conduite_current_settings(labeling)
                expression = cur[0] if cur else _expression('conduite')
                layer.setLabeling(
                    _make_conduite_labeling(reseau, expression, value, unit))
                layer.triggerRepaint()
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
            expression = build_expression(role, fields_prefs.get(role))

            # Conduites : rule-based → reconstruire avec la taille courante
            if role == 'conduite' or isinstance(labeling, QgsRuleBasedLabeling):
                cur = _conduite_current_settings(labeling)
                size = cur[1] if cur else LABEL_SIZE_MAP_UNITS
                unit = cur[2] if cur else QgsUnitTypes.RenderMapUnits
                layer.setLabeling(
                    _make_conduite_labeling(reseau, expression, size, unit))
                layer.triggerRepaint()
                continue

            pal = labeling.settings()
            pal.fieldName   = expression
            pal.isExpression = True
            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.triggerRepaint()
