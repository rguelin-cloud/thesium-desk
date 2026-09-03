# -*- coding: utf-8 -*-
# nextones-diag-jalon8b5-replay-vs-prod-v1.py
# Jalon 8B.5 - Analyse differentielle replay vs prod sur fenetre chevauchement.
#
# Objectif : comprendre pourquoi le replay surperforme la prod de +12.29%
# sur 65 cycles (NAV 8B.4 = $1,085,628 vs prod $966,781).
#
# Angles d'analyse :
#   A. Volumes orders/fills : replay vs prod cote a cote
#   B. Taux de rejet : combien d'orders prod refuses par risk/broker que le replay
#      laisse passer (Strict A, concentration, etc.)
#   C. Positions composition : tickers detenus, ponderation, similarite
#   D. Cash usage : replay sous-investi vs prod ? Inversement ?
#   E. Frais/slippage cumul replay vs prod
#   F. Top deltas orders : ordres presents en replay et absents en prod (et inverse)
#
# Window de chevauchement : prend max(min replay_nav, min portfolio_history)
# jusqu'a max date commune.
#
# Pas d'ecriture, ASCII pur.
# Usage : py -3.13 nextones-diag-jalon8b5-replay-vs-prod-v1.py

import sqlite3
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
RUN_ID = 15  # Jalon 8B.4

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 78)
print(f"DIAG Jalon 8B.5 - Replay (run_id={RUN_ID}) vs Prod - fenetre chevauchement")
print("=" * 78)

# --- Determiner fenetre chevauchement ---
row = cur.execute(
    "SELECT MIN(day_t) min_d, MAX(day_t) max_d FROM replay_nav_history WHERE run_id=?",
    (RUN_ID,),
).fetchone()
replay_min, replay_max = row["min_d"], row["max_d"]
row = cur.execute(
    "SELECT MIN(date) min_d, MAX(date) max_d FROM portfolio_history"
).fetchone()
prod_min, prod_max = row["min_d"], row["max_d"]
overlap_start = max(replay_min, prod_min)
overlap_end = min(replay_max, prod_max)
print(f"\n[FENETRE]")
print(f"  Replay  : {replay_min} -> {replay_max}")
print(f"  Prod    : {prod_min} -> {prod_max}")
print(f"  Overlap : {overlap_start} -> {overlap_end}")

# ====================================================================
# A. VOLUMES ORDERS / FILLS replay vs prod sur la fenetre overlap
# ====================================================================
print("\n" + "=" * 78)
print("[A] Volumes orders / fills (overlap)")
print("=" * 78)

r_orders = cur.execute(
    "SELECT COUNT(*) n, "
    "       SUM(CASE WHEN UPPER(side)='BUY' THEN 1 ELSE 0 END) buys, "
    "       SUM(CASE WHEN UPPER(side)='SELL' THEN 1 ELSE 0 END) sells, "
    "       SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) filled, "
    "       SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) rejected "
    "FROM replay_orders WHERE run_id=? AND day_t BETWEEN ? AND ?",
    (RUN_ID, overlap_start, overlap_end),
).fetchone()
print(f"  Replay  : orders={r_orders['n']}  BUY={r_orders['buys']}  SELL={r_orders['sells']}  "
      f"filled={r_orders['filled']}  rejected={r_orders['rejected']}")

# Prod orders - schema pas certain, on detecte les colonnes
prod_cols = [r["name"] for r in cur.execute("PRAGMA table_info(orders)").fetchall()]
date_col = None
for c in ("created_at", "ts", "ts_created", "timestamp", "decision_ts"):
    if c in prod_cols:
        date_col = c
        break
side_col = "side" if "side" in prod_cols else None
status_col = "status" if "status" in prod_cols else None

print(f"  [prod schema] orders date_col={date_col} cols={prod_cols[:10]}...")

