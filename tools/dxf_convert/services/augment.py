from __future__ import annotations
from typing import Dict, Tuple, Optional, List, Callable, Iterable
from shapely.geometry import Point
from .conversion_service import _make_crs

try:
    import geopandas as gpd
    import pandas as pd
except Exception:
    gpd = None
    pd = None

ProgressCB = Optional[Callable[[str], None]]

def _say(cb: ProgressCB, msg: str):
    if cb:
        try: cb(msg)
        except: pass

def _safe_s(val):
    try:
        if val is None: return None
        s = str(val)
        return s.replace("\r\n","\n").replace("\r","\n")
    except Exception:
        return None

def _strip_mtext(raw: str) -> Optional[str]:
    """Strip MTEXT RTF escape codes (\\P, \\~, \\Cn, \\Hx, ...) and return plain text."""
    import re
    try:
        s = str(raw)
        # Replace paragraph breaks with space
        s = re.sub(r'\\P', ' ', s)
        # Remove format codes: \Cx \Hx \Tx \Qx \Wx \Ox \Kx \kx \lx \pN... etc.
        s = re.sub(r'\\[A-Za-z][^;{}\\ ]*;?', '', s)
        # Remove braces used for grouping
        s = re.sub(r'[{}]', '', s)
        # Collapse whitespace
        s = re.sub(r'[ \t]+', ' ', s).strip()
        return s if s else None
    except Exception:
        return _safe_s(raw)

def _in_selected(layer_name: str, selected: Optional[Iterable[str]]) -> bool:
    if not selected:
        return False
    try:
        return layer_name in set(selected)
    except Exception:
        return False

def _merge_into(out: dict, gdf: "gpd.GeoDataFrame"):
    """Merge gdf rows (grouped by layer/geom) into out dict, appending to existing keys."""
    if gdf is None or len(gdf) == 0:
        return
    if "layer" not in gdf.columns or "geom" not in gdf.columns:
        return
    for (layer, geom), sub in gdf.groupby(["layer", "geom"]):
        key = (str(layer), str(geom))
        sub_r = sub.reset_index(drop=True)
        if key in out:
            out[key] = pd.concat([out[key], sub_r]).reset_index(drop=True)
        else:
            out[key] = sub_r

def _reproject(gdf: "gpd.GeoDataFrame", src_epsg, tgt_epsg) -> "gpd.GeoDataFrame":
    src_crs = _make_crs(src_epsg or 4326)
    if gdf.crs is None:
        gdf = gdf.set_crs(src_crs)
    if tgt_epsg:
        tgt_crs = _make_crs(tgt_epsg)
        if tgt_crs != src_crs:
            try: gdf = gdf.to_crs(tgt_crs)
            except Exception: pass
    return gdf


def _collect_text_ogr(
    dxf_path: str,
    *,
    src_epsg,
    tgt_epsg=None,
    on_progress=None,
) -> Dict[Tuple[str, str], "gpd.GeoDataFrame"]:
    """OGR-based TEXT/MTEXT extraction — scans ALL DXF layers regardless of geometry selection."""
    out: Dict[Tuple[str, str], gpd.GeoDataFrame] = {}
    try:
        from osgeo import ogr, gdal
    except Exception:
        return out

    rows: List[dict] = []

    try:
        gdal.SetConfigOption("DXF_INLINE_BLOCKS", "YES")
    except Exception:
        pass

    ds = ogr.Open(dxf_path, 0)
    if ds is None:
        return out

    lyr = ds.GetLayerByName("entities") or (ds.GetLayer(0) if ds.GetLayerCount() else None)
    if lyr is None:
        ds = None; return out

    defn = lyr.GetLayerDefn()
    field_names = [defn.GetFieldDefn(i).GetName() for i in range(defn.GetFieldCount())]

    text_field = next((f for f in field_names if f.lower() == "text"), None)
    if text_field is None:
        _say(on_progress, "[augment:ogr] No 'Text' field found in DXF entities layer")
        ds = None; return out

    _say(on_progress, "[augment:ogr] scanning all DXF entities for TEXT/MTEXT …")
    lyr.ResetReading()
    for f in lyr:
        try:
            subclass = str(f.GetField("SubClasses") or "") if "SubClasses" in field_names else ""
            if subclass:
                if "AcDbText" not in subclass and "AcDbMText" not in subclass:
                    continue

            text_val = f.GetField(text_field)
            if not text_val:
                continue

            g = f.GetGeometryRef()
            if g is None:
                continue
            x, y = g.GetX(), g.GetY()

            layer_name = (f.GetField("Layer") if "Layer" in field_names else None) or "0"

            rot = None
            for cand in ("Angle", "angle", "Rotation", "rotation"):
                if cand in field_names:
                    v = f.GetField(cand)
                    if v is not None:
                        rot = float(v); break

            height = None
            for cand in ("Height", "height", "TextHeight"):
                if cand in field_names:
                    v = f.GetField(cand)
                    if v is not None:
                        height = float(v); break

            rows.append({
                "layer": f"{layer_name}_TEXT", "geom": "POINT",
                "geometry": Point(x, y),
                "text": _safe_s(text_val),
                "rotation": rot if rot is not None else 0.0,
                "height": height,
                "src_layer": layer_name,
            })
        except Exception:
            continue
    ds = None

    if not rows:
        _say(on_progress, "[augment:ogr] no TEXT/MTEXT entities found")
        return out

    src_crs = _make_crs(src_epsg or 4326)
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=src_crs)
    gdf = _reproject(gdf, src_epsg, tgt_epsg)

    for (layer, geom), sub in gdf.groupby(["layer", "geom"]):
        out[(str(layer), str(geom))] = sub.reset_index(drop=True)

    _say(on_progress, f"[augment:ogr] TEXT: {len(rows)} label(s) → {len(out)} layer(s)")
    return out


