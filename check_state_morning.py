# =====================================================================
# check_state_morning.py
# Diagnostic complet post-cycle v6.5.1 (lecture DB directe, pas d'API)
# =====================================================================
import sqlite3
from pathlib import Path

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if not Path(DB).exists():
    print(f"[ERREUR] DB introuvable : {DB}")
    raise SystemExit(1)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("  ETAT DU SYSTEME — Lundi matin 2026-05-25")
print("=" * 70)

# ---------------------------------------------------------------------
# 1. Ordres #165 -> #169 : verdict final
# ---------------------------------------------------------------------
print()
print("[1] Verdict final des 5 ordres concernes (#165 -> #169)")
print("-" * 70)
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status,
           datetime(o.created_at,   'localtime') AS created,
           datetime(o.validated_at, 'localtime') AS validated,
           o.rejection_reason
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     WHERE o.id BETWEEN 165 AND 169
     ORDER BY o.id
""")
rows = cur.fetchall()
if not rows:
    print("  Aucun ordre trouve dans la plage 165-169 (?)")
else:
    for r in rows:
        reason = (r["rejection_reason"] or "")[:55]
        val    = r["validated"] or "-"
        print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  "
              f"qty={r['quantity']:<8}  status={r['status']:<10}  "
              f"validated={val:<20}  {reason}")

# ---------------------------------------------------------------------
# 2. Ordres pending TOTAL (tous tickers)
# ---------------------------------------------------------------------
print()
print("[2] Ordres pending actuels (tous tickers)")
print("-" * 70)
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity,
           datetime(o.created_at,'localtime') AS created
      FROM orders o
      JOIN instruments i ON i.id = o.instrument_id
     WHERE o.status='pending'
     ORDER BY o.id
""")
pendings = cur.fetchall()
if not pendings:
    print("  AUCUN ordre pending — base propre")
else:
    for r in pendings:
        print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  "
              f"qty={r['quantity']:<8}  created={r['created']}")

# ---------------------------------------------------------------------
# 3. Positions actuelles vs targets (META / LINK / ETH + autres)
# ---------------------------------------------------------------------
print()
print("[3] Positions actuelles vs targets")
print("-" * 70)
cur.execute("""
    SELECT i.ticker,
           pp.quantity, pp.avg_cost, pp.current_price,
           pp.weight_pct AS weight_now,
           pt.target_weight_pct AS weight_tgt,
           (pp.weight_pct - pt.target_weight_pct) AS drift
      FROM portfolio_positions pp
      JOIN instruments i ON i.id = pp.instrument_id
 LEFT JOIN portfolio_targets pt
        ON pt.ticker = i.ticker AND pt.active = 1
     ORDER BY i.ticker
""")
rows = cur.fetchall()
print(f"  {'Ticker':<7} {'Qty':>10} {'Px':>10} {'Wgt%':>8} {'Tgt%':>8} {'Drift%':>9}")
for r in rows:
    drift = r["drift"] if r["drift"] is not None else 0
    tgt   = r["weight_tgt"] if r["weight_tgt"] is not None else 0
    print(f"  {r['ticker']:<7} {r['quantity']:>10.4f} "
          f"{r['current_price'] or 0:>10.2f} "
          f"{r['weight_now'] or 0:>8.2f} "
          f"{tgt:>8.2f} "
          f"{drift:>+9.2f}")

# ---------------------------------------------------------------------
# 4. Portfolio state (NAV / cash)
# ---------------------------------------------------------------------
print()
print("[4] Portfolio state")
print("-" * 70)
cur.execute("""
    SELECT cash, total_value, total_pnl, total_pnl_pct,
           daily_pnl, daily_pnl_pct, var_95, max_drawdown
      FROM portfolio_state
     ORDER BY id DESC LIMIT 1
""")
ps = cur.fetchone()
if ps:
    print(f"  Cash         : {ps['cash']:>14,.2f} EUR")
    print(f"  Total value  : {ps['total_value']:>14,.2f} EUR")
    print(f"  Total PnL    : {ps['total_pnl']:>14,.2f} EUR  ({ps['total_pnl_pct']:+.2f}%)")
    print(f"  Daily PnL    : {ps['daily_pnl']:>14,.2f} EUR  ({ps['daily_pnl_pct']:+.2f}%)")
    print(f"  VaR 95       : {ps['var_95'] or 0:>14,.2f}")
    print(f"  Max drawdown : {ps['max_drawdown'] or 0:>14,.2f}")

# ---------------------------------------------------------------------
# 5. Dernier cycle + actions CAPPED
# ---------------------------------------------------------------------
print()
print("[5] 5 derniers logs cycle_reconciliation (focus CAPPED)")
print("-" * 70)
cur.execute("""
    SELECT cycle_id, ticker, action, reason,
           signals_in, qty_in, side_in,
           delta_signal_pct, delta_target_pct,
           datetime(created_at,'localtime') AS created
      FROM cycle_reconciliation_log
     ORDER BY id DESC LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    flag = "  [CAP]" if r["action"] == "CAPPED" else ""
    reason = (r["reason"] or "")[:55]
    print(f"  {r['created']:<20} {r['cycle_id']:<20} {r['ticker']:<6} "
          f"{r['action']:<12}{flag}  {reason}")

# ---------------------------------------------------------------------
# 6. Trigger dedup actif ?
# ---------------------------------------------------------------------
print()
print("[6] Trigger SQLite dedup")
print("-" * 70)
cur.execute("""
    SELECT name, sql FROM sqlite_master
     WHERE type='trigger' AND name='trg_orders_dedup'
""")
trg = cur.fetchone()
if trg:
    print(f"  Trigger '{trg['name']}' : ACTIF")
else:
    print(f"  Trigger 'trg_orders_dedup' : ABSENT (a reinstaller)")

con.close()
print()
print("=" * 70)
print("  Diagnostic termine")
print("=" * 70)
