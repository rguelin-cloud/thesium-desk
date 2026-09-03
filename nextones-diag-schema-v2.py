"""
nextones-diag-schema-v2.py
Diag complementaire : instruments + portfolio_positions + portfolio_state.
Objectif : trouver le bon JOIN prices.instrument_id <-> symbol et la structure positions.

Usage : py -3.13 nextones-diag-schema-v2.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")


def show_table(c, name):
    print(f"\n--- {name} ---")
    try:
        cols = c.execute(f"PRAGMA table_info({name})").fetchall()
        if not cols:
            print(f"   [MISS] table {name} inexistante")
            return
        for col in cols:
            print(f"   {col['name']:25s} {col['type']}")
        n = c.execute(f"SELECT COUNT(*) AS n FROM {name}").fetchone()["n"]
        print(f"   rows : {n}")
        rows = c.execute(f"SELECT * FROM {name} LIMIT 5").fetchall()
        print(f"   sample (5) :")
        for r in rows:
            print("     " + dict(r).__str__())
    except Exception as e:
        print(f"   [ERR] {e}")


def main() -> None:
    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row

    print("=" * 60)
    print(" Diag instruments / portfolio_positions / portfolio_state")
    print("=" * 60)

    for t in ("instruments", "portfolio_positions", "portfolio_state",
              "portfolio_targets", "portfolio_targets_history"):
        show_table(c, t)

    # Test JOIN prices <-> instruments
    print("\n[JOIN test] prices x instruments (top 10 par nb lignes) :")
    try:
        rows = c.execute("""
            SELECT i.symbol AS sym, COUNT(p.id) AS n,
                   MIN(p.date) AS dmin, MAX(p.date) AS dmax
            FROM prices p
            JOIN instruments i ON i.id = p.instrument_id
            GROUP BY i.symbol
            ORDER BY n DESC
            LIMIT 10
        """).fetchall()
        for r in rows:
            print(f"   {r['sym']:15s} rows={r['n']:5d}  {r['dmin']} -> {r['dmax']}")
    except Exception as e:
        print(f"   [ERR JOIN1] {e}")
        # fallback : peut-etre que la colonne s'appelle ticker
        try:
            rows = c.execute("""
                SELECT i.ticker AS sym, COUNT(p.id) AS n
                FROM prices p JOIN instruments i ON i.id = p.instrument_id
                GROUP BY i.ticker ORDER BY n DESC LIMIT 10
            """).fetchall()
            print("   (fallback ticker)")
            for r in rows:
                print(f"   {r['sym']:15s} rows={r['n']:5d}")
        except Exception as e2:
            print(f"   [ERR JOIN2] {e2}")

    # NVDA returns sample (60 derniers)
    print("\n[NVDA 60 derniers closes] :")
    try:
        rows = c.execute("""
            SELECT p.date, p.close
            FROM prices p JOIN instruments i ON i.id = p.instrument_id
            WHERE i.symbol = 'NVDA'
            ORDER BY p.date DESC LIMIT 60
        """).fetchall()
        print(f"   rows : {len(rows)}")
        if rows:
            print(f"   plus recent : {rows[0]['date']} close={rows[0]['close']}")
            print(f"   plus ancien : {rows[-1]['date']} close={rows[-1]['close']}")
    except Exception as e:
        print(f"   [ERR] {e}")

    c.close()


if __name__ == "__main__":
    main()
