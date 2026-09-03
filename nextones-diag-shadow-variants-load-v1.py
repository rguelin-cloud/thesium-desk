"""
Diag rapide : qu est-ce que load_variants renvoie vraiment ?
"""
import sqlite3, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row

cur = conn.cursor()
cur.execute("PRAGMA table_info(shadow_variants)")
print("[Schema shadow_variants]")
for r in cur.fetchall():
    print(f"  {r['name']:25s} {r['type']}")

print("\n[Sample rows]")
cur.execute("SELECT * FROM shadow_variants WHERE active=1")
rows = cur.fetchall()
print(f"  n_active = {len(rows)}")
for r in rows:
    d = dict(r)
    print(f"\n  keys = {list(d.keys())}")
    for k, v in d.items():
        sv = str(v)[:60]
        print(f"    {k:20s} = {sv}")

conn.close()
