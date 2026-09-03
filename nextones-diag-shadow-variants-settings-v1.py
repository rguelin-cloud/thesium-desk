"""
Diag: dump complet des 4 variantes shadow + leurs settings JSON.
Affiche variant_id, name, description, settings (parse JSON) en clair.
"""
import os
import sqlite3
import json

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 80)
print("TABLE shadow_variants - schema")
print("=" * 80)
cur.execute("PRAGMA table_info(shadow_variants)")
for r in cur.fetchall():
    print(f"  {r['cid']:2d} {r['name']:20s} {r['type']:15s} pk={r['pk']}")

print()
print("=" * 80)
print("CONTENU des 4 variantes")
print("=" * 80)
cur.execute("SELECT * FROM shadow_variants ORDER BY variant_id")
for r in cur.fetchall():
    d = dict(r)
    print()
    print(f"--- variant_id={d.get('variant_id')} name={d.get('name')} ---")
    for k, v in d.items():
        if k == "settings" and v:
            print(f"  {k}:")
            try:
                parsed = json.loads(v)
                print(json.dumps(parsed, indent=4, ensure_ascii=False, sort_keys=True))
            except Exception as e:
                print(f"  [parse error: {e}]")
                print(f"  raw: {v}")
        else:
            print(f"  {k}: {v}")

conn.close()
