"""Dump ALL group codes of the first 3 MULTILEADER entities from GDC.dxf."""
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

cur_type = None
ml_count = 0
cur_codes = []

for code, val in pairs[entities_start:]:
    if code == 0:
        if cur_type == "MULTILEADER" and cur_codes:
            print(f"\n=== MULTILEADER #{ml_count} ===")
            for c, v in cur_codes:
                # Highlight text-like codes
                marker = " <-- TEXT?" if c in (1, 3, 4, 9, 301, 302, 303, 304, 305, 306) else ""
                print(f"  {c:5d}  {v!r:60s}{marker}")
            ml_count += 1
            if ml_count >= 3:
                break
        cur_type = val
        cur_codes = []
    elif cur_type == "MULTILEADER":
        cur_codes.append((code, val))

print(f"\nTotal MULTILEADER entities scanned: {ml_count}")
