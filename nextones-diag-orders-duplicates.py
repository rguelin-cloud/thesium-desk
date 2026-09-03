#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : pourquoi 26 ordres pending (13 paires de doublons identiques)
# Verifie :
# - liste des ordres pending groupes par (ticker, side, qty)
# - cycle_id et created_at pour chaque doublon
# - source_thesis_id si dispo
# - logs de execute-cycle recent (2 appels ?)

import os
import sys
import sqlite3
from collections import defaultdict

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    if not os.path.isfile(DB):
        print("ERR : DB introuvable :", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    print("=== 1. Schema orders ===")
    try:
        cols = conn.execute("PRAGMA table_info(orders)").fetchall()
        for c in cols:
            print("  ", c["name"], c["type"])
    except Exception as e:
        print("  ERR schema :", e)

    print()
    print("=== 2. Tous les orders pending ===")
    try:
        rows = conn.execute("""
            SELECT * FROM orders
            WHERE status IN ('pending', 'validation', 'pending_validation')
            ORDER BY id ASC
        """).fetchall()
        print("  Total pending :", len(rows))
        for r in rows:
            d = dict(r)
            keys_show = ["id", "ticker", "side", "qty", "status",
                         "created_at", "cycle_id", "source_thesis_id",
                         "thesis_id", "order_type"]
            short = {k: d.get(k) for k in keys_show if k in d}
            print("  ", short)
    except Exception as e:
        print("  ERR orders :", e)

    print()
    print("=== 3. Doublons par (ticker, side, qty) ===")
    try:
        rows = conn.execute("""
            SELECT ticker, side, qty, COUNT(*) as n,
                   GROUP_CONCAT(id) as ids,
                   GROUP_CONCAT(cycle_id) as cycle_ids,
                   GROUP_CONCAT(created_at) as created_ats
            FROM orders
            WHERE status IN ('pending', 'validation', 'pending_validation')
            GROUP BY ticker, side, qty
            HAVING n > 1
            ORDER BY n DESC, ticker
        """).fetchall()
        if not rows:
            print("  Aucun doublon detecte")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR dedup :", e)

    print()
    print("=== 4. Cycles recents (run_cycle table si existe) ===")
    try:
        cols = conn.execute("PRAGMA table_info(run_cycle)").fetchall()
        if cols:
            rows = conn.execute("""
                SELECT * FROM run_cycle
                ORDER BY id DESC LIMIT 5
            """).fetchall()
            for r in rows:
                print("  ", dict(r))
        else:
            print("  Pas de table run_cycle")
    except Exception as e:
        print("  Pas run_cycle :", e)

    print()
    print("=== 5. cycles table si existe ===")
    try:
        cols = conn.execute("PRAGMA table_info(cycles)").fetchall()
        if cols:
            rows = conn.execute("""
                SELECT * FROM cycles
                ORDER BY id DESC LIMIT 5
            """).fetchall()
            for r in rows:
                print("  ", dict(r))
        else:
            print("  Pas de table cycles")
    except Exception as e:
        print("  Pas cycles :", e)

    print()
    print("=== 6. Group by cycle_id sur orders pending ===")
    try:
        rows = conn.execute("""
            SELECT cycle_id, COUNT(*) as n,
                   MIN(created_at) as first_at,
                   MAX(created_at) as last_at
            FROM orders
            WHERE status IN ('pending', 'validation', 'pending_validation')
            GROUP BY cycle_id
            ORDER BY cycle_id DESC
        """).fetchall()
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR group :", e)

    conn.close()
    print()
    print("=== DONE diag doublons ===")


if __name__ == "__main__":
    main()
