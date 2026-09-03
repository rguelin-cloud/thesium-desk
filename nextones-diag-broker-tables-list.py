# -*- coding: utf-8 -*-
# nextones-diag-broker-tables-list.py
# Liste toutes les tables broker_* (et tables connexes) pour identifier
# le bon nom du mapping ActivTrades.

import sqlite3
import os

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def main():
    if not os.path.exists(DB_PATH):
        print(f"FATAL DB introuvable : {DB_PATH}")
        return
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    print("=== Tables (LIKE broker% ou map%) ===")
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
          AND (name LIKE 'broker%' OR name LIKE '%mapping%' OR name LIKE '%map%')
        ORDER BY name
    """)
    tables = [r[0] for r in cur.fetchall()]
    if not tables:
        print("  (aucune table broker/mapping trouvee)")
    for t in tables:
        print(f"\n--- {t} ---")
        cur.execute(f"PRAGMA table_info({t})")
        for col in cur.fetchall():
            print(f"  {col[1]:30s} {col[2]:15s} NOT NULL={col[3]} DEF={col[4]}")
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  -> {cnt} lignes")
        if cnt > 0:
            cur.execute(f"SELECT * FROM {t} LIMIT 3")
            rows = cur.fetchall()
            for r in rows:
                print(f"  sample : {r}")

    print("\n=== Tables universe_* ===")
    cur.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE 'universe%'
        ORDER BY name
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}")

    print("\n=== Schema universe_candidates (colonnes NOT NULL) ===")
    cur.execute("PRAGMA table_info(universe_candidates)")
    for col in cur.fetchall():
        nn = "NOT NULL" if col[3] else ""
        df = f" DEFAULT={col[4]}" if col[4] is not None else ""
        print(f"  {col[1]:25s} {col[2]:15s} {nn}{df}")

    print("\n=== Echantillon universe_candidates (3 lignes recentes) ===")
    cur.execute("""
        SELECT ticker, status, proposed_at, scan_batch
        FROM universe_candidates
        ORDER BY id DESC LIMIT 3
    """)
    for r in cur.fetchall():
        print(f"  {r}")

    conn.close()


if __name__ == "__main__":
    main()
