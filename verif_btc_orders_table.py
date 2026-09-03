# verif_btc_orders_table.py
# Verifie si BTC a bien un row dans orders pour le cycle 20260525-100150

import sqlite3, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 70)
print("Schema theses")
print("=" * 70)
cols_th = [r["name"] for r in c.execute("PRAGMA table_info(theses)")]
print(f"  colonnes: {cols_th}")

print()
print("=" * 70)
print("TOUS les ordres post-reset (10:00 et apres) avec ticker")
print("=" * 70)
for r in c.execute(
    "SELECT o.id, i.ticker, i.id AS iid, o.side, o.quantity, o.status, "
    "       o.thesis_id, o.created_at, o.rejection_reason "
    "FROM orders o LEFT JOIN instruments i ON o.instrument_id = i.id "
    "WHERE o.created_at >= '2026-05-25 10:00:00' "
    "ORDER BY o.created_at, o.id"
):
    marker = " ### " if r["ticker"] == "BTC" else "     "
    print(f"  {marker}id={r['id']:<4} {str(r['ticker']):<6} iid={r['iid']} "
          f"{r['side']:<5} qty={r['quantity']:<12} status={r['status']:<22} "
          f"thesis={r['thesis_id']} {r['created_at']}")
    if r["rejection_reason"]:
        print(f"            rejection: {r['rejection_reason']}")

print()
print("=" * 70)
print("ORDERS - filtre instrument_id=15 (BTC)")
print("=" * 70)
for r in c.execute(
    "SELECT * FROM orders WHERE instrument_id=15 ORDER BY created_at DESC LIMIT 10"
):
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("COUNT ordres par cycle (via theses.cycle_id si dispo)")
print("=" * 70)
# Voir si theses a une colonne cycle_id
if "cycle_id" in cols_th:
    for r in c.execute(
        "SELECT t.cycle_id, COUNT(o.id) AS n_orders, "
        "       GROUP_CONCAT(i.ticker) AS tickers "
        "FROM orders o "
        "JOIN theses t ON o.thesis_id = t.id "
        "LEFT JOIN instruments i ON o.instrument_id = i.id "
        "WHERE o.created_at >= '2026-05-25 10:00:00' "
        "GROUP BY t.cycle_id ORDER BY t.cycle_id"
    ):
        print(f"  cycle={r['cycle_id']}  n_orders={r['n_orders']}  tickers={r['tickers']}")
else:
    print(f"  pas de col cycle_id dans theses. Cherche autre lien...")
    for r in c.execute(
        "SELECT DATE(o.created_at) AS d, TIME(o.created_at) AS t, "
        "       GROUP_CONCAT(i.ticker) AS tickers, COUNT(*) AS n "
        "FROM orders o LEFT JOIN instruments i ON o.instrument_id = i.id "
        "WHERE o.created_at >= '2026-05-25 10:00:00' "
        "GROUP BY o.created_at ORDER BY o.created_at"
    ):
        print(f"  {r['d']} {r['t']}  n={r['n']}  tickers={r['tickers']}")

print()
print("=" * 70)
print("DERNIER CYCLE reconciliation (rappel)")
print("=" * 70)
last = c.execute(
    "SELECT cycle_id, MAX(created_at) FROM cycle_reconciliation_log "
    "GROUP BY cycle_id ORDER BY MAX(created_at) DESC LIMIT 5"
).fetchall()
for r in last:
    print(f"  {r[0]}  {r[1]}")

c.close()
