"""
BACKFILL convergence_snapshots PROD depuis replay_convergence_snapshots run_id=15.

Strategie :
- Convergence est STABLE jour par jour (replay = 36 snapshots/jour pour 1 cycle replay).
- On copie ces 36 snapshots vers TOUS les cycles prod du meme jour.
- Idempotent : skip si (cycle_id, ticker) deja present.
- Marker source : created_at = 'BACKFILL_REPLAY_RUN15_<original_created_at>'

Fenetre cible : 2026-03-14 -> 2026-06-08 (15 jours avec theses + 13 jours avec cycles prod).
Insertion attendue : ~2,100 rows.

Usage :
  py -3.13 .\\nextones-backfill-convergence-from-replay-v1.py --dry-run
  py -3.13 .\\nextones-backfill-convergence-from-replay-v1.py --apply
"""
import sqlite3
import os
import sys
import argparse
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_FILE = os.path.join(DB, "thesium.db")
RUN_ID = 15
WINDOW_START_DAY = "2026-03-14"
WINDOW_END_DAY = "2026-06-08"
MARKER_PREFIX = "BACKFILL_REPLAY_RUN15"


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="effectuer les inserts (sinon dry-run)")
    p.add_argument("--dry-run", action="store_true",
                   help="dry-run (defaut)")
    return p.parse_args()


