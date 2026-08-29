# -*- coding: utf-8 -*-
"""Post-traitement du DXF : ajoute fond + cadre + ligne de rappel autour
des étiquettes des regards et tabourets.

QgsDxfExport écrit chaque étiquette en MTEXT à l'emplacement (lbl_x,lbl_y)
mais perd le fond blanc, le contour gris et le callout vers la feature.

Stratégie :
  1. Pour chaque MTEXT sur un calque regard_*/tabouret_*, on lit la
     largeur visuelle (groupe DXF 41), la hauteur du texte (parsée depuis
     le code \\H... du contenu, ou via le groupe 40 si présent), le point
     d'attache (groupe 71) et le contenu plain.
  2. On en déduit la bbox visuelle exacte en unités du dessin.
  3. On retrouve la feature d'origine par son champ « nom » (= 1ʳᵉ ligne
     du texte, ex : « REP00 » ou « EP-BRCHT01 »). Robuste aux offsets
     de coordonnées.
  4. On supprime le MTEXT, on insère HATCH (fond) + LWPOLYLINE (cadre)
     + LINE (callout vers le bord du rect), puis on ré-ajoute le MTEXT
     en dernier — son nouveau handle plus élevé le place en sommet de
     l'ordre de tracé DXF.
"""

import os
import re
import traceback

from . import i18n
from qgis.core import QgsProject, QgsVectorLayer, QgsMessageLog, Qgis
from . import errlog

_LOG_TAG = "CanaPlan/DXF"


def _log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(msg, _LOG_TAG, level)


def _plugin_libs_dir():
    """Retourne le chemin du dossier `libs/` à la racine du plugin CanaPlan,
    en le créant et en l'ajoutant au sys.path si nécessaire.
    """
    import sys
    # Le module dxf_postprocess est dans CanaPlan/tools/, donc on remonte de 2.
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    libs = os.path.join(plugin_root, "libs")
    os.makedirs(libs, exist_ok=True)
    if libs not in sys.path:
        sys.path.insert(0, libs)
    return libs


def _ensure_libs_on_path():
    """Ajoute libs/ du plugin au sys.path si pas déjà fait. À appeler tôt."""
    _plugin_libs_dir()


def _install_and_import_ezdxf():
    """Installe ezdxf dans le dossier libs/ du plugin (isolé, sans droits
    admin, sans pollution système) puis l'importe. Lève l'exception si
    l'installation échoue.

    --no-deps est délibéré : ezdxf déclare numpy en dépendance dure, or
    libs/ passe AVANT le reste du sys.path. Laisser pip tirer numpy ici
    déposerait, dans libs/, un numpy qui masquerait celui de QGIS — au
    mieux redondant, au pire construit pour une autre plateforme. On
    installe donc explicitement les seules dépendances pures de ezdxf et
    on laisse numpy à QGIS. C'est la même liste que requirements-libs.txt.
    """
    import sys
    import subprocess  # nosec B404
    libs = _plugin_libs_dir()
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--target", libs,
        "--upgrade",
        "--no-deps",
        "--no-warn-script-location",
        "ezdxf", "fontTools", "pyparsing", "typing_extensions",
    ]
    _log(f"Installation ezdxf dans {libs}…", Qgis.Info)
    # cmd est bati juste au-dessus a partir de sys.executable et de noms de
    # paquets litteraux ; seul --target pointe vers libs/, un chemin calcule
    # depuis __file__. Liste d'arguments, sans shell.
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)  # nosec B603
    if res.returncode != 0:
        raise RuntimeError(
            f"pip install ezdxf a retourné {res.returncode}\n"
            f"STDOUT: {res.stdout[-800:]}\nSTDERR: {res.stderr[-800:]}"
        )
    import importlib
    importlib.invalidate_caches()
    import ezdxf
    return ezdxf


# Ajoute libs/ au sys.path dès l'import du module — comme ça si ezdxf y est
# déjà installé d'un export précédent, l'import suivant le trouve directement.
_ensure_libs_on_path()

# Préfixes des calques cibles (case-insensitive : on matche "regard_EP" etc.)
_TARGET_PREFIXES = ('regard_', 'tabouret_')

# Style DXF dédié pour nos étiquettes : Arial (la police QGIS).
# Sans style explicite, AutoCAD utilise STANDARD = txt.shx (police bâton
# très large) → les étiquettes débordent horizontalement.
_BET_TEXT_STYLE = 'BET_Arial'
_BET_TEXT_FONT = 'arial.ttf'

# Facteur d'échelle appliqué à la hauteur de la police (et donc à sa
# largeur globale puisque Arial est proportionnel). 0.84 = police 16%
# plus petite que dans QGIS, ce qui absorbe le débordement.
_TEXT_HEIGHT_SCALE = 0.84

