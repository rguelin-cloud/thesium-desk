# nextones-run-replay-8b3-v1.py
# Smoke-test Jalon 8B.3 - Execution Engine Wrapper
# Lance un replay 3 cycles (2026-06-08 / 09 / 10) puis valide :
#   1) replay_runs   : 1 nouvelle ligne, status='completed'
#   2) replay_cycles : 3 nouvelles lignes
#   3) Convergence + targets + history (sanity check 8B.2 toujours OK)
#   4) [8B.3] cash bouge   : cash_final < initial_capital ET cash_final > 0
#   5) [8B.3] orders > 0   : replay_orders non vide
#   6) [8B.3] fills  > 0   : replay_fills non vide, fill_price>0, slippage_bps>=0
#   7) [8B.3] positions>0  : replay_positions non vide (snapshot final)
#   8) [8B.3] NAV history  : 3 lignes, NAV evolue (daily_pnl renseigne)
#   9) [8B.3] Integrity    : sum(buy_notional) - sum(sell_notional) ~= K - cash_final
#
# Usage : py -3.13 nextones-run-replay-8b3-v1.py

import os
import sys
import sqlite3
import datetime

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = os.path.join(PROD_DIR, "thesium.db")
INITIAL_CAPITAL = 1_000_000.0
INTEGRITY_EPSILON = 1.0  # $1 tolerance (rounding flotant)

sys.path.insert(0, PROD_DIR)


def log(msg=""):
    print(msg, flush=True)


def section(title):
    log("")
    log("=" * 72)
    log(title)
    log("=" * 72)


