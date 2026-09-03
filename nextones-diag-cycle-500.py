# -*- coding: utf-8 -*-
"""
[DIAG_CYCLE_500_V1]
Diagnostic du HTTP 500 sur /api/run-agents.

1) Lance le cycle directement en local (sans HTTP) pour capter la stack complete.
2) Affiche l'etat de SOL (instruments / prices / target_universe) - cause probable.
3) Liste les agents executes par run_decision_cycle.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-cycle-500.py
"""
import os
import sys
import sqlite3
import traceback
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"

# Pour importer les modules du projet
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def diag_sol_state() -> None:
    section("1) Etat SOL dans la DB")
    conn = sqlite3.connect(str(DB))
    try:
        inst = conn.execute(
            "SELECT id, ticker, name, sector, asset_class FROM instruments WHERE ticker='SOL';"
        ).fetchone()
        print(f"instruments       : {inst}")

        tu = conn.execute(
            "SELECT id, ticker, asset_class, sector, is_active, max_weight_pct "
            "FROM target_universe WHERE ticker='SOL';"
        ).fetchone()
        print(f"target_universe   : {tu}")

        if inst is not None:
            iid = inst[0]
            n = conn.execute(
                "SELECT COUNT(*) FROM prices WHERE instrument_id=?;", (iid,)
            ).fetchone()[0]
            last = conn.execute(
                "SELECT date, close FROM prices WHERE instrument_id=? "
                "ORDER BY date DESC LIMIT 1;", (iid,)
            ).fetchone()
            print(f"prices count(SOL) : {n}")
            print(f"prices last(SOL)  : {last}")
            if n == 0:
                print()
                print(">>> CAUSE PROBABLE: SOL n'a aucun prix.")
                print(">>> Les agents (PCA / risk / factor) peuvent crasher sur SOL.")
    finally:
        conn.close()


def diag_cycle_locks() -> None:
    section("2) Verrous de cycle eventuels")
    conn = sqlite3.connect(str(DB))
    try:
        try:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('cycle_locks','run_locks','agent_lock');"
            ).fetchall()
            print(f"tables verrous  : {rows}")
            for (t,) in rows:
                r = conn.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 5;").fetchall()
                print(f"  {t}: {r}")
        except Exception as e:
            print(f"(pas de table verrou: {e})")
    finally:
        conn.close()


def run_cycle_inproc() -> None:
    section("3) Execution du cycle EN LOCAL (capte la stack)")

    candidates = [
        ("decision_cycle",                 "run_decision_cycle"),
        ("agents.decision_cycle",          "run_decision_cycle"),
        ("agents.orchestrator",            "run_decision_cycle"),
        ("orchestrator",                   "run_decision_cycle"),
        ("api_server_with_static",        "run_decision_cycle"),
    ]

    func = None
    src  = None
    for mod_name, fn_name in candidates:
        try:
            mod = __import__(mod_name, fromlist=[fn_name])
            func = getattr(mod, fn_name, None)
            if callable(func):
                src = f"{mod_name}.{fn_name}"
                break
        except Exception:
            continue

    if not callable(func):
        print("[FAIL] Impossible de localiser run_decision_cycle.")
        print("       Cherche dans les sources le nom exact de la fonction:")
        print('       grep -rn "def run_decision_cycle\\|def run_cycle" *.py agents\\\\')
        return

    print(f"[OK] Fonction trouvee: {src}")
    print("Appel en cours...")
    try:
        res = func()  # signature standard
        print(f"[OK] cycle retourne: {type(res).__name__}")
        if isinstance(res, dict):
            for k, v in res.items():
                s = str(v)
                if len(s) > 200:
                    s = s[:200] + "..."
                print(f"  {k}: {s}")
    except TypeError:
        # certains projets attendent une connexion / user_id
        try:
            conn = sqlite3.connect(str(DB))
            res = func(conn)
            print(f"[OK] cycle(conn) retourne: {type(res).__name__}")
        except Exception:
            print("[FAIL] Stack complete:")
            traceback.print_exc()
    except Exception:
        print("[FAIL] Stack complete:")
        traceback.print_exc()


def main() -> int:
    diag_sol_state()
    diag_cycle_locks()
    run_cycle_inproc()
    section("FIN")
    print("Copie cette sortie pour qu'on identifie l'agent en erreur.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
