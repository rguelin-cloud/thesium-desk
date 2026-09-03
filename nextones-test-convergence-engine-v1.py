"""
[TEST_CONVERGENCE_ENGINE_V1]
Test standalone du Convergence Engine sur le cycle courant.

Sequence :
  1. Charge convergence_engine.py (deja dans le PYTHONPATH workspace)
  2. compute_convergence(conn, cycle_id=<dernier regime_log>)
  3. Affiche tableau resume + dump JSON 3 tickers (1 equity + 1 crypto + 1 forced_exit)
  4. save_convergence_snapshot -> verifie INSERT
"""

import os
import sys
import json
import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

# convergence_engine.py doit etre dans le meme dossier que ce script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from convergence_engine import (  # noqa: E402
    compute_convergence,
    render_convergence_summary,
    save_convergence_snapshot,
)


def latest_cycle(conn):
    cur = conn.execute(
        "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row[0] if row else None


def main():
    if not os.path.exists(DB_PATH):
        print("ERROR: DB not found")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cycle_id = latest_cycle(conn)
        print("=" * 78)
        print("Test convergence sur cycle_id = %s" % cycle_id)
        print("=" * 78)

        results = compute_convergence(conn, cycle_id=cycle_id)
        print("")
        print("Tickers retournes : %d" % len(results))
        print("")
        print(render_convergence_summary(results))

        # Dump JSON detaille : 1 equity + 1 crypto + 1 forced_exit
        print("")
        print("=" * 78)
        print("DUMP DETAILLE")
        print("=" * 78)

        equity_sample = next(
            (r for r in results if not r["is_crypto"]
             and not r["forced_exit"]),
            None,
        )
        crypto_sample = next((r for r in results if r["is_crypto"]), None)
        exit_sample = next((r for r in results if r["forced_exit"]), None)

        for label, r in [
            ("EQUITY", equity_sample),
            ("CRYPTO", crypto_sample),
            ("FORCED_EXIT", exit_sample),
        ]:
            print("")
            print("--- %s ---" % label)
            if r is None:
                print("  (aucun)")
                continue
            print(json.dumps(r, indent=2, ensure_ascii=False, default=str))

        # Persistence
        print("")
        print("=" * 78)
        print("PERSISTENCE")
        print("=" * 78)
        try:
            n = save_convergence_snapshot(conn, cycle_id, results)
            print("INSERT OK : %d lignes" % n)

            cur = conn.execute(
                "SELECT COUNT(*) FROM convergence_snapshots "
                "WHERE cycle_id = ?",
                (cycle_id,),
            )
            print("Lignes en DB pour ce cycle : %d" % cur.fetchone()[0])
        except sqlite3.OperationalError as e:
            print("PERSISTENCE SKIP : %s" % e)
            print("(lance d'abord nextones-install-convergence-schema-v1.py)")

        print("")
        print("DONE")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
