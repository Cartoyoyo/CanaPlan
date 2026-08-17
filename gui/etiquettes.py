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
from qgis.PyQt.QtCore import QSizeF, QVariant, QSettings

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

# Décalage de l'étiquette d'un ouvrage par rapport à son symbole, en unités
# carte (mètres). Le symbole de regard est un cercle de 1 m de diamètre et
# celui de tabouret un carré de 0,4 m (main._apply_style).
#
# 1,5 m depuis le centre dégage le plus gros des deux (rayon 0,5 m) avec 1 m
# de marge, ce qui laisse à la ligne de rappel la place d'être vue : à 1 m
# le pavé venait toucher le symbole et le connecteur se réduisait à rien.
# Sur papier cela fait 6 mm au 1:250, une longueur de renvoi classique.
#
# En unités carte comme les symboles eux-mêmes : le rapport visuel entre
# l'ouvrage et son étiquette ne bouge donc pas avec le zoom.
LABEL_OFFSET_MAP_UNITS = 1.5

# Longueur minimale d'une ligne de rappel, en MILLIMETRES : en deçà,
# l'étiquette est encore assez près de son objet pour se passer de rappel.
# En millimètres et non en unités carte, sinon le seuil dépend du zoom : à
# 1:1000 un seuil de 5 m ne se déclenche qu'après 5 mm sur papier, à 1:100
# après 50 mm — le rappel apparaîtrait et disparaîtrait selon l'échelle.
CALLOUT_MIN_LENGTH_MM = 1.5

# Plafond absolu de dézoom, utilisé quand le seuil ne peut pas être déduit
# de la taille du texte (mode « points », où le texte garde la même taille
# à l'écran et ne devient donc jamais illisible).
LABEL_MIN_SCALE = 2000

# Hauteur de texte en dessous de laquelle une étiquette n'est plus lisible,
# en millimètres papier. Sert à déduire le seuil de dézoom par défaut.
#
# Mesuré sur un réseau de 1200 regards, seuil désactivé, rendu 1200x800 :
#
#     échelle   texte    étiquettes   rendu
#     1/250     2.50 mm       292      155 ms
#     1/400     1.56 mm       524      252 ms
#     1/500     1.25 mm      1280      611 ms
#     1/700     0.89 mm      1744     1095 ms
#     1/1000    0.62 mm      5328     3268 ms
#     1/2000    0.31 mm       560     3272 ms
#
# Au-delà du 1:400 le texte passe sous 1,5 mm — illisible — et le moteur
# passe de 0,6 à 3,3 secondes par redessin à tenter de placer des milliers
# d'étiquettes que personne ne pourra lire, dont la plupart sont ensuite
# écartées pour cause de collision. Le coût est dans la tentative.
MIN_READABLE_MM = 1.5


def default_min_scale(size, unit):
    """Seuil de dézoom déduit de la taille du texte (0 = aucun seuil).

    En unités carte, le texte rétrécit avec le zoom : on coupe dès qu'il
    passe sous MIN_READABLE_MM. En points, il garde sa taille à l'écran et
    reste lisible à toute échelle — seul le plafond de performance joue.
    """
    if unit != QgsUnitTypes.RenderMapUnits:
        return LABEL_MIN_SCALE
    try:
        size = float(size)
    except (TypeError, ValueError):
        return LABEL_MIN_SCALE
    if size <= 0:
        return LABEL_MIN_SCALE
    # Arrondi au 50 le plus proche : un seuil « 1/400 » se lit mieux
    # qu'un « 1/417 » dans le dialogue.
    seuil = size * 1000.0 / MIN_READABLE_MM
    return max(200, int(round(seuil / 50.0)) * 50)

# Priorité de placement (0 = la plus faible, 10 = la plus forte). Un nom de
# regard est l'information qu'on cherche en premier sur un plan de réseau ;
# les caractéristiques d'un branchement se retrouvent au besoin dans la
# table. En cas de conflit, c'est donc le branchement qui cède.
_PRIORITY = {
    'regard':      10,
    'tabouret':    9,
    'conduite':    6,
    'branchement': 4,
}