# Facteur de largeur (group 41 du TEXT) — laissé à 1.0 puisque la
# réduction est portée par _TEXT_HEIGHT_SCALE (uniforme, pas de
# distorsion horizontale). Réglable si besoin.
_TEXT_WIDTH_FACTOR = 1.0

# Padding autour du texte (= LABEL_PADDING_MAP_UNITS dans gui/etiquettes.py)
_PADDING = 0.4

# Espacement utilisé pour DIMENSIONNER LE CADRE et POSITIONNER chaque
# ligne TEXT (multiplicateur de char_height). 1.2 = rendu QGIS.
# Stratégie : on remplace le MTEXT par N entités TEXT indépendantes (1 par
# ligne), positionnées exactement à 1.2 × char_h d'écart. AutoCAD rend
# chaque TEXT individuellement → aucune interférence avec les règles de
# spacing MTEXT (at-least, line_spacing_factor partiellement honoré, etc.).
_FRAME_LINE_SPACING = 1.2

# Couleurs ACI et lineweights (1/100 mm)
_FILL_COLOR_ACI = 7        # 7 = blanc/noir selon fond ; SOLID
_OUTLINE_COLOR_ACI = 8     # gris foncé
_CALLOUT_COLOR_ACI = 8
_OUTLINE_LINEWEIGHT = 20   # 0.20 mm
_CALLOUT_LINEWEIGHT = 15   # 0.15 mm

# Dimensions des symboles ponctuels (= _apply_style dans main.py)
_REGARD_RADIUS  = 0.5   # cercle Ø 1.0 m → rayon 0.5 m
_TABOURET_HALF  = 0.2   # carré 0.4 m → demi-côté 0.2 m
_SYM_LINEWEIGHT = 25    # 0.25 mm contour symbole

# XDATA — attributs QGIS attachés à chaque INSERT regard/tabouret
_XDATA_APPID = "CANAPLAN"
_ROLE_FIELDS = {
    'regard':   ['nom', 'tn', 'fe_radier', 'profondeur'],
    'tabouret': ['nom', 'tn', 'fe_entree',  'profondeur'],
}
# ATTDEF dans les blocs BET_* : (TAG_DXF, clé_dans_attrs_dict)
# Visible au double-clic dans AutoCAD / AutoCAD Map.
_ATTDEF_FIELDS = {
    'regard':   [('NOM', 'nom'), ('TN', 'tn'), ('FE_RADIER', 'fe_radier'), ('PROFONDEUR', 'profondeur')],
    'tabouret': [('NOM', 'nom'), ('TN', 'tn'), ('FE_ENTREE', 'fe_entree'), ('PROFONDEUR', 'profondeur')],
}

# Regex pour extraire la hauteur de char depuis le contenu MTEXT : "\H0.476319;"
_RE_HEIGHT = re.compile(r'\\H([0-9.]+)\s*;')

# Codes MTEXT avec paramètres terminés par ';' à supprimer purement.
# Ex : \fArial|i0|b0;  \H0.476319;  \C7;  \W0.8;  \Q15;  \T1.5;  \A1;
_RE_MTEXT_PARAM_CODES = re.compile(r'\\[fFhHcCWQTAa][^;]*;')

# Codes MTEXT sans paramètres (toggles formatage)
_RE_MTEXT_TOGGLE = re.compile(r'\\[LOKlok]')


def _mtext_to_plain(raw):
    """Convertit le contenu raw d'un MTEXT (avec codes de formatage) en
    texte simple compatible avec une entité DXF TEXT.

    ezdxf.plain_text() laisse parfois des séquences \\~ ou \\P en place
    selon les versions ; on fait notre propre passe pour être sûr.
    """
    if not raw:
        return ''
    s = raw
    # Codes avec paramètres (\f...; \H...; \C...; etc.)
    s = _RE_MTEXT_PARAM_CODES.sub('', s)
    # Toggles formatage (\L \O \K \l \o \k)
    s = _RE_MTEXT_TOGGLE.sub('', s)
    # Sauts de ligne
    s = s.replace('\\P', '\n').replace('\\p', '\n')
    # Espace insécable → espace normal (TEXT n'a pas la notion)
    s = s.replace('\\~', ' ')
    # Accolades de groupes de formatage
    s = s.replace('{', '').replace('}', '')
    # Backslash littéral en tout dernier
    s = s.replace('\\\\', '\\')
    # Collapse runs of regular spaces (les "TN   :" / "P      :" du QGIS
    # viennent d'un alignement monospace inutile en Arial proportionnel).
    s = re.sub(r' {2,}', ' ', s)
    return s

# Regex pour extraire un facteur d'échelle si présent (\Hxxxx;) avec x suivi
# de l'unité. On reste simple.


