"""Test the ASCII parser directly on GDC.dxf without QGIS/ezdxf."""
import sys
sys.path.insert(0, r"C:\Users\y_laloux\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\cad_to_gis_convert")

dxf_path = r"C:\Users\y_laloux\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\cad_to_gis_convert\GDC.dxf"

with open(dxf_path, encoding="utf-8", errors="replace") as fh:
    lines = [ln.rstrip("\r\n") for ln in fh]

pairs = []
i = 0
while i < len(lines) - 1:
    try:
        pairs.append((int(lines[i].strip()), lines[i+1].strip()))
    except ValueError:
        pass
    i += 2

# Find ENTITIES section
entities_start = None
for idx, (code, val) in enumerate(pairs):
    if code == 2 and val.upper() == "ENTITIES":
        entities_start = idx + 1
        break

print(f"ENTITIES starts at pair {entities_start}")

rows_attrib = []
rows_leader = []

cur_type = None
cur = {}
seen_x = seen_y = False

def flush():
    if cur_type == "ATTRIB":
        x = cur.get("x"); y = cur.get("y")
        txt = cur.get("text") or cur.get("tag")
        if x is not None and y is not None and txt:
            rows_attrib.append({"layer": cur.get("layer","0"), "tag": cur.get("tag"), "text": txt, "x": x, "y": y})
    elif cur_type == "MULTILEADER":
        x = cur.get("x"); y = cur.get("y")
        txt = cur.get("text")
        if x is not None and y is not None and txt:
            rows_leader.append({"layer": cur.get("layer","0"), "text": txt, "x": x, "y": y})

for code, val in pairs[entities_start:]:
    if code == 0:
        flush()
        if val in ("ENDSEC", "EOF"):
            break
        cur_type = val
        cur = {}
        seen_x = seen_y = False
    elif cur_type == "ATTRIB":
        if code == 8:   cur["layer"] = val
        elif code == 1: cur["text"] = val
        elif code == 2: cur["tag"] = val
        elif code == 10 and not seen_x:
            try: cur["x"] = float(val); seen_x = True
            except: pass
        elif code == 20 and not seen_y:
            try: cur["y"] = float(val); seen_y = True
            except: pass
    elif cur_type == "MULTILEADER":
        if code == 8:   cur["layer"] = val
        elif code == 304 and "text" not in cur:
            if val not in ("LEADER_LINE{", "LEADER{"):
                cur["text"] = val
        elif code == 10 and not seen_x:
            try: cur["x"] = float(val); seen_x = True
            except: pass
        elif code == 20 and not seen_y:
            try: cur["y"] = float(val); seen_y = True
            except: pass

print(f"\n=== ATTRIB: {len(rows_attrib)} found ===")
for r in rows_attrib[:8]:
    print(f"  layer={r['layer']} | tag={r['tag']} | text={r['text']!r} | x={r['x']:.2f}")

from collections import Counter
attrib_layers = Counter(r["layer"] for r in rows_attrib)
print(f"\nATTRIB distinct layers:")
for k, v in attrib_layers.most_common():
    print(f"  {v:4d}  {k}")

print(f"\n=== MULTILEADER: {len(rows_leader)} found ===")
for r in rows_leader[:10]:
    print(f"  layer={r['layer']} | text={r['text']!r} | x={r['x']:.3f}")

ml_layers = Counter(r["layer"] for r in rows_leader)
print(f"\nMULTILEADER distinct layers:")
for k, v in ml_layers.most_common():
    print(f"  {v:4d}  {k}")

print(f"\n=== SUMMARY ===")
print(f"  ATTRIB:      {len(rows_attrib)} rows → would create {len(attrib_layers)} _TEXT layers")
print(f"  MULTILEADER: {len(rows_leader)} rows → would create {len(ml_layers)} _TEXT layers")
