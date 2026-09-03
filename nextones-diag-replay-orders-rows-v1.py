# Verifie si les tables replay_orders / replay_positions / replay_nav (ancienne) contiennent des donnees
# avant de DROP+recreer avec le schema 8B.3
import os, sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB, timeout=10.0)
cur = conn.cursor()

print("=" * 70)
print("DIAG : count rows tables 8B.3 candidates au DROP")
print("=" * 70)

for tbl in ["replay_orders", "replay_positions", "replay_nav"]:
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f"  {tbl:<25s} : {n} rows")
        if n > 0:
            print(f"    (sample 3 rows)")
            for r in cur.execute(f"SELECT * FROM {tbl} LIMIT 3").fetchall():
                print(f"      {r}")
    except Exception as e:
        print(f"  {tbl:<25s} : ERROR {e}")

# Verifie DDL replay_nav si existe
print("\n--- DDL replay_nav (si existe) ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_nav'"
).fetchone()
if row:
    print(row[0])
else:
    print("  (n'existe pas)")

conn.close()
