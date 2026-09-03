"""
nextones-diag-prices-schema.py
Diag de la table prices pour comprendre pourquoi VaR + Correlation ont skip.

Usage :
  py -3.13 nextones-diag-prices-schema.py
"""
from __future__ import annotations
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")


def main() -> None:
    if not DB.exists():
        print(f"[FATAL] DB introuvable : {DB}")
        return

    c = sqlite3.connect(str(DB))
    c.row_factory = sqlite3.Row

    print("=" * 60)
    print(" Diag prices / positions / portfolio_history")
    print("=" * 60)

    # Tables existantes
    print("\n[1] Tables candidates :")
    rows = c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE '%price%' OR name LIKE '%position%' "
        "OR name LIKE '%portfolio%' OR name LIKE '%nav%')"
    ).fetchall()
    for r in rows:
        print(f"   - {r['name']}")

    # Schema prices
    print("\n[2] Schema prices :")
    try:
        cols = c.execute("PRAGMA table_info(prices)").fetchall()
        for col in cols:
            print(f"   {col['name']:20s} {col['type']}")
    except Exception as e:
        print(f"   [ERR] {e}")

    # Lignes totales
    print("\n[3] Volume :")
    try:
        n = c.execute("SELECT COUNT(*) AS n FROM prices").fetchone()["n"]
        print(f"   prices total rows : {n}")
        n_sym = c.execute("SELECT COUNT(DISTINCT symbol) AS n FROM prices").fetchone()["n"]
        print(f"   prices distinct symbols : {n_sym}")
    except Exception as e:
        print(f"   [ERR] {e}")

    # Top symboles
    print("\n[4] Top 15 symboles par nb de lignes :")
    try:
        rows = c.execute(
            "SELECT symbol, COUNT(*) AS n, MIN(date) AS dmin, MAX(date) AS dmax "
            "FROM prices GROUP BY symbol ORDER BY n DESC LIMIT 15"
        ).fetchall()
        for r in rows:
            print(f"   {r['symbol']:15s} rows={r['n']:5d}  {r['dmin']} -> {r['dmax']}")
    except Exception as e:
        print(f"   [ERR] {e}")

    # Cas NVDA
    print("\n[5] NVDA (toutes variantes) :")
    try:
        rows = c.execute(
            "SELECT symbol, COUNT(*) AS n, MIN(date) AS dmin, MAX(date) AS dmax "
            "FROM prices WHERE symbol LIKE '%NVDA%' OR symbol LIKE '%nvda%' "
            "GROUP BY symbol"
        ).fetchall()
        if not rows:
            print("   [MISS] aucune ligne LIKE NVDA dans prices")
        for r in rows:
            print(f"   {r['symbol']:15s} rows={r['n']:5d}  {r['dmin']} -> {r['dmax']}")
    except Exception as e:
        print(f"   [ERR] {e}")

    # 3 derniers prix NVDA si trouve
    print("\n[6] 3 derniers prix NVDA :")
    try:
        rows = c.execute(
            "SELECT * FROM prices WHERE symbol='NVDA' ORDER BY date DESC LIMIT 3"
        ).fetchall()
        if not rows:
            print("   [MISS] aucune ligne symbol='NVDA' (exact)")
        for r in rows:
            print("   " + dict(r).__str__())
    except Exception as e:
        print(f"   [ERR] {e}")

    # Positions actuelles
    print("\n[7] Positions actuelles :")
    try:
        cols = c.execute("PRAGMA table_info(positions)").fetchall()
        col_names = [col["name"] for col in cols]
        print(f"   columns : {col_names}")
        rows = c.execute("SELECT * FROM positions LIMIT 20").fetchall()
        for r in rows:
            print("   " + dict(r).__str__())
    except Exception as e:
        print(f"   [ERR] {e}")

    # Portfolio history
    print("\n[8] Portfolio history schema :")
    try:
        cols = c.execute("PRAGMA table_info(portfolio_history)").fetchall()
        for col in cols:
            print(f"   {col['name']:20s} {col['type']}")
        last = c.execute(
            "SELECT * FROM portfolio_history ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if last:
            print(f"   last row : {dict(last)}")
    except Exception as e:
        print(f"   [ERR] {e}")

    # Risk pretrade log (deja existant ?)
    print("\n[9] risk_pretrade_log (3 dernieres entrees) :")
    try:
        rows = c.execute(
            "SELECT id, ts, symbol, side, qty, passed, blocked_by FROM risk_pretrade_log "
            "ORDER BY id DESC LIMIT 3"
        ).fetchall()
        for r in rows:
            print(f"   {dict(r)}")
    except Exception as e:
        print(f"   [ERR] {e}")

    c.close()


if __name__ == "__main__":
    main()