# Champs de position et de visibilité stockés dans la couche
LBL_X       = 'lbl_x'
LBL_Y       = 'lbl_y'
LBL_VISIBLE = 'lbl_visible'   # 1 = affichée, 0 = masquée
LBL_ROT     = 'lbl_rot'       # rotation en degrés (étiquettes de ligne épinglées)

_POINT_ROLES = ('regard', 'tabouret')
_LINE_ROLES  = ('conduite', 'branchement')

# Clé de projet du forçage d'affichage. Remplace le flag global UseAllLabels
# du moteur, qui forçait aussi les étiquettes des fonds BAN / noms de rue /
# PCI — ce que personne n'a jamais demandé en cochant « Forcer toutes les
# étiquettes visibles » dans un plugin de réseau d'assainissement.
_FORCE_SCOPE = 'BET_HUMIDE'
_FORCE_KEY   = 'force_all_labels'


def _ensure_label_fields(layer, role):
    """Ajoute lbl_x / lbl_y / lbl_rot / lbl_visible selon le rôle.

    Lignes (conduite, branchement) : les quatre champs — lbl_rot fige
    l'orientation d'une étiquette épinglée sur l'angle de sa ligne.
    Points (regard, tabouret) : lbl_x + lbl_y + lbl_visible ; un symbole
    ponctuel n'a pas d'orientation à conserver.
    """
    fields = layer.fields()
    if role in _LINE_ROLES:
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

_ROLE_LABELS = {
    'regard': 'Regard', 'tabouret': 'Tabouret',
    'conduite': 'Conduite', 'branchement': 'Branchement',
}


def get_force_all_labels() -> bool:
    """Retourne l'état courant du forçage d'affichage (propriété de projet)."""
    try:
        return QgsProject.instance().readBoolEntry(
            _FORCE_SCOPE, _FORCE_KEY, False)[0]
    except Exception:
        return False


def _make_callout(dashed=False, min_length_mm=CALLOUT_MIN_LENGTH_MM):
    """Ligne de rappel entre l'étiquette et son objet.

    Le seuil de déclenchement est en millimètres papier (voir
    CALLOUT_MIN_LENGTH_MM) : le rappel apparaît à la même distance visuelle
    quelle que soit l'échelle d'affichage. Les ouvrages ponctuels passent
    min_length_mm=0 : leur étiquette étant toujours décalée du symbole, le
    connecteur doit toujours être tracé, y compris au petit zoom où le
    décalage de 1 m fait moins d'un millimètre sur le papier.
    """
    props = {
        'line_color': '100,100,100,200' if dashed else '120,120,120,255',
        'line_width': '0.3',
        'line_width_unit': 'MM',
    }
    if dashed:
        props['line_style'] = 'dash'
    callout = QgsSimpleLineCallout()
    callout.setEnabled(True)
    callout.setMinimumLength(min_length_mm)
    callout.setMinimumLengthUnit(QgsUnitTypes.RenderMillimeters)
    callout.setLineSymbol(QgsLineSymbol.createSimple(props))
    return callout


def _apply_placement_policy(pal, role, min_scale=LABEL_MIN_SCALE):
    """Priorité, obstacles, forçage et seuil d'échelle — communs à tous les rôles.

    Les ouvrages ponctuels sont déclarés obstacles : sans cela une
    caractéristique de conduite peut se poser sur le symbole d'un regard,
    qui devient illisible alors que c'est le repère principal du plan.
    Les lignes, elles, ne sont pas des obstacles : une étiquette curviligne
    est *censée* reposer sur sa conduite.
    """
    pal.priority = _PRIORITY.get(role, 5)

    is_obstacle = role in _POINT_ROLES
    try:
        obstacle = pal.obstacleSettings()
        obstacle.setIsObstacle(is_obstacle)
        if is_obstacle:
            # 1.5 : le moteur écarte franchement plutôt que de frôler.
            obstacle.setFactor(1.5)
        pal.setObstacleSettings(obstacle)
    except AttributeError:
        # QGIS < 3.12 : attributs directs sur QgsPalLayerSettings.
        pal.obstacle = is_obstacle
        if is_obstacle:
            pal.obstacleFactor = 1.5

    # Forçage limité aux couches du plugin (voir _FORCE_SCOPE).
    pal.displayAll = get_force_all_labels()

    if min_scale:
        pal.scaleVisibility = True
        pal.minimumScale = float(min_scale)   # dénominateur max (dézoom)
        pal.maximumScale = 0.0                # aucune limite au zoom
    else:
        pal.scaleVisibility = False


