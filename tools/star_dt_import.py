# tools/star_dt_import.py
"""Import de fichiers Star-DT au format GML (CNIG / DT-DICT) vers GeoPackage.

Format Star-DT (CNIG) — standard d'echange pour les DT/DICT.
Types d'elements geres :
  - Accessoire       : Point  — boites de jonction, chambres, etc.
  - Coffret          : Point  — coffrets en surface
  - Poteau           : Point  — supports aeriens
  - Fourreau         : Ligne  — gaines de protection (pas de fluide)
  - CableElectrique  : Ligne  — cables HTA (Haute Tension A) ou BT (Basse Tension)

Subtilities prises en compte :
  - Les cables HTA (6 dans cet exemple) et BT (19) sont separes en deux
    couches distinctes avec une symbologie adaptee (HTA = rouge epais,
    BT = orange fin).
  - Les cables avec XYschematique=true ou precisionXY=C sont affiches en
    pointilles (trace schematique, geometrie imprecise).
  - La positionVerticale (underground / suspendedOrElevated / onGroundSurface)
    est importee comme attribut.
  - Les fourreaux sont des gaines vides, affichees en gris pointille.
  - Les accessoires sont differencies par typeAccessoire (junctionBox, ras...).
"""

import os
import xml.etree.ElementTree as ET
from qgis.core import (
    QgsVectorLayer, QgsField, QgsFeature, QgsGeometry,
    QgsPointXY, QgsWkbTypes, QgsProject,
    QgsLineSymbol, QgsSymbol,
    QgsSimpleLineSymbolLayer, QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer, QgsUnitTypes,
    QgsVectorFileWriter, QgsCoordinateReferenceSystem,
    QgsMarkerLineSymbolLayer, QgsFontMarkerSymbolLayer,
    QgsSymbolLayer, QgsProperty,
    QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

NS = {
    "star-dt": "http://cnig.gouv.fr/star-dt/core",
    "gml": "http://www.opengis.net/gml/3.2",
    "xlink": "http://www.w3.org/1999/xlink",
}

# ---- Symbologie detaillee ----
# Lignes : largeur en MILLIMETRES (constante a l'ecran et a l'impression).
# Points : diametre en unites carte (metres), inchange.
# (couleur, largeur_ligne_mm, diametre_marqueur_m, style_pointille)
TYPE_STYLES = {
    "Cable_HTA":            (QColor(225, 6, 0),     0.25, 0, False),  # rouge vif
    "Cable_BT":             (QColor(140, 0, 0),     0.18, 0, False),  # rouge sombre
    "Cable_HTA_schematique":(QColor(225, 6, 0),     0.25, 0, True),
    "Cable_BT_schematique": (QColor(140, 0, 0),     0.18, 0, True),
    "Fourreau":             (QColor(147, 18, 12),   0.18, 0, True),   # #93120C, tirets
    "Accessoire":           (QColor(255, 170, 0),   0,   0.8, False), # orange, rond 0.8m
    "Coffret":              (QColor(255, 100, 0),   0,   0.6, False), # orange fonce
    "Poteau":               (QColor(180, 180, 180), 0,   0.5, False), # gris
    "PointLeveOuvrageReseau": (QColor(0, 120, 200), 0,   0.2, False), # bleu, petit
}

# ---- Marqueurs de classe de precision le long des cables ----
# En MILLIMETRES : le rythme des coupures ne depend donc pas de l'echelle.
_PRECISION_FIELD = "precisionXY"   # classe A / B / C sur les ouvrages
_LEVE_FIELD = "leve"               # mesure en metres sur les points leves
# 3 mm : au-dessus du seuil de lisibilite a l'impression (2 mm). Au 1:200 cela
# represente 0,60 m au sol, et le texte garde la meme taille physique a toutes
# les echelles. La coupure suit, sinon le libelle mordrait sur le trait.
_MARKER_TEXT_SIZE = 3.0            # hauteur du libelle "HTA-A"
_MARKER_GAP = 10.5                 # coupure du trait : doit contenir "HTA-C" (9,2 mm)
_MARKER_DASH = 10.0                # trait plein entre deux coupures
_LABEL_TEXT_SIZE = 3.0             # etiquettes ponctuelles (mm, comme le reste)
_LABEL_DIST = 1.0                  # ecart etiquette / symbole (mm)


def _text(el, tag):
    child = el.find(f"star-dt:{tag}", NS)
    return child.text.strip() if child is not None and child.text else ""


def _dimension(geom_el, values_count):
    """Nombre de coordonnees par sommet.

    L'attribut gml:srsDimension fait foi. Il ne faut surtout pas le deviner a
    partir du nombre de valeurs : une ligne 2D de 3 sommets a 6 valeurs, ce qui
    est aussi divisible par 3, et la lire en 3D melange les X et les Y.
    """
    raw = geom_el.get("srsDimension") or ""
    try:
        dim = int(raw)
    except ValueError:
        dim = 0
    if dim not in (2, 3):
        # Sans indication fiable : 3D seulement si 2D est impossible.
        dim = 2 if values_count % 2 == 0 else 3
    if values_count % dim:
        dim = 2
    return dim


def _coords(text, dim):
    """Convertit une liste de valeurs GML en QgsPointXY (X et Y uniquement)."""
    parts = text.split()
    pts = []
    for i in range(0, len(parts) - dim + 1, dim):
        try:
            pts.append(QgsPointXY(float(parts[i]), float(parts[i + 1])))
        except ValueError:
            continue
    return pts


def _parse_point(geom_el):
    pos = geom_el.find("gml:pos", NS)
    if pos is None or not pos.text:
        return None
    parts = pos.text.split()
    if len(parts) < 2:
        return None
    pts = _coords(pos.text, _dimension(geom_el, len(parts)))
    return QgsGeometry.fromPointXY(pts[0]) if pts else None


def _parse_linestring(geom_el):
    pos_list = geom_el.find("gml:posList", NS)
    if pos_list is None or not pos_list.text:
        return None
    parts = pos_list.text.split()
    if len(parts) < 4:
        return None
    pts = _coords(pos_list.text, _dimension(geom_el, len(parts)))
    return QgsGeometry.fromPolylineXY(pts) if len(pts) >= 2 else None


def _parse_polygon(geom_el):
    """Polygone GML : on retient l'anneau exterieur."""
    ring = geom_el.find("gml:exterior/gml:LinearRing/gml:posList", NS)
    if ring is None or not ring.text:
        return None
    parts = ring.text.split()
    if len(parts) < 6:
        return None
    pts = _coords(ring.text, _dimension(geom_el, len(parts)))
    return QgsGeometry.fromPolygonXY([pts]) if len(pts) >= 3 else None


_GEOM_PARSERS = {
    "Point": _parse_point,
    "LineString": _parse_linestring,
    "Curve": _parse_linestring,
    "Polygon": _parse_polygon,
    "Surface": _parse_polygon,
}


def _element_geometry(el):
    """Retourne (QgsGeometry, srsName) pour un objet StaR-DT / StaR-Elec."""
    geom_el = el.find("star-dt:geometrie", NS)
    if geom_el is None:
        return None, ""
    for child in geom_el:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        parser = _GEOM_PARSERS.get(tag)
        if parser is None:
            continue
        geom = parser(child)
        if geom is not None and not geom.isEmpty():
            return geom, (child.get("srsName") or "")
    return None, ""


# ---- Champs communs a tous les types ----
_COMMON_FIELDS = [
    ("identifiant",       QVariant.String),
    ("reseau",            QVariant.String),
    ("statut",            QVariant.String),
    ("positionVerticale", QVariant.String),
    ("visibleSurface",    QVariant.String),
    ("sensible",          QVariant.String),
    ("miseAJour",         QVariant.String),
    ("caracteristiques",  QVariant.String),
]

# Ordre d'affichage prioritaire. Les classes StaR-Elec absentes de cette liste
# (Support, Regard, Jonction, PosteElectrique, Luminaire...) sont decouvertes
# dans le fichier et ajoutees ensuite, par ordre alphabetique.
_OUTPUT_TYPE_ORDER = [
    "Cable_HTA", "Cable_BT", "Fourreau",
    "Accessoire", "Coffret", "Poteau",
    "PointLeveOuvrageReseau",
]


def _as_path_list(gml_paths):
    """Normalise l'argument en liste de chemins (accepte un str ou une liste)."""
    if not gml_paths:
        return []
    if isinstance(gml_paths, str):
        return [gml_paths]
    return list(gml_paths)


def _cable_output_type(el):
    """Determine le type de sortie pour un CableElectrique."""
    tension = _text(el, "classeTension")
    return "Cable_HTA" if tension == "HTA" else "Cable_BT"


def _output_type(el):
    """Nom de couche de sortie pour un objet, ou None s'il n'est pas cartographiable.

    Tout objet portant une <geometrie> est retenu : le fichier peut contenir
    n'importe quelle classe StaR-DT ou StaR-Elec. Seuls les CableElectrique
    sont scindes (HTA / BT).
    """
    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
    if el.find("star-dt:geometrie", NS) is None:
        return None
    if tag == "CableElectrique":
        return _cable_output_type(el)
    return tag


def _iter_objects(root):
    """Itere sur les objets du fichier (premier enfant de chaque <member>)."""
    for member in root.findall("star-dt:member", NS):
        for child in member:
            yield child
            break


def sort_output_types(names):
    """Types connus d'abord (ordre metier), puis les autres par ordre alphabetique."""
    def key(name):
        if name in _OUTPUT_TYPE_ORDER:
            return (0, _OUTPUT_TYPE_ORDER.index(name), "")
        return (1, 0, name.lower())
    return sorted(names, key=key)


def scan_star_dt(gml_paths):
    """Analyse un ou plusieurs fichiers GML et retourne les counts par type.

    Pour les CableElectrique, decompose en HTA et BT.
    """
    counts = {}
    for gml_path in _as_path_list(gml_paths):
        try:
            root = ET.parse(gml_path).getroot()
        except Exception:
            continue
        for el in _iter_objects(root):
            out_type = _output_type(el)
            if out_type:
                counts[out_type] = counts.get(out_type, 0) + 1
    return counts


def _attribute_value(el, tag_name):
    """Valeur d'un attribut : texte, ou dernier segment du xlink:href.

    Les attributs multivalues sont concatenes.
    """
    values = []
    for child in el.findall(f"star-dt:{tag_name}", NS):
        text = child.text.strip() if child.text else ""
        if not text:
            href = child.get("{http://www.w3.org/1999/xlink}href", "")
            text = href.rsplit("/", 1)[-1] if href else ""
        if text:
            values.append(text)
    return " ; ".join(values)


def _discover_fields(elements):
    """Liste ordonnee des attributs presents sur un ensemble d'objets.

    Les champs communs StaR-DT viennent en tete, les attributs propres a la
    classe (StaR-Elec ou specialisation Enedis) suivent dans l'ordre rencontre.
    """
    seen = []
    for el in elements:
        for child in el:
            name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if name == "geometrie" or name in seen:
                continue
            seen.append(name)

    common = [name for name, _ in _COMMON_FIELDS if name in seen]
    others = [name for name in seen if name not in common]
    return common + others


def _extract_file_identifier(gml_path):
    """Extrait le premier identifiant du fichier pour nommer le groupe."""
    try:
        root = ET.parse(gml_path).getroot()
    except Exception:
        return ""
    for el in _iter_objects(root):
        ident = _text(el, "identifiant")
        if ident:
            return ident
    return ""


def import_star_dt(gml_paths, gpkg_path, selected_types=None,
                   parent_group_name=None):
    """Importe un ou plusieurs fichiers Star-DT GML dans un GeoPackage
    et charge les couches dans QGIS.

    Args:
        gml_paths: chemin d'un fichier .gml, ou liste de chemins
        gpkg_path: chemin du GeoPackage de sortie
        selected_types: liste de noms de types de sortie (Cable_HTA, Cable_BT,
                        Fourreau, Accessoire, Coffret, Poteau), ou None pour tout
        parent_group_name: nom du groupe dans la legende

    Returns:
        dict {type_name: QgsVectorLayer} des couches creees.
    """
    paths = _as_path_list(gml_paths)
    if not paths:
        return {}

    if selected_types is None:
        selected_types = list(scan_star_dt(paths).keys())

    if parent_group_name is None:
        if len(paths) == 1:
            file_id = _extract_file_identifier(paths[0])
            parent_group_name = f"Star-DT - {file_id}" if file_id else "Star-DT"
        else:
            parent_group_name = f"Star-DT - {len(paths)} fichiers"

    # 1) Regrouper les elements XML par type de sortie (tous fichiers confondus)
    #    Les arbres sont conserves pour que les elements restent valides.
    members_by_type = {t: [] for t in selected_types}
    trees = []
    srs_name = ""
    for gml_path in paths:
        tree = ET.parse(gml_path)
        trees.append(tree)
        for el in _iter_objects(tree.getroot()):
            key = _output_type(el)
            if key in members_by_type:
                members_by_type[key].append(el)
                if not srs_name:
                    _, srs_name = _element_geometry(el)

    # 2) Creer les couches
    project = QgsProject.instance()
    # Le systeme de coordonnees est celui declare dans le GML (srsName), pas
    # celui du projet : sinon les objets se retrouvent au mauvais endroit.
    crs_str = ""
    if srs_name:
        crs = QgsCoordinateReferenceSystem(srs_name)
        if crs.isValid():
            crs_str = crs.authid() or srs_name
    if not crs_str:
        crs = project.crs()
        crs_str = crs.authid() if crs.isValid() else "EPSG:2154"
    ctx = project.transformContext()
    created = {}

    # Supprimer le GPKG existant pour eviter tout conflit.
    # Les couches du projet qui pointent dessus doivent d'abord etre retirees :
    # ecraser un GeoPackage encore ouvert par QGIS fait planter l'application.
    gpkg_uri_base = gpkg_path.replace("\\", "/")
    _release_gpkg(project, gpkg_path)
    if os.path.exists(gpkg_path):
        try:
            os.remove(gpkg_path)
        except OSError as exc:
            raise RuntimeError(
                f"Le GeoPackage de sortie est verrouille et ne peut pas etre "
                f"remplace :\n{gpkg_path}\n\nFermez-le (QGIS, Explorateur, autre "
                f"logiciel) ou choisissez un autre nom de sortie.\n({exc})")

    # Phase 1 : ecrire toutes les couches dans le GPKG.
    # Aucune couche n'est chargee ici : garder le GeoPackage ouvert pendant
    # qu'on y ajoute des tables laisse GDAL servir un catalogue de couches
    # perime, et les couches suivantes semblent introuvables.
    written = []  # [(out_type, is_cable, feat_count)]

    first = True
    for out_type in sort_output_types(selected_types):
        elements = members_by_type.get(out_type, [])
        if not elements:
            continue

        # Geometries d'abord : le type de couche est deduit des donnees
        # (le meme fichier peut porter des points, lignes ou surfaces).
        parsed = []
        geom_type = None
        for el in elements:
            geom, _ = _element_geometry(el)
            if geom is None:
                continue
            if geom_type is None:
                geom_type = geom.type()
            elif geom.type() != geom_type:
                continue
            parsed.append((el, geom))

        if not parsed or geom_type is None:
            continue

        wkb_name = {
            QgsWkbTypes.PointGeometry:   "Point",
            QgsWkbTypes.LineGeometry:    "LineString",
            QgsWkbTypes.PolygonGeometry: "Polygon",
        }.get(geom_type)
        if wkb_name is None:
            continue

        mem_layer = QgsVectorLayer(f"{wkb_name}?crs={crs_str}", out_type, "memory")
        dp = mem_layer.dataProvider()

        field_names = _discover_fields(elements)
        dp.addAttributes([QgsField(name, QVariant.String) for name in field_names])
        mem_layer.updateFields()

        mem_layer.startEditing()
        is_cable = out_type.startswith("Cable_")
        feat_count = 0
        for el, gml_geom in parsed:
            feat = QgsFeature(mem_layer.fields())
            feat.setGeometry(gml_geom)
            feat.setAttributes([_attribute_value(el, name) for name in field_names])
            mem_layer.addFeature(feat)
            feat_count += 1

        mem_layer.commitChanges()

        if feat_count == 0:
            continue

        # Ecrire dans le GeoPackage
        opts = QgsVectorFileWriter.SaveVectorOptions()
        opts.driverName = "GPKG"
        opts.layerName = out_type
        opts.actionOnExistingFile = (
            QgsVectorFileWriter.CreateOrOverwriteFile if first
            else QgsVectorFileWriter.CreateOrOverwriteLayer
        )
        first = False

        err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem_layer, gpkg_path, ctx, opts)

        if err != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                f"Erreur ecriture couche {out_type} (code={err}) : {msg}")

        # Liberer la couche memoire
        del mem_layer

        written.append((out_type, is_cable, feat_count))

    # Phase 2 : charger les couches ecrites depuis le GeoPackage
    for out_type, is_cable, feat_count in written:
        layer_uri = f"{gpkg_uri_base}|layername={out_type}"
        layer = QgsVectorLayer(layer_uri, out_type, "ogr")
        if not layer.isValid():
            raise RuntimeError(
                f"Impossible de charger {out_type} ({feat_count} entites ecrites)"
                f" — URI: {layer_uri}")

        # Symbologie
        _apply_style(layer, out_type, is_cable)
        _apply_labels(layer, out_type)

        project.addMapLayer(layer, False)
        _get_or_create_group(project, parent_group_name).addLayer(layer)
        created[out_type] = layer

    # Zoom sur l'etendue des couches importees
    if created:
        extent = None
        for layer in created.values():
            if extent is None:
                extent = layer.extent()
            else:
                extent.combineExtentWith(layer.extent())
        if extent is not None:
            from qgis.utils import iface
            canvas = iface.mapCanvas()
            canvas.setExtent(extent)
            canvas.refresh()

    return created


