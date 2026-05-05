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
)
from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor

NS = {
    "star-dt": "http://cnig.gouv.fr/star-dt/core",
    "gml": "http://www.opengis.net/gml/3.2",
    "xlink": "http://www.w3.org/1999/xlink",
}

# ---- Types natifs Star-DT et leur geometrie ----
ELEMENT_TYPES = {
    "Accessoire":       QgsWkbTypes.PointGeometry,
    "Coffret":          QgsWkbTypes.PointGeometry,
    "Poteau":           QgsWkbTypes.PointGeometry,
    "Fourreau":         QgsWkbTypes.LineGeometry,
    "CableElectrique":  QgsWkbTypes.LineGeometry,
}

# ---- Symbologie detaillee ----
# (couleur, largeur_ligne_m, diametre_marqueur_m, style_pointille)
TYPE_STYLES = {
    "Cable_HTA":            (QColor(200, 0, 0),     0.4, 0, False),  # rouge, trait fin
    "Cable_BT":             (QColor(255, 140, 0),   0.25, 0, False),  # orange, tres fin
    "Cable_HTA_schematique":(QColor(200, 0, 0),     0.4, 0, True),
    "Cable_BT_schematique": (QColor(255, 140, 0),   0.25, 0, True),
    "Fourreau":             (QColor(160, 160, 160), 0.3, 0, True),   # gris, tirets
    "Accessoire":           (QColor(255, 170, 0),   0,   0.8, False), # orange, rond 0.8m
    "Coffret":              (QColor(255, 100, 0),   0,   0.6, False), # orange fonce
    "Poteau":               (QColor(180, 180, 180), 0,   0.5, False), # gris
}


def _text(el, tag):
    child = el.find(f"star-dt:{tag}", NS)
    return child.text.strip() if child is not None and child.text else ""


def _href(el, tag):
    child = el.find(f"star-dt:{tag}", NS)
    if child is None:
        return ""
    href = child.get("{http://www.w3.org/1999/xlink}href", "")
    return href.rsplit("/", 1)[-1] if href else ""


def _parse_point(geom_el):
    pos = geom_el.find("gml:pos", NS)
    if pos is None or not pos.text:
        return None
    parts = pos.text.strip().split()
    if len(parts) < 2:
        return None
    return QgsGeometry.fromPointXY(QgsPointXY(float(parts[0]), float(parts[1])))


def _parse_linestring(geom_el):
    pos_list = geom_el.find("gml:posList", NS)
    if pos_list is None or not pos_list.text:
        return None
    parts = pos_list.text.strip().split()
    n = len(parts)
    if n < 4:
        return None
    stride = 3 if n % 3 == 0 else 2
    pts = []
    for i in range(0, n - stride + 1, stride):
        pts.append(QgsPointXY(float(parts[i]), float(parts[i + 1])))
    return QgsGeometry.fromPolylineXY(pts)


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

_EXTRA_FIELDS = {
    "Accessoire":       [("typeAccessoire", QVariant.String)],
    "Poteau":           [],
    "Coffret":          [],
    "Fourreau":         [
        ("code", QVariant.String),
        ("typeElement", QVariant.String),
        ("exemptionIC", QVariant.String),
    ],
    "CableElectrique":  [
        ("typeElement", QVariant.String),
        ("hierarchie", QVariant.String),
        ("exemptionIC", QVariant.String),
        ("classeTension", QVariant.String),
        ("fonctionCable", QVariant.String),
        ("regime", QVariant.String),
        ("precisionXY", QVariant.String),
        ("XYschematique", QVariant.String),
    ],
}


def scan_star_dt(gml_path):
    """Analyse un fichier Star-DT GML et retourne les counts par type.

    Pour les CableElectrique, decompose en HTA et BT.
    """
    counts = {}
    try:
        tree = ET.parse(gml_path)
        root = tree.getroot()
        for member in root.findall("star-dt:member", NS):
            for child in member:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "CableElectrique":
                    tension = _text(child, "classeTension")
                    key = "Cable_HTA" if tension == "HTA" else "Cable_BT"
                    counts[key] = counts.get(key, 0) + 1
                elif tag in ELEMENT_TYPES:
                    counts[tag] = counts.get(tag, 0) + 1
                break
    except Exception:
        pass
    return counts