def _line_text_format(reseau, role, size=LABEL_SIZE_MAP_UNITS,
                      unit=QgsUnitTypes.RenderMapUnits):
    """Format texte des conduites et branchements (halo blanc)."""
    # Conduites EP : gras + halo épais, hérité de la v1.0 pour les distinguer
    # sur un plan où EU et EP se superposent souvent.
    bold      = (role == 'conduite' and reseau == 'EP')
    buffer_mm = 1.4 if bold else 0.8

    fmt = QgsTextFormat()
    font = QFont('Arial', 9)
    font.setBold(bold)
    fmt.setFont(font)
    fmt.setSizeUnit(unit)
    fmt.setSize(size)
    fmt.setColor(_TEXT_COLORS.get(reseau, QColor(0, 0, 0)))
    buf = QgsTextBufferSettings()
    buf.setEnabled(True)
    buf.setSize(buffer_mm)
    buf.setSizeUnit(QgsUnitTypes.RenderMillimeters)
    buf.setColor(QColor(255, 255, 255))
    buf.setOpacity(0.9)
    fmt.setBuffer(buf)
    return fmt


def _make_line_labeling(reseau, role, expression, size=LABEL_SIZE_MAP_UNITS,
                        unit=QgsUnitTypes.RenderMapUnits,
                        min_scale=LABEL_MIN_SCALE):
    """Rule-based labeling des lignes (conduites et branchements) :
      - règle 1 (lbl_x IS NULL)     : Curved auto, le texte suit la ligne.
      - règle 2 (lbl_x IS NOT NULL) : OverPoint épinglé à lbl_x/lbl_y avec
        l'orientation figée lbl_rot (conserve l'angle de la ligne) + rappel.

    Les branchements suivent le même schéma que les conduites : ce sont eux
    qui en ont le plus besoin, un texte « matériau | Ø | L | pente | cote »
    ne tenant pas sur une ligne de quelques mètres.
    """
    fmt  = _line_text_format(reseau, role, size, unit)
    show = QgsProperty.fromExpression(f'coalesce("{LBL_VISIBLE}", 1)')
    nom  = _ROLE_LABELS.get(role, role.capitalize())

    def _base():
        pal = QgsPalLayerSettings()
        pal.enabled = True
        pal.isExpression = True
        pal.fieldName = expression
        pal.setFormat(fmt)
        _apply_placement_policy(pal, role, min_scale)
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
    rule_auto.setDescription(f'{nom} – auto')

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
        pal_pin.setCallout(_make_callout(dashed=True))
    except Exception:
        pass
    rule_pin = QgsRuleBasedLabeling.Rule(pal_pin)
    rule_pin.setFilterExpression(f'"{LBL_X}" IS NOT NULL')
    rule_pin.setDescription(f'{nom} – épinglée')

    root = QgsRuleBasedLabeling.Rule(None)
    root.appendChild(rule_auto)
    root.appendChild(rule_pin)
    return QgsRuleBasedLabeling(root)


def _line_current_settings(labeling):
    """Extrait (expression, size, unit, min_scale) de la 1re règle d'un labeling ligne."""
    try:
        rules = labeling.rootRule().children()
        if rules:
            s = rules[0].settings()
            min_scale = s.minimumScale if s.scaleVisibility else 0
            return s.fieldName, s.format().size(), s.format().sizeUnit(), min_scale
    except Exception:
        pass
    return None