def _read_layer_padding(lyr, fallback=0.4):
    """Retourne le padding en unités carte du fond d'étiquette de la couche,
    lu depuis QgsTextBackgroundSettings. Fallback si lecture impossible.
    """
    try:
        from qgis.core import QgsUnitTypes, QgsTextBackgroundSettings
        labeling = lyr.labeling()
        if labeling is None:
            return fallback
        pal = labeling.settings()
        bg = pal.format().background()
        if not bg.enabled():
            return fallback
        size = bg.size()
        unit = bg.sizeUnit()
        # On considère la moyenne X/Y comme padding uniforme
        avg = (size.width() + size.height()) / 2.0
        if unit == QgsUnitTypes.RenderMapUnits:
            return float(avg)
        # Si l'unité est mm/points/pixels, on ne peut pas convertir sans
        # connaître le DPI/échelle ; on laisse le fallback.
        return fallback
    except Exception:
        return fallback


def _build_origin_index_by_name():
    """Retourne {nom_couche_DXF: {'features': {nom: (x, y)}, 'padding': p}}.

    Le matching est insensible à la casse côté nom de calque (regard_EP
    vs regard_eu).
    """
    index = {}
    root = QgsProject.instance().layerTreeRoot()
    for node in root.findLayers():
        if not node.isVisible():
            continue
        lyr = node.layer()
        if lyr is None or not isinstance(lyr, QgsVectorLayer):
            continue
        layer_name = lyr.name()
        if not layer_name.lower().startswith(_TARGET_PREFIXES):
            continue
        fields = lyr.fields()
        if fields.indexFromName('nom') < 0:
            continue
        per_layer = {}
        for feat in lyr.getFeatures():
            nom = feat['nom']
            if nom is None:
                continue
            nom = str(nom).strip()
            if not nom:
                continue
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                pt = geom.asPoint()
                per_layer[nom] = (float(pt.x()), float(pt.y()))
            except Exception as _err:
                errlog.ignored(_err, "dxf_postprocess._build_origin_index_by_name:254")
                continue
        if per_layer:
            entry = {
                'features': per_layer,
                'padding': _read_layer_padding(lyr, _PADDING),
            }
            index[layer_name] = entry
            index[layer_name.lower()] = entry
    return index


def _parse_char_height(raw_text, fallback):
    """Extrait la hauteur de char depuis le code \\H... du contenu MTEXT.
    Retourne fallback si non trouvée.
    """
    if not raw_text:
        return fallback
    m = _RE_HEIGHT.search(raw_text)
    if not m:
        return fallback
    try:
        return float(m.group(1))
    except (TypeError, ValueError):
        return fallback


def _count_mtext_lines(raw_text):
    """Compte le nombre de lignes dans le contenu MTEXT (séparateurs \\P).
    raw_text est la chaîne brute (avec codes de formatage).
    """
    if not raw_text:
        return 1
    # Compte les \P ; le nombre de lignes = occurrences + 1
    return raw_text.count('\\P') + 1


def _bbox_from_mtext(insert_xy, attach_point, width, height):
    """Calcule la bbox (x0, y0, x1, y1) à partir du point d'insertion et
    du point d'attache DXF (groupe 71, valeurs 1-9).
    """
    ix, iy = insert_xy
    col = (attach_point - 1) % 3   # 0=left, 1=center, 2=right
    row = (attach_point - 1) // 3  # 0=top, 1=middle, 2=bottom
    if col == 0:
        x0 = ix
    elif col == 1:
        x0 = ix - width / 2
    else:
        x0 = ix - width
    if row == 0:
        y0 = iy - height
    elif row == 1:
        y0 = iy - height / 2
    else:
        y0 = iy
    return x0, y0, x0 + width, y0 + height


def _first_word(plain_text):
    """Retourne le premier « mot » du texte plain (jusqu'au premier saut
    de ligne), sans espaces ni caractères de formatage résiduels.
    """
    if not plain_text:
        return ''
    first = plain_text.split('\n', 1)[0]
    return first.strip()


def _rect_edge_point(x0, y0, x1, y1, from_xy):
    """Intersection segment [from_xy → centre rect] avec bord du rect.
    Sert à terminer le callout au contact du cadre.
    """
    cx = (x0 + x1) / 2
    cy = (y0 + y1) / 2
    fx, fy = from_xy
    dx = cx - fx
    dy = cy - fy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return cx, cy
    half_w = (x1 - x0) / 2
    half_h = (y1 - y0) / 2
    if abs(dx) < 1e-9:
        t = half_h / abs(dy)
    elif abs(dy) < 1e-9:
        t = half_w / abs(dx)
    else:
        t = min(half_w / abs(dx), half_h / abs(dy))
    return cx - t * dx, cy - t * dy


# ─────────────────────────────────────────────────────────────────────────────
#  Symboles ponctuels (regards = cercle, tabourets = carré)
# ─────────────────────────────────────────────────────────────────────────────

