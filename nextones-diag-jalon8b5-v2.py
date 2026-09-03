# -*- coding: utf-8 -*-
# nextones-diag-jalon8b5-v2.py
# Suite Jalon 8B.5 - analyse differentielle v2
# Fix colonne replay_orders + ajout analyses fines.
#
# Usage : py -3.13 nextones-diag-jalon8b5-v2.py

import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
RUN_ID = 15

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 0. Schemas replay_orders et replay_fills
print("=" * 78)
print("[SCHEMAS replay_orders / replay_fills]")
print("=" * 78)
ro_cols = [r["name"] for r in cur.execute("PRAGMA table_info(replay_orders)").fetchall()]
print(f"  replay_orders : {ro_cols}")
rf_cols = [r["name"] for r in cur.execute("PRAGMA table_info(replay_fills)").fetchall()]
print(f"  replay_fills  : {rf_cols}")

# Detecter colonnes
reject_col_r = None
for c in ("reject_reason", "rejection_reason", "reason", "comment", "details", "risk_check_result"):
    if c in ro_cols:
        reject_col_r = c
        break
print(f"  reject_col replay = {reject_col_r}")

# Fenetre overlap fixe
S, E = "2026-05-25", "2026-06-12"

# ====================================================================
# B. REJETS replay + prod
# ====================================================================
print("\n" + "=" * 78)
print(f"[B] Rejets replay vs prod (overlap {S} -> {E})")
print("=" * 78)

if reject_col_r:
    print(f"\n  Replay - top raisons rejet ({reject_col_r}) :")
    for r in cur.execute(
        f"SELECT {reject_col_r} reason, COUNT(*) n FROM replay_orders "
        f"WHERE run_id=? AND status='rejected' AND day_t BETWEEN ? AND ? "
        f"GROUP BY {reject_col_r} ORDER BY n DESC LIMIT 15",
        (RUN_ID, S, E),
    ).fetchall():
        rea = str(r["reason"]) if r["reason"] else "NULL"
        print(f"    {rea[:65]:65s}  n={r['n']:4d}")

# Prod : risk_check_result
print(f"\n  Prod - distribution risk_check_result (rejected only) :")
for r in cur.execute(
    "SELECT risk_check_result reason, COUNT(*) n FROM orders "
    "WHERE status='rejected' AND DATE(created_at) BETWEEN ? AND ? "
    "GROUP BY risk_check_result ORDER BY n DESC LIMIT 15",
    (S, E),
).fetchall():
    rea = str(r["reason"]) if r["reason"] else "NULL"
    print(f"    {rea[:65]:65s}  n={r['n']:4d}")

# Prod - status complets
print(f"\n  Prod - distribution status :")
for r in cur.execute(
    "SELECT status, COUNT(*) n FROM orders "
    "WHERE DATE(created_at) BETWEEN ? AND ? GROUP BY status ORDER BY n DESC",
    (S, E),
).fetchall():
    print(f"    status={(r['status'] or 'NULL'):30s}  n={r['n']:4d}")

# ====================================================================
# G. PROD - quels tickers MAJORITAIRES en prod, et sont-ils tradees en replay ?
# ====================================================================
print("\n" + "=" * 78)
print(f"[G] Top tickers prod fills (filled) vs replay")
print("=" * 78)
print(f"\n  Prod - top tickers (fills.fill_price * fill_quantity) :")
prod_top = cur.execute(
    "SELECT i.ticker, COUNT(f.id) n, "
    "       SUM(f.fill_price * f.fill_quantity) tot "
    "FROM fills f "
    "JOIN orders o ON o.id = f.order_id "
    "JOIN instruments i ON i.id = o.instrument_id "
    "WHERE DATE(f.filled_at) BETWEEN ? AND ? "
    "GROUP BY i.ticker ORDER BY tot DESC LIMIT 20",
    (S, E),
).fetchall()
prod_tickers = {}
for r in prod_top:
    print(f"    {r['ticker']:6s}  n={r['n']:3d}  total=${(r['tot'] or 0):>12,.2f}")
    prod_tickers[r["ticker"]] = (r["n"], r["tot"] or 0)

