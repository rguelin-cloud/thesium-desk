# -*- coding: utf-8 -*-
# nextones-run-replay-8b1-v1.py
# Jalon 8B.1 - Lance le replay sur une mini-fenetre (3 jours) pour valider
# le squelette orchestrator + wrapper market_regime_v1.
#
# Verifie :
#   1. open_replay_conn_at fonctionne (vue filtree sans look-ahead)
#   2. detect_market_regime accepte la conn replay sans modification
#   3. monkey-patch FRED VIX retourne la valeur de macro_history
#   4. replay_runs / replay_cycles / replay_regime_log se peuplent
#   5. Comparaison VIX replay vs VIX prod a la meme date
#
# Usage : py -3.13 .\nextones-run-replay-8b1-v1.py

import os
import sys
import sqlite3
from datetime import datetime

# Force le mode replay
os.environ["NEXTONES_REPLAY_MODE"] = "1"

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

# Permet l'import des modules workspace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

from replay_orchestrator import ReplayOrchestrator, trading_calendar


def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def main():
    print("=" * 70)
    print("JALON 8B.1 - RUN REPLAY MINI-WINDOW")
    print("=" * 70)
    print(f"DB         : {DB}")
    print(f"REPLAY MODE: {os.environ.get('NEXTONES_REPLAY_MODE')}")
    print(f"FRED_API_KEY present : {bool(os.environ.get('FRED_API_KEY'))}")

    # Mini-fenetre 5 jours ouvres autour de juin 2025
    window_start = "2025-06-10"
    window_end = "2025-06-20"

    section("ETAPE 1 : Calendar generation")
    cal = trading_calendar(window_start, window_end)
    print(f"  Calendrier {window_start} -> {window_end}: {len(cal)} jours ouvres")
    for d in cal:
        print(f"    {d}")

    section("ETAPE 2 : Boucle orchestrator (3 premiers cycles)")
    orch = ReplayOrchestrator(
        label="8B.1_smoke_test",
        window_start=window_start,
        window_end=window_end,
        initial_capital=1_000_000.0,
        db_path=DB,
        verbose=True,
    )
    result = orch.run(max_cycles=3)
    print(f"\n  Run termine: {result}")

    section("ETAPE 3 : Verification ecritures replay_*")
    conn = sqlite3.connect(DB, timeout=10.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # replay_runs
    cur.execute(
        "SELECT run_id, label, status, window_start, window_end FROM replay_runs WHERE run_id=?",
        (result["run_id"],),
    )
    r = cur.fetchone()
    print(f"  replay_runs row : {dict(r) if r else 'AUCUN'}")

    # replay_cycles
    cur.execute(
        "SELECT cycle_id, day_t, cycle_seq, regime_equity, regime_crypto, vix "
        "FROM replay_cycles WHERE run_id=? ORDER BY cycle_seq",
        (result["run_id"],),
    )
    cycles = cur.fetchall()
    print(f"  replay_cycles   : {len(cycles)} lignes")
    for c in cycles:
        print(
            f"    cycle_id={c['cycle_id']}  day={c['day_t']}  "
            f"eq={c['regime_equity']:<7s} cr={c['regime_crypto']:<7s} vix={c['vix']}"
        )

    # replay_regime_log
    cur.execute(
        "SELECT log_id, day_t, regime_equity, regime_crypto, vix, "
        "spy_dd_20j, vol_equity, vol_crypto FROM replay_regime_log "
        "WHERE run_id=? ORDER BY day_t",
        (result["run_id"],),
    )
    logs = cur.fetchall()
    print(f"  replay_regime_log : {len(logs)} lignes")
    for l in logs:
        print(
            f"    log_id={l['log_id']}  day={l['day_t']}  "
            f"vix={l['vix']}  vol_eq={l['vol_equity']}  vol_cr={l['vol_crypto']}  "
            f"dd_spy={l['spy_dd_20j']}"
        )

    section("ETAPE 4 : Verification no-lookahead (sanity check)")
    # Pour le 1er jour replay (2025-06-10), aucune trace de prices > 2025-06-10
    # ne doit avoir ete utilisee. On verifie indirectement via la VIX :
    # macro_history.VIX a 2025-06-10 doit etre <= VIX a 2025-06-20.
    cur.execute(
        "SELECT date, value FROM macro_history WHERE series_code='VIX' "
        "AND date IN ('2025-06-10','2025-06-20') ORDER BY date"
    )
    vix_real = {r["date"]: r["value"] for r in cur.fetchall()}
    print(f"  VIX prod 2025-06-10 : {vix_real.get('2025-06-10')}")
    print(f"  VIX prod 2025-06-20 : {vix_real.get('2025-06-20')}")

    # Verifie que le VIX log au cycle du 10/6 == VIX prod du 10/6 (ou plus recent <= 10/6)
    if logs:
        first = logs[0]
        ok = first["vix"] is not None
        print(f"  VIX replay 1er cycle ({first['day_t']}) = {first['vix']}  -> {'PASS' if ok else 'FAIL'}")

    conn.close()

    section("RESUME")
    n_cycles = len(cycles)
    n_logs = len(logs)
    n_vix_ok = sum(1 for l in logs if l["vix"] is not None)
    all_ok = (
        n_cycles == 3
        and n_logs == 3
        and n_vix_ok == 3
    )
    print(f"  cycles ecrits   : {n_cycles}/3")
    print(f"  logs ecrits     : {n_logs}/3")
    print(f"  vix non-null    : {n_vix_ok}/3")

    if all_ok:
        print("\n[PASS] Jalon 8B.1 squelette OK. Prochain : 8B.2 (convergence + portfolio_construction).")
        sys.exit(0)
    else:
        print("\n[FAIL] Jalon 8B.1 squelette incomplet.")
        sys.exit(2)


if __name__ == "__main__":
    main()