def _read_symbol_color(lyr):
    """Retourne (r, g, b) depuis le renderer de la couche, ou None."""
    try:
        renderer = lyr.renderer()
        if renderer and hasattr(renderer, 'symbol') and renderer.symbol():
            c = renderer.symbol().color()
            return (c.red(), c.green(), c.blue())
    except Exception as _err:
        errlog.ignored(_err, "dxf_postprocess._read_symbol_color:357")
    return None


def _feat_attrs(feat, role):
    """Lit les champs métier d'une feature QGIS selon son rôle.
    Retourne un dict {field: valeur_python} (None si NULL QGIS).
    """
    attrs = {}
    for field in _ROLE_FIELDS.get(role, []):
        try:
            val = feat[field]
            # QVariant NULL → None
            if val is None or (hasattr(val, 'isNull') and val.isNull()):
                attrs[field] = None
            else:
                # Convertit en type Python natif
                try:
                    attrs[field] = float(val)
                except (TypeError, ValueError):
                    attrs[field] = str(val) if val != '' else None
        except Exception:
            attrs[field] = None
    # nom reste string
    nom = attrs.get('nom')
    if nom is not None:
        attrs['nom'] = str(nom)
    return attrs


def _attrs_to_xdata(attrs):
    """Sérialise un dict d'attributs en liste de tags XDATA.

    Structure : paires (1000, nom_champ), (code_valeur, valeur).
      - str  → code 1000
      - float → code 1040
      - int   → code 1070
      - None  → (1000, '')
    """
    tags = []
    for name, val in attrs.items():
        tags.append((1000, name))
        if val is None:
            tags.append((1000, ''))
        elif isinstance(val, float):
            tags.append((1040, val))
        elif isinstance(val, int):
            tags.append((1070, val))
        else:
            tags.append((1000, str(val)))
    return tags


def _xdata_to_attrs(xdata_tags):
    """Relit des tags XDATA (liste de GroupCode) en dict d'attributs.
    Inverse de _attrs_to_xdata(). Utilisé à l'import.
    """
    attrs = {}
    it = iter(xdata_tags)
    for tag in it:
        if getattr(tag, 'code', None) == 1000:
            name = tag.value
            try:
                vtag = next(it)
                code = getattr(vtag, 'code', None)
                if code == 1040:
                    attrs[name] = float(vtag.value)
                elif code == 1070:
                    attrs[name] = int(vtag.value)
                elif vtag.value == '':
                    attrs[name] = None
                else:
                    attrs[name] = vtag.value
            except StopIteration:
                attrs[name] = None
    return attrs


def _build_point_symbol_index():
    """Retourne {nom_lower: {'layer_name': str, 'role': str, 'reseau': str,
                             'rgb': (r,g,b),
                             'features': [((x,y), attrs_dict), ...]}}
    pour toutes les couches regard_*/tabouret_* visibles.
    attrs_dict contient les champs métier (nom, tn, fe_radier/fe_entree,
    profondeur) lus depuis chaque feature QGIS.
    """
    index = {}
    root = QgsProject.instance().layerTreeRoot()
    for node in root.findLayers():
        if not node.isVisible():
            continue
        lyr = node.layer()
        if lyr is None or not isinstance(lyr, QgsVectorLayer):
            continue
        name = lyr.name()
        if not name.lower().startswith(_TARGET_PREFIXES):
            continue
        role = 'regard' if name.lower().startswith('regard_') else 'tabouret'
        reseau = 'EU' if 'eu' in name.lower() else 'EP'
        rgb = _read_symbol_color(lyr)
        if rgb is None:
            rgb = (255, 0, 0) if reseau == 'EU' else (0, 0, 255)
        features = []
        for feat in lyr.getFeatures():
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            try:
                pt = geom.asPoint()
                xy = (float(pt.x()), float(pt.y()))
                attrs = _feat_attrs(feat, role)
                features.append((xy, attrs))
            except Exception as _err:
                errlog.ignored(_err, "dxf_postprocess._build_point_symbol_index:470")
                continue
        if features:
            index[name.lower()] = {
                'layer_name': name,
                'role': role,
                'reseau': reseau,
                'rgb': rgb,
                'features': features,
            }
    return index


# Préfixe des noms de blocs BET (pour les repérer au nettoyage)
_BET_BLOCK_PREFIX = 'BET_'


