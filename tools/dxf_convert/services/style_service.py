# -*- coding: utf-8 -*-
"""
DXF-faithful styling for QGIS layers.
- Full AutoCAD Color Index (ACI) palette
- DXF linetype → QGIS dash pattern
- DXF layer table reader (ASCII DXF + ezdxf fallback)
- apply_dxf_style(): sets color, linetype, lineweight on a QgsVectorLayer
"""
from __future__ import annotations
import colorsys
from typing import Dict, Optional, Tuple
from ... import errlog
from qgis.core import Qgis


# ---------------------------------------------------------------------------
# ACI palette — full 256 entries
# ---------------------------------------------------------------------------

def _hsv_to_rgb(h, s, v) -> Tuple[int, int, int]:
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s, v)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def _build_aci_palette() -> Dict[int, Tuple[int, int, int]]:
    p: Dict[int, Tuple[int, int, int]] = {
        0:   (0,   0,   0),    # BYBLOCK → black
        1:   (255, 0,   0),    # Red
        2:   (255, 255, 0),    # Yellow
        3:   (0,   255, 0),    # Green
        4:   (0,   255, 255),  # Cyan
        5:   (0,   0,   255),  # Blue
        6:   (255, 0,   255),  # Magenta
        7:   (0,   0,   0),    # White/Black → black (light bg)
        8:   (65,  65,  65),
        9:   (128, 128, 128),
        256: (0,   0,   0),    # BYLAYER → black fallback
    }

    # Colors 10–249: 24 hue groups × 10 shades
    # Hues evenly spaced from 0° to 345° in 15° steps
    # AutoCAD shade pattern within each group (S, V):
    shade_sv = [
        (1.00, 1.00),  # 0 – full colour
        (0.50, 1.00),  # 1 – tint 50%
        (1.00, 0.75),  # 2 – shade 75%
        (0.50, 0.75),  # 3
        (1.00, 0.50),  # 4 – shade 50%
        (0.50, 0.50),  # 5
        (1.00, 0.38),  # 6 – shade 38%
        (0.50, 0.38),  # 7
        (1.00, 0.25),  # 8 – shade 25%
        (0.50, 0.25),  # 9
    ]
    for group in range(24):
        hue = group * 15  # 0, 15, 30 … 345
        for shade, (s, v) in enumerate(shade_sv):
            aci = 10 + group * 10 + shade
            p[aci] = _hsv_to_rgb(hue, s, v)

    # Gray scale 250–255
    for i, val in enumerate([38, 77, 115, 153, 191, 229]):
        p[250 + i] = (val, val, val)

    return p


ACI_PALETTE: Dict[int, Tuple[int, int, int]] = _build_aci_palette()


def aci_to_rgb(aci: int, layer_color: int = 7) -> Tuple[int, int, int]:
    """Resolve ACI index to (R, G, B).
    aci=-1 or 256 means BYLAYER → use layer_color instead."""
    if aci in (-1, 256):
        aci = abs(layer_color)  # layer color can be negative (frozen layer)
    if aci == 0:
        return (0, 0, 0)
    return ACI_PALETTE.get(abs(aci), (0, 0, 0))


# ---------------------------------------------------------------------------
# DXF linetype → QGIS custom dash vector (in mm)
# ---------------------------------------------------------------------------

# Format: list of [mark, space, mark, space …] lengths in mm
_LINETYPE_PATTERNS: Dict[str, Optional[list]] = {
    "CONTINUOUS":   None,           # solid
    "BYLAYER":      None,
    "BYBLOCK":      None,
    "DASHED":       [6.0, 3.0],
    "DASHED2":      [3.0, 1.5],
    "DASHEDX2":     [12.0, 6.0],
    "HIDDEN":       [3.0, 1.5],
    "HIDDEN2":      [1.5, 0.75],
    "HIDDENX2":     [6.0, 3.0],
    "CENTER":       [15.0, 3.0, 3.0, 3.0],
    "CENTER2":      [7.5,  1.5, 1.5, 1.5],
    "CENTERX2":     [30.0, 6.0, 6.0, 6.0],
    "DOT":          [0.5,  2.5],
    "DOT2":         [0.5,  1.25],
    "DOTX2":        [0.5,  5.0],
    "DASHDOT":      [8.0,  2.5, 0.5, 2.5],
    "DASHDOT2":     [4.0,  1.25, 0.5, 1.25],
    "DASHDOTX2":    [16.0, 5.0, 0.5, 5.0],
    "DIVIDE":       [8.0,  2.5, 0.5, 2.5, 0.5, 2.5],
    "DIVIDE2":      [4.0,  1.25, 0.5, 1.25, 0.5, 1.25],
    "DIVIDEX2":     [16.0, 5.0, 0.5, 5.0, 0.5, 5.0],
    "BORDER":       [8.0,  2.5, 8.0, 2.5, 0.5, 2.5],
    "BORDER2":      [4.0,  1.25, 4.0, 1.25, 0.5, 1.25],
    "BORDERX2":     [16.0, 5.0, 16.0, 5.0, 0.5, 5.0],
    "PHANTOM":      [15.0, 3.0, 3.0, 3.0, 3.0, 3.0],
    "PHANTOM2":     [7.5,  1.5, 1.5, 1.5, 1.5, 1.5],
    "PHANTOMX2":    [30.0, 6.0, 6.0, 6.0, 6.0, 6.0],
}


