# Apres patch caps+smoothing : verifier que :
#   1. target_universe.max_weight_pct sont bien a 7.0/5.0/3.0
#   2. params_json.smoothing_max_delta_pct = 2.0
#   3. Le dernier cycle a recalcule les targets
#   4. portfolio_targets affiche les nouveaux targets (~4.5%)
#   5. Reconciler log : dernieres lignes

import sqlite3
from pathlib import Path
import json

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("[1] target_universe (apres patch)")
print("=" * 70)
rows = cur.execute("SELECT ticker, max_weight_pct, min_weight_pct FROM target_universe ORDER BY ticker").fetchall()
for r in rows:
    print(f"  {r['ticker']:<6} max={r['max_weight_pct']:.2f}  min={r['min_weight_pct']:.2f}")

print()
print("=" * 70)
print("[2] target_construction_config")
print("=" * 70)
r = cur.execute("SELECT params_json, updated_at FROM target_construction_config WHERE id=1").fetchone()
cfg = json.loads(r["params_json"])
print(f"  smoothing_max_delta_pct = {cfg.get('smoothing_max_delta_pct')}")
print(f"  budget_maintain         = {cfg.get('budget_maintain')}")
print(f"  budget_build            = {cfg.get('budget_build')}")
print(f"  beta_temp               = {cfg.get('beta_temp')}")
print(f"  updated_at              = {r['updated_at']}")

print()
print("=" * 70)
print("[3] portfolio_targets actuels")
print("=" * 70)
rows = cur.execute("""SELECT ticker, target_weight_pct, snapshot_id, updated_at, score
                      FROM portfolio_targets WHERE active=1
                      ORDER BY target_weight_pct DESC""").fetchall()
total = 0
for r in rows:
    print(f"  {r['ticker']:<6} target={r['target_weight_pct']:>6.2f}% "
          f"score={r['score']:.4f}  snap={r['snapshot_id']}  updated={r['updated_at']}")
    total += r["target_weight_pct"] or 0
print(f"\n  Sum target : {total:.2f}%")

print()
print("=" * 70)
print("[4] Tous les snapshots des dernieres heures")
print("=" * 70)
rows = cur.execute("""SELECT DISTINCT snapshot_id, regime, MAX(created_at) as last,
                             SUM(target_weight_pct) as sum_target
                      FROM portfolio_targets_history
                      GROUP BY snapshot_id
                      ORDER BY last DESC LIMIT 8""").fetchall()
for r in rows:
    print(f"  {r['snapshot_id']}  regime={r['regime']:<10} sum={r['sum_target']:.2f}%  {r['last']}")

print()
print("=" * 70)
print("[5] Dernier cycles_daily")
print("=" * 70)
rows = cur.execute("SELECT * FROM cycles_daily ORDER BY rowid DESC LIMIT 3").fetchall()
for r in rows:
    print("  " + " | ".join(f"{k}={r[k]}" for k in r.keys()))

print()
print("=" * 70)
print("[6] Reconciler log : 20 dernieres entrees")
print("=" * 70)
rows = cur.execute("""SELECT cycle_id, ticker, action, reason,
                             qty_in, side_in, conviction_max,
                             delta_signal_pct, delta_target_pct, created_at
                      FROM cycle_reconciliation_log
                      ORDER BY rowid DESC LIMIT 20""").fetchall()
for r in rows:
    print(f"  {r['created_at']} | {r['cycle_id']} | {r['ticker']:<6} | {r['action']:<25} | "
          f"conv={r['conviction_max']} side={r['side_in']:<5} "
          f"dsig={r['delta_signal_pct']:+.2f}% dtgt={r['delta_target_pct']:+.2f}%")
    print(f"      reason: {r['reason']}")

print()
print("=" * 70)
print("[7] Theses generees aujourd'hui : compte par symbole")
print("=" * 70)
today = "2026-05-29"
rows = cur.execute("""SELECT i.ticker, COUNT(*) as n, MAX(t.created_at) as last
                      FROM theses t
                      JOIN instruments i ON i.id = t.instrument_id
                      WHERE substr(t.created_at, 1, 10) = ?
                      GROUP BY i.ticker
                      ORDER BY n DESC""", (today,)).fetchall()
for r in rows:
    print(f"  {r['ticker']:<6} n={r['n']:<4} last={r['last']}")

con.close()
print("\n[DONE]")