def _ensure_symbol_block(doc, role, reseau, rgb):
    """Retourne le BlockLayout du symbole BET_*, en (re)créant la définition.

    Noms : BET_REGARD_EU / BET_REGARD_EP / BET_TABOURET_EU / BET_TABOURET_EP.
    Le bloc est centré sur (0,0) — l'INSERT place l'origine sur la feature.
    Les ATTDEFs sont invisibles (flags=1) mais visibles au double-clic AutoCAD.
    Le bloc est toujours recréé pour inclure les ATTDEFs à jour.
    """
    block_name = f"BET_{'REGARD' if role == 'regard' else 'TABOURET'}_{reseau}"

    # Supprime le bloc existant pour le recréer avec ATTDEFs à jour
    if block_name in doc.blocks:
        try:
            doc.blocks.delete_block(block_name, safe=False)
        except Exception as exc:
            _log(f"Impossible de supprimer {block_name} : {exc}", Qgis.Warning)
            return doc.blocks[block_name], block_name

    r, g, b = rgb
    rgb_int = (r << 16) | (g << 8) | b
    blk = doc.blocks.new(block_name)

    if role == 'regard':
        # Disque plein : HATCH arc + CIRCLE contour, centré sur (0,0)
        try:
            h = blk.add_hatch(color=1, dxfattribs={'true_color': rgb_int})
            h.set_solid_fill()
            ep = h.paths.add_edge_path()
            ep.add_arc(center=(0, 0), radius=_REGARD_RADIUS,
                       start_angle=0, end_angle=360, ccw=True)
        except Exception as exc:
            _log(f"Bloc {block_name} HATCH : {exc}", Qgis.Warning)
        try:
            blk.add_circle((0, 0), _REGARD_RADIUS,
                           dxfattribs={'true_color': rgb_int,
                                       'lineweight': _SYM_LINEWEIGHT})
        except Exception as exc:
            _log(f"Bloc {block_name} CIRCLE : {exc}", Qgis.Warning)
    else:
        # Carré plein : HATCH + LWPOLYLINE, centré sur (0,0)
        h = _TABOURET_HALF
        pts = [(-h, -h), (h, -h), (h, h), (-h, h)]
        try:
            hatch = blk.add_hatch(color=1, dxfattribs={'true_color': rgb_int})
            hatch.set_solid_fill()
            hatch.paths.add_polyline_path(pts, is_closed=True)
        except Exception as exc:
            _log(f"Bloc {block_name} HATCH : {exc}", Qgis.Warning)
        try:
            blk.add_lwpolyline(pts, close=True,
                               dxfattribs={'true_color': rgb_int,
                                           'lineweight': _SYM_LINEWEIGHT})
        except Exception as exc:
            _log(f"Bloc {block_name} LWPOLYLINE : {exc}", Qgis.Warning)

    # ATTDEFs invisibles (flags=1) — valeurs renseignées par add_auto_attribs()
    for tag, _field in _ATTDEF_FIELDS.get(role, []):
        try:
            blk.add_attdef(tag, (0, 0),
                           dxfattribs={'height': 0.25, 'flags': 1, 'prompt': tag})
        except Exception as exc:
            _log(f"Bloc {block_name} ATTDEF {tag} : {exc}", Qgis.Warning)

    _log(f"Bloc {block_name} créé ({len(_ATTDEF_FIELDS.get(role, []))} ATTDEFs).")
    return blk, block_name


def add_point_symbols(dxf_path):
    """Remplace les entités ponctuelles incorrectes de QgsDxfExport par des
    INSERT référençant des blocs BET_REGARD_EU/EP et BET_TABOURET_EU/EP.

    Avantages vs entités individuelles :
      - 1 INSERT par feature (vs HATCH + CIRCLE/LWPOLYLINE) → fichier plus léger
      - Symbole modifiable une seule fois dans la définition de bloc
      - Prêt pour l'ajout d'attributs ATTRIB (XDATA, étape suivante)

    Retourne le nombre de symboles écrits.
    """
    try:
        import ezdxf
    except ImportError:
        try:
            ezdxf = _install_and_import_ezdxf()
        except Exception as exc:
            raise RuntimeError(f"ezdxf requis : {exc}") from exc

    if not os.path.exists(dxf_path):
        raise RuntimeError(f"DXF introuvable : {dxf_path}")

    sym_index = _build_point_symbol_index()
    if not sym_index:
        _log("Aucune couche regard_*/tabouret_* visible → aucun symbole ponctuel.",
             Qgis.Warning)
        return 0

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    # Enregistre l'AppID CanaPlan (nécessaire avant tout set_xdata)
    if _XDATA_APPID not in doc.appids:
        doc.appids.add(_XDATA_APPID)

    # Nettoyage : supprime les entités ponctuelles QgsDxfExport (POINT, CIRCLE,
    # HATCH) ET les éventuels INSERT BET_* d'un export précédent sur ces calques.
    target_lowers = set(sym_index.keys())

    def _is_target_layer(ent):
        lay = getattr(ent.dxf, 'layer', '')
        return lay.lower() in target_lowers or any(
            lay.lower().startswith(p) for p in _TARGET_PREFIXES)

    def _is_bet_insert(ent):
        if ent.dxftype() != 'INSERT':
            return False
        bname = getattr(ent.dxf, 'name', '') or ''
        return bname.startswith(_BET_BLOCK_PREFIX) and _is_target_layer(ent)

    to_del = [e for e in msp
              if (e.dxftype() in ('POINT', 'CIRCLE', 'HATCH') and _is_target_layer(e))
              or _is_bet_insert(e)]
    for e in to_del:
        msp.delete_entity(e)

    n_written = 0
    for key, entry in sym_index.items():
        layer_name = entry['layer_name']
        _, block_name = _ensure_symbol_block(
            doc, entry['role'], entry['reseau'], entry['rgb'])

        # Prépare le mapping TAG→valeur pour add_auto_attribs()
        attdef_map = _ATTDEF_FIELDS.get(entry['role'], [])

        for (x, y), attrs in entry['features']:
            try:
                ref = msp.add_blockref(block_name, (x, y),
                                       dxfattribs={'layer': layer_name})
                # XDATA : attributs QGIS attachés à l'INSERT (lecture par XDLIST)
                if attrs:
                    try:
                        ref.set_xdata(_XDATA_APPID, _attrs_to_xdata(attrs))
                    except Exception as exc:
                        _log(f"XDATA {block_name} ({x:.1f},{y:.1f}) : {exc}",
                             Qgis.Warning)
                # ATTRIB : attributs visibles au double-clic dans AutoCAD Map
                if attdef_map and attrs:
                    try:
                        attrib_values = {}
                        for tag, field in attdef_map:
                            val = attrs.get(field)
                            attrib_values[tag] = (
                                '' if val is None
                                else f"{val:.3f}" if isinstance(val, float)
                                else str(val)
                            )
                        ref.add_auto_attribs(attrib_values)
                    except Exception as exc:
                        _log(f"ATTRIB {block_name} ({x:.1f},{y:.1f}) : {exc}",
                             Qgis.Warning)
                n_written += 1
            except Exception as exc:
                _log(f"INSERT {block_name} ({x:.1f},{y:.1f}) : {exc}",
                     Qgis.Warning)

    doc.saveas(dxf_path)
    _log(f"add_point_symbols : {n_written} INSERT écrits "
         f"({len(sym_index)} blocs BET_*).")
    return n_written


