# -*- coding: utf-8 -*-
# nextones-diag-regime-reads-v1.py
# Inspecte detect_market_regime : tables lues + verifie que TEMP VIEW peut shadow une table

import os
import re
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")


def dump_reads():
    p = os.path.join(ROOT, "market_regime_v1.py")
    with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    print("=" * 80)
    print("TABLES LUES par market_regime_v1.py")
    print("=" * 80)

    # Extrait toutes les requetes FROM <table>
    froms = re.findall(r"FROM\s+(\w+)", src, re.IGNORECASE)
    tables = sorted(set(t.lower() for t in froms))
    print("Tables (FROM):")
    for t in tables:
        print(f"  {t}")

    # JOINs
    joins = re.findall(r"JOIN\s+(\w+)", src, re.IGNORECASE)
    if joins:
        print("Tables (JOIN):")
        for t in sorted(set(j.lower() for j in joins)):
            print(f"  {t}")

    # Acces variables tickers/series specifiques
    print()
    print("Constantes detectees (SPY/BTC/VIX/etc.):")
    consts = re.findall(r"['\"]([A-Z]{2,10})['\"]", src)
    counter = {}
    for c in consts:
        counter[c] = counter.get(c, 0) + 1
    for c, n in sorted(counter.items(), key=lambda x: -x[1])[:20]:
        if n >= 2:
            print(f"  {c}  x{n}")

    # Signature de toutes les fonctions internes
    print()
    print("Fonctions internes:")
    defs = re.findall(r"^def\s+(\w+)\s*\(([^)]*)\)", src, re.MULTILINE)
    for fname, fargs in defs:
        a_short = fargs if len(fargs) <= 100 else fargs[:97] + "..."
        print(f"  def {fname}({a_short})")


def test_temp_view_shadow():
    print()
    print("=" * 80)
    print("TEST : TEMP VIEW peut-elle shadow une table reelle ?")
    print("=" * 80)
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE prices (id INTEGER, date TEXT, close REAL)")
    cur.execute("INSERT INTO prices VALUES (1, '2025-01-01', 100), (2, '2025-06-01', 200), (3, '2025-12-01', 300)")

    # Test 1 : SELECT direct
    cur.execute("SELECT COUNT(*) FROM prices")
    print(f"  Avant view : COUNT(prices) = {cur.fetchone()[0]}")

    # Test 2 : tentative TEMP VIEW avec meme nom
    try:
        cur.execute("CREATE TEMP VIEW prices AS SELECT * FROM prices WHERE date <= '2025-06-30'")
        print("  CREATE TEMP VIEW prices : OK (creee)")
    except Exception as e:
        print(f"  CREATE TEMP VIEW prices : ERR {e}")

    try:
        cur.execute("SELECT COUNT(*) FROM prices")
        n = cur.fetchone()[0]
        print(f"  Apres view  : COUNT(prices) = {n}  -> {'SHADOW OK' if n == 2 else 'PAS DE SHADOW (vraie table consultee)'}")
    except Exception as e:
        print(f"  SELECT apres view : ERR {e}")

    conn.close()


def test_alternative_approach():
    """
    Approche alternative : ATTACH DATABASE + renaming.
    """
    print()
    print("=" * 80)
    print("TEST : Approche alternative - ATTACH + table snapshot")
    print("=" * 80)

    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()

    # On simule : DB prod avec 'prices', et on cree une table 'prices_replay' filtree
    cur.execute("CREATE TABLE prices_real (id INTEGER, date TEXT, close REAL)")
    cur.execute("INSERT INTO prices_real VALUES (1, '2025-01-01', 100), (2, '2025-06-01', 200), (3, '2025-12-01', 300)")

    day_t = "2025-06-30"
    # Cree une table temp filtree
    cur.execute(f"CREATE TEMP TABLE prices AS SELECT * FROM prices_real WHERE date <= ?", (day_t,))

    cur.execute("SELECT COUNT(*) FROM prices")
    print(f"  TEMP TABLE prices : COUNT = {cur.fetchone()[0]} (attendu 2)")
    conn.close()


def main():
    dump_reads()
    test_temp_view_shadow()
    test_alternative_approach()


if __name__ == "__main__":
    main()
