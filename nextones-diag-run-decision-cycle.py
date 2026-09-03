# -*- coding: utf-8 -*-
"""
[DIAG_RUN_DECISION_CYCLE_V1]
Execute execution_engine.run_decision_cycle(conn) en LOCAL avec
row_factory=sqlite3.Row pour reproduire exactement le contexte
serveur et capter la stack complete du HTTP 500.

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-run-decision-cycle.py
"""
import os
import sys
import sqlite3
import traceback
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def open_conn():
    conn = sqlite3.connect(str(DB), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 30000;")
    except Exception:
        pass
    return conn


def main() -> int:
    print("=" * 70)
    print("  Reproduction HTTP 500 sur /api/orders/execute-cycle")
    print("=" * 70)

    try:
        from execution_engine import run_decision_cycle
        print("[OK] execution_engine.run_decision_cycle importe.")
    except Exception:
        print("[FAIL] import execution_engine:")
        traceback.print_exc()
        return 1

    conn = open_conn()
    try:
        print("\n>>> run_decision_cycle(conn) ...\n")
        res = run_decision_cycle(conn)
        conn.commit()
        print("\n[OK] cycle termine sans erreur :")
        if isinstance(res, dict):
            for k, v in res.items():
                s = str(v)
                if len(s) > 300:
                    s = s[:300] + "..."
                print(f"  {k}: {s}")
        else:
            print(f"  retour: {type(res).__name__}")
    except Exception:
        print("\n" + "=" * 70)
        print("  STACK COMPLETE (la cause du 500)")
        print("=" * 70)
        traceback.print_exc()
        try:
            conn.rollback()
        except Exception:
            pass
        return 2
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