def apply_ltscale(dxf_path, export_scale):
    """Ajuste l'échelle des types de ligne EU/EP dans le DXF post-export.

    Deux niveaux :
      • Global  : $LTSCALE dans le header — neutral (1.0) pour ne pas affecter
        les linetypes simples déjà bien calibrés.
      • Par entité : dxf.ltscale = export_scale / 1000 sur les entités dont le
        linetype est détecté comme EU ou EP (complex linetypes avec texte).
        Formule : coordonnées Lambert 93 en mètres → scale 200 donne 0.20 m de
        motif, scale 500 → 0.50 m, etc.

    Ne lève pas d'exception — les erreurs sont loggées et la fonction retourne
    le nombre d'entités modifiées (0 si ezdxf absent ou aucun EU/EP trouvé).
    """
    try:
        import ezdxf
    except ImportError:
        _log("apply_ltscale : ezdxf absent, ltscale ignoré.", Qgis.Warning)
        return 0

    if not os.path.exists(dxf_path):
        _log(f"apply_ltscale : fichier absent {dxf_path}", Qgis.Warning)
        return 0

    try:
        doc = ezdxf.readfile(dxf_path)
    except Exception as exc:
        _log(f"apply_ltscale lecture : {exc}", Qgis.Warning)
        return 0

    # ── Import local pour réutiliser _build_lt_reseau_map sans dépendance circulaire
    try:
        from tools.dxf_convert.services.conversion_service import _build_lt_reseau_map
        lt_reseau = _build_lt_reseau_map(doc)
    except Exception:
        lt_reseau = {}

    if not lt_reseau:
        _log("apply_ltscale : aucun linetype EU/EP détecté — pas de modification.",
             Qgis.Info)
        return 0

    # Header global : $LTSCALE = 1.0 (neutre ; per-entity fait le travail fin)
    try:
        doc.header['$LTSCALE'] = 1.0
    except Exception as exc:
        _log(f"apply_ltscale $LTSCALE header : {exc}", Qgis.Warning)

    # Valeur per-entity : calibrée pour coordonnées en mètres (Lambert 93)
    entity_scale = max(0.01, float(export_scale) / 1000.0)

    msp = doc.modelspace()
    n_modified = 0
    lt_names_upper = {k.upper(): v for k, v in lt_reseau.items()}
    for ent in msp:
        try:
            lt = getattr(ent.dxf, 'linetype', '') or ''
            if lt.upper() in lt_names_upper:
                ent.dxf.ltscale = entity_scale
                n_modified += 1
        except Exception as _err:
            errlog.ignored(_err, "dxf_postprocess.apply_ltscale:717")
            continue

    try:
        doc.saveas(dxf_path)
        _log(f"apply_ltscale : {n_modified} entité(s) → ltscale={entity_scale:.4f} "
             f"(scale={export_scale}).")
    except Exception as exc:
        _log(f"apply_ltscale sauvegarde : {exc}", Qgis.Warning)
        return 0

    return n_modified