if date_col:
    p_orders = cur.execute(
        f"SELECT COUNT(*) n, "
        f"       SUM(CASE WHEN UPPER({side_col})='BUY' THEN 1 ELSE 0 END) buys, "
        f"       SUM(CASE WHEN UPPER({side_col})='SELL' THEN 1 ELSE 0 END) sells, "
        f"       SUM(CASE WHEN {status_col}='filled' THEN 1 ELSE 0 END) filled, "
        f"       SUM(CASE WHEN {status_col}='rejected' THEN 1 ELSE 0 END) rejected "
        f"FROM orders WHERE DATE({date_col}) BETWEEN ? AND ?",
        (overlap_start, overlap_end),
    ).fetchone()
    print(f"  Prod    : orders={p_orders['n']}  BUY={p_orders['buys']}  SELL={p_orders['sells']}  "
          f"filled={p_orders['filled']}  rejected={p_orders['rejected']}")

# Fills
r_fills = cur.execute(
    "SELECT COUNT(*) n, SUM(notional) total_n, "
    "       SUM(CASE WHEN UPPER(side)='BUY' THEN notional ELSE 0 END) buy_n, "
    "       SUM(CASE WHEN UPPER(side)='SELL' THEN notional ELSE 0 END) sell_n, "
    "       AVG(slippage_bps) avg_slip "
    "FROM replay_fills WHERE run_id=? AND day_t BETWEEN ? AND ?",
    (RUN_ID, overlap_start, overlap_end),
).fetchone()
print(f"\n  Replay fills : n={r_fills['n']}  total_notional=${r_fills['total_n']:>12,.2f}")
print(f"                 buy=${r_fills['buy_n']:>12,.2f}  sell=${r_fills['sell_n']:>12,.2f}  "
      f"avg_slip_bps={r_fills['avg_slip']:.2f}")

# Prod fills
fill_cols = [r["name"] for r in cur.execute("PRAGMA table_info(fills)").fetchall()]
print(f"  [prod schema] fills cols={fill_cols[:12]}...")
f_date = None
for c in ("filled_at", "ts", "fill_ts", "timestamp"):
    if c in fill_cols:
        f_date = c
        break
notional_col = "notional" if "notional" in fill_cols else (
    "fill_price" if "fill_price" in fill_cols else None
)
if f_date and notional_col:
    p_fills = cur.execute(
        f"SELECT COUNT(*) n, SUM({notional_col}) total_n "
        f"FROM fills WHERE DATE({f_date}) BETWEEN ? AND ?",
        (overlap_start, overlap_end),
    ).fetchone()
    print(f"  Prod   fills : n={p_fills['n']}  total_notional=${p_fills['total_n']:>12,.2f}"
          if p_fills["total_n"] else f"  Prod   fills : n={p_fills['n']}")

# ====================================================================
# B. REJETS - replay vs prod
# ====================================================================
print("\n" + "=" * 78)
print("[B] Taux de rejet et raisons")
print("=" * 78)
print("\n  Replay - top raisons rejet :")
for r in cur.execute(
    "SELECT reject_reason, COUNT(*) n FROM replay_orders "
    "WHERE run_id=? AND status='rejected' AND day_t BETWEEN ? AND ? "
    "GROUP BY reject_reason ORDER BY n DESC LIMIT 10",
    (RUN_ID, overlap_start, overlap_end),
).fetchall():
    print(f"    {(r['reject_reason'] or 'NULL')[:60]:60s}  n={r['n']:4d}")

