# -*- coding: utf-8 -*-
# Verifie le schema reel de convergence_snapshots et confirme l'absence de 'regime'

import os
import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def main():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row

    print("--- PRAGMA table_info(convergence_snapshots) ---")
    rows = c.execute("PRAGMA table_info(convergence_snapshots)").fetchall()
    for r in rows:
        print("  " + dict(r).__repr__())

    print("\n--- 1 ligne convergence_snapshots SOL (toutes colonnes via SELECT *) ---")
    r = c.execute(
        "SELECT * FROM convergence_snapshots WHERE ticker='SOL' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    if r:
        print("  " + dict(r).__repr__())

    print("\n--- Test exact du SELECT de apply_convergence_sizing (avec regime) ---")
    try:
        rr = c.execute(
            "SELECT ticker, sizing_multiplier, regime, forced_exit, drift "
            "FROM convergence_snapshots WHERE cycle_id = ?",
            ("20260610-112411",)
        ).fetchall()
        print("  OK, " + str(len(rr)) + " rows")
    except Exception as e:
        print("  [EXCEPTION] " + type(e).__name__ + ": " + str(e))

    print("\n--- Test SANS regime (cibler le fix) ---")
    try:
        rr = c.execute(
            "SELECT ticker, sizing_multiplier, forced_exit, drift "
            "FROM convergence_snapshots WHERE cycle_id = ?",
            ("20260610-112411",)
        ).fetchall()
        print("  OK, " + str(len(rr)) + " rows")
        forced = [dict(r) for r in rr if r["forced_exit"] == 1]
        print("  forced_exit=1 : " + str(len(forced)) + " tickers")
        for f in forced[:10]:
            print("    " + str(f))
    except Exception as e:
        print("  [EXCEPTION] " + str(e))

    c.close()


if __name__ == "__main__":
    main()