def _collect_attrib_multileader_ascii(
    dxf_path: str,
    *,
    src_epsg,
    tgt_epsg=None,
    on_progress=None,
) -> Dict[Tuple[str, str], "gpd.GeoDataFrame"]:
    """ASCII DXF parser for ATTRIB and MULTILEADER entities.

    Used when ezdxf is unavailable or finds nothing.
    ATTRIB: group codes 1=text, 2=tag, 8=layer, 10=X, 20=Y, 40=height, 50=rotation
    MULTILEADER: group codes 304=text, 8=layer, 10=X, 20=Y (first occurrence)
    """
    out: Dict[Tuple[str, str], gpd.GeoDataFrame] = {}

    try:
        with open(dxf_path, "r", encoding="utf-8", errors="replace") as fh:
            lines = [ln.rstrip("\r\n") for ln in fh]
    except Exception:
        return out

    pairs: List[Tuple[int, str]] = []
    i = 0
    while i < len(lines) - 1:
        try:
            pairs.append((int(lines[i].strip()), lines[i + 1].strip()))
        except ValueError:
            pass
        i += 2

    # Find ENTITIES section
    entities_start = None
    for idx, (code, val) in enumerate(pairs):
        if code == 2 and val.upper() == "ENTITIES":
            entities_start = idx + 1
            break
    if entities_start is None:
        _say(on_progress, "[augment:ascii] ENTITIES section not found")
        return out

    rows_attrib: List[dict] = []
    rows_leader: List[dict] = []

    cur_type: Optional[str] = None
    cur: Dict[str, object] = {}
    seen_x = seen_y = False  # track first 10/20 per entity

    def _flush():
        if cur_type == "ATTRIB":
            x = cur.get("x"); y = cur.get("y")
            txt = cur.get("text") or cur.get("tag")
            if x is not None and y is not None and txt:
                lname = str(cur.get("layer", "0"))
                rows_attrib.append({
                    "layer": f"{lname}_TEXT", "geom": "POINT",
                    "geometry": Point(float(x), float(y)),
                    "text": _safe_s(txt),
                    "rotation": float(cur.get("rotation", 0.0) or 0.0),
                    "height": float(cur["height"]) if cur.get("height") is not None else None,
                    "tag": _safe_s(cur.get("tag")),
                    "src_layer": lname,
                })
        elif cur_type == "MULTILEADER":
            x = cur.get("x"); y = cur.get("y")
            txt = cur.get("text")
            if x is not None and y is not None and txt:
                lname = str(cur.get("layer", "0"))
                rows_leader.append({
                    "layer": f"{lname}_TEXT", "geom": "POINT",
                    "geometry": Point(float(x), float(y)),
                    "text": _safe_s(txt),
                    "rotation": 0.0,
                    "height": None,
                    "tag": None,
                    "src_layer": lname,
                })

    for code, val in pairs[entities_start:]:
        if code == 0:
            _flush()
            if val in ("ENDSEC", "EOF"):
                break
            cur_type = val
            cur = {}
            seen_x = False; seen_y = False
        elif cur_type == "ATTRIB":
            if code == 8:
                cur["layer"] = val
            elif code == 1:
                cur["text"] = val
            elif code == 2:
                cur["tag"] = val
            elif code == 10:
                if not seen_x:
                    try: cur["x"] = float(val); seen_x = True
                    except ValueError: pass
            elif code == 20:
                if not seen_y:
                    try: cur["y"] = float(val); seen_y = True
                    except ValueError: pass
            elif code == 40:
                try: cur["height"] = float(val)
                except ValueError: pass
            elif code == 50:
                try: cur["rotation"] = float(val)
                except ValueError: pass
        elif cur_type == "MULTILEADER":
            if code == 8:
                cur["layer"] = val
            elif code == 304 and "text" not in cur:
                # First code 304 = mtext content (inside CONTEXT_DATA{)
                # Second code 304 = 'LEADER_LINE{' structural marker — ignore
                if val not in ("LEADER_LINE{", "LEADER{"):
                    cur["text"] = val
            elif code == 10:
                if not seen_x:
                    try: cur["x"] = float(val); seen_x = True
                    except ValueError: pass
            elif code == 20:
                if not seen_y:
                    try: cur["y"] = float(val); seen_y = True
                    except ValueError: pass

    _say(on_progress, f"[augment:ascii] ATTRIB={len(rows_attrib)}, MULTILEADER={len(rows_leader)}")

    all_rows = rows_attrib + rows_leader
    if not all_rows:
        return out

    src_crs = _make_crs(src_epsg or 4326)
    gdf = gpd.GeoDataFrame(all_rows, geometry="geometry", crs=src_crs)
    gdf = _reproject(gdf, src_epsg, tgt_epsg)
    _merge_into(out, gdf)
    return out