def main():
    args = parse_args()
    apply_changes = bool(args.apply)
    mode = "APPLY" if apply_changes else "DRY-RUN"

    print("=" * 78)
    print("BACKFILL convergence_snapshots <- replay run_id=" + str(RUN_ID))
    print("MODE :", mode)
    print("FENETRE :", WINDOW_START_DAY, "->", WINDOW_END_DAY)
    print("=" * 78)

    if not os.path.exists(DB_FILE):
        print("DB introuvable:", DB_FILE)
        sys.exit(1)

    con = sqlite3.connect(DB_FILE, timeout=30.0)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # Step 1 : recuperer cycles prod par jour dans la fenetre
    print("\n[1/4] Inventaire cycles prod fenetre aveugle")
    prod_cycles_by_day = {}
    rows = cur.execute(
        "SELECT DISTINCT cycle_id, substr(cycle_id,1,8) day_t "
        "FROM regime_log "
        "WHERE substr(cycle_id,1,8) BETWEEN ? AND ? "
        "ORDER BY cycle_id",
        (WINDOW_START_DAY.replace("-", ""), WINDOW_END_DAY.replace("-", ""))
    ).fetchall()
    for r in rows:
        d = r["day_t"]
        prod_cycles_by_day.setdefault(d, []).append(r["cycle_id"])
    print("  Jours :", len(prod_cycles_by_day),
          " - Cycles totaux :", sum(len(v) for v in prod_cycles_by_day.values()))

    # Step 2 : recuperer snapshots replay 1 par jour (le premier cycle_id_replay)
    print("\n[2/4] Inventaire snapshots replay par jour")
    replay_by_day = {}
    rows = cur.execute(
        "SELECT day_t, ticker, direction_consensus, n_aligned, n_present, "
        "convergence_pct, sizing_multiplier, forced_exit, drift, is_crypto, "
        "buckets_json, created_at "
        "FROM replay_convergence_snapshots "
        "WHERE run_id=? "
        "ORDER BY day_t, cycle_id_replay, ticker",
        (RUN_ID,)
    ).fetchall()
    # Garder 1 jeu de snapshots par jour (le 1er cycle_id_replay = premier vu)
    seen_pair = set()
    for r in rows:
        # day_t format '2026-05-29' -> converter en 'YYYYMMDD' pour match prod
        d_compact = r["day_t"].replace("-", "")
        key = (d_compact, r["ticker"])
        if key in seen_pair:
            continue
        seen_pair.add(key)
        replay_by_day.setdefault(d_compact, []).append(dict(r))
    print("  Jours avec snapshots replay :", len(replay_by_day))
    print("  Sample tickers par jour :")
    for d in sorted(replay_by_day.keys())[:3]:
        tks = [s["ticker"] for s in replay_by_day[d]]
        print("    " + d + " : " + str(len(tks)) + " tickers")

    # Step 3 : intersection jours prod / jours replay
    print("\n[3/4] Plan d insertion")
    common_days = sorted(set(prod_cycles_by_day.keys()) & set(replay_by_day.keys()))
    print("  Jours communs (prod inter replay) :", len(common_days))

    plan = []
    for d in common_days:
        cycles = prod_cycles_by_day[d]
        snaps = replay_by_day[d]
        for cyc in cycles:
            for sn in snaps:
                plan.append((cyc, sn))
    print("  Rows projetes :", len(plan))

    # Step 4 : verifier idempotence (rows deja presents)
    print("\n[4/4] Verification idempotence")
    existing = set()
    rows = cur.execute(
        "SELECT cycle_id, ticker FROM convergence_snapshots "
        "WHERE substr(cycle_id,1,8) BETWEEN ? AND ?",
        (WINDOW_START_DAY.replace("-", ""), WINDOW_END_DAY.replace("-", ""))
    ).fetchall()
    for r in rows:
        existing.add((r["cycle_id"], r["ticker"]))
    print("  Rows deja presents (cycle_id, ticker) :", len(existing))

    to_insert = []
    for cyc, sn in plan:
        if (cyc, sn["ticker"]) in existing:
            continue
        to_insert.append((cyc, sn))
    print("  Rows a inserer apres dedup :", len(to_insert))

    if not to_insert:
        print("\n  RIEN A FAIRE - tout est deja backfille.")
        con.close()
        return

    # Apercu
    print("\n  Apercu 5 premiers inserts prevus :")
    for cyc, sn in to_insert[:5]:
        print("    cyc=" + cyc + " tkr=" + sn["ticker"] +
              " dir=" + str(sn["direction_consensus"])[:6] +
              " fe=" + str(sn["forced_exit"]) +
              " mult=" + str(sn["sizing_multiplier"]) +
              " conv=" + str(sn["convergence_pct"]))

    if not apply_changes:
        print("\n[DRY-RUN] Aucune insertion effectuee. Relancer avec --apply.")
        con.close()
        return

    # APPLY
    print("\n[APPLY] Insertion en cours...")
    sql = (
        "INSERT INTO convergence_snapshots "
        "(cycle_id, ticker, direction_consensus, n_aligned, n_present, "
        "convergence_pct, sizing_multiplier, forced_exit, drift, is_crypto, "
        "buckets_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    now_marker = MARKER_PREFIX + "_" + datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    inserted = 0
    try:
        for cyc, sn in to_insert:
            cur.execute(sql, (
                cyc,
                sn["ticker"],
                sn["direction_consensus"],
                sn["n_aligned"],
                sn["n_present"],
                sn["convergence_pct"],
                sn["sizing_multiplier"],
                sn["forced_exit"],
                sn["drift"],
                sn["is_crypto"],
                sn["buckets_json"],
                now_marker,
            ))
            inserted += 1
        con.commit()
        print("  Inserts effectues :", inserted)
        print("  Marker created_at :", now_marker)
    except sqlite3.Error as e:
        con.rollback()
        print("  [ERR] insert rollback :", e)
        con.close()
        sys.exit(2)

    # Verification post-insert
    print("\n[VERIFICATION post-apply]")
    rows = cur.execute(
        "SELECT substr(cycle_id,1,8) day_t, COUNT(*) n, "
        "SUM(forced_exit) n_fe "
        "FROM convergence_snapshots "
        "WHERE created_at LIKE ? "
        "GROUP BY substr(cycle_id,1,8) "
        "ORDER BY day_t",
        (MARKER_PREFIX + "%",)
    ).fetchall()
    print("  Distribution par jour (backfill total) :")
    print("  day      | n_snaps | n_forced_exit")
    for r in rows:
        print("  " + r["day_t"] + " |  " + str(r["n"]) +
              "     | " + str(r["n_fe"] or 0))

    con.close()
    print("\n" + "=" * 78)
    print("DONE - backfill convergence complete")
    print("=" * 78)


if __name__ == "__main__":
    main()
