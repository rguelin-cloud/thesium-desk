"""
shadow_backfill.py - Phase 9.7 - Backfill historique shadow_engine + shadow_fills.

Strategie :
  1. Selectionne 1 cycle par jour (le DERNIER de chaque jour) depuis convergence_snapshots
  2. Pour chaque cycle :
     a. Lance shadow_engine (genere shadow_cycle_snapshots + shadow_orders)
     b. Lance shadow_simulate_fills (genere shadow_fills sur J+1)
  3. Stats finales : n_cycles, n_orders, n_fills total

Idempotent grace au DELETE WHERE des sous-scripts (engine + fills).
Safe-fail : log par cycle, continue si un fail.
"""
import sqlite3
import subprocess
import sys
import os
import time
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DB_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def get_last_cycle_per_day(db_path, day_min=None, day_max=None):
    """Retourne liste de (day, cycle_id) : 1 cycle par jour (le plus tardif).

    Source : convergence_snapshots
    """
    conn = sqlite3.connect(db_path, timeout=30)
    cur = conn.cursor()
    sql = """
        SELECT SUBSTR(cycle_id,1,8) day, MAX(cycle_id) last_cycle
        FROM convergence_snapshots
        WHERE 1=1
    """
    params = []
    if day_min:
        sql += " AND SUBSTR(cycle_id,1,8) >= ?"
        params.append(day_min)
    if day_max:
        sql += " AND SUBSTR(cycle_id,1,8) <= ?"
        params.append(day_max)
    sql += " GROUP BY day ORDER BY day"
    cur.execute(sql, params)
    out = cur.fetchall()
    conn.close()
    return out


def run_subprocess(script_name, cycle_id, db_path, timeout=180):
    script_path = os.path.join(ROOT, script_name)
    if not os.path.exists(script_path):
        return -1, f"script not found: {script_path}"
    cmd = [sys.executable, script_path, "--cycle-id", cycle_id, "--db", db_path]
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        return r.returncode, (r.stderr[-300:] if r.stderr else "")
    except subprocess.TimeoutExpired:
        return -2, "TIMEOUT"
    except Exception as e:
        return -3, f"EXC {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument("--day-min", default=None, help="format YYYYMMDD")
    ap.add_argument("--day-max", default=None, help="format YYYYMMDD")
    ap.add_argument("--skip-fills", action="store_true",
                    help="ne lance pas shadow_simulate_fills (engine seulement)")
    args = ap.parse_args()

    print("=" * 78)
    print("SHADOW BACKFILL - Phase 9.7")
    print(f"DB      : {args.db}")
    print(f"Range   : {args.day_min or '(open)'} -> {args.day_max or '(open)'}")
    print(f"Fills   : {'SKIP' if args.skip_fills else 'YES'}")
    print("=" * 78)

    # 1. Selection cycles
    cycles = get_last_cycle_per_day(args.db, args.day_min, args.day_max)
    print(f"\n[INFO] {len(cycles)} cycles selectionnes (1/jour)")
    for d, c in cycles:
        print(f"  {d}  {c}")

    if not cycles:
        print("\n[WARN] aucun cycle a traiter")
        return 0

    # 2. Boucle
    t0 = time.time()
    n_engine_ok = 0
    n_fills_ok = 0
    n_fail = 0
    errors = []

    print(f"\n{'='*78}")
    print(f"PROCESSING {len(cycles)} cycles...")
    print("=" * 78)

    for idx, (day, cycle_id) in enumerate(cycles, 1):
        print(f"\n[{idx}/{len(cycles)}] day={day} cycle={cycle_id}")

        # a. shadow_engine
        rc, err = run_subprocess("shadow_engine.py", cycle_id, args.db)
        if rc == 0:
            print(f"  engine OK")
            n_engine_ok += 1
        else:
            print(f"  engine FAIL rc={rc} : {err[:150]}")
            n_fail += 1
            errors.append((cycle_id, "engine", rc, err[:100]))
            continue

        # b. shadow_simulate_fills (sauf si skip)
        if not args.skip_fills:
            rc, err = run_subprocess("shadow_simulate_fills.py", cycle_id, args.db)
            if rc == 0:
                print(f"  fills  OK")
                n_fills_ok += 1
            else:
                print(f"  fills  FAIL rc={rc} : {err[:150]}")
                errors.append((cycle_id, "fills", rc, err[:100]))

    elapsed = time.time() - t0

    # 3. Stats finales
    print(f"\n{'='*78}")
    print("BACKFILL DONE")
    print("=" * 78)
    print(f"  cycles processed   : {len(cycles)}")
    print(f"  engine OK          : {n_engine_ok}/{len(cycles)}")
    if not args.skip_fills:
        print(f"  fills OK           : {n_fills_ok}/{len(cycles)}")
    print(f"  failures           : {n_fail}")
    print(f"  elapsed            : {elapsed:.1f}s ({elapsed/max(len(cycles),1):.1f}s/cycle)")

    if errors:
        print(f"\n[ERRORS] {len(errors)} :")
        for cid, stage, rc, msg in errors[:10]:
            print(f"  {cid} [{stage}] rc={rc} : {msg}")

    # 4. Stats DB finales
    conn = sqlite3.connect(args.db, timeout=30)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shadow_cycle_snapshots")
    n_snaps = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM shadow_orders")
    n_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM shadow_fills")
    n_fills = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT cycle_id) FROM shadow_cycle_snapshots")
    n_cycles_dist = cur.fetchone()[0]
    conn.close()

    print(f"\n[DB STATE] cycles_distinct={n_cycles_dist} snaps={n_snaps} orders={n_orders} fills={n_fills}")
    print("=" * 78)
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
