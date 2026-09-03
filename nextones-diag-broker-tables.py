# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-BROKER-TABLES-V1]
# Cartographie des 3 tables broker pour aligner add-symbol sur le schema reel.
#
# Usage : py -3.13 nextones-diag-broker-tables.py

import os
import sqlite3
import sys

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

TABLES = [
    "broker_universe_activtrades",
    "instrument_broker_mapping",
    "broker_mapping_audit",
]


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERREUR: base introuvable {DB_PATH}")
        sys.exit(2)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    for t in TABLES:
        print("=" * 72)
        print(f"TABLE: {t}")
        print("-" * 72)
        cur = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)
        )
        row = cur.fetchone()
        if not row:
            print(f"  [ABSENTE]")
            continue
        print("DDL:")
        print(row["sql"])
        print()
        print("Colonnes (PRAGMA table_info):")
        cur = con.execute(f"PRAGMA table_info({t})")
        for r in cur.fetchall():
            print(
                f"  - {r['name']:25s} {r['type']:15s} "
                f"notnull={r['notnull']} dflt={r['dflt_value']!r} pk={r['pk']}"
            )
        print()
        cur = con.execute(f"SELECT COUNT(*) AS n FROM {t}")
        n = cur.fetchone()["n"]
        print(f"Lignes: {n}")
        if n > 0:
            print("Echantillon (3 lignes):")
            cur = con.execute(f"SELECT * FROM {t} LIMIT 3")
            for r in cur.fetchall():
                print(f"  {dict(r)}")
        print()

    # Verifier specifiquement si REET.US est deja la
    print("=" * 72)
    print("CHECK REET.US dans broker_universe_activtrades:")
    try:
        cur = con.execute(
            "SELECT * FROM broker_universe_activtrades WHERE broker_symbol=?",
            ("REET.US",),
        )
        row = cur.fetchone()
        if row:
            print(f"  PRESENT -> {dict(row)}")
        else:
            print("  ABSENT")
    except Exception as e:
        print(f"  ERREUR query: {e}")

    # Verifier instruments table (pour mapping eventuel)
    print("=" * 72)
    print("CHECK table instruments (pour mapping REET):")
    cur = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='instruments'"
    )
    if not cur.fetchone():
        print("  table instruments absente")
    else:
        cur = con.execute("PRAGMA table_info(instruments)")
        cols = [r["name"] for r in cur.fetchall()]
        print(f"  colonnes instruments: {cols}")
        for col in cols:
            if col.lower() in ("ticker", "symbol", "code"):
                try:
                    cur = con.execute(
                        f"SELECT id, {col} FROM instruments WHERE {col}=? LIMIT 1",
                        ("REET",),
                    )
                    row = cur.fetchone()
                    if row:
                        print(f"  REET trouve via {col} -> id={row['id']}")
                    else:
                        print(f"  REET introuvable via {col}")
                except Exception as e:
                    print(f"  query {col}: {e}")

    con.close()


if __name__ == "__main__":
    main()