def _make_point_labeling(reseau, role, expression, size=LABEL_SIZE_MAP_UNITS,
                         unit=QgsUnitTypes.RenderMapUnits,
                         padding=LABEL_PADDING_MAP_UNITS,
                         min_scale=LABEL_MIN_SCALE,
                         offset=None):
    """Étiquetage des ouvrages ponctuels : pavé blanc encadré, décalé du
    symbole et relié à lui par une ligne de rappel.

    Le pavé est écarté de LABEL_OFFSET_MAP_UNITS : posé sur le symbole, il
    masquerait l'ouvrage, qui est le repère principal du plan. Le décalage
    rend le connecteur indispensable pour savoir à quel ouvrage l'étiquette
    se rapporte quand plusieurs regards sont proches.
    """
    pal = QgsPalLayerSettings()
    pal.enabled = True
    pal.isExpression = True
    pal.fieldName = expression
    pal.placement = QgsPalLayerSettings.AroundPoint
    # Lu à l'appel et non figé en valeur par défaut, pour que la constante
    # reste ajustable sans réimporter le module.
    pal.dist = LABEL_OFFSET_MAP_UNITS if offset is None else offset
    pal.distUnits = QgsUnitTypes.RenderMapUnits

    pc = QgsPropertyCollection()
    pc.setProperty(QgsPalLayerSettings.Show,
                   QgsProperty.fromExpression(f'coalesce("{LBL_VISIBLE}", 1)'))
    pc.setProperty(QgsPalLayerSettings.PositionX, QgsProperty.fromField(LBL_X))
    pc.setProperty(QgsPalLayerSettings.PositionY, QgsProperty.fromField(LBL_Y))
    pc.setProperty(QgsPalLayerSettings.Hali, QgsProperty.fromValue('Center'))
    pc.setProperty(QgsPalLayerSettings.Vali, QgsProperty.fromValue('Half'))
    pal.setDataDefinedProperties(pc)

    fmt = QgsTextFormat()
    fmt.setFont(QFont('Arial', 9))
    fmt.setSizeUnit(unit)
    fmt.setSize(size)
    fmt.setColor(_TEXT_COLORS.get(reseau, QColor(0, 0, 0)))

    bg = QgsTextBackgroundSettings()
    bg.setEnabled(True)
    bg.setType(QgsTextBackgroundSettings.ShapeRectangle)
    bg.setFillColor(QColor(255, 255, 255, 191))
    bg.setStrokeColor(QColor(80, 80, 80, 255))
    bg.setStrokeWidth(0.3)
    bg.setSizeType(QgsTextBackgroundSettings.SizeBuffer)
    bg.setSizeUnit(unit)
    bg.setSize(QSizeF(padding, padding))
    fmt.setBackground(bg)
    pal.setFormat(fmt)

    try:
        # min_length_mm=0 : le connecteur est tracé quel que soit le zoom.
        pal.setCallout(_make_callout(dashed=False, min_length_mm=0.0))
    except Exception:
        pass

    _apply_placement_policy(pal, role, min_scale)
    return QgsVectorLayerSimpleLabeling(pal)


def remembered_size():
    """Dernière taille d'étiquette choisie par l'utilisateur, en (valeur, unité).

    Lue dans QSettings, où la pose le dialogue « Taille des étiquettes ».
    Sans elle, reconstruire un étiquetage rebasculerait le plan sur la taille
    par défaut (2 m, soit un dimensionnement pour le 1:800) et ruinerait le
    réglage d'un plan monté au 1:200 ou au 1:250.
    """
    s = QSettings()
    mode = s.value("BET_HUMIDE/label_size_mode", "map_units")
    raw  = s.value("BET_HUMIDE/label_size_value", None)
    unit = (QgsUnitTypes.RenderPoints if mode == 'points'
            else QgsUnitTypes.RenderMapUnits)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return LABEL_SIZE_MAP_UNITS, QgsUnitTypes.RenderMapUnits
    if value <= 0:
        return LABEL_SIZE_MAP_UNITS, QgsUnitTypes.RenderMapUnits
    return value, unit