def _same_file(path_a, path_b):
    try:
        return (os.path.normcase(os.path.abspath(path_a))
                == os.path.normcase(os.path.abspath(path_b)))
    except Exception:
        return False


def _release_gpkg(project, gpkg_path):
    """Retire du projet les couches qui pointent sur ce GeoPackage.

    Indispensable avant de le supprimer/reecrire : tant qu'une couche l'utilise,
    le fichier reste ouvert par GDAL et l'ecraser fait planter QGIS.
    """
    to_remove = []
    for layer_id, layer in project.mapLayers().items():
        try:
            source = layer.source().split("|")[0]
        except Exception:
            continue
        if source and _same_file(source, gpkg_path):
            to_remove.append(layer_id)

    if not to_remove:
        return

    project.removeMapLayers(to_remove)

    # Supprimer les groupes devenus vides
    root = project.layerTreeRoot()
    for child in list(root.children()):
        if hasattr(child, "children") and not child.children():
            name = child.name() if hasattr(child, "name") else ""
            if name.startswith("Star-DT"):
                root.removeChildNode(child)

    try:
        from qgis.utils import iface
        iface.mapCanvas().refresh()
    except Exception:
        pass


def _apply_style(layer, out_type, is_cable=False):
    """Applique une symbologie detaillee selon le type.

    Cables HTA : trait rouge vif, coupe par les marqueurs 'HTA-<classe>'
    Cables BT  : trait rouge sombre, coupe par les marqueurs 'BT-<classe>'
    Fourreaux  : trait #93120C pointille
    Lignes     : largeurs en millimetres. Points : diametres en unites carte.
    """
    style = TYPE_STYLES.get(out_type)
    if style is None:
        return

    color, width, marker_size, dashed = style

    if is_cable:
        # Symbole cable : trait coupe + marqueurs "HTA-A" / "BT-C"
        abbr = "HTA" if out_type == "Cable_HTA" else "BT"
        has_precision = layer.fields().indexOf(_PRECISION_FIELD) >= 0
        layer.setRenderer(QgsSingleSymbolRenderer(
            _make_labeled_line_symbol(color, width, abbr, has_precision)))

    elif layer.geometryType() == QgsWkbTypes.LineGeometry:
        # Fourreau : ligne #93120C pointillee
        sl = QgsSimpleLineSymbolLayer(color, width)
        sl.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        if dashed:
            sl.setCustomDashVector([2.0, 1.2])
            sl.setCustomDashPatternUnit(QgsUnitTypes.RenderMillimeters)
            sl.setUseCustomDashPattern(True)
        layer.setRenderer(QgsSingleSymbolRenderer(QgsLineSymbol([sl])))

    else:
        # Points : rond
        symbol = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
        ml = QgsSimpleMarkerSymbolLayer(
            QgsSimpleMarkerSymbolLayer.Circle, marker_size)
        ml.setColor(color)
        ml.setStrokeColor(color.darker(130))
        ml.setSizeUnit(QgsUnitTypes.RenderMapUnits)
        symbol.changeSymbolLayer(0, ml)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    layer.triggerRepaint()


