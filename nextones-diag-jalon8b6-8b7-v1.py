# -*- coding: utf-8 -*-
# nextones-diag-jalon8b6-8b7-v1.py
# Jalons 8B.6 (rotation 2026-05-29) + 8B.7 (forced_exit prod sur crypto)
#
# 8B.6 : pourquoi la prod a investi $311k en 1 jour le 2026-05-29 ?
#   - Lister TOUS les orders prod du 2026-05-29 + ticker + side + qty + status
#   - Identifier le cycle_id correspondant
#   - Comparer le regime_log avant/le jour J : changement ?
#   - Comparer les scores convergence/PCA avant/le jour J
#   - Verifier si convergence etait deploye/actif a cette date
#
# 8B.7 : forced_exit convergence prod sur tickers crypto (ETH/BTC/SOL/LINK/AMZN/GOOGL)
#   - Convergence_snapshots prod sur fenetre overlap : quel verdict ?
#   - Si forced_exit etait actif, comment les orders BUY sont passes quand meme ?
#   - Verifier les bypass historiques (convergence_block_v1 deploye QUAND ?)
#   - Lister les bypass_reason eventuels dans risk_check_json
#
# ASCII pur. Usage : py -3.13 nextones-diag-jalon8b6-8b7-v1.py

import sqlite3
import json
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
RUN_ID = 15
PIVOT_DAY = "2026-05-29"
OVERLAP_START = "2026-05-25"
OVERLAP_END = "2026-06-12"
CRYPTO_TICKERS = ("BTC", "ETH", "SOL", "LINK", "AMZN", "GOOGL", "MSFT")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()


def safe_select(sql, params=()):
    """Wrapper qui catch les erreurs schema."""
    try:
        return cur.execute(sql, params).fetchall()
    except sqlite3.OperationalError as e:
        print(f"    [SCHEMA ERR] {e}")
        return []


# ====================================================================
# PRE - schemas pour comprendre la prod
# ====================================================================
print("=" * 78)
print("[PRE] Schemas des tables impliquees")
print("=" * 78)
for t in ("orders", "fills", "convergence_snapshots", "regime_log",
          "portfolio_targets", "market_regime_log"):
    try:
        cols = [r["name"] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"  {t:30s} cols={cols}")
    except Exception as e:
        print(f"  {t:30s} ERR {e}")


# ====================================================================
# 8B.6 - SECTION A : tous les orders prod du 2026-05-29
# ====================================================================
print("\n" + "=" * 78)
print(f"[8B.6-A] Orders prod du {PIVOT_DAY}")
print("=" * 78)

orders_pivot = safe_select(
    "SELECT o.id, o.cycle_id, i.ticker, o.side, o.quantity qty, o.order_type, "
    "       o.status, o.created_at, "
    "       SUBSTR(o.risk_check_result, 1, 80) risk_short "
    "FROM orders o LEFT JOIN instruments i ON i.id=o.instrument_id "
    "WHERE DATE(o.created_at)=? "
    "ORDER BY o.created_at, o.id",
    (PIVOT_DAY,),
)
print(f"  n_orders={len(orders_pivot)}")
print(f"\n  {'id':>6s} | {'ticker':6s} | side | {'qty':>8s} | status     | cycle_id")
print(f"  " + "-" * 70)
cycles_pivot = set()
for r in orders_pivot:
    cycles_pivot.add(r["cycle_id"])
    print(f"  {r['id']:>6d} | {(r['ticker'] or '?'):6s} | {r['side']:4s} | "
          f"{r['qty']:>8.2f} | {(r['status'] or 'NULL'):10s} | {r['cycle_id']}")
print(f"\n  cycle_ids pivot day = {sorted(cycles_pivot)}")

# Aggregation par ticker
print(f"\n  Aggregation par ticker (pivot day) :")
agg = safe_select(
    "SELECT i.ticker, o.side, COUNT(*) n, SUM(o.quantity) qty, "
    "       SUM(CASE WHEN o.status='filled' THEN 1 ELSE 0 END) filled, "
    "       SUM(CASE WHEN o.status='cancelled' THEN 1 ELSE 0 END) cancelled, "
    "       SUM(CASE WHEN o.status='rejected' THEN 1 ELSE 0 END) rejected "
    "FROM orders o LEFT JOIN instruments i ON i.id=o.instrument_id "
    "WHERE DATE(o.created_at)=? GROUP BY i.ticker, o.side "
    "ORDER BY i.ticker, o.side",
    (PIVOT_DAY,),
)
for r in agg:
    print(f"    {(r['ticker'] or '?'):6s} {r['side']:4s} n={r['n']:3d} qty={r['qty']:>10.2f} "
          f"filled={r['filled']} cancelled={r['cancelled']} rejected={r['rejected']}")