def main():
    section("SMOKE-TEST 8B.3 - Execution Engine Wrapper")
    log(f"DB         : {DB_PATH}")
    log(f"Initial K  : ${INITIAL_CAPITAL:,.2f}")

    if not os.path.exists(DB_PATH):
        log("FAIL : thesium.db introuvable")
        sys.exit(1)

    # 1) Run le replay
    section("[RUN] Replay 3 cycles : 2026-06-08 / 09 / 10")
    from replay_orchestrator import ReplayOrchestrator

    orch = ReplayOrchestrator(
        prod_db_path=DB_PATH,
        initial_capital=INITIAL_CAPITAL,
        verbose=True,
    )
    run_id = orch.run_replay(
        start_date="2026-06-08",
        end_date="2026-06-10",
    )
    log(f"\n>>> run_id retourne : {run_id}")

    # 2) Verifications DB
    section("[CHECKS] Validation 9 criteres")

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    checks = []

    def check(name, ok, detail=""):
        checks.append((name, ok, detail))
        status = "PASS" if ok else "FAIL"
        log(f"  [{status}] {name:48s} {detail}")

    # 1) replay_runs : 1 ligne, status=completed
    row = cur.execute(
        "SELECT run_id, status, start_date, end_date, n_cycles FROM replay_runs WHERE run_id=?",
        (run_id,),
    ).fetchone()
    if row:
        ok = row["status"] == "completed"
        check(
            "1. replay_runs status=completed",
            ok,
            f"status={row['status']} n_cycles={row['n_cycles']}",
        )
    else:
        check("1. replay_runs status=completed", False, "row not found")

    # 2) replay_cycles : 3 lignes
    n_cycles = cur.execute(
        "SELECT COUNT(*) FROM replay_cycles WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    check("2. replay_cycles = 3", n_cycles == 3, f"n_cycles={n_cycles}")

    # 3) Convergence + targets + history (sanity 8B.2)
    n_conv = cur.execute(
        "SELECT COUNT(*) FROM replay_convergence_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    n_tgt = cur.execute(
        "SELECT COUNT(*) FROM replay_targets WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    n_hist = cur.execute(
        "SELECT COUNT(*) FROM replay_targets_history WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    check(
        "3. Convergence + targets + history (8B.2 OK)",
        n_conv > 0 and n_tgt >= 15 * 3 and n_hist > 0,
        f"conv={n_conv} targets={n_tgt} hist={n_hist}",
    )

    # 4) cash bouge
    cash_final = cur.execute(
        "SELECT cash FROM replay_nav_history WHERE run_id=? ORDER BY day_t DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    cash_final = cash_final["cash"] if cash_final else None
    if cash_final is None:
        check("4. cash bouge (< K et > 0)", False, "cash_final introuvable")
    else:
        ok = cash_final < INITIAL_CAPITAL and cash_final > 0
        check(
            "4. cash bouge (< K et > 0)",
            ok,
            f"cash_final=${cash_final:,.2f}",
        )

    # 5) orders > 0
    n_orders = cur.execute(
        "SELECT COUNT(*) FROM replay_orders WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    n_buys = cur.execute(
        "SELECT COUNT(*) FROM replay_orders WHERE run_id=? AND side='BUY'", (run_id,)
    ).fetchone()[0]
    n_sells = cur.execute(
        "SELECT COUNT(*) FROM replay_orders WHERE run_id=? AND side='SELL'", (run_id,)
    ).fetchone()[0]
    check(
        "5. replay_orders > 0",
        n_orders > 0,
        f"orders={n_orders} (BUY={n_buys} SELL={n_sells})",
    )

    # 6) fills > 0 + fill_price>0 + slippage_bps>=0
    n_fills = cur.execute(
        "SELECT COUNT(*) FROM replay_fills WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    bad_fills = cur.execute(
        "SELECT COUNT(*) FROM replay_fills WHERE run_id=? AND (fill_price<=0 OR slippage_bps<0)",
        (run_id,),
    ).fetchone()[0]
    check(
        "6. replay_fills > 0 (prix>0, slip>=0)",
        n_fills > 0 and bad_fills == 0,
        f"fills={n_fills} bad={bad_fills}",
    )

    # 7) positions > 0 (snapshot final cycle 3)
    last_cycle_replay = cur.execute(
        "SELECT MAX(cycle_id) FROM replay_cycles WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    n_pos = cur.execute(
        "SELECT COUNT(*) FROM replay_positions WHERE run_id=? AND cycle_id_replay=?",
        (run_id, last_cycle_replay),
    ).fetchone()[0]
    check(
        "7. replay_positions (snapshot final) > 0",
        n_pos > 0,
        f"positions_final={n_pos}",
    )

    # 8) NAV history : 3 lignes, NAV evolue
    nav_rows = cur.execute(
        "SELECT day_t, nav, cash, positions_value, daily_pnl, daily_pnl_pct "
        "FROM replay_nav_history WHERE run_id=? ORDER BY day_t",
        (run_id,),
    ).fetchall()
    n_nav = len(nav_rows)
    navs = [r["nav"] for r in nav_rows]
    nav_evolves = len(set(round(n, 2) for n in navs)) > 1 if navs else False
    check(
        "8. replay_nav_history = 3 et NAV evolue",
        n_nav == 3 and nav_evolves,
        f"navs={[f'{n:,.2f}' for n in navs]}",
    )

    # 9) Integrity : sum(buy_notional) - sum(sell_notional) ~= K - cash_final
    buy_notional = cur.execute(
        "SELECT COALESCE(SUM(notional),0) FROM replay_fills WHERE run_id=? AND side='BUY'",
        (run_id,),
    ).fetchone()[0]
    sell_notional = cur.execute(
        "SELECT COALESCE(SUM(notional),0) FROM replay_fills WHERE run_id=? AND side='SELL'",
        (run_id,),
    ).fetchone()[0]
    net_outflow = buy_notional - sell_notional
    cash_decrease = INITIAL_CAPITAL - (cash_final if cash_final else INITIAL_CAPITAL)
    diff = abs(net_outflow - cash_decrease)
    check(
        "9. Integrity sum(notional) == K - cash",
        diff < INITIAL_CAPITAL * 0.001,  # 0.1% tolerance
        f"buy_not=${buy_notional:,.2f} sell_not=${sell_notional:,.2f} "
        f"net=${net_outflow:,.2f} cash_decr=${cash_decrease:,.2f} diff=${diff:.2f}",
    )

    # Detail orders breakdown
    section("[DETAIL] Orders breakdown")
    rows = cur.execute(
        "SELECT day_t, COUNT(*) as n, "
        "SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) as nb_buy, "
        "SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) as nb_sell, "
        "SUM(CASE WHEN status='filled' THEN 1 ELSE 0 END) as nb_filled, "
        "SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) as nb_rejected "
        "FROM replay_orders WHERE run_id=? GROUP BY day_t ORDER BY day_t",
        (run_id,),
    ).fetchall()
    log("  day_t       | n   | BUY | SELL| filled | rejected")
    log("  " + "-" * 60)
    for r in rows:
        log(
            f"  {r['day_t']}  | {r['n']:>3d} | {r['nb_buy']:>3d} | {r['nb_sell']:>3d} | "
            f"{r['nb_filled']:>6d} | {r['nb_rejected']:>8d}"
        )

    # NAV evolution
    section("[DETAIL] NAV evolution")
    log("  day_t       | NAV           | cash          | pos_value     | daily_pnl   | %")
    log("  " + "-" * 90)
    for r in nav_rows:
        pct = r["daily_pnl_pct"] if r["daily_pnl_pct"] is not None else 0.0
        log(
            f"  {r['day_t']}  | ${r['nav']:>12,.2f} | ${r['cash']:>12,.2f} | "
            f"${r['positions_value']:>12,.2f} | ${r['daily_pnl']:>10,.2f} | {pct:>6.3f}%"
        )

    # Top 5 positions finales
    section("[DETAIL] Top 5 positions (cycle final)")
    pos_rows = cur.execute(
        "SELECT ticker, quantity, avg_cost, current_price, weight_pct, unrealized_pnl "
        "FROM replay_positions WHERE run_id=? AND cycle_id_replay=? "
        "ORDER BY ABS(weight_pct) DESC LIMIT 5",
        (run_id, last_cycle_replay),
    ).fetchall()
    log("  ticker  | qty       | avg_cost  | px_now    | weight%  | unreal_pnl")
    log("  " + "-" * 70)
    for r in pos_rows:
        log(
            f"  {r['ticker']:<8s}| {r['quantity']:>9.2f} | {r['avg_cost']:>9.2f} | "
            f"{r['current_price']:>9.2f} | {r['weight_pct']:>7.3f}% | ${r['unrealized_pnl']:>10,.2f}"
        )

    conn.close()

    # Verdict
    section("VERDICT 8B.3")
    n_pass = sum(1 for _, ok, _ in checks if ok)
    n_total = len(checks)
    log(f"  Score : {n_pass}/{n_total}")
    for name, ok, detail in checks:
        mark = "[PASS]" if ok else "[FAIL]"
        log(f"    {mark} {name}")

    if n_pass == n_total:
        log("\n  >>> Jalon 8B.3 DONE - Execution Engine wrapper OPERATIONNEL")
        sys.exit(0)
    else:
        log(f"\n  >>> {n_total - n_pass} checks failed - investiguer")
        sys.exit(2)


if __name__ == "__main__":
    main()