def _make_labeled_line_symbol(color, width, abbr, has_precision=True):
    """Trait coupe a intervalle regulier, chaque coupure portant 'HTA-A' / 'BT-C'.

    Rendu vise :  ----HTA-A----HTA-A----

    La coupure est obtenue en synchronisant le motif de tirets et l'intervalle
    des marqueurs : meme periode, et decalage du marqueur au milieu du blanc.
    Les deux se mesurent depuis le debut de la ligne, donc chaque libelle tombe
    exactement dans une coupure. C'est deterministe, et contrairement aux
    symboles de masque QGIS (dont l'API a change entre les versions et qui ne
    masquent pas la couche qui les porte), ca ne depend d'aucune version.

    Tout est en millimetres : les deux motifs doivent partager la meme unite
    pour rester synchronises, quelle que soit l'echelle d'affichage.
    """
    period = _MARKER_DASH + _MARKER_GAP

    # ---- Couche 1 : trait fin, interrompu a chaque marqueur ----
    line = QgsSimpleLineSymbolLayer(color, width)
    line.setWidthUnit(QgsUnitTypes.RenderMillimeters)
    line.setCustomDashVector([_MARKER_DASH, _MARKER_GAP])
    line.setCustomDashPatternUnit(QgsUnitTypes.RenderMillimeters)
    line.setUseCustomDashPattern(True)

    # ---- Couche 2 : libelle repete, centre dans la coupure ----
    marker_line = QgsMarkerLineSymbolLayer()
    marker_line.setInterval(period)
    marker_line.setIntervalUnit(QgsUnitTypes.RenderMillimeters)
    marker_line.setPlacement(QgsMarkerLineSymbolLayer.Interval)
    marker_line.setOffsetAlongLine(_MARKER_DASH + _MARKER_GAP / 2.0)
    marker_line.setOffsetAlongLineUnit(QgsUnitTypes.RenderMillimeters)

    # Sous-symbole : marqueur police
    sub = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
    font_marker = QgsFontMarkerSymbolLayer()
    font_marker.setFontFamily("Arial")
    font_marker.setCharacter(abbr)
    font_marker.setColor(color)
    font_marker.setSize(_MARKER_TEXT_SIZE)
    font_marker.setSizeUnit(QgsUnitTypes.RenderMillimeters)

    if has_precision:
        # La classe varie d'une entite a l'autre : le texte est pilote par le champ.
        expr = (f"'{abbr}-' || coalesce(nullif(\"{_PRECISION_FIELD}\", ''), '?')")
        try:
            font_marker.setDataDefinedProperty(
                QgsSymbolLayer.PropertyCharacter, QgsProperty.fromExpression(expr))
        except Exception:
            pass  # a defaut, le libelle reste la seule tension

    sub.changeSymbolLayer(0, font_marker)
    marker_line.setSubSymbol(sub)

    # Le symbole est construit a partir de la liste : un QgsLineSymbol() vide
    # contient deja une ligne pleine par defaut, qui rebouchait les coupures et
    # barrait le libelle.
    return QgsLineSymbol([line, marker_line])


