"""Diag : schema reel shadow_variants."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()
print("=== shadow_variants columns ===")
cur.execute("PRAGMA table_info(shadow_variants)")
for c in cur.fetchall():
    print(f"  {c[1]:25s} {c[2]:15s} nn={c[3]}")
print("\n=== sample rows ===")
cur.execute("SELECT * FROM shadow_variants")
cols = [d[0] for d in cur.description]
print(" | ".join(cols))
for r in cur.fetchall():
    print(" | ".join(str(v)[:30] for v in r))
conn.close()
