"""
Verifie que le hook justification ecrit bien dans orders.justification.
Affiche les 10 derniers ordres avec leur justification (ou NULL).
"""
import os
import sqlite3

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT o.id, o.side, o.quantity, o.status, o.created_at,
           o.cycle_id, i.ticker, o.justification, o.justification_memo IS NOT NULL AS has_memo
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     ORDER BY o.id DESC LIMIT 10
""").fetchall()

print(f"{'ID':>4} {'TIME':<19} {'TICK':<6} {'SIDE':<5} {'QTY':>7} {'STATUS':<20} {'MEMO':<5} JUSTIFICATION")
print("-" * 140)

for r in rows:
    j = r["justification"] or "(NULL)"
    if len(j) > 90:
        j = j[:87] + "..."
    tag = "yes" if r["has_memo"] else "-"
    created = (r["created_at"] or "")[:19]
    print(f"#{r['id']:>3} {created:<19} {r['ticker']:<6} {r['side']:<5} {r['quantity']:>7} {r['status']:<20} {tag:<5} {j}")

# Stats globales
row = conn.execute("SELECT COUNT(*) AS n, SUM(CASE WHEN justification IS NOT NULL THEN 1 ELSE 0 END) AS n_j FROM orders").fetchone()
print()
print(f"[STATS] total orders={row['n']} with_justification={row['n_j']}")

conn.close()