def linetype_pattern(linetype_name: str) -> Optional[list]:
    """Return QGIS dash vector for the given DXF linetype, or None for solid."""
    return _LINETYPE_PATTERNS.get((linetype_name or "CONTINUOUS").upper())


# ---------------------------------------------------------------------------
# DXF layer table reader
# ---------------------------------------------------------------------------

class LayerInfo:
    __slots__ = ("color", "linetype", "lineweight", "frozen")

    def __init__(self, color=7, linetype="CONTINUOUS", lineweight=0, frozen=False):
        self.color = color          # ACI int (negative = frozen)
        self.linetype = linetype    # string
        self.lineweight = lineweight  # in 1/100 mm (0 = default)
        self.frozen = frozen


def read_dxf_layer_table(dxf_path: str) -> Dict[str, LayerInfo]:
    """Read DXF LAYER table. Returns dict[layer_name → LayerInfo].
    Tries ezdxf first, then ASCII text parsing."""
    try:
        return _read_via_ezdxf(dxf_path)
    except Exception as _err:
        errlog.ignored(_err, "style_service.read_dxf_layer_table:140")
    try:
        return _read_via_ascii(dxf_path)
    except Exception as _err:
        errlog.ignored(_err, "style_service.read_dxf_layer_table:144")
    return {}


def _read_via_ezdxf(dxf_path: str) -> Dict[str, LayerInfo]:
    import ezdxf
    doc = ezdxf.readfile(dxf_path)
    out: Dict[str, LayerInfo] = {}
    for lyr in doc.layers:
        name = str(lyr.dxf.name)
        color = int(getattr(lyr.dxf, "color", 7))
        try:
            lt = str(lyr.dxf.linetype) if hasattr(lyr.dxf, "linetype") else "CONTINUOUS"
        except Exception:
            lt = "CONTINUOUS"
        try:
            lw = int(lyr.dxf.lineweight) if hasattr(lyr.dxf, "lineweight") else 0
        except Exception:
            lw = 0
        frozen = bool(getattr(lyr, "is_frozen", lambda: False)())
        out[name] = LayerInfo(color=color, linetype=lt, lineweight=lw, frozen=frozen)
    return out


def _read_via_ascii(dxf_path: str) -> Dict[str, LayerInfo]:
    """Parse ASCII DXF for the LAYER table.
    Handles any order of tables (VPORT, LTYPE, LAYER …).
    """
    out: Dict[str, LayerInfo] = {}

    try:
        with open(dxf_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.rstrip("\r\n") for ln in fh]
    except Exception:
        return out

    # Read pairs (group_code, value)
    pairs = []
    i = 0
    while i < len(lines) - 1:
        try:
            pairs.append((int(lines[i].strip()), lines[i + 1].strip()))
        except ValueError as _err:
            errlog.ignored(_err, "style_service._read_via_ascii:187")
        i += 2

    # Locate the LAYER table
    layer_table_start = None
    for idx, (code, val) in enumerate(pairs):
        if code == 0 and val == "TABLE":
            # Next meaningful pair should be (2, "LAYER")
            for j in range(idx + 1, min(idx + 5, len(pairs))):
                if pairs[j][0] == 2 and pairs[j][1].upper() == "LAYER":
                    layer_table_start = j + 1
                    break
            if layer_table_start is not None:
                break  # found it

    if layer_table_start is None:
        return out  # no LAYER table found

    def _save(cur):
        if "name" in cur:
            try:
                out[str(cur["name"])] = LayerInfo(
                    color=int(cur.get("color", 7)),
                    linetype=str(cur.get("linetype", "CONTINUOUS")),
                    lineweight=int(cur.get("lineweight", 0)),
                    frozen=bool(int(cur.get("flags", 0)) & 1),
                )
            except Exception as _err:
                errlog.ignored(_err, "style_service._save:215")

    cur: Dict[str, object] = {}
    in_entry = False

    for code, val in pairs[layer_table_start:]:
        if code == 0:
            if val == "ENDTAB":
                _save(cur)
                break                       # end of LAYER table
            if val == "LAYER":
                _save(cur)                  # save previous entry
                cur = {}
                in_entry = True
        elif in_entry:
            if code == 2:
                cur["name"] = val
            elif code == 62:
                try: cur["color"] = int(val)
                except ValueError as _err:
                    errlog.ignored(_err, "style_service._read_via_ascii:235")
            elif code == 6:
                cur["linetype"] = val
            elif code == 370:
                try: cur["lineweight"] = int(val)
                except ValueError as _err:
                    errlog.ignored(_err, "style_service._read_via_ascii:241")
            elif code == 70:
                try: cur["flags"] = int(val)
                except ValueError as _err:
                    errlog.ignored(_err, "style_service._read_via_ascii:245")

    return out