def apply_etiquettes(layer, role, reseau=None, size=None, unit=None,
                     min_scale=None):
    """Active les étiquettes sur la couche selon son rôle (point ou ligne).

    reseau      : 'EU' → texte rouge, 'EP' → texte bleu (None = noir)
    size / unit : None → dernière taille choisie par l'utilisateur.
    min_scale   : None → seuil déduit de la taille (voir default_min_scale).
    """
    _ensure_label_fields(layer, role)
    _reset_label_visibility(layer)

    if size is None or unit is None:
        size, unit = remembered_size()
    if min_scale is None:
        min_scale = default_min_scale(size, unit)
    padding = size * (LABEL_PADDING_MAP_UNITS / LABEL_SIZE_MAP_UNITS)

    if role in _LINE_ROLES:
        # Rule-based : auto curviligne tant que l'étiquette n'a pas été
        # déplacée, épinglée et orientée dès qu'elle l'a été.
        labeling = _make_line_labeling(reseau, role, _expression(role),
                                       size, unit, min_scale)
    else:
        labeling = _make_point_labeling(reseau, role, _expression(role),
                                        size, unit, padding, min_scale)

    layer.setLabeling(labeling)
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def remove_etiquettes(layer):
    """Désactive les étiquettes sur la couche."""
    layer.setLabelsEnabled(False)
    layer.triggerRepaint()


def _clear_legacy_engine_flag():
    """Retire le flag UseAllLabels posé par les versions <= 1.3 du plugin.

    C'était un réglage de projet : il forçait aussi les étiquettes des fonds
    BAN, noms de rue et PCI. Il est remplacé par displayAll, posé couche par
    couche. Sans ce nettoyage, un projet enregistré avant garderait ses fonds
    saturés d'étiquettes sans que rien dans l'interface ne l'explique.
    """
    if _LabelEngineSettings is None:
        return
    try:
        project  = QgsProject.instance()
        settings = project.labelingEngineSettings()
        if not settings.testFlag(_LabelEngineSettings.UseAllLabels):
            return
        settings.setFlag(_LabelEngineSettings.UseAllLabels, False)
        project.setLabelingEngineSettings(settings)
    except Exception:
        pass


def _mutate_pal(labeling, func):
    """Renvoie un nouveau labeling où func(pal) a été appliqué à chaque règle.

    Rien n'est modifié en place : Rule.settings() rend le pointeur interne de
    la règle, donc le muter puis le réinjecter par setSettings() ferait
    détruire l'objet qu'on vient de passer. On repart d'une copie et on
    reconstruit les règles.
    """
    if isinstance(labeling, QgsRuleBasedLabeling):
        root = QgsRuleBasedLabeling.Rule(None)
        for rule in labeling.rootRule().children():
            src = rule.settings()
            if src is None:
                continue
            pal = QgsPalLayerSettings(src)
            func(pal)
            new_rule = QgsRuleBasedLabeling.Rule(pal)
            new_rule.setFilterExpression(rule.filterExpression())
            new_rule.setDescription(rule.description())
            root.appendChild(new_rule)
        return QgsRuleBasedLabeling(root)

    pal = QgsPalLayerSettings(labeling.settings())
    func(pal)
    return QgsVectorLayerSimpleLabeling(pal)


def set_force_all_labels(enabled: bool, canvas=None, plugin=None):
    """Active ou désactive l'affichage forcé des étiquettes DU PLUGIN.

    Quand activé : aucune étiquette EU/EP n'est supprimée par le moteur —
    elle est décalée pour minimiser les chevauchements.

    Contrairement aux versions précédentes, les fonds de plan (BAN, noms de
    rue, PCI) ne sont pas concernés : le réglage est posé couche par couche
    via displayAll, et non sur le moteur de rendu du projet.
    """
    try:
        QgsProject.instance().writeEntry(_FORCE_SCOPE, _FORCE_KEY, bool(enabled))
    except Exception:
        pass
    _clear_legacy_engine_flag()

    if plugin is not None:
        def _set(pal):
            pal.displayAll = bool(enabled)
        for reseau in ('EU', 'EP'):
            for layer in plugin._get_couches(reseau).values():
                labeling = layer.labeling()
                if labeling is None:
                    continue
                layer.setLabeling(_mutate_pal(labeling, _set))
                layer.triggerRepaint()

    if canvas is not None:
        canvas.refresh()


