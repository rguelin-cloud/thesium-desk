"""Trouver un cycle prod recent dont J+1 est dispo en DB (fill-testable)."""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("""
    SELECT cycle_id, COUNT(*) as n_snaps, SUM(forced_exit) as n_fe
    FROM convergence_snapshots
    WHERE SUBSTR(cycle_id,1,8) BETWEEN '20260608' AND '20260611'
    GROUP BY cycle_id
    ORDER BY cycle_id DESC
""")
for r in cur.fetchall():
    print(f"  {r['cycle_id']:25s} n={r['n_snaps']:3d} fe={r['n_fe']}")
conn.close()
