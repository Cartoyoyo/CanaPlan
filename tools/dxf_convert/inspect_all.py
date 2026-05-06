import sqlite3, sys

db = r"C:\Users\y_laloux\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\cad_to_gis_convert\GDC.gpkg"
con = sqlite3.connect(db)
cur = con.cursor()
cur.execute("SELECT table_name FROM gpkg_contents ORDER BY table_name")
layers = [r[0] for r in cur.fetchall()]
print("=== LAYERS IN GDC.gpkg ===")
for name in layers:
    cur.execute("SELECT COUNT(*) FROM [" + name + "]")
    count = cur.fetchone()[0]
    cur.execute("PRAGMA table_info([" + name + "])")
    cols = [r[1] for r in cur.fetchall()]
    has_text = any(c.lower() == "text" for c in cols)
    print(f"  {name}  |  {count} rows  |  has_text={has_text}  |  cols={cols[:16]}")
    if count > 0 and has_text:
        cur.execute("SELECT text FROM [" + name + "] LIMIT 5")
        vals = [r[0] for r in cur.fetchall()]
        print(f"    text samples: {vals}")
con.close()
print("\nDone.")