# Fills pivot day
print(f"\n  Fills prod du {PIVOT_DAY} (ce qui a reellement bouge le cash) :")
fills_pivot = safe_select(
    "SELECT i.ticker, o.side, f.fill_price, f.fill_quantity, "
    "       f.fill_price * f.fill_quantity notional "
    "FROM fills f JOIN orders o ON o.id=f.order_id "
    "JOIN instruments i ON i.id=o.instrument_id "
    "WHERE DATE(f.filled_at)=? ORDER BY notional DESC",
    (PIVOT_DAY,),
)
tot = 0
for r in fills_pivot:
    n = r["notional"] or 0
    tot += n
    print(f"    {r['ticker']:6s} {r['side']:4s} qty={r['fill_quantity']:>8.2f} "
          f"px=${r['fill_price']:>8.2f} notional=${n:>11,.2f}")
print(f"  TOTAL pivot day notional = ${tot:,.2f}")


# ====================================================================
# 8B.6 - SECTION B : regime + convergence au pivot day
# ====================================================================
print("\n" + "=" * 78)
print(f"[8B.6-B] Regime / convergence prod autour du {PIVOT_DAY}")
print("=" * 78)

print(f"\n  regime_log autour du pivot day :")
rl = safe_select(
    "SELECT cycle_id, "
    "       CASE WHEN created_at IS NOT NULL THEN DATE(created_at) "
    "            ELSE substr(cycle_id,1,8) END d, "
    "       regime, vix, equity_state, crypto_state, "
    "       SUBSTR(details_json, 1, 80) details_short "
    "FROM regime_log "
    "WHERE substr(cycle_id, 1, 8) BETWEEN ? AND ? "
    "ORDER BY cycle_id LIMIT 30",
    (PIVOT_DAY.replace("-", "")[:6] + "20",  # 2026-05-20
     PIVOT_DAY.replace("-", "")[:6] + "31"),  # 2026-05-31
)
if not rl:
    # Schema differs : essai market_regime_log
    print(f"    (fallback market_regime_log)")
    rl = safe_select(
        "SELECT cycle_id, * FROM market_regime_log "
        "WHERE substr(cycle_id, 1, 8) BETWEEN ? AND ? "
        "ORDER BY cycle_id LIMIT 30",
        ("20260520", "20260531"),
    )
for r in rl[:15]:
    try:
        print(f"    cycle={r['cycle_id']:20s} regime={r.get('regime') if hasattr(r,'get') else 'NA'}")
    except Exception:
        # Print all columns
        print(f"    {dict(r)}")


# ====================================================================
# 8B.6 - SECTION C : convergence_snapshots prod au pivot day
# ====================================================================
print("\n" + "=" * 78)
print(f"[8B.6-C / 8B.7] Convergence prod sur pivot day + crypto tickers")
print("=" * 78)

print(f"\n  convergence_snapshots autour du pivot day {PIVOT_DAY} :")
cs = safe_select(
    "SELECT cycle_id, ticker, forced_exit, drift_block, multiplier, "
    "       agreement_pct, status "
    "FROM convergence_snapshots "
    "WHERE substr(cycle_id, 1, 8) BETWEEN ? AND ? "
    "ORDER BY cycle_id, ticker",
    ("20260525", "20260601"),
)
print(f"  rows={len(cs)}")
# Aggregation : combien de forced_exit par cycle ?
print(f"\n  forced_exit / drift_block par cycle (top 10) :")
agg_conv = {}
for r in cs:
    cid = r["cycle_id"]
    agg_conv.setdefault(cid, {"fe": 0, "dr": 0, "total": 0, "tickers_fe": []})
    agg_conv[cid]["total"] += 1
    if r["forced_exit"]:
        agg_conv[cid]["fe"] += 1
        agg_conv[cid]["tickers_fe"].append(r["ticker"])
    if r["drift_block"]:
        agg_conv[cid]["dr"] += 1
for cid in sorted(agg_conv.keys())[:15]:
    a = agg_conv[cid]
    print(f"    {cid:25s} total={a['total']:3d} forced_exit={a['fe']:3d} "
          f"drift_block={a['dr']:3d} fe_tickers={a['tickers_fe'][:8]}")

