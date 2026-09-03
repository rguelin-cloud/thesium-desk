# check_btc_cycle.py
# Inspection BTC apres cycle Jalon 3
import sqlite3, os, sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
if not os.path.exists(DB):
    print(f"[KO] DB introuvable : {DB}")
    sys.exit(1)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 70)
print("DERNIER CYCLE")
print("=" * 70)
rows = list(c.execute(
    "SELECT cycle_id, MAX(created_at) AS last_ts FROM cycle_reconciliation_log "
    "GROUP BY cycle_id ORDER BY last_ts DESC LIMIT 1"
))
if rows:
    last_cycle = rows[0]["cycle_id"]
    print(f"cycle_id = {last_cycle}  ({rows[0]['last_ts']})")
else:
    last_cycle = None
    print("Aucun cycle trouve")

print()
print("=" * 70)
print("ORDRES pending_validation (top 15)")
print("=" * 70)
for r in c.execute(
    "SELECT ticker, side, qty, status, created_at "
    "FROM order_proposals WHERE status='pending_validation' "
    "ORDER BY created_at DESC LIMIT 15"
):
    print(f"  {r['ticker']:<8} {r['side']:<5} qty={r['qty']:<14} {r['created_at']}")

print()
print("=" * 70)
print("RECONCILIATION BTC (5 derniers)")
print("=" * 70)
for r in c.execute(
    "SELECT cycle_id, ticker, action, reason, qty_in, delta_signal_pct, created_at "
    "FROM cycle_reconciliation_log WHERE ticker='BTC' "
    "ORDER BY created_at DESC LIMIT 5"
):
    print(f"  cycle={r['cycle_id']}  action={r['action']}  qty_in={r['qty_in']}  "
          f"delta={r['delta_signal_pct']}  {r['created_at']}")
    print(f"    raison: {r['reason']}")

print()
print("=" * 70)
print("RECONCILIATION dernier cycle (tous tickers)")
print("=" * 70)
if last_cycle:
    for r in c.execute(
        "SELECT ticker, action, qty_in, delta_signal_pct, reason "
        "FROM cycle_reconciliation_log WHERE cycle_id=? "
        "ORDER BY ticker", (last_cycle,)
    ):
        print(f"  {r['ticker']:<8} {r['action']:<22} qty={r['qty_in']:<14} "
              f"delta={r['delta_signal_pct']}")
        if r['action'] in ('DROPPED', 'REJECTED'):
            print(f"      -> {r['reason']}")

c.close()
