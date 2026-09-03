# -*- coding: utf-8 -*-
"""
[DIAG_SOL_PIPELINE_V1]
Trace ce qui arrive a SOL dans le dernier cycle :
- prix dispo
- proposition emise par CryptoAgent ?
- passe le reconciler ?
- target_universe / theses / orders / fills

Usage:
    cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk
    py -3.13 nextones-diag-sol-pipeline.py
"""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

def section(t):
    print("\n" + "="*70)
    print(f"  {t}")
    print("="*70)

def q(conn, sql, params=()):
    return conn.execute(sql, params).fetchall()

def main():
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    section("1) instruments + target_universe")
    for r in q(conn, "SELECT id, ticker, name, sector, asset_class FROM instruments WHERE ticker='SOL'"):
        print(f"  instruments     : {dict(r)}")
    for r in q(conn, "SELECT * FROM target_universe WHERE ticker='SOL'"):
        print(f"  target_universe : {dict(r)}")

    section("2) prices(SOL)")
    rows = q(conn, """
        SELECT p.date, p.open, p.close, p.volume
        FROM prices p JOIN instruments i ON i.id=p.instrument_id
        WHERE i.ticker='SOL' ORDER BY p.date DESC LIMIT 20
    """)
    print(f"  total recent: {len(rows)}")
    for r in rows:
        print(f"  {dict(r)}")
    n_total = q(conn, "SELECT COUNT(*) c FROM prices p JOIN instruments i ON i.id=p.instrument_id WHERE i.ticker='SOL'")[0]["c"]
    print(f"  TOTAL prix SOL: {n_total}")

    section("3) theses (toutes recentes, filtrage SOL)")
    try:
        rows = q(conn, """
            SELECT t.id, t.ticker, t.agent, t.signal, t.composite_score, t.conviction,
                   t.proposed_action, t.created_at
            FROM theses t
            WHERE t.ticker='SOL'
            ORDER BY t.id DESC LIMIT 10
        """)
        if rows:
            for r in rows: print(f"  {dict(r)}")
        else:
            print("  Aucune these pour SOL.")
    except Exception as e:
        print(f"  (table theses non accessible: {e})")

    section("4) orders SOL")
    try:
        rows = q(conn, """
            SELECT o.id, o.side, o.quantity, o.status, o.created_at,
                   o.rejection_reason, o.thesis_id
            FROM orders o JOIN instruments i ON i.id=o.instrument_id
            WHERE i.ticker='SOL'
            ORDER BY o.id DESC LIMIT 20
        """)
        if rows:
            for r in rows: print(f"  {dict(r)}")
        else:
            print("  Aucun ordre pour SOL.")
    except Exception as e:
        print(f"  (erreur: {e})")

    section("5) risk_pretrade_log SOL (3 dernieres entrees)")
    try:
        rows = q(conn, """
            SELECT * FROM risk_pretrade_log
            WHERE ticker='SOL'
            ORDER BY id DESC LIMIT 5
        """)
        if rows:
            for r in rows: print(f"  {dict(r)}")
        else:
            print("  Aucune entree risk_pretrade pour SOL.")
    except Exception as e:
        print(f"  (table risk_pretrade_log absente ou autre: {e})")

    section("6) Sample features CryptoAgent que SOL peut calculer")
    # Simule un check RSI / mom
    closes = [r["close"] for r in q(conn,
        "SELECT close FROM prices p JOIN instruments i ON i.id=p.instrument_id "
        "WHERE i.ticker='SOL' ORDER BY date ASC")]
    print(f"  closes disponibles: {len(closes)} -> {closes}")
    print(f"  RSI(14) calculable: {'OUI' if len(closes) >= 15 else 'NON (need >=15)'}")
    print(f"  Momentum 30j : {'OUI' if len(closes) >= 31 else 'NON (need >=31)'}")
    print(f"  Vol 30j     : {'OUI' if len(closes) >= 30 else 'NON (need >=30)'}")
    print(f"  Sharpe 90j  : {'OUI' if len(closes) >= 90 else 'NON (need >=90)'}")

    print()
    print("=> SOL filtre par scoring/threshold tant qu'il n'a pas >=15 closes.")
    print("=> Solution: enrichir prices(SOL) avec 90 jours d'historique via CoinGecko.")

    conn.close()

if __name__ == "__main__":
    main()