if date_col and status_col:
    print("\n  Prod - top raisons rejet :")
    reject_col = None
    for c in ("reject_reason", "rejection_reason", "reason", "comment", "details"):
        if c in prod_cols:
            reject_col = c
            break
    print(f"    [reject_col detected={reject_col}]")
    if reject_col:
        for r in cur.execute(
            f"SELECT {reject_col} reason, COUNT(*) n FROM orders "
            f"WHERE {status_col}='rejected' AND DATE({date_col}) BETWEEN ? AND ? "
            f"GROUP BY {reject_col} ORDER BY n DESC LIMIT 10",
            (overlap_start, overlap_end),
        ).fetchall():
            print(f"    {(r['reason'] or 'NULL')[:60]:60s}  n={r['n']:4d}")
    else:
        for r in cur.execute(
            f"SELECT {status_col} st, COUNT(*) n FROM orders "
            f"WHERE DATE({date_col}) BETWEEN ? AND ? "
            f"GROUP BY {status_col} ORDER BY n DESC LIMIT 10",
            (overlap_start, overlap_end),
        ).fetchall():
            print(f"    status={r['st']:30s}  n={r['n']:4d}")

# ====================================================================
# C. POSITIONS COMPOSITION au dernier jour overlap
# ====================================================================
print("\n" + "=" * 78)
print(f"[C] Positions composition au {overlap_end}")
print("=" * 78)

# Replay - positions du dernier cycle
last_cir = cur.execute(
    "SELECT MAX(cycle_id_replay) FROM replay_positions WHERE run_id=?",
    (RUN_ID,),
).fetchone()[0]
print(f"\n  Replay (cycle_id_replay={last_cir}) :")
r_pos = cur.execute(
    "SELECT ticker, quantity qty, avg_cost, current_price px, weight_pct "
    "FROM replay_positions WHERE run_id=? AND cycle_id_replay=? "
    "ORDER BY weight_pct DESC",
    (RUN_ID, last_cir),
).fetchall()
print(f"    {'ticker':6s} | {'qty':>10s} | {'avg_cost':>10s} | {'px':>10s} | {'weight':>8s}")
print(f"    " + "-" * 56)
r_tickers = set()
for p in r_pos[:25]:
    print(f"    {p['ticker']:6s} | {p['qty']:>10.2f} | {p['avg_cost']:>10.2f} | "
          f"{p['px']:>10.2f} | {p['weight_pct']:>7.3f}%")
    r_tickers.add(p["ticker"])

# Prod - positions actuelles
print(f"\n  Prod (positions courantes) :")
pos_cols = [r["name"] for r in cur.execute("PRAGMA table_info(portfolio_positions)").fetchall()]
print(f"    [prod schema portfolio_positions cols={pos_cols}]")
# Schema attendu : instrument_id, quantity, avg_cost
qty_col = "quantity" if "quantity" in pos_cols else "qty"
try:
    p_pos = cur.execute(
        f"SELECT i.ticker, pp.{qty_col} qty, pp.avg_cost "
        f"FROM portfolio_positions pp JOIN instruments i ON i.id=pp.instrument_id "
        f"WHERE pp.{qty_col} > 0 ORDER BY pp.{qty_col} * COALESCE(pp.avg_cost, 0) DESC"
    ).fetchall()
    p_tickers = set()
    for p in p_pos[:25]:
        print(f"    {p['ticker']:6s} | {p['qty']:>10.2f} | {(p['avg_cost'] or 0):>10.2f}")
        p_tickers.add(p["ticker"])
    print(f"\n  Overlap tickers replay vs prod : {sorted(r_tickers & p_tickers)}")
    print(f"  Only in replay : {sorted(r_tickers - p_tickers)}")
    print(f"  Only in prod   : {sorted(p_tickers - r_tickers)}")
except Exception as e:
    print(f"    ERR : {e}")

# ====================================================================
# D. CASH USAGE - replay vs prod
# ====================================================================
print("\n" + "=" * 78)
print(f"[D] Cash usage sur overlap")
print("=" * 78)
print(f"\n  day_t       | NAV replay     | cash replay   | NAV prod       | cash_pct r/p")
print(f"  " + "-" * 80)
rows = cur.execute(
    "SELECT r.day_t, r.nav nav_r, r.cash cash_r, r.positions_value pv_r, "
    "       p.total_value nav_p, p.cash cash_p "
    "FROM replay_nav_history r "
    "INNER JOIN portfolio_history p ON p.date = r.day_t "
    "WHERE r.run_id=? ORDER BY r.day_t",
    (RUN_ID,),
).fetchall()
for r in rows:
    cash_p = r["cash_p"] if r["cash_p"] is not None else 0
    cash_pct_r = 100.0 * r["cash_r"] / r["nav_r"] if r["nav_r"] else 0
    cash_pct_p = 100.0 * cash_p / r["nav_p"] if r["nav_p"] else 0
    print(f"  {r['day_t']}  | ${r['nav_r']:>12,.2f} | ${r['cash_r']:>11,.2f} | "
          f"${r['nav_p']:>12,.2f} | r={cash_pct_r:5.1f}% p={cash_pct_p:5.1f}%")