# ---------------------------------------------------------------------------
# Apply DXF-faithful style to a QgsVectorLayer
# ---------------------------------------------------------------------------

def apply_dxf_style(
    qgs_layer,
    dxf_layer_name: str,
    layer_table: Dict[str, LayerInfo],
    *,
    override_color: Optional[Tuple[int, int, int]] = None,
):
    """Apply DXF-faithful colour, linetype and lineweight to a QgsVectorLayer."""
    try:
        from qgis.core import (
            QgsSingleSymbolRenderer, QgsSymbol,
            QgsSimpleLineSymbolLayer, QgsSimpleFillSymbolLayer,
            QgsWkbTypes,
        )
        from qgis.PyQt.QtGui import QColor
    except Exception:
        return

    # ── 1. Resolve colour ──────────────────────────────────────────────────
    info = layer_table.get(dxf_layer_name)

    if override_color:
        rgb = override_color
        confident = True
    elif info:
        rgb = aci_to_rgb(abs(info.color), abs(info.color))
        confident = True          # we have the layer table entry
    else:
        rgb = _sample_color_from_layer(qgs_layer, layer_table, dxf_layer_name)
        confident = rgb != (0, 0, 0)   # only apply if we found something real

    # If we have no colour info at all, let QGIS keep its own default cycling
    if not confident:
        return

    qcolor = QColor(*rgb)
    if qcolor.lightness() > 230:          # avoid invisible-white on white canvas
        qcolor = QColor(40, 40, 40)

    # ── 2. Resolve linetype & lineweight ──────────────────────────────────
    lt_name = (info.linetype if info else "CONTINUOUS") or "CONTINUOUS"
    dash    = linetype_pattern(lt_name)
    raw_lw  = info.lineweight if info else 0
    lw_mm   = raw_lw / 100.0 if raw_lw > 0 else 0.26   # 0 = default 0.26 mm

    # ── 3. Build default symbol then customise ────────────────────────────
    try:
        geom_type = qgs_layer.geometryType()   # 0=Point 1=Line 2=Polygon
        symbol    = QgsSymbol.defaultSymbol(geom_type)
        if symbol is None:
            return

        symbol.setColor(qcolor)

        if geom_type == QgsWkbTypes.GeometryType.LineGeometry:
            # Walk symbol layers to reach the SimpleLineSymbolLayer
            for idx in range(symbol.symbolLayerCount()):
                sl = symbol.symbolLayer(idx)
                if isinstance(sl, QgsSimpleLineSymbolLayer):
                    sl.setColor(qcolor)
                    sl.setWidth(lw_mm)
                    sl.setWidthUnit(Qgis.RenderUnit.Millimeters)
                    if dash:
                        sl.setUseCustomDashPattern(True)
                        sl.setCustomDashVector(dash)
                        sl.setCustomDashPatternUnit(Qgis.RenderUnit.Millimeters)
                    break

        elif geom_type == QgsWkbTypes.GeometryType.PolygonGeometry:
            for idx in range(symbol.symbolLayerCount()):
                sl = symbol.symbolLayer(idx)
                if isinstance(sl, QgsSimpleFillSymbolLayer):
                    sl.setStrokeColor(qcolor)
                    sl.setFillColor(QColor(qcolor.red(), qcolor.green(), qcolor.blue(), 40))
                    sl.setStrokeWidth(lw_mm)
                    sl.setStrokeWidthUnit(Qgis.RenderUnit.Millimeters)
                    break

        # Point/annotation: color already set via symbol.setColor()

        qgs_layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        qgs_layer.triggerRepaint()

    except Exception as _err:
        errlog.ignored(_err, "style_service.apply_dxf_style:338")


def _sample_color_from_layer(
    qgs_layer, layer_table, dxf_layer_name
) -> Tuple[int, int, int]:
    """Fallback: read the 'Color' field from layer features and vote on the ACI index."""
    try:
        field_names = [f.name() for f in qgs_layer.fields()]
        color_field = next((f for f in field_names if f.lower() == "color"), None)
        if color_field is None:
            return (0, 0, 0)

        from collections import Counter
        counts: Counter = Counter()
        for feat in qgs_layer.getFeatures():
            try:
                val = int(feat[color_field])
                counts[val] += 1
            except (TypeError, ValueError) as _err:
                errlog.ignored(_err, "style_service._sample_color_from_layer:358")
            if sum(counts.values()) >= 100:
                break

        if not counts:
            return (0, 0, 0)

        dominant = counts.most_common(1)[0][0]

        # BYLAYER → resolve via layer table
        if dominant in (-1, 256):
            info = layer_table.get(dxf_layer_name)
            layer_aci = abs(info.color) if info else 7
            return aci_to_rgb(layer_aci, layer_aci)

        return aci_to_rgb(dominant, 7)
    except Exception:
        return (0, 0, 0)
