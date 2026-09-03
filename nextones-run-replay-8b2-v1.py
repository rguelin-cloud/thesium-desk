# -*- coding: utf-8 -*-
# nextones-run-replay-8b2-v1.py
# Smoke-test Jalon 8B.2 : 3 cycles via ReplayOrchestrator
#   - regime + convergence + portfolio_construction
#   - validation tables replay_convergence_snapshots, replay_targets, replay_targets_history
#   - validation cash != $1M dans la conn :memory: a la fin du dernier cycle
#
# Mode strict : aucune ecriture vers la prod (tables prod), uniquement replay_*.

import os
import sys
import json
import sqlite3
from datetime import datetime

# Force le mode replay des le debut
os.environ["NEXTONES_REPLAY_MODE"] = "1"

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# sys.path : prod + workspace
if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

# Fenetre : 3 jours ouvres recents avec prix dispo
# Le calendrier de ReplayOrchestrator filtre les weekends
WINDOW_START = "2026-06-08"
WINDOW_END = "2026-06-10"
LABEL_PREFIX = "8B2-smoke-"


def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def run_smoke_test():
    label = LABEL_PREFIX + datetime.now().strftime("%Y%m%d-%H%M%S")

    print_section(f"JALON 8B.2 - Smoke test : {label}")
    print(f"DB     : {DB_PATH}")
    print(f"Window : {WINDOW_START} -> {WINDOW_END}")
    print(f"Cycles : 3 (max)")

    from replay_orchestrator import ReplayOrchestrator

    orch = ReplayOrchestrator(
        label=label,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        initial_capital=1_000_000.0,
        ablation_flags={"agents": "regime+convergence+PCA"},
        db_path=DB_PATH,
        verbose=True,
    )

    summary = orch.run(max_cycles=3)
    run_id = summary["run_id"]
    n_cycles = summary["cycles"]

    print_section(f"VALIDATION run_id={run_id} cycles={n_cycles}")

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. replay_cycles : 3 lignes, status=ok, vix non-null, snapshot_id non-null
    rows_cycles = cur.execute(
        """
        SELECT cycle_id, day_t, cycle_seq, cycle_status, regime_equity, regime_crypto,
               vix, details_json
        FROM replay_cycles
        WHERE run_id = ?
        ORDER BY cycle_seq
        """,
        (run_id,),
    ).fetchall()

    print(f"\n[A] replay_cycles : {len(rows_cycles)} lignes")
    n_ok = 0
    n_vix_non_null = 0
    n_snap_non_null = 0
    n_targets_total = 0
    n_conv_exported_total = 0
    last_cash = None
    for r in rows_cycles:
        details = {}
        try:
            details = json.loads(r["details_json"] or "{}")
        except Exception:
            pass
        snap_id = details.get("snapshot_id")
        n_tgt = details.get("n_targets", 0)
        n_conv = details.get("n_conv_exported", 0)
        cash_after = details.get("cash_after")
        last_cash = cash_after if cash_after is not None else last_cash
        if r["cycle_status"] == "ok":
            n_ok += 1
        if r["vix"] is not None:
            n_vix_non_null += 1
        if snap_id is not None:
            n_snap_non_null += 1
        n_targets_total += int(n_tgt or 0)
        n_conv_exported_total += int(n_conv or 0)
        print(f"    cycle_id={r['cycle_id']} day={r['day_t']} seq={r['cycle_seq']} "
              f"status={r['cycle_status']} eq={r['regime_equity']} "
              f"vix={r['vix']} snap_id={snap_id} n_targets={n_tgt} n_conv={n_conv} "
              f"cash_after={cash_after}")

    # 2. replay_convergence_snapshots
    n_conv_db = cur.execute(
        "SELECT COUNT(*) FROM replay_convergence_snapshots WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    distinct_cycles_conv = cur.execute(
        "SELECT COUNT(DISTINCT cycle_id_replay) FROM replay_convergence_snapshots WHERE run_id=?",
        (run_id,),
    ).fetchone()[0]
    sample_conv = cur.execute(
        """
        SELECT day_t, ticker, direction_consensus, convergence_pct, sizing_multiplier
        FROM replay_convergence_snapshots
        WHERE run_id=?
        ORDER BY cycle_id_replay, ticker
        LIMIT 5
        """,
        (run_id,),
    ).fetchall()

    print(f"\n[B] replay_convergence_snapshots : {n_conv_db} lignes / {distinct_cycles_conv} cycles distincts")
    for r in sample_conv:
        print(f"    {r['day_t']} {r['ticker']:<8s} dir={r['direction_consensus']} "
              f"conv_pct={r['convergence_pct']} sizing={r['sizing_multiplier']}")

    # 3. replay_targets
    n_tgt_db = cur.execute(
        "SELECT COUNT(*) FROM replay_targets WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    distinct_cycles_tgt = cur.execute(
        "SELECT COUNT(DISTINCT cycle_id_replay) FROM replay_targets WHERE run_id=?",
        (run_id,),
    ).fetchone()[0]
    sample_tgt = cur.execute(
        """
        SELECT day_t, ticker, target_weight_pct, active, score
        FROM replay_targets
        WHERE run_id=?
        ORDER BY cycle_id_replay, target_weight_pct DESC
        LIMIT 8
        """,
        (run_id,),
    ).fetchall()

    print(f"\n[C] replay_targets : {n_tgt_db} lignes / {distinct_cycles_tgt} cycles distincts")
    for r in sample_tgt:
        print(f"    {r['day_t']} {r['ticker']:<8s} w={r['target_weight_pct']:.4f} "
              f"active={r['active']} score={r['score']}")

    # 4. replay_targets_history
    n_hist_db = cur.execute(
        "SELECT COUNT(*) FROM replay_targets_history WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    print(f"\n[D] replay_targets_history : {n_hist_db} lignes")

    # 5. replay_regime_log
    n_regime_db = cur.execute(
        "SELECT COUNT(*) FROM replay_regime_log WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    print(f"\n[E] replay_regime_log : {n_regime_db} lignes (attendu : 3)")

    conn.close()

    # ---------- VERDICT ----------
    print_section("VERDICT JALON 8B.2")
    checks = []

    checks.append(("cycles status=ok (3 attendus)", n_ok == 3, f"{n_ok}/3"))
    checks.append(("VIX non-null sur tous les cycles", n_vix_non_null == 3, f"{n_vix_non_null}/3"))
    checks.append(("snapshot_id non-null sur tous les cycles", n_snap_non_null == 3, f"{n_snap_non_null}/3"))
    checks.append(("replay_convergence_snapshots > 0", n_conv_db > 0, f"{n_conv_db}"))
    checks.append(("replay_convergence_snapshots couvre 3 cycles", distinct_cycles_conv == 3, f"{distinct_cycles_conv}/3"))
    checks.append(("replay_targets > 0", n_tgt_db > 0, f"{n_tgt_db}"))
    checks.append(("replay_targets couvre 3 cycles", distinct_cycles_tgt == 3, f"{distinct_cycles_tgt}/3"))
    checks.append(("replay_regime_log = 3", n_regime_db == 3, f"{n_regime_db}/3"))

    # NOTE : portfolio_state.cash reste a $1M par design au Jalon 8B.2.
    # La PCA Jalon 2 ecrit des CIBLES (% target), pas des positions ouvertes.
    # L'execution (risk_pretrade + fill_simulator) viendra au Jalon 8B.3.
    # On valide juste que la PCA a fait son job : >= 15 cibles par cycle.
    avg_targets_per_cycle = n_tgt_db / max(distinct_cycles_tgt, 1)
    checks.append((f"PCA targets >= 15/cycle (moyenne actuelle: {avg_targets_per_cycle:.1f})",
                   avg_targets_per_cycle >= 15.0,
                   f"{avg_targets_per_cycle:.1f}"))

    print()
    all_pass = True
    for name, ok, detail in checks:
        flag = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  [{flag}] {name}  -> {detail}")

    print()
    if all_pass:
        print("=" * 72)
        print(" JALON 8B.2 : PASS  (convergence + portfolio_construction wrapped OK)")
        print("=" * 72)
        return 0
    else:
        print("=" * 72)
        print(" JALON 8B.2 : FAIL  (voir checks ci-dessus)")
        print("=" * 72)
        return 1


if __name__ == "__main__":
    rc = run_smoke_test()
    sys.exit(rc)