# ---- Association entre type de sortie et tag XML source ----
# Pour les cables, le tag source est CableElectrique, mais on filtre par classeTension.
_OUTPUT_TYPE_MAP = {
    "Cable_HTA":            "CableElectrique",
    "Cable_BT":             "CableElectrique",
    "Fourreau":             "Fourreau",
    "Accessoire":           "Accessoire",
    "Coffret":              "Coffret",
    "Poteau":               "Poteau",
}

# Ordre d'affichage dans le dialogue
_OUTPUT_TYPE_ORDER = [
    "Cable_HTA", "Cable_BT", "Fourreau",
    "Accessoire", "Coffret", "Poteau",
]


def _cable_output_type(el):
    """Determine le type de sortie pour un CableElectrique."""
    tension = _text(el, "classeTension")
    return "Cable_HTA" if tension == "HTA" else "Cable_BT"


def _extract_file_identifier(gml_path):
    """Extrait le premier identifiant du fichier Star-DT pour nommer le groupe."""
    try:
        tree = ET.parse(gml_path)
        root = tree.getroot()
        for member in root.findall("star-dt:member", NS):
            for child in member:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag in ELEMENT_TYPES:
                    ident = _text(child, "identifiant")
                    if ident:
                        return ident
                break
    except Exception:
        pass
    return ""


def import_star_dt(gml_path, gpkg_path, selected_types=None,
                   parent_group_name=None):
    """Importe un fichier Star-DT GML dans un GeoPackage et les charge dans QGIS.

    Args:
        gml_path: chemin du fichier .gml
        gpkg_path: chemin du GeoPackage de sortie
        selected_types: liste de noms de types de sortie (Cable_HTA, Cable_BT,
                        Fourreau, Accessoire, Coffret, Poteau), ou None pour tout
        parent_group_name: nom du groupe dans la legende

    Returns:
        dict {type_name: QgsVectorLayer} des couches creees.
    """
    if selected_types is None:
        selected_types = _OUTPUT_TYPE_ORDER

    if parent_group_name is None:
        file_id = _extract_file_identifier(gml_path)
        parent_group_name = f"Star-DT - {file_id}" if file_id else "Star-DT"

    tree = ET.parse(gml_path)
    root = tree.getroot()

    # 1) Regrouper les elements XML par type de sortie
    members_by_type = {t: [] for t in selected_types}
    for member in root.findall("star-dt:member", NS):
        for child in member:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "CableElectrique":
                key = _cable_output_type(child)
            elif tag in _OUTPUT_TYPE_MAP:
                key = tag
            else:
                break
            if key in members_by_type:
                members_by_type[key].append(child)
            break

    # 2) Creer les couches
    project = QgsProject.instance()
    crs = project.crs()
    crs_str = crs.authid() if crs.isValid() else "EPSG:2154"
    ctx = project.transformContext()
    created = {}

    # Supprimer le GPKG existant pour eviter tout conflit
    gpkg_uri_base = gpkg_path.replace("\\", "/")
    if os.path.exists(gpkg_path):
        try:
            os.remove(gpkg_path)
        except OSError:
            pass

    first = True
    for out_type in _OUTPUT_TYPE_ORDER:
        if out_type not in selected_types:
            continue
        elements = members_by_type.get(out_type, [])
        if not elements:
            continue

        xml_tag = _OUTPUT_TYPE_MAP.get(out_type)
        geom_type = ELEMENT_TYPES.get(xml_tag)
        if geom_type is None:
            continue

        is_line = (geom_type == QgsWkbTypes.LineGeometry)
        uri = f"{'LineString' if is_line else 'Point'}?crs={crs_str}"
        mem_layer = QgsVectorLayer(uri, out_type, "memory")
        dp = mem_layer.dataProvider()

        all_fields = _COMMON_FIELDS + _EXTRA_FIELDS.get(xml_tag, [])
        fields_list = [QgsField(name, ftype) for name, ftype in all_fields]
        dp.addAttributes(fields_list)
        mem_layer.updateFields()

        mem_layer.startEditing()
        is_cable = (xml_tag == "CableElectrique")
        feat_count = 0
        for el in elements:
            geom_el = el.find("star-dt:geometrie", NS)
            if geom_el is None:
                continue

            gml_geom = None
            for child in geom_el:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "Point":
                    gml_geom = _parse_point(child)
                elif tag == "LineString":
                    gml_geom = _parse_linestring(child)
                if gml_geom is not None:
                    break

            if gml_geom is None or gml_geom.isEmpty():
                continue

            feat = QgsFeature(mem_layer.fields())
            feat.setGeometry(gml_geom)

            attrs = [
                _text(el, "identifiant"),
                _href(el, "reseau"),
                _href(el, "statut"),
                _text(el, "positionVerticale"),
                _text(el, "visibleSurface"),
                _text(el, "sensible"),
                _text(el, "miseAJour"),
                _text(el, "caracteristiques"),
            ]

            for field_name, _ in _EXTRA_FIELDS.get(xml_tag, []):
                if field_name in ("typeAccessoire", "typeElement", "fonctionCable"):
                    attrs.append(_href(el, field_name))
                else:
                    attrs.append(_text(el, field_name))

            feat.setAttributes(attrs)
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
            else QgsVectorFileWriter.AppendToDatasetNoConfirm
        )
        first = False

        err, msg, _, _ = QgsVectorFileWriter.writeAsVectorFormatV3(
            mem_layer, gpkg_path, ctx, opts)

        if err != QgsVectorFileWriter.NoError:
            raise RuntimeError(
                f"Erreur ecriture couche {out_type} (code={err}) : {msg}")

        # Liberer la couche memoire avant de charger le GPKG
        del mem_layer

        # Charger depuis le GPKG
        layer_uri = f"{gpkg_uri_base}|layername={out_type}"
        layer = QgsVectorLayer(layer_uri, out_type, "ogr")
        if not layer.isValid():
            raise RuntimeError(
                f"Impossible de charger {out_type} ({feat_count} entites ecrites)"
                f" — URI: {layer_uri}")

        # Symbologie
        _apply_style(layer, out_type, is_cable)

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


