# -*- coding: utf-8 -*-
# nextones-run-replay-8b4-v1.py
# Jalon 8B.4 - Smoke-test fenetre 90 jours + benchmark vs prod.
#
# Fenetre  : 2026-03-14 -> 2026-06-12 (65 cycles ouvres attendus)
# Criteres :
#   HARD (bloquants) :
#     1. status=done
#     2. n_cycles == trading_days(start, end) - tolerance 1
#     3. integrity per-cycle : net_buy_sell_cumul == K - cash sur 100% des cycles
#     4. cash > 0 sur tous les cycles
#     5. positions_value > 0 sur >50% des cycles
#   SOFT (informatif benchmark) :
#     6. NAV final replay vs NAV final prod (2026-06-12) - delta absolu et %
#     7. Correlation trajectoire NAV sur jours de chevauchement (>=14)
#
# Usage : py -3.13 nextones-run-replay-8b4-v1.py
# 100% ASCII pur.

import sqlite3
import sys
from datetime import datetime, date, timedelta

# Imports depuis le repo prod
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)

from replay_orchestrator import ReplayOrchestrator  # noqa: E402

WINDOW_START = "2026-03-14"
WINDOW_END = "2026-06-12"
K_INITIAL = 1_000_000.0
TOL_INTEGRITY = 1.0  # $1 tolerance par cycle (slippage rounding)

# Tolerance globale sur n_cycles (jours feries NYSE non geres dans _is_trading_day)
N_CYCLES_TOL = 5


def _is_trading_day(d):
    return d.weekday() < 5