def get_label_min_scale(plugin):
    """Seuil d'échelle courant, lu sur la première couche étiquetée (0 = aucun)."""
    for reseau in ('EU', 'EP'):
        for layer in plugin._get_couches(reseau).values():
            labeling = layer.labeling()
            if labeling is None:
                continue
            try:
                if isinstance(labeling, QgsRuleBasedLabeling):
                    pal = labeling.rootRule().children()[0].settings()
                else:
                    pal = labeling.settings()
            except Exception:
                continue
            return int(pal.minimumScale) if pal.scaleVisibility else 0
    # Aucune couche étiquetée : proposer le seuil déduit de la taille
    # mémorisée plutôt qu'un plafond arbitraire.
    return default_min_scale(*remembered_size())


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


def apply_label_size_all(plugin, mode, value, min_scale=None):
    """Applique la taille d'étiquette à toutes les couches EU et EP.

    mode      : 'points'    → taille fixe écran (QgsUnitTypes.RenderPoints)
                'map_units' → taille en mètres  (QgsUnitTypes.RenderMapUnits)
    value     : float — taille dans l'unité correspondante
    min_scale : dénominateur du seuil de dézoom, 0 pour aucun seuil.
                None → conserve le seuil déjà en place sur la couche.
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

            # Lignes : rule-based → reconstruire avec la nouvelle taille
            if role in _LINE_ROLES or isinstance(labeling, QgsRuleBasedLabeling):
                # Les règles filtrent sur lbl_x : sur une couche étiquetée par
                # une version antérieure du plugin (branchements sans champs
                # de position), le filtre ne trouverait aucun objet.
                _ensure_label_fields(layer, role)
                cur = _line_current_settings(labeling)
                expression = cur[0] if cur else _expression(role)
                scale = min_scale if min_scale is not None else (
                    cur[3] if cur else LABEL_MIN_SCALE)
                layer.setLabeling(
                    _make_line_labeling(reseau, role, expression, value, unit,
                                        scale))
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
            if min_scale is not None:
                if min_scale:
                    pal.scaleVisibility = True
                    pal.minimumScale = float(min_scale)
                    pal.maximumScale = 0.0
                else:
                    pal.scaleVisibility = False
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
    """Après un renommage : s'assure que le moteur d'étiquettes est configuré.

    - Crée les champs lbl_* si absents (nouvelles features)
    - Configure apply_etiquettes UNIQUEMENT si la couche n'a jamais été
      labellisée
    - Sinon déclenche un simple repaint : l'expression lit le champ nom, donc
      les nouveaux numéros apparaissent sans rien reconstruire.

    Les positions lbl_x / lbl_y ne sont PAS modifiées. Une couche dont
    l'étiquetage existe déjà n'est jamais reconstruite : le faire
    réappliquerait la taille par défaut et casserait un plan dimensionné
    pour le 1:200 ou le 1:250.

    Les étiquettes sont en revanche rallumées : on renumérote pour lire les
    nouveaux numéros, donc les laisser masquées viderait l'opération de son
    sens. C'est le rallumage qui est voulu, pas la reconstruction — les deux
    étaient auparavant liés dans la même branche.
    """
    _ensure_label_fields(layer, role)
    if layer.labeling() is None:
        apply_etiquettes(layer, role, reseau)   # couche jamais étiquetée
    layer.setLabelsEnabled(True)
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

            # Lignes : rule-based → reconstruire avec la taille courante
            if role in _LINE_ROLES or isinstance(labeling, QgsRuleBasedLabeling):
                _ensure_label_fields(layer, role)
                cur = _line_current_settings(labeling)
                size  = cur[1] if cur else LABEL_SIZE_MAP_UNITS
                unit  = cur[2] if cur else QgsUnitTypes.RenderMapUnits
                scale = cur[3] if cur else LABEL_MIN_SCALE
                layer.setLabeling(
                    _make_line_labeling(reseau, role, expression, size, unit,
                                        scale))
                layer.triggerRepaint()
                continue

            pal = labeling.settings()
            pal.fieldName   = expression
            pal.isExpression = True
            layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
            layer.triggerRepaint()