def _apply_style(layer, out_type, is_cable=False):
    """Applique une symbologie detaillee selon le type.

    Cables HTA : trait rouge + marqueurs 'HTA' repetes tous les 15 m
    Cables BT  : trait orange + marqueurs 'BT' repetes tous les 15 m
    Fourreaux  : trait gris pointille
    Points     : ronds colores, taille en unites carte.
    """
    style = TYPE_STYLES.get(out_type)
    if style is None:
        return

    color, width, marker_size, dashed = style

    if is_cable:
        # Symbole cable : ligne + marqueurs textuels
        abbr = "HTA" if out_type == "Cable_HTA" else "BT"
        layer.setRenderer(
            QgsSingleSymbolRenderer(_make_labeled_line_symbol(color, width, abbr)))

    elif layer.geometryType() == QgsWkbTypes.LineGeometry:
        # Fourreau : ligne grise pointillee
        symbol = QgsLineSymbol()
        sl = QgsSimpleLineSymbolLayer(color, width)
        sl.setWidthUnit(QgsUnitTypes.RenderMapUnits)
        if dashed:
            sl.setCustomDashVector([3, 2])
            sl.setUseCustomDashPattern(True)
        symbol.appendSymbolLayer(sl)
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))

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


def _make_labeled_line_symbol(color, width, abbr):
    """Cree un symbole de ligne compose :
       - trait fin de couleur
       - marqueur texte repete (ex: 'HTA', 'BT') tous les 15m.
    """
    symbol = QgsLineSymbol()

    # ---- Couche 1 : trait fin ----
    line = QgsSimpleLineSymbolLayer(color, width)
    line.setWidthUnit(QgsUnitTypes.RenderMapUnits)
    symbol.appendSymbolLayer(line)

    # ---- Couche 2 : marqueur texte repete ----
    marker_line = QgsMarkerLineSymbolLayer()
    marker_line.setInterval(15.0)
    marker_line.setIntervalUnit(QgsUnitTypes.RenderMapUnits)
    marker_line.setPlacement(QgsMarkerLineSymbolLayer.Interval)

    # Sous-symbole : marqueur police
    sub = QgsSymbol.defaultSymbol(QgsWkbTypes.PointGeometry)
    font_marker = QgsFontMarkerSymbolLayer()
    font_marker.setFontFamily("Arial")
    font_marker.setCharacter(abbr)
    font_marker.setColor(color)
    font_marker.setSize(2.2)
    font_marker.setSizeUnit(QgsUnitTypes.RenderMapUnits)
    sub.changeSymbolLayer(0, font_marker)
    marker_line.setSubSymbol(sub)

    symbol.appendSymbolLayer(marker_line)
    return symbol


def _get_or_create_group(project, group_name):
    """Retourne le groupe (le cree en tete de legende si absent)."""
    root = project.layerTreeRoot()
    group = root.findGroup(group_name)
    if group is None:
        group = root.insertGroup(0, group_name)
    return group
