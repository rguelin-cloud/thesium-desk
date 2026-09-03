"""Diag Phase 9.7 backfill 90j : verifier sources disponibles.

shadow_engine lit :
  - convergence_snapshots (cycle_id, ticker, convergence_pct, forced_exit, target_weight_pct)
  - portfolio_targets_history (cycle_id, ticker, target_weight_pct, qty_current)
  - shadow_variants (variants actifs)

Pour 90j on a besoin d'une source de :
  1. cycles distincts par jour (1 cycle/jour suffit)
  2. convergence_snapshots (deja en DB ? populate par scheduler ?)
  3. portfolio_targets_history (deja en DB ? ou replay_targets_history Jalon 8B.4 ?)
"""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# 1. convergence_snapshots couverture
print("=== convergence_snapshots ===")
cur.execute("""
    SELECT COUNT(*) total, COUNT(DISTINCT cycle_id) cycles,
           MIN(SUBSTR(cycle_id,1,8)) min_day, MAX(SUBSTR(cycle_id,1,8)) max_day
    FROM convergence_snapshots
""")
r = cur.fetchone()
print(f"  rows={r[0]} cycles={r[1]} day_min={r[2]} day_max={r[3]}")
# Cycles par jour
cur.execute("""
    SELECT SUBSTR(cycle_id,1,8) day, COUNT(DISTINCT cycle_id) n_cycles
    FROM convergence_snapshots
    GROUP BY day ORDER BY day DESC LIMIT 15
""")
print("  Top 15 days (recent) :")
for r in cur.fetchall():
    print(f"    {r[0]}  n_cycles={r[1]}")

# 2. portfolio_targets_history (alimente par scheduler prod)
print("\n=== portfolio_targets_history ===")
cur.execute("PRAGMA table_info(portfolio_targets_history)")
cols = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols}")
cur.execute("""
    SELECT COUNT(*) total, COUNT(DISTINCT cycle_id) cycles,
           MIN(SUBSTR(cycle_id,1,8)) min_day, MAX(SUBSTR(cycle_id,1,8)) max_day
    FROM portfolio_targets_history
""")
r = cur.fetchone()
print(f"  rows={r[0]} cycles={r[1]} day_min={r[2]} day_max={r[3]}")

# 3. replay_targets_history (Jalon 8B.4)
print("\n=== replay_targets_history (Jalon 8B.4) ===")
cur.execute("PRAGMA table_info(replay_targets_history)")
cols = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols}")
cur.execute("""
    SELECT COUNT(*) total, COUNT(DISTINCT cycle_id_replay) cycles,
           COUNT(DISTINCT run_id) runs,
           COUNT(DISTINCT day_t) days,
           MIN(day_t) day_min, MAX(day_t) day_max
    FROM replay_targets_history
""")
r = cur.fetchone()
print(f"  rows={r[0]} cycles_replay={r[1]} runs={r[2]} days={r[3]} day_min={r[4]} day_max={r[5]}")
# Listes des runs
cur.execute("""
    SELECT run_id, COUNT(DISTINCT cycle_id_replay) cycles, COUNT(DISTINCT day_t) days,
           MIN(day_t) min_d, MAX(day_t) max_d
    FROM replay_targets_history
    GROUP BY run_id ORDER BY run_id DESC
""")
print("  Runs :")
for r in cur.fetchall():
    print(f"    run_id={r[0]} cycles={r[1]} days={r[2]} [{r[3]} -> {r[4]}]")

# 4. Verifier sample colonne content
print("\n=== replay_targets_history sample (3 rows run_id=15) ===")
cur.execute("SELECT * FROM replay_targets_history WHERE run_id=15 LIMIT 3")
rcols = [d[0] for d in cur.description]
print("  " + " | ".join(rcols))
for r in cur.fetchall():
    print("  " + " | ".join(str(v)[:25] for v in r))

# 5. Shadow engine code anchors : qu'est-ce qu'il lit exactement ?
print("\n=== shadow_engine.py imports/queries ===")
import os
with open(os.path.join(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk", "shadow_engine.py"), "rb") as f:
    se_src = f.read().decode("utf-8-sig", errors="replace")
import re
# Cherche SELECT FROM
for m in re.finditer(r"FROM\s+(\w+)", se_src):
    print(f"  FROM {m.group(1)}")

conn.close()