def collect_annotations_and_blocks(
    dxf_path: str,
    *,
    src_epsg: int,
    tgt_epsg: Optional[int] = None,
    include_text: bool = True,
    include_blocks: bool = True,
    keep_block_transform: bool = True,
    target_layers: Optional[List[str]] = None,
    on_progress: ProgressCB = None,
):
    """Return extra buckets (TEXT/MTEXT/ATTRIB/MULTILEADER & BLOCKS).

    Text extraction covers ALL DXF layers (TEXT, MTEXT, ATTRIB, MULTILEADER).
    BLOCK attributes are filtered to target_layers if provided.
    """
    if gpd is None:
        raise RuntimeError("geopandas is required for TEXT/MTEXT/BLOCK augmentation but was not found.")

    out: Dict[Tuple[str, str], gpd.GeoDataFrame] = {}

    try:
        import ezdxf as _ezdxf
        _ezdxf_ok = True
    except Exception:
        _ezdxf_ok = False

    if not _ezdxf_ok:
        _say(on_progress, "[augment] ezdxf not available → OGR/ASCII fallback")
        if include_text:
            out.update(_collect_text_ogr(dxf_path, src_epsg=src_epsg, tgt_epsg=tgt_epsg,
                                         on_progress=on_progress))
            ascii_extra = _collect_attrib_multileader_ascii(
                dxf_path, src_epsg=src_epsg, tgt_epsg=tgt_epsg, on_progress=on_progress
            )
            for k, v in ascii_extra.items():
                if k in out:
                    out[k] = pd.concat([out[k], v]).reset_index(drop=True)
                else:
                    out[k] = v
        return out

    try:
        doc = _ezdxf.readfile(dxf_path)
    except Exception as ex:
        _say(on_progress, f"[augment] failed to read for annotations: {ex}")
        return out

    msp = doc.modelspace()
    sel = set(target_layers or [])

    src_crs = _make_crs(src_epsg or 4326)

    # ── TEXT / MTEXT ──────────────────────────────────────────────────────────
    if include_text:
        rows_text: List[dict] = []
        _say(on_progress, "[augment] scanning for TEXT/MTEXT …")
        for e in msp.query("TEXT MTEXT"):
            try:
                src_layer = (getattr(e.dxf, "layer", "0") or "0")
                if e.dxftype() == "TEXT":
                    ip = e.dxf.insert
                    txt = _safe_s(e.dxf.text)
                    rot = float(getattr(e.dxf, "rotation", 0.0) or 0.0)
                    h = getattr(e.dxf, "height", None)
                    style = getattr(e.dxf, "style", None)
                else:  # MTEXT
                    ip = e.dxf.insert
                    try: txt = _safe_s(e.plain_text())
                    except Exception:
                        txt = _safe_s(getattr(e, "text", None) or getattr(e.dxf, "text", None))
                    rot = float(getattr(e.dxf, "rotation", 0.0) or 0.0)
                    h = getattr(e.dxf, "char_height", None)
                    style = getattr(e.dxf, "style", None)
                if not txt:
                    continue
                rows_text.append({
                    "layer": f"{src_layer}_TEXT", "geom": "POINT",
                    "geometry": Point(ip.x, ip.y),
                    "text": txt, "rotation": rot,
                    "height": float(h) if h is not None else None,
                    "style": _safe_s(style), "src_layer": src_layer,
                })
            except Exception:
                continue
        _say(on_progress, f"[augment] TEXT/MTEXT: {len(rows_text)}")
        if rows_text:
            gdf = gpd.GeoDataFrame(rows_text, geometry="geometry", crs=src_crs)
            gdf = _reproject(gdf, src_epsg, tgt_epsg)
            _merge_into(out, gdf)

    # ── ATTRIB (from INSERT blocks) ───────────────────────────────────────────
    if include_text:
        rows_attrib: List[dict] = []
        _say(on_progress, "[augment] scanning INSERT blocks for ATTRIB …")
        for ins in msp.query("INSERT"):
            try:
                src_layer = (getattr(ins.dxf, "layer", "0") or "0")
                ins_ip = ins.dxf.insert
                for a in ins.attribs():
                    try:
                        txt = _safe_s(getattr(a.dxf, "text", None))
                        tag = _safe_s(getattr(a.dxf, "tag", None))
                        if not txt:
                            continue
                        a_ip = getattr(a.dxf, "insert", ins_ip)
                        rot = float(getattr(a.dxf, "rotation", 0.0) or 0.0)
                        h = getattr(a.dxf, "height", None)
                        attrib_layer = str(getattr(a.dxf, "layer", None) or src_layer)
                        rows_attrib.append({
                            "layer": f"{attrib_layer}_TEXT", "geom": "POINT",
                            "geometry": Point(a_ip.x, a_ip.y),
                            "text": txt, "rotation": rot,
                            "height": float(h) if h is not None else None,
                            "tag": tag, "src_layer": attrib_layer,
                        })
                    except Exception:
                        continue
            except Exception:
                continue
        _say(on_progress, f"[augment] ATTRIB: {len(rows_attrib)}")
        if rows_attrib:
            gdf_a = gpd.GeoDataFrame(rows_attrib, geometry="geometry", crs=src_crs)
            gdf_a = _reproject(gdf_a, src_epsg, tgt_epsg)
            _merge_into(out, gdf_a)

    # ── MULTILEADER ───────────────────────────────────────────────────────────
    if include_text:
        rows_ml: List[dict] = []
        _say(on_progress, "[augment] scanning for MULTILEADER …")
        try:
            for ml in msp.query("MULTILEADER"):
                try:
                    src_layer = (getattr(ml.dxf, "layer", "0") or "0")
                    txt = None
                    x = y = None

                    # ezdxf context API (ezdxf >= 0.17)
                    ctx = getattr(ml, "context", None)
                    if ctx is not None:
                        mt = getattr(ctx, "mtext", None)
                        if mt is not None:
                            raw = getattr(mt, "default_content", None)
                            if raw:
                                txt = _strip_mtext(raw)
                            ins_pt = getattr(mt, "insert", None)
                            if ins_pt is not None:
                                try: x, y = float(ins_pt[0]), float(ins_pt[1])
                                except Exception: pass

                    if not txt:
                        txt = _safe_s(getattr(ml.dxf, "text", None))

                    if not txt or x is None:
                        continue

                    rows_ml.append({
                        "layer": f"{src_layer}_TEXT", "geom": "POINT",
                        "geometry": Point(x, y),
                        "text": txt, "rotation": 0.0,
                        "height": None, "tag": None, "src_layer": src_layer,
                    })
                except Exception:
                    continue
        except Exception as ex:
            _say(on_progress, f"[augment] MULTILEADER scan error: {ex}")
        _say(on_progress, f"[augment] MULTILEADER: {len(rows_ml)}")
        if rows_ml:
            gdf_ml = gpd.GeoDataFrame(rows_ml, geometry="geometry", crs=src_crs)
            gdf_ml = _reproject(gdf_ml, src_epsg, tgt_epsg)
            _merge_into(out, gdf_ml)

    # ── ASCII fallback if ezdxf found zero text entities ─────────────────────
    if include_text and not out:
        _say(on_progress, "[augment] ezdxf found no text → ASCII fallback for ATTRIB/MULTILEADER")
        ascii_extra = _collect_attrib_multileader_ascii(
            dxf_path, src_epsg=src_epsg, tgt_epsg=tgt_epsg, on_progress=on_progress
        )
        out.update(ascii_extra)

    # ── BLOCK INSERT attributes (for BLOCKS layer) ────────────────────────────
    if include_blocks and sel:
        rows_blk: List[dict] = []
        for ins in msp.query("INSERT"):
            try:
                src_layer = (getattr(ins.dxf, "layer", "0") or "0")
                if src_layer not in sel:
                    continue
                ip = ins.dxf.insert
                row = {
                    "layer": "BLOCKS", "geom": "POINT", "geometry": Point(ip.x, ip.y),
                    "src_layer": src_layer,
                    "block_name": _safe_s(getattr(ins.dxf, "name", None) or getattr(ins, "name", None)),
                }
                try:
                    for a in ins.attribs():
                        tag = _safe_s(getattr(a.dxf, "tag", None))
                        val_a = _safe_s(getattr(a.dxf, "text", None))
                        if tag: row[f"att_{tag}"] = val_a
                except Exception:
                    pass
                if keep_block_transform:
                    try:
                        row.update({
                            "blk_ins_x": float(ip.x), "blk_ins_y": float(ip.y),
                            "blk_ins_z": float(getattr(ip, "z", 0.0) or 0.0),
                            "blk_rotation": float(getattr(ins.dxf, "rotation", 0.0) or 0.0),
                            "blk_sx": float(getattr(ins.dxf, "xscale", 1.0) or 1.0),
                            "blk_sy": float(getattr(ins.dxf, "yscale", 1.0) or 1.0),
                            "blk_sz": float(getattr(ins.dxf, "zscale", 1.0) or 1.0),
                        })
                    except Exception:
                        pass
                rows_blk.append(row)
            except Exception:
                continue
        if rows_blk:
            gdfb = gpd.GeoDataFrame(rows_blk, geometry="geometry", crs=src_crs)
            gdfb = _reproject(gdfb, src_epsg, tgt_epsg)
            out[("BLOCKS", "POINT")] = gdfb.reset_index(drop=True)

    if not out:
        _say(on_progress, "[augment] no text or block attributes found")
    else:
        _say(on_progress, f"[augment] added {len(out)} extra bucket(s)")

    return out