def add_label_decorations(dxf_path):
    """Ajoute fond + cadre + callout autour de chaque MTEXT issu d'un
    calque regard_*/tabouret_*. Retourne le nombre d'étiquettes décorées.

    Lève RuntimeError si ezdxf est absent ou si l'écriture échoue.
    """
    try:
        import ezdxf
    except ImportError:
        _log("ezdxf absent — tentative d'installation via pip…", Qgis.Info)
        try:
            ezdxf = _install_and_import_ezdxf()
            _log("ezdxf installé avec succès.", Qgis.Info)
        except Exception as exc:
            _log(f"Installation ezdxf échouée : {exc}\n{traceback.format_exc()}",
                 Qgis.Critical)
            raise RuntimeError(
                i18n.tr('dxf_ezdxf_manquant', detail=exc)
            ) from exc

    from ezdxf.enums import TextEntityAlignment

    if not os.path.exists(dxf_path):
        raise RuntimeError(f"DXF introuvable : {dxf_path}")

    origin_index = _build_origin_index_by_name()
    _log(f"Index features regards/tabourets : "
         f"{[(k, len(v)) for k, v in origin_index.items() if k == k.lower() or True][:6]}")
    if not origin_index:
        _log("Aucune couche regard_*/tabouret_* visible avec champ 'nom' — "
             "rien à décorer.", Qgis.Warning)
        return 0

    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    # Garantit la présence d'un text style Arial pour les TEXT décorées.
    if _BET_TEXT_STYLE not in doc.styles:
        try:
            doc.styles.add(_BET_TEXT_STYLE, font=_BET_TEXT_FONT)
        except Exception as exc:
            _log(f"Création style « {_BET_TEXT_STYLE} » échouée : {exc} "
                 "— fallback STANDARD (txt.shx, plus large)", Qgis.Warning)

    # Collecte des MTEXT à décorer (modification pendant itération interdite)
    to_decorate = []
    n_mtext_total = 0
    n_mtext_skipped_layer = 0
    n_mtext_unmatched_name = 0
    for mtext in msp.query('MTEXT'):
        n_mtext_total += 1
        layer_name = mtext.dxf.layer
        entry = origin_index.get(layer_name) or origin_index.get(layer_name.lower())
        if not entry:
            n_mtext_skipped_layer += 1
            continue
        feature_dict = entry['features']
        padding = entry['padding']

        try:
            ix = float(mtext.dxf.insert.x)
            iy = float(mtext.dxf.insert.y)
        except (AttributeError, TypeError, ValueError) as _err:
            errlog.ignored(_err, "dxf_postprocess.add_label_decorations:794")
            continue

        attach = int(getattr(mtext.dxf, 'attachment_point', 7))
        # Largeur depuis groupe 41 (= largeur visuelle si word-wrap auto)
        width = float(getattr(mtext.dxf, 'width', 0.0) or 0.0)
        # Hauteur de char : groupe 40 si présent, sinon parsée depuis le texte
        char_h_default = float(getattr(mtext.dxf, 'char_height', 0.0) or 0.0)
        raw_text = mtext.text or ''
        char_h = _parse_char_height(raw_text, char_h_default)
        if char_h <= 0:
            char_h = 0.5  # fallback désespoir

        n_lines = _count_mtext_lines(raw_text)
        # Group 44 = line spacing factor (default 1.0 → 1.667 × char_h entre lignes)
        ls_factor = float(getattr(mtext.dxf, 'line_spacing_factor', 1.0) or 1.0)
        text_h = n_lines * char_h * _FRAME_LINE_SPACING * ls_factor

        # Conversion du contenu MTEXT en texte propre (sans codes de
        # formatage), utilisable directement dans une entité TEXT.
        plain = _mtext_to_plain(raw_text)

        # Si pas de largeur dans le DXF, estimation à partir du contenu
        if width <= 0:
            lines = (plain or ' ').split('\n')
            max_chars = max((len(l) for l in lines), default=1)
            width = max_chars * char_h * 0.6
        feat_name = _first_word(plain)
        origin = feature_dict.get(feat_name)
        if origin is None and feat_name:
            origin = None  # placeholder, set below
        # On peut tomber sur un mot avec espaces protégés ; tente une variante
        if origin is None and feat_name:
            stripped = feat_name.replace(' ', '').replace(' ', '')
            for k, v in feature_dict.items():
                if k.replace(' ', '').replace(' ', '') == stripped:
                    origin = v
                    break

        # Bbox visuelle du texte, élargie du padding (lu depuis la couche)
        tx0, ty0, tx1, ty1 = _bbox_from_mtext((ix, iy), attach, width, text_h)
        x0 = tx0 - padding
        y0 = ty0 - padding
        x1 = tx1 + padding
        y1 = ty1 + padding

        to_decorate.append({
            'mtext': mtext,
            'layer': layer_name,
            'rect': (x0, y0, x1, y1),
            'text_bbox': (tx0, ty0, tx1, ty1),
            'origin': origin,
            'attribs': mtext.dxfattribs(drop={'handle', 'owner'}),
            'plain': plain,
            'char_h': char_h,
        })

    n_decorated = 0
    for d in to_decorate:
        x0, y0, x1, y1 = d['rect']
        rect_pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

        # On supprime le MTEXT pour le ré-ajouter en dernier (z-order)
        msp.delete_entity(d['mtext'])

        # Fond blanc (HATCH SOLID, TrueColor pour rester blanc quel que soit
        # le fond AutoCAD — l'ACI 7 vire au noir sur fond clair)
        try:
            hatch = msp.add_hatch(
                color=_FILL_COLOR_ACI,
                dxfattribs={
                    'layer': d['layer'],
                    'true_color': 0xFFFFFF,
                },
            )
            hatch.paths.add_polyline_path(rect_pts, is_closed=True)
            hatch.set_solid_fill(color=_FILL_COLOR_ACI)
        except Exception as exc:
            _log(f"HATCH échoué : {exc}", Qgis.Warning)

        # Contour
        try:
            msp.add_lwpolyline(
                rect_pts,
                close=True,
                dxfattribs={
                    'layer': d['layer'],
                    'color': _OUTLINE_COLOR_ACI,
                    'lineweight': _OUTLINE_LINEWEIGHT,
                },
            )
        except Exception as _err:
            errlog.ignored(_err, "dxf_postprocess.add_label_decorations:886")

        # Callout : feature origine → bord du rectangle
        origin = d['origin']
        if origin is not None:
            ox, oy = origin
            inside = (x0 <= ox <= x1) and (y0 <= oy <= y1)
            if not inside:
                ex, ey = _rect_edge_point(x0, y0, x1, y1, (ox, oy))
                try:
                    msp.add_line(
                        (ox, oy), (ex, ey),
                        dxfattribs={
                            'layer': d['layer'],
                            'color': _CALLOUT_COLOR_ACI,
                            'lineweight': _CALLOUT_LINEWEIGHT,
                        },
                    )
                except Exception as _err:
                    errlog.ignored(_err, "dxf_postprocess.add_label_decorations:905")

        # Remplacement du MTEXT par N entités TEXT indépendantes (1 par
        # ligne). Chaque TEXT est positionnée à la coordonnée Y exacte
        # qu'on choisit (espacement = _FRAME_LINE_SPACING × char_h),
        # alignée à gauche sur le bord intérieur gauche du cadre.
        # Pas de dépendance aux règles de spacing MTEXT d'AutoCAD.
        char_h = d['char_h']
        plain_lines = (d['plain'] or '').split('\n') or [' ']
        n_lines_actual = len(plain_lines)

        # Bord intérieur gauche du cadre = bord gauche du texte original
        tx0, ty0, tx1, ty1 = d['text_bbox']
        text_x = tx0
        # Centre vertical du cadre : on répartit les lignes autour
        cy = (y0 + y1) / 2
        spacing = char_h * _FRAME_LINE_SPACING

        # Attribs : layer/color/rotation préservés du MTEXT, style forcé
        # à Arial pour un rendu propre (sinon STANDARD = txt.shx déborde).
        # height × _TEXT_HEIGHT_SCALE rétrécit la police de manière
        # uniforme pour faire tenir le texte dans le cadre QGIS.
        base_attribs = {
            'layer': d['layer'],
            'height': char_h * _TEXT_HEIGHT_SCALE,
            'width': _TEXT_WIDTH_FACTOR,
            'style': (_BET_TEXT_STYLE if _BET_TEXT_STYLE in doc.styles
                      else d['attribs'].get('style', 'STANDARD')),
        }
        for k in ('color', 'true_color', 'rotation'):
            if k in d['attribs']:
                base_attribs[k] = d['attribs'][k]

        line_added = False
        for i, line_text in enumerate(plain_lines):
            line_text = line_text.rstrip()  # ne pas strip à gauche : on garde
                                            # les espaces protégés (alignement)
            if not line_text:
                continue
            # i=0 → ligne du haut. y_i = cy + ((n-1)/2 - i) × spacing
            y_i = cy + ((n_lines_actual - 1) / 2.0 - i) * spacing
            try:
                txt = msp.add_text(line_text, dxfattribs=dict(base_attribs))
                txt.set_placement(
                    (text_x, y_i),
                    align=TextEntityAlignment.MIDDLE_LEFT,
                )
                line_added = True
            except Exception as exc:
                _log(f"Ajout TEXT « {line_text[:30]} » échoué : {exc}",
                     Qgis.Warning)

        if line_added:
            n_decorated += 1

    doc.saveas(dxf_path)
    return n_decorated