def trading_days(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    out = []
    d = start
    while d <= end:
        if _is_trading_day(d):
            out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def main():
    print("=" * 72)
    print("SMOKE-TEST 8B.4 - Replay 90 jours + benchmark vs prod")
    print("=" * 72)
    print(f"DB         : {DB}")
    print(f"Window     : {WINDOW_START} -> {WINDOW_END}")
    print(f"K initial  : ${K_INITIAL:,.2f}")
    expected_days = trading_days(WINDOW_START, WINDOW_END)
    print(f"Expected   : {len(expected_days)} cycles ouvres")

    # --------- RUN ---------
    print("\n" + "=" * 72)
    print(f"[RUN] Replay {len(expected_days)} cycles")
    print("=" * 72)
    label = "jalon-8b4-90d-" + datetime.now().strftime("%Y%m%dT%H%M%S")
    t0 = datetime.now()
    orch = ReplayOrchestrator(
        label=label,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        initial_capital=K_INITIAL,
        db_path=DB,
        verbose=False,  # silencieux pour eviter 65 dumps PCA
    )
    stats = orch.run()
    elapsed = (datetime.now() - t0).total_seconds()
    run_id = stats["run_id"]
    print(f"\n>>> run_id={run_id}  cycles={stats['cycles']}  status={stats['status']}  elapsed={elapsed:.1f}s")
    print(f"    moyenne par cycle = {elapsed / max(1, stats['cycles']):.2f}s")

    # --------- CHECKS ---------
    print("\n" + "=" * 72)
    print("[CHECKS] Validation HARD criteria")
    print("=" * 72)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    checks = []

    # 1. status
    row = cur.execute(
        "SELECT status FROM replay_runs WHERE run_id=?", (run_id,)
    ).fetchone()
    if row and row["status"] == "done":
        checks.append(("PASS", "1. status=done", f"status={row['status']}"))
    else:
        checks.append(("FAIL", "1. status=done", f"status={row['status'] if row else 'None'}"))

    # 2. n_cycles
    n_cycles = cur.execute(
        "SELECT COUNT(*) FROM replay_cycles WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    diff = abs(n_cycles - len(expected_days))
    if diff <= N_CYCLES_TOL:
        checks.append(("PASS", "2. n_cycles within tolerance",
                       f"got={n_cycles} expected~={len(expected_days)} diff={diff}"))
    else:
        checks.append(("FAIL", "2. n_cycles within tolerance",
                       f"got={n_cycles} expected~={len(expected_days)} diff={diff}"))

    # 3. integrity per-cycle : cash + sum(buy_cumul) - sum(sell_cumul) == K
    # On parcourt par day_t croissant et compare a chaque cycle.
    fills_per_cycle = cur.execute(
        "SELECT cycle_id_replay, day_t, "
        "       SUM(CASE WHEN UPPER(side)='BUY' THEN notional ELSE 0 END) buy_n, "
        "       SUM(CASE WHEN UPPER(side)='SELL' THEN notional ELSE 0 END) sell_n "
        "FROM replay_fills WHERE run_id=? GROUP BY cycle_id_replay, day_t "
        "ORDER BY day_t",
        (run_id,),
    ).fetchall()
    nav_per_cycle = {
        r["cycle_id_replay"]: r["cash"]
        for r in cur.execute(
            "SELECT cycle_id_replay, cash FROM replay_nav_history WHERE run_id=?",
            (run_id,),
        ).fetchall()
    }

    cum_buy = 0.0
    cum_sell = 0.0
    bad_cycles = []
    integrity_rows = []
    for fpc in fills_per_cycle:
        cir = fpc["cycle_id_replay"]
        cum_buy += float(fpc["buy_n"] or 0)
        cum_sell += float(fpc["sell_n"] or 0)
        cash = nav_per_cycle.get(cir)
        if cash is None:
            bad_cycles.append((cir, fpc["day_t"], "no_nav_row"))
            continue
        expected_cash = K_INITIAL - cum_buy + cum_sell
        diff_dollars = abs(cash - expected_cash)
        integrity_rows.append({
            "cir": cir, "day_t": fpc["day_t"],
            "cash": cash, "expected": expected_cash, "diff": diff_dollars,
        })
        if diff_dollars > TOL_INTEGRITY:
            bad_cycles.append((cir, fpc["day_t"], f"diff=${diff_dollars:,.2f}"))

    if not bad_cycles:
        checks.append(("PASS", "3. integrity per-cycle (cumul)",
                       f"all {len(integrity_rows)} cycles within ${TOL_INTEGRITY:.2f}"))
    else:
        checks.append(("FAIL", "3. integrity per-cycle (cumul)",
                       f"{len(bad_cycles)} cycles failed (first: {bad_cycles[0]})"))

    # 4. cash > 0
    min_cash = cur.execute(
        "SELECT MIN(cash) FROM replay_nav_history WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    if min_cash is not None and min_cash > 0:
        checks.append(("PASS", "4. cash > 0 sur tous cycles", f"min_cash=${min_cash:,.2f}"))
    else:
        checks.append(("FAIL", "4. cash > 0 sur tous cycles", f"min_cash={min_cash}"))

    # 5. positions_value > 0 sur >50% des cycles
    n_pos_rows = cur.execute(
        "SELECT COUNT(*) FROM replay_nav_history "
        "WHERE run_id=? AND positions_value > 0",
        (run_id,),
    ).fetchone()[0]
    n_total = cur.execute(
        "SELECT COUNT(*) FROM replay_nav_history WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    pct = (100.0 * n_pos_rows / n_total) if n_total else 0
    if pct >= 50.0:
        checks.append(("PASS", "5. positions_value>0 sur >=50%", f"{n_pos_rows}/{n_total} = {pct:.1f}%"))
    else:
        checks.append(("FAIL", "5. positions_value>0 sur >=50%", f"{n_pos_rows}/{n_total} = {pct:.1f}%"))

    # Affichage HARD checks
    n_hard_pass = sum(1 for c in checks if c[0] == "PASS")
    n_hard_total = len(checks)
    for status, label, detail in checks:
        print(f"  [{status}] {label:42s}  {detail}")

    # --------- BENCHMARK SOFT ---------
    print("\n" + "=" * 72)
    print("[BENCHMARK SOFT] Replay vs prod")
    print("=" * 72)

    # NAV final replay au WINDOW_END
    last_nav_row = cur.execute(
        "SELECT day_t, nav, cash, positions_value FROM replay_nav_history "
        "WHERE run_id=? ORDER BY day_t DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    nav_replay_final = last_nav_row["nav"] if last_nav_row else None
    day_replay_final = last_nav_row["day_t"] if last_nav_row else None
    print(f"  Replay  final : day_t={day_replay_final}  NAV=${nav_replay_final:,.2f}")
    if nav_replay_final:
        total_return_replay = 100.0 * (nav_replay_final - K_INITIAL) / K_INITIAL
        print(f"                  total_return = {total_return_replay:+.2f}%")

    # NAV prod a la meme date
    prod_row = cur.execute(
        "SELECT date, total_value FROM portfolio_history "
        "WHERE date=? ORDER BY date DESC LIMIT 1",
        (day_replay_final,),
    ).fetchone()
    if prod_row:
        nav_prod = prod_row["total_value"]
        print(f"  Prod    final : date={prod_row['date']}  NAV=${nav_prod:,.2f}")
        delta = nav_replay_final - nav_prod
        delta_pct = 100.0 * delta / nav_prod
        print(f"  Delta replay-prod : ${delta:,.2f}  ({delta_pct:+.2f}%)")
    else:
        print(f"  Prod    final : pas de portfolio_history a la date {day_replay_final}")
        nav_prod = None

    # Trajectoire chevauchement
    print(f"\n  Trajectoire chevauchement (replay vs prod) :")
    overlap = cur.execute(
        "SELECT r.day_t, r.nav nav_replay, p.total_value nav_prod "
        "FROM replay_nav_history r "
        "INNER JOIN portfolio_history p ON p.date = r.day_t "
        "WHERE r.run_id=? ORDER BY r.day_t",
        (run_id,),
    ).fetchall()
    print(f"    n_overlap = {len(overlap)}")
    if overlap:
        # Correlation simple
        rs = [r["nav_replay"] for r in overlap]
        ps = [r["nav_prod"] for r in overlap]
        if len(rs) >= 2:
            mr = sum(rs) / len(rs)
            mp = sum(ps) / len(ps)
            num = sum((rs[i] - mr) * (ps[i] - mp) for i in range(len(rs)))
            den_r = (sum((x - mr) ** 2 for x in rs)) ** 0.5
            den_p = (sum((x - mp) ** 2 for x in ps)) ** 0.5
            corr = (num / (den_r * den_p)) if (den_r > 0 and den_p > 0) else None
            print(f"    Correlation NAV replay vs prod = "
                  f"{corr:+.4f}" if corr is not None else "    Correlation : NA")
        # Affiche premieres + dernieres lignes
        print(f"    day_t       | NAV replay     | NAV prod       | delta")
        print(f"    " + "-" * 60)
        sample = overlap if len(overlap) <= 8 else overlap[:3] + overlap[-3:]
        for r in sample:
            d = r["nav_replay"] - r["nav_prod"]
            print(f"    {r['day_t']}  | ${r['nav_replay']:>12,.2f} | "
                  f"${r['nav_prod']:>12,.2f} | ${d:>+10,.2f}")

    # --------- VERDICT ---------
    print("\n" + "=" * 72)
    print("VERDICT 8B.4")
    print("=" * 72)
    print(f"  HARD  : {n_hard_pass}/{n_hard_total}")
    for status, label, _ in checks:
        print(f"    [{status}] {label}")
    print(f"  SOFT (benchmark) : informatif uniquement")

    if n_hard_pass == n_hard_total:
        print(f"\n  >>> Jalon 8B.4 PASS - Replay 90j event-driven OPERATIONNEL")
    else:
        print(f"\n  >>> {n_hard_total - n_hard_pass} HARD checks failed - investiguer")

    con.close()


if __name__ == "__main__":
    main()