def attach_block_transform_to_buckets(buckets, blocks, *, on_progress=None):
    if gpd is None:
        raise RuntimeError("geopandas is required for attach_block_transform_to_buckets but was not found.")
    if blocks is None or len(blocks) == 0:
        _say(on_progress, "[augment] no BLOCKS to attach"); return

    cols = ["blk_ins_x", "blk_ins_y", "blk_ins_z", "blk_rotation", "blk_sx", "blk_sy", "blk_sz"]
    have = [c for c in cols if c in blocks.columns]
    if not have:
        _say(on_progress, "[augment] BLOCKS has no transform fields"); return

    bx = blocks.geometry.x.to_numpy(); by = blocks.geometry.y.to_numpy()
    bvals = {c: (blocks[c].to_numpy() if c in blocks.columns else None) for c in cols}

    def attach_one_gdf(gdf):
        for c in cols:
            if c not in gdf.columns:
                gdf[c] = None
        reps = gdf.geometry if all(gdf.geometry.geom_type == "Point") else gdf.geometry.centroid
        gx = reps.x.to_numpy(); gy = reps.y.to_numpy()
        for i in range(len(gdf)):
            j_best = 0; d2_best = float("inf")
            x = gx[i]; y = gy[i]
            for j in range(len(blocks)):
                dx = x - bx[j]; dy = y - by[j]; d2 = dx * dx + dy * dy
                if d2 < d2_best: d2_best = d2; j_best = j
            for c in cols:
                arr = bvals.get(c)
                if arr is not None: gdf.at[i, c] = arr[j_best]

    for key, gdf in buckets.items():
        layer, geom = key
        if layer == "BLOCKS":
            continue
        try:
            attach_one_gdf(gdf)
        except Exception as ex:
            _say(on_progress, f"[augment] attach failed on {layer}: {ex}")
