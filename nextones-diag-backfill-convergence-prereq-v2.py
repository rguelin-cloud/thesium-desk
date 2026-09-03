"""
DIAG pre-backfill v2 - inspecter compute_convergence + coverage theses + replay_convergence_snapshots
Objectif : valider que backfill est codable proprement.
"""
import sqlite3
import os
import re
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_FILE = os.path.join(DB, "thesium.db")
MOD = os.path.join(DB, "convergence_engine.py")
WINDOW_START = "20260314"
WINDOW_END = "20260608"


print("=" * 78)
print("[A] Signature complete compute_convergence + save_convergence_snapshot")
print("=" * 78)

with open(MOD, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.split("\n")

# Extraire la def compute_convergence avec params jusqu a -> ou :
for fname in ("compute_convergence", "save_convergence_snapshot",
              "_load_agent_burst", "_get_burst_window"):
    for i, line in enumerate(lines):
        if line.lstrip().startswith("def " + fname + "("):
            # capturer signature multi-ligne
            j = i
            sig_lines = []
            depth = 0
            started = False
            while j < len(lines) and j < i + 30:
                s = lines[j]
                sig_lines.append(s)
                for c in s:
                    if c == "(":
                        depth += 1
                        started = True
                    elif c == ")":
                        depth -= 1
                if started and depth == 0:
                    break
                j += 1
            print("\n  L" + str(i + 1) + ": " + fname)
            for s in sig_lines:
                print("    " + s.rstrip())
            break


print()
print("=" * 78)
print("[B] Coverage theses dans fenetre aveugle (par created_at)")
print("=" * 78)

con = sqlite3.connect(DB_FILE)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Distribution par jour created_at sur fenetre
rows = cur.execute(
    "SELECT substr(created_at,1,10) day_t, "
    "COUNT(*) n, "
    "COUNT(DISTINCT instrument_id) n_inst, "
    "COUNT(DISTINCT agent_type) n_agents "
    "FROM theses "
    "WHERE substr(created_at,1,10) BETWEEN '2026-03-14' AND '2026-06-08' "
    "GROUP BY substr(created_at,1,10) "
    "ORDER BY day_t"
).fetchall()
print("  Jours avec theses dans fenetre aveugle :", len(rows))
print("  day_t      | n_theses | n_inst | n_agent_types")
print("  " + "-" * 55)
total_theses = 0
for r in rows:
    total_theses += r["n"]
    print("  {} |   {:4d}   |   {:3d}  |     {}".format(
        r["day_t"], r["n"], r["n_inst"], r["n_agents"]
    ))
print("  TOTAL :", total_theses, "theses")

# Distribution par agent_type sur la fenetre
print("\n  Agent_types dans la fenetre (volumes) :")
rows = cur.execute(
    "SELECT agent_type, COUNT(*) n FROM theses "
    "WHERE substr(created_at,1,10) BETWEEN '2026-03-14' AND '2026-06-08' "
    "GROUP BY agent_type ORDER BY n DESC"
).fetchall()
for r in rows:
    print("    {:25s} n={}".format(r["agent_type"] or "?", r["n"]))


print()
print("=" * 78)
print("[C] replay_convergence_snapshots - schema + coverage")
print("=" * 78)
cols = [r[1] for r in cur.execute("PRAGMA table_info(replay_convergence_snapshots)").fetchall()]
print("  schema cols=", cols)
n = cur.execute("SELECT COUNT(*) FROM replay_convergence_snapshots").fetchone()[0]
print("  total rows :", n)

# Distinct run_ids
rows = cur.execute(
    "SELECT run_id, COUNT(*) n, MIN(day_t) min_day, MAX(day_t) max_day "
    "FROM replay_convergence_snapshots GROUP BY run_id ORDER BY run_id"
).fetchall()
print("\n  Par run_id :")
for r in rows:
    print("    run_id={} n={} day {} -> {}".format(
        r["run_id"], r["n"], r["min_day"], r["max_day"]
    ))

# Distribution par jour pour run_id=15
print("\n  Distribution par jour pour run_id=15 (notre jalon 8B.4) :")
rows = cur.execute(
    "SELECT day_t, COUNT(*) n, SUM(forced_exit) n_fe "
    "FROM replay_convergence_snapshots WHERE run_id=15 "
    "GROUP BY day_t ORDER BY day_t LIMIT 20"
).fetchall()
for r in rows:
    print("    {} : n={} fe={}".format(r["day_t"], r["n"], r["n_fe"] or 0))


print()
print("=" * 78)
print("[D] Burst window detection - exemple cycle 20260529-085707")
print("=" * 78)
# Quelles theses sont 'burst' avant ce cycle ?
# created_at autour de '2026-05-29 08:57:07' / 30 min avant
rows = cur.execute(
    "SELECT id, instrument_id, agent_type, substr(created_at,1,19) ts, "
    "proposed_action, conviction_score "
    "FROM theses "
    "WHERE created_at BETWEEN '2026-05-29 08:00:00' AND '2026-05-29 09:00:00' "
    "ORDER BY created_at LIMIT 30"
).fetchall()
print("  Theses dans burst window 08:00-09:00 du 29/05 :", len(rows))
for r in rows[:30]:
    print("    L{:5d} inst={:4d} {:15s} {} act={:8s} conv={}".format(
        r["id"], r["instrument_id"] or 0, r["agent_type"] or "?",
        r["ts"], (r["proposed_action"] or "?")[:8],
        r["conviction_score"]
    ))


print()
print("=" * 78)
print("[E] Comparaison replay_convergence vs prod - meme conclusion ?")
print("=" * 78)
# Sample : pour BTC autour 20260529, qu a dit le replay ?
rows = cur.execute(
    "SELECT run_id, day_t, cycle_id_replay, ticker, "
    "direction_consensus, forced_exit, sizing_multiplier, convergence_pct "
    "FROM replay_convergence_snapshots "
    "WHERE run_id=15 AND day_t BETWEEN '2026-05-28' AND '2026-06-01' "
    "AND ticker IN ('BTC','ETH','SOL','LINK','AMZN','GOOGL','MSFT') "
    "ORDER BY day_t, ticker"
).fetchall()
print("  Convergence REPLAY (run_id=15) tickers crypto pivot day +/-:")
print("  day_t      | cycle_replay         | tkr   | dir   | fe | mult | conv")
for r in rows:
    print("  {} | {:20s} | {:5s} | {:5s} |  {} | {:4.2f} | {:.2f}".format(
        r["day_t"], r["cycle_id_replay"] or "?", r["ticker"],
        (r["direction_consensus"] or "?")[:5],
        r["forced_exit"], r["sizing_multiplier"] or 0,
        r["convergence_pct"] or 0
    ))

con.close()
print()
print("=" * 78)
print("DONE - diag v2 pre-backfill convergence")
print("=" * 78)
