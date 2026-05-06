dxf_path = r"C:\Users\y_laloux\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\cad_to_gis_convert\GDC.dxf"

with open(dxf_path, encoding="utf-8", errors="replace") as fh:
    raw_lines = [ln.rstrip("\r\n") for ln in fh]

pairs = []
i = 0
while i < len(raw_lines) - 1:
    try:
        pairs.append((int(raw_lines[i].strip()), raw_lines[i+1].strip()))
    except ValueError:
        pass
    i += 2

# Find ENTITIES section
entities_start = None
for idx, (code, val) in enumerate(pairs):
    if code == 2 and val.upper() == "ENTITIES":
        entities_start = idx + 1
        break

print(f"Total pairs: {len(pairs)}, ENTITIES starts at pair {entities_start}")
print()

# Count entity types
from collections import Counter
entity_counts = Counter()
cur_type = None
for code, val in pairs[entities_start:]:
    if code == 0:
        if val in ("ENDSEC", "EOF"):
            break
        cur_type = val
        entity_counts[val] += 1

print("=== Entity counts in ENTITIES section ===")
for k, v in entity_counts.most_common(15):
    print(f"  {k}: {v}")

print()
print("=== First 12 ATTRIB entities ===")
cur_type = None
cur = {}
seen_x = seen_y = False
count = 0

def show(cur):
    print(f"  layer={cur.get('layer','?')} | tag={cur.get('tag','?')} | text={cur.get('text','?')!r} | x={cur.get('x','?')} | y={cur.get('y','?')}")

for code, val in pairs[entities_start:]:
    if code == 0:
        if cur_type == "ATTRIB" and "x" in cur:
            show(cur)
            count += 1
        if val in ("ENDSEC", "EOF"):
            break
        if count >= 12:
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

print()
print("=== Distinct ATTRIB layers ===")
cur_type = None
attrib_layers = Counter()
for code, val in pairs[entities_start:]:
    if code == 0:
        cur_type = val
        if val in ("ENDSEC", "EOF"): break
    elif cur_type == "ATTRIB" and code == 8:
        attrib_layers[val] += 1

for k, v in attrib_layers.most_common():
    print(f"  {v:4d}  {k}")

print()
print("=== First 3 MULTILEADER entities (codes 8, 304, 10, 20) ===")
cur_type = None
cur = {}
seen_x = seen_y = False
count = 0
for code, val in pairs[entities_start:]:
    if code == 0:
        if cur_type == "MULTILEADER":
            print(f"  layer={cur.get('layer','?')} | text={cur.get('text','?')!r} | x={cur.get('x','?')} | y={cur.get('y','?')}")
            count += 1
        if val in ("ENDSEC", "EOF") or count >= 3: break
        cur_type = val
        cur = {}
        seen_x = seen_y = False
    elif cur_type == "MULTILEADER":
        if code == 8:    cur["layer"] = val
        elif code == 304: cur["text"] = val
        elif code == 10 and not seen_x:
            try: cur["x"] = float(val); seen_x = True
            except: pass
        elif code == 20 and not seen_y:
            try: cur["y"] = float(val); seen_y = True
            except: pass