print(f"\n  Replay - top tickers fills (overlap) :")
replay_top = cur.execute(
    "SELECT ticker, COUNT(*) n, SUM(notional) tot FROM replay_fills "
    "WHERE run_id=? AND day_t BETWEEN ? AND ? GROUP BY ticker "
    "ORDER BY tot DESC LIMIT 20",
    (RUN_ID, S, E),
).fetchall()
replay_tickers = {}
for r in replay_top:
    print(f"    {r['ticker']:6s}  n={r['n']:3d}  total=${(r['tot'] or 0):>12,.2f}")
    replay_tickers[r["ticker"]] = (r["n"], r["tot"] or 0)

print(f"\n  Tickers presents EN PROD MAIS PAS EN REPLAY :")
miss = sorted(set(prod_tickers) - set(replay_tickers))
for t in miss:
    n, tot = prod_tickers[t]
    print(f"    {t:6s}  n_prod={n:3d}  tot_prod=${tot:>12,.2f}")
print(f"\n  Tickers presents EN REPLAY MAIS PAS EN PROD :")
extra = sorted(set(replay_tickers) - set(prod_tickers))
for t in extra:
    n, tot = replay_tickers[t]
    print(f"    {t:6s}  n_rep={n:3d}  tot_rep=${tot:>12,.2f}")

# ====================================================================
# H. PROD - composition positions vs replay
# ====================================================================
print("\n" + "=" * 78)
print(f"[H] Composition positions actuelles prod")
print("=" * 78)
prod_pos = cur.execute(
    "SELECT i.ticker, pp.quantity qty, pp.avg_cost "
    "FROM portfolio_positions pp "
    "JOIN instruments i ON i.id = pp.instrument_id "
    "WHERE pp.quantity > 0 ORDER BY pp.quantity * COALESCE(pp.avg_cost, 0) DESC"
).fetchall()
print(f"  Prod n_positions = {len(prod_pos)}")
for p in prod_pos[:25]:
    val = p["qty"] * (p["avg_cost"] or 0)
    print(f"    {p['ticker']:6s} | qty={p['qty']:>10.2f} | avg=${(p['avg_cost'] or 0):>9.2f} | "
          f"val=${val:>12,.2f}")

# ====================================================================
# I. CASH PROD evolution
# ====================================================================
print("\n" + "=" * 78)
print(f"[I] Cash evolution prod vs replay")
print("=" * 78)
print(f"  day_t       | nav prod      | cash prod    | nav replay    | cash replay | "
      f"alloc prod | alloc replay")
print(f"  " + "-" * 110)
for r in cur.execute(
    "SELECT r.day_t, r.nav nav_r, r.cash cash_r, r.positions_value pv_r, "
    "       p.total_value nav_p, p.cash cash_p "
    "FROM replay_nav_history r "
    "INNER JOIN portfolio_history p ON p.date = r.day_t "
    "WHERE r.run_id=? ORDER BY r.day_t",
    (RUN_ID,),
).fetchall():
    cash_p = r["cash_p"] or 0
    alloc_p = 100.0 * (1 - cash_p / r["nav_p"]) if r["nav_p"] else 0
    alloc_r = 100.0 * (1 - r["cash_r"] / r["nav_r"]) if r["nav_r"] else 0
    print(f"  {r['day_t']}  | ${r['nav_p']:>11,.2f} | ${cash_p:>10,.2f} | "
          f"${r['nav_r']:>11,.2f} | ${r['cash_r']:>10,.2f} | "
          f"{alloc_p:5.1f}%    | {alloc_r:5.1f}%")

# ====================================================================
# J. FEES + SLIPPAGE prod (fees colonne)
# ====================================================================
print("\n" + "=" * 78)
print(f"[J] Fees + slippage prod (overlap)")
print("=" * 78)
row = cur.execute(
    "SELECT COUNT(*) n, SUM(fees) tot_fees, AVG(fees) avg_fees, "
    "       SUM(slippage) tot_slip, AVG(slippage) avg_slip "
    "FROM fills WHERE DATE(filled_at) BETWEEN ? AND ?",
    (S, E),
).fetchone()
print(f"  fills={row['n']}  tot_fees=${(row['tot_fees'] or 0):,.2f}  "
      f"avg_fees=${(row['avg_fees'] or 0):.4f}")
print(f"  tot_slippage=${(row['tot_slip'] or 0):,.2f}  avg_slippage=${(row['avg_slip'] or 0):.4f}")

con.close()
print("\nDONE")
