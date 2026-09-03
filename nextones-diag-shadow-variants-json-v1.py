"""Affiche le settings_json COMPLET de chaque variant."""
import sqlite3, json
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT variant_id, name, settings_json FROM shadow_variants WHERE active=1")
for r in cur.fetchall():
    d = json.loads(r['settings_json'])
    print(f"\nvariant_id={r['variant_id']} name={r['name']}")
    for k, v in d.items():
        print(f"  {k:25s} = {v}")
conn.close()
