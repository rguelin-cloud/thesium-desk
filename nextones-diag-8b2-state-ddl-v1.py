# -*- coding: utf-8 -*-
# nextones-diag-8b2-state-ddl-v1.py
# Recupere les DDL ORIGINAUX (avec PK/UNIQUE/INDEX) des tables d'etat
# pour pouvoir les recreer proprement dans la conn :memory:.

import sqlite3

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

STATE_TABLES = [
    "convergence_snapshots",
    "portfolio_targets",
    "portfolio_targets_history",
    "portfolio_positions",
    "portfolio_history",
    "portfolio_state",
    "regime_log",
    "market_regime_log",
    "universe_candidates",
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("=" * 72)
print("DIAG 8B.2 - DDL des tables d'etat (avec constraints)")
print("=" * 72)

for t in STATE_TABLES:
    print()
    print("=" * 72)
    print(f" TABLE : {t}")
    print("=" * 72)

    # DDL principal
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)
    ).fetchone()
    if not row:
        print("  (table absente en prod)")
        continue
    print(row[0])

    # Indexes associes
    idx_rows = cur.execute(
        """
        SELECT name, sql FROM sqlite_master
        WHERE type='index' AND tbl_name=? AND sql IS NOT NULL
        ORDER BY name
        """,
        (t,),
    ).fetchall()
    if idx_rows:
        print()
        print("  -- Indexes --")
        for nm, sql in idx_rows:
            print(f"  [{nm}]")
            print(f"    {sql}")

conn.close()