# ====================================================================
# E. FRAIS / SLIPPAGE replay
# ====================================================================
print("\n" + "=" * 78)
print(f"[E] Slippage / cost replay (overlap)")
print("=" * 78)
row = cur.execute(
    "SELECT COUNT(*) n, AVG(slippage_bps) avg_slip, MAX(slippage_bps) max_slip, "
    "       SUM(notional * slippage_bps / 10000) implicit_cost "
    "FROM replay_fills WHERE run_id=? AND day_t BETWEEN ? AND ?",
    (RUN_ID, overlap_start, overlap_end),
).fetchone()
print(f"  fills={row['n']}  avg_slip_bps={row['avg_slip']:.2f}  max={row['max_slip']:.2f}  "
      f"cost_implicit=${row['implicit_cost']:.2f}")

# ====================================================================
# F. TOP DELTAS ORDERS - tickers traites par replay non traites par prod (et inverse)
# ====================================================================
print("\n" + "=" * 78)
print(f"[F] Top tickers traites - replay vs prod (overlap)")
print("=" * 78)
print(f"\n  Replay - top tickers filled (BUY+SELL count) :")
for r in cur.execute(
    "SELECT ticker, COUNT(*) n, SUM(notional) tot FROM replay_fills "
    "WHERE run_id=? AND day_t BETWEEN ? AND ? GROUP BY ticker "
    "ORDER BY n DESC LIMIT 15",
    (RUN_ID, overlap_start, overlap_end),
).fetchall():
    print(f"    {r['ticker']:6s}  n={r['n']:3d}  total=${r['tot']:>12,.2f}")

if f_date:
    print(f"\n  Prod - top tickers filled (overlap) :")
    ticker_col = None
    for c in ("ticker", "symbol", "instrument_id"):
        if c in fill_cols:
            ticker_col = c
            break
    qty_col_f = "quantity" if "quantity" in fill_cols else (
        "fill_quantity" if "fill_quantity" in fill_cols else None
    )
    if ticker_col == "instrument_id":
        # JOIN
        try:
            for r in cur.execute(
                f"SELECT i.ticker, COUNT(*) n, "
                f"       SUM(COALESCE({notional_col}, 0)) tot "
                f"FROM fills f JOIN instruments i ON i.id=f.instrument_id "
                f"WHERE DATE(f.{f_date}) BETWEEN ? AND ? "
                f"GROUP BY i.ticker ORDER BY n DESC LIMIT 15",
                (overlap_start, overlap_end),
            ).fetchall():
                print(f"    {r['ticker']:6s}  n={r['n']:3d}  total=${(r['tot'] or 0):>12,.2f}")
        except Exception as e:
            print(f"    ERR : {e}")
    elif ticker_col:
        for r in cur.execute(
            f"SELECT {ticker_col} ticker, COUNT(*) n "
            f"FROM fills WHERE DATE({f_date}) BETWEEN ? AND ? "
            f"GROUP BY {ticker_col} ORDER BY n DESC LIMIT 15",
            (overlap_start, overlap_end),
        ).fetchall():
            print(f"    {r['ticker']:6s}  n={r['n']:3d}")

con.close()
print("\n" + "=" * 78)
print("DONE - voir analyse plus haut pour identifier la cause du +12%")
print("=" * 78)
