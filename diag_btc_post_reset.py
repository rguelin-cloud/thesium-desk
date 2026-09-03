# diag_btc_post_reset.py
# Apres reset, BTC absent des 9 ordres pending. On cherche pourquoi.

import sqlite3, os, json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 70)
print("1) ETAT portfolio_targets actuel")
print("=" * 70)
for r in c.execute("SELECT * FROM portfolio_targets ORDER BY ticker"):
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("2) Dernier snapshot portfolio_targets_history")
print("=" * 70)
rows = list(c.execute(
    "SELECT snapshot_id, MAX(created_at) AS last_ts "
    "FROM portfolio_targets_history GROUP BY snapshot_id "
    "ORDER BY last_ts DESC LIMIT 1"
))
if rows:
    snap = rows[0]["snapshot_id"]
    print(f"snapshot_id = {snap}  ({rows[0]['last_ts']})")
    for r in c.execute(
        "SELECT ticker, score, target_weight_pct, components_json, included, cap_floor_applied "
        "FROM portfolio_targets_history WHERE snapshot_id=? ORDER BY ticker",
        (snap,)
    ):
        try:
            comps = json.loads(r["components_json"])
        except Exception:
            comps = {}
        r_norm = comps.get("R_norm", "?")
        c_norm = comps.get("C_norm", "?")
        marker = " ### " if r["ticker"] == "BTC" else "     "
        print(f"  {marker}{r['ticker']:<8} score={r['score']:<8} tw={r['target_weight_pct']:<5} "
              f"incl={r['included']} R_norm={r_norm} C_norm={c_norm} "
              f"cap_floor={r['cap_floor_applied']!r}")

print()
print("=" * 70)
print("3) Dernier cycle reconciliation - BTC particulierement")
print("=" * 70)
last_cycle_rows = list(c.execute(
    "SELECT cycle_id, MAX(created_at) AS last_ts FROM cycle_reconciliation_log "
    "GROUP BY cycle_id ORDER BY last_ts DESC LIMIT 1"
))
if last_cycle_rows:
    last_cycle = last_cycle_rows[0]["cycle_id"]
    print(f"Dernier cycle: {last_cycle} ({last_cycle_rows[0]['last_ts']})\n")
    for r in c.execute(
        "SELECT ticker, action, qty_in, side_in, delta_signal_pct, delta_target_pct, reason "
        "FROM cycle_reconciliation_log WHERE cycle_id=? ORDER BY ticker",
        (last_cycle,)
    ):
        marker = " ### " if r["ticker"] == "BTC" else "     "
        print(f"  {marker}{r['ticker']:<8} {r['action']:<22} qty_in={r['qty_in']:<10} "
              f"side={r['side_in']} dsig={r['delta_signal_pct']} dtgt={r['delta_target_pct']}")
        if r["ticker"] == "BTC" or r["action"] in ("DROPPED", "REJECTED"):
            print(f"           raison: {r['reason']}")
else:
    print("Aucun cycle apres reset")

print()
print("=" * 70)
print("4) Theses creees apres reset")
print("=" * 70)
# Quel est le timestamp du reset ? Le row le plus recent de portfolio_state
ts_reset_row = c.execute("SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1").fetchone()
if ts_reset_row:
    ts_reset = dict(ts_reset_row).get("created_at") or dict(ts_reset_row).get("updated_at") or "2026-05-25 10:00:00"
    print(f"Reference reset ts ~ {ts_reset}\n")
    q = """
    SELECT t.id, i.ticker, t.status, t.side, t.quantity_pct, t.conviction, t.created_at
    FROM theses t LEFT JOIN instruments i ON t.instrument_id = i.id
    WHERE t.created_at >= ?
    ORDER BY t.created_at DESC, t.id DESC
    """
    for r in c.execute(q, (ts_reset,)):
        marker = " ### " if r["ticker"] == "BTC" else "     "
        print(f"  {marker}thesis_id={r['id']:<5} {str(r['ticker']):<6} status={r['status']:<14} "
              f"side={str(r['side']):<5} qty_pct={r['quantity_pct']} conv={r['conviction']} {r['created_at']}")

print()
print("=" * 70)
print("5) Tous les ordres post-reset (BTC compris ou non)")
print("=" * 70)
for r in c.execute(
    "SELECT o.id, i.ticker, o.side, o.quantity, o.status, o.created_at, o.thesis_id "
    "FROM orders o LEFT JOIN instruments i ON o.instrument_id = i.id "
    "ORDER BY o.created_at DESC, o.id DESC LIMIT 20"
):
    marker = " ### " if r["ticker"] == "BTC" else "     "
    print(f"  {marker}order_id={r['id']:<4} {str(r['ticker']):<6} {r['side']:<5} qty={r['quantity']:<10} "
          f"status={r['status']:<22} thesis={r['thesis_id']} {r['created_at']}")

print()
print("=" * 70)
print("6) Position BTC dans portfolio_positions (devrait etre 0 ou absent)")
print("=" * 70)
for r in c.execute(
    "SELECT p.*, i.ticker FROM portfolio_positions p "
    "LEFT JOIN instruments i ON p.instrument_id = i.id"
):
    print(f"  {dict(r)}")

c.close()