# 8B.7 : convergence sur les crypto tickers specifiques
print(f"\n  Convergence detail pour CRYPTO tickers ({CRYPTO_TICKERS}) :")
ph = ",".join(["?"] * len(CRYPTO_TICKERS))
cs_crypto = safe_select(
    f"SELECT cycle_id, ticker, forced_exit, drift_block, multiplier, "
    f"       agreement_pct, status "
    f"FROM convergence_snapshots "
    f"WHERE ticker IN ({ph}) "
    f"  AND substr(cycle_id, 1, 8) BETWEEN ? AND ? "
    f"ORDER BY cycle_id, ticker",
    tuple(CRYPTO_TICKERS) + ("20260525", "20260612"),
)
print(f"  rows={len(cs_crypto)}")
print(f"\n  {'cycle_id':25s} {'ticker':6s} {'fe':>3s} {'dr':>3s} {'mult':>5s} "
      f"{'agree':>6s} status")
print(f"  " + "-" * 70)
for r in cs_crypto[:50]:
    print(f"  {r['cycle_id']:25s} {r['ticker']:6s} {r['forced_exit']:>3} {r['drift_block']:>3} "
          f"{(r['multiplier'] or 0):>5.2f} {(r['agreement_pct'] or 0):>6.2f} "
          f"{r['status'] or ''}")


# ====================================================================
# 8B.7 - SECTION D : risk_check_json des orders crypto pivot day
# ====================================================================
print("\n" + "=" * 78)
print(f"[8B.7-D] risk_check_json complet des orders crypto pivot day")
print("=" * 78)

risk_orders = safe_select(
    "SELECT o.id, i.ticker, o.side, o.quantity qty, o.status, "
    "       o.cycle_id, o.risk_check_result "
    f"FROM orders o JOIN instruments i ON i.id=o.instrument_id "
    f"WHERE i.ticker IN ({ph}) AND DATE(o.created_at)=? "
    f"ORDER BY o.id",
    tuple(CRYPTO_TICKERS) + (PIVOT_DAY,),
)
for r in risk_orders:
    print(f"\n  order_id={r['id']} {r['ticker']:6s} {r['side']:4s} qty={r['qty']:.2f} "
          f"status={r['status']} cycle={r['cycle_id']}")
    rc = r["risk_check_result"] or ""
    # Pretty-print json si possible
    try:
        j = json.loads(rc)
        for k, v in list(j.items())[:8]:
            vs = str(v)[:100]
            print(f"    {k}: {vs}")
    except Exception:
        print(f"    raw: {rc[:300]}")


# ====================================================================
# 8B.7 - SECTION E : quand a ete deploye le convergence prod ?
# ====================================================================
print("\n" + "=" * 78)
print("[8B.7-E] Historique convergence_snapshots prod - quand a debute ?")
print("=" * 78)
row = cur.execute(
    "SELECT MIN(cycle_id) min_c, MAX(cycle_id) max_c, COUNT(*) n "
    "FROM convergence_snapshots"
).fetchone()
print(f"  convergence_snapshots : min_cycle={row['min_c']}  max={row['max_c']}  n={row['n']}")

# Distribution par jour
print(f"\n  Distribution convergence_snapshots par jour (20 derniers jours) :")
days_conv = safe_select(
    "SELECT substr(cycle_id, 1, 8) day, COUNT(*) n, "
    "       SUM(forced_exit) fe, SUM(drift_block) dr "
    "FROM convergence_snapshots "
    "WHERE substr(cycle_id, 1, 8) >= ? "
    "GROUP BY substr(cycle_id, 1, 8) ORDER BY day DESC LIMIT 25",
    ("20260520",),
)
for r in days_conv:
    print(f"    {r['day']}  n={r['n']:4d}  fe={r['fe'] or 0:3d}  dr={r['dr'] or 0:3d}")

# ====================================================================
# 8B.6 - SECTION F : portfolio_targets prod avant/apres pivot
# ====================================================================
print("\n" + "=" * 78)
print(f"[8B.6-F] portfolio_targets prod autour du pivot day")
print("=" * 78)

pt_cols = [r["name"] for r in cur.execute("PRAGMA table_info(portfolio_targets)").fetchall()]
print(f"  schema cols={pt_cols}")
print(f"\n  Distribution snapshot_id autour du pivot day :")
pt_days = safe_select(
    "SELECT snapshot_id, COUNT(*) n, "
    "       AVG(target_weight_pct) avg_w, MAX(target_weight_pct) max_w "
    "FROM portfolio_targets "
    "GROUP BY snapshot_id ORDER BY snapshot_id DESC LIMIT 10",
)
for r in pt_days:
    print(f"    {(r['snapshot_id'] or 'NULL')[:40]:40s} n={r['n']:3d} "
          f"avg_w={(r['avg_w'] or 0):.2f}% max_w={(r['max_w'] or 0):.2f}%")


con.close()
print("\n" + "=" * 78)
print("DONE - analyse 8B.6 + 8B.7 complete")
print("=" * 78)