def _apply_labels(layer, out_type):
    """Etiquette les couches ponctuelles.

    - PointLeveOuvrageReseau : la mesure <leve> en metres (ex. 254.64).
      Son precisionXY est un entier en centimetres (10 = 10 cm), pas une
      classe A/B/C : l'etiqueter n'aurait aucun sens.
    - Autres points (Poteau...) : la classe de precision A / B / C.
    """
    fields = layer.fields()
    if out_type == "PointLeveOuvrageReseau":
        if fields.indexOf(_LEVE_FIELD) < 0:
            return
        expression = f"format_number(to_real(\"{_LEVE_FIELD}\"), 2)"
    elif fields.indexOf(_PRECISION_FIELD) >= 0:
        expression = f"\"{_PRECISION_FIELD}\""
    else:
        return

    try:
        settings = QgsPalLayerSettings()
        settings.fieldName = expression
        settings.isExpression = True
        settings.placement = QgsPalLayerSettings.AroundPoint
        settings.dist = _LABEL_DIST
        settings.distUnits = QgsUnitTypes.RenderMillimeters

        text_format = QgsTextFormat()
        text_format.setSize(_LABEL_TEXT_SIZE)
        text_format.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        text_format.setColor(QColor(60, 60, 60))
        settings.setFormat(text_format)

        layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        layer.setLabelsEnabled(True)
    except Exception:
        pass  # l'etiquetage est un confort : ne jamais faire echouer l'import


def _get_or_create_group(project, group_name):
    """Retourne le groupe (le cree en tete de legende si absent)."""
    root = project.layerTreeRoot()
    group = root.findGroup(group_name)
    if group is None:
        group = root.insertGroup(0, group_name)
    return group
