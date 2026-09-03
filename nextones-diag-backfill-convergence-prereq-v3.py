"""
DIAG pre-backfill v3 - corrige format cycle_id_replay (int)
+ ajoute mapping cycle_id_prod <-> cycle_id_replay pour la fenetre aveugle.
"""
import sqlite3
import os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_FILE = os.path.join(DB, "thesium.db")
RUN_ID = 15
WINDOW_START_DAY = "2026-03-14"
WINDOW_END_DAY = "2026-06-08"


con = sqlite3.connect(DB_FILE)
con.row_factory = sqlite3.Row
cur = con.cursor()


print("=" * 78)
print("[E v3] Convergence REPLAY tickers crypto pivot day +/-")
print("=" * 78)
rows = cur.execute(
    "SELECT day_t, cycle_id_replay, cycle_id_prod, ticker, "
    "direction_consensus, forced_exit, sizing_multiplier, convergence_pct, is_crypto "
    "FROM replay_convergence_snapshots "
    "WHERE run_id=? AND day_t BETWEEN '2026-05-28' AND '2026-06-01' "
    "AND ticker IN ('BTC','ETH','SOL','LINK','AMZN','GOOGL','MSFT') "
    "ORDER BY day_t, ticker",
    (RUN_ID,)
).fetchall()
print("  day_t      | cyc_rep | cyc_prod              | tkr   | dir    | fe | mult  | conv | crypto")
print("  " + "-" * 100)
for r in rows:
    print("  {} | {!s:>7} | {!s:21} | {:5s} | {:6s} |  {} | {:4.2f}  | {:.2f} |  {}".format(
        r["day_t"], r["cycle_id_replay"], r["cycle_id_prod"] or "-",
        r["ticker"], (r["direction_consensus"] or "?")[:6],
        r["forced_exit"], r["sizing_multiplier"] or 0,
        r["convergence_pct"] or 0,
        r["is_crypto"]
    ))


print()
print("=" * 78)
print("[F] Mapping cycle_id_prod -> cycle_id_replay sur fenetre aveugle")
print("=" * 78)
# Voir combien de cycle_id_prod sont presents dans replay run_id=15
rows = cur.execute(
    "SELECT day_t, cycle_id_replay, cycle_id_prod, COUNT(*) n_snaps, "
    "SUM(forced_exit) n_fe "
    "FROM replay_convergence_snapshots "
    "WHERE run_id=? AND day_t BETWEEN ? AND ? "
    "GROUP BY day_t, cycle_id_replay, cycle_id_prod "
    "ORDER BY day_t",
    (RUN_ID, WINDOW_START_DAY, WINDOW_END_DAY)
).fetchall()
print("  Mappings disponibles :", len(rows), "(cycle_replay = 1 par jour)")
print("  day_t      | cyc_rep | cyc_prod              | n_snaps | n_fe")
for r in rows[-20:]:
    print("  {} | {!s:>7} | {!s:21} | {:6d}  | {}".format(
        r["day_t"], r["cycle_id_replay"], r["cycle_id_prod"] or "-",
        r["n_snaps"], r["n_fe"] or 0
    ))


print()
print("=" * 78)
print("[G] Cycles prod fenetre aveugle vs cycles replay (qui manque ?)")
print("=" * 78)
# Cycles prod (regime_log) entre 2026-05-25 et 2026-06-08
prod_cycles = set(r[0] for r in cur.execute(
    "SELECT DISTINCT cycle_id FROM regime_log "
    "WHERE substr(cycle_id,1,8) BETWEEN '20260525' AND '20260608'"
).fetchall())

# Cycles prod mappes dans replay run_id=15
replay_prod_cycles = set(r[0] for r in cur.execute(
    "SELECT DISTINCT cycle_id_prod FROM replay_convergence_snapshots "
    "WHERE run_id=? AND day_t BETWEEN '2026-05-25' AND '2026-06-08' "
    "AND cycle_id_prod IS NOT NULL",
    (RUN_ID,)
).fetchall())

inter = prod_cycles & replay_prod_cycles
missing = prod_cycles - replay_prod_cycles
print("  prod_cycles in window :", len(prod_cycles))
print("  replay maps to prod   :", len(replay_prod_cycles))
print("  intersection          :", len(inter))
print("  prod cycles SANS replay convergence :", len(missing))
print("  Sample missing :")
for c in sorted(missing)[:20]:
    print("    ", c)


print()
print("=" * 78)
print("[H] schema convergence_snapshots prod (cible backfill) - confirmation finale")
print("=" * 78)
cols = [(r[1], r[2], r[3], r[4]) for r in cur.execute("PRAGMA table_info(convergence_snapshots)").fetchall()]
print("  col_name | type | notnull | default")
for n, t, nn, d in cols:
    print("    {:25s} {:10s} nn={} default={}".format(n, t, nn, d))


print()
print("=" * 78)
print("[I] Estimation rows a inserer (replay run_id=15 mappes vers prod fenetre)")
print("=" * 78)
n = cur.execute(
    "SELECT COUNT(*) FROM replay_convergence_snapshots "
    "WHERE run_id=? AND day_t BETWEEN '2026-05-25' AND '2026-06-08' "
    "AND cycle_id_prod IS NOT NULL",
    (RUN_ID,)
).fetchone()[0]
print("  rows transferable replay->prod (fenetre aveugle complete) :", n)

# Total rows replay run_id=15 (toute la fenetre 2026-03-16 -> 2026-06-12)
n_full = cur.execute(
    "SELECT COUNT(*) FROM replay_convergence_snapshots "
    "WHERE run_id=?",
    (RUN_ID,)
).fetchone()[0]
print("  rows totaux replay run_id=15 :", n_full)

con.close()
print()
print("=" * 78)
print("DONE - diag v3 ready for backfill")
print("=" * 78)
