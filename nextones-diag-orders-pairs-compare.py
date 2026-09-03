#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : compare les paires d ordres pending (cycle 13:02 vs cycle 13:15)
# pour decider lesquels annuler en toute securite.
# Affiche : id, instrument_id->ticker, side, quantity, thesis_id, created_at

import os
import sys
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def main():
    if not os.path.isfile(DB):
        print("ERR : DB introuvable :", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    print("=== Orders pending avec ticker (join instruments) ===")
    try:
        rows = conn.execute("""
            SELECT o.id, i.ticker, o.side, o.quantity,
                   o.thesis_id, o.created_at, o.status
            FROM orders o
            LEFT JOIN instruments i ON i.id = o.instrument_id
            WHERE o.status IN ('pending', 'pending_validation', 'validation')
            ORDER BY o.created_at, o.id
        """).fetchall()
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR join :", e)

    print()
    print("=== Doublons (ticker, side, quantity) ===")
    try:
        rows = conn.execute("""
            SELECT i.ticker, o.side, o.quantity,
                   COUNT(*) as n,
                   GROUP_CONCAT(o.id) as ids,
                   GROUP_CONCAT(o.created_at) as created_ats,
                   GROUP_CONCAT(o.thesis_id) as thesis_ids
            FROM orders o
            LEFT JOIN instruments i ON i.id = o.instrument_id
            WHERE o.status IN ('pending', 'pending_validation', 'validation')
            GROUP BY i.ticker, o.side, o.quantity
            HAVING n > 1
            ORDER BY i.ticker
        """).fetchall()
        if not rows:
            print("  Aucun doublon strict (ticker+side+quantity)")
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR dedup :", e)

    print()
    print("=== Group by created_at (cycles distincts) ===")
    try:
        rows = conn.execute("""
            SELECT substr(created_at, 1, 16) as bucket,
                   COUNT(*) as n,
                   MIN(id) as min_id,
                   MAX(id) as max_id
            FROM orders
            WHERE status IN ('pending', 'pending_validation', 'validation')
            GROUP BY substr(created_at, 1, 16)
            ORDER BY bucket
        """).fetchall()
        for r in rows:
            print("  ", dict(r))
    except Exception as e:
        print("  ERR buckets :", e)

    conn.close()
    print()
    print("=== DONE ===")


if __name__ == "__main__":
    main()
