#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag avant Phase 2 graphe :
1. Schema table prices (colonnes)
2. SPY/QQQ presents dans instruments ? combien de prices ?
3. portfolio_history : MIN(date), MAX(date), count
"""
import sqlite3
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("1) SCHEMA prices")
    print("=" * 70)
    for row in cur.execute("PRAGMA table_info(prices)").fetchall():
        print("  " + str(dict(row)))

    print()
    print("=" * 70)
    print("2) SCHEMA instruments")
    print("=" * 70)
    for row in cur.execute("PRAGMA table_info(instruments)").fetchall():
        print("  " + str(dict(row)))

    print()
    print("=" * 70)
    print("3) SPY / QQQ dans instruments")
    print("=" * 70)
    rows = cur.execute(
        "SELECT * FROM instruments WHERE ticker IN ('SPY','QQQ','^GSPC','^NDX','^SPX')"
    ).fetchall()
    if not rows:
        print("  ABSENT - SPY/QQQ non presents dans instruments")
    for row in rows:
        print("  " + str(dict(row)))

    print()
    print("=" * 70)
    print("4) Count prices pour SPY/QQQ (si presents)")
    print("=" * 70)
    for tk in ("SPY", "QQQ"):
        try:
            r = cur.execute(
                "SELECT COUNT(*) AS c, MIN(date) AS dmin, MAX(date) AS dmax "
                "FROM prices p JOIN instruments i ON p.instrument_id = i.id "
                "WHERE i.ticker = ?",
                (tk,),
            ).fetchone()
            print("  " + tk + " : count=" + str(r["c"]) + " min=" + str(r["dmin"]) + " max=" + str(r["dmax"]))
        except Exception as e:
            print("  " + tk + " : ERROR " + str(e))

    print()
    print("=" * 70)
    print("5) portfolio_history : MIN/MAX date + count")
    print("=" * 70)
    r = cur.execute(
        "SELECT COUNT(*) AS c, MIN(date) AS dmin, MAX(date) AS dmax FROM portfolio_history"
    ).fetchone()
    print("  count=" + str(r["c"]) + " min=" + str(r["dmin"]) + " max=" + str(r["dmax"]))

    print()
    print("=" * 70)
    print("6) Sample 3 lignes portfolio_history recentes")
    print("=" * 70)
    for row in cur.execute(
        "SELECT date, total_value, cash, total_pnl FROM portfolio_history ORDER BY date DESC LIMIT 3"
    ).fetchall():
        print("  " + str(dict(row)))

    conn.close()


if __name__ == "__main__":
    main()
