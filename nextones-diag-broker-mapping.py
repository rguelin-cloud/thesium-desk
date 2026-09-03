# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-BROKER-MAPPING-V1]
# Diagnostic complet de la table instrument_broker_mapping :
#   - existence
#   - schema (colonnes)
#   - count total
#   - count par valeur de tradable
#   - sample 20 lignes
#   - confronte aux 20 tickers Thesium remontes par le reconciler
#
# Usage : py -3.13 nextones-diag-broker-mapping.py

import os
import sqlite3
import sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

THESIUM_TICKERS = [
    "AAPL", "AMD", "AMZN", "BTC", "CAT", "CSCO", "ETH", "GOOGL", "HYPE",
    "LINK", "META", "MSFT", "NVDA", "PLD", "SOL", "TSLA", "TXN", "XLE",
    "XLK", "ZEC",
]


def banner(t):
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    if not os.path.exists(DB):
        print("[FAIL] db introuvable :", DB)
        sys.exit(1)

    con = sqlite3.connect(DB, timeout=10.0)
    con.execute("PRAGMA busy_timeout=10000")
    cur = con.cursor()

    banner("[1] Existence des tables broker_*")
    rows = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'broker_%' OR name LIKE '%broker%' "
        "ORDER BY name"
    ).fetchall()
    for r in rows:
        print("  -", r[0])
    if not rows:
        print("  (aucune table broker_*)")

    banner("[2] Schema instrument_broker_mapping")
    try:
        cols = cur.execute(
            "PRAGMA table_info(instrument_broker_mapping)"
        ).fetchall()
        if not cols:
            print("  (table absente ou vide de colonnes)")
        else:
            for c in cols:
                # cid, name, type, notnull, dflt_value, pk
                print(f"  cid={c[0]} name={c[1]:25s} type={c[2]:15s} "
                      f"notnull={c[3]} pk={c[5]}")
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[3] Count instrument_broker_mapping")
    try:
        n_total = cur.execute(
            "SELECT COUNT(*) FROM instrument_broker_mapping"
        ).fetchone()[0]
        print(f"  total                 : {n_total}")
        try:
            n_tradable = cur.execute(
                "SELECT COUNT(*) FROM instrument_broker_mapping "
                "WHERE tradable=1"
            ).fetchone()[0]
            print(f"  WHERE tradable=1      : {n_tradable}")
        except sqlite3.Error as e:
            print(f"  [WARN] filtre tradable=1 KO : {e}")
        try:
            n_t0 = cur.execute(
                "SELECT COUNT(*) FROM instrument_broker_mapping "
                "WHERE tradable=0"
            ).fetchone()[0]
            print(f"  WHERE tradable=0      : {n_t0}")
        except sqlite3.Error:
            pass
        try:
            n_tnull = cur.execute(
                "SELECT COUNT(*) FROM instrument_broker_mapping "
                "WHERE tradable IS NULL"
            ).fetchone()[0]
            print(f"  WHERE tradable IS NULL: {n_tnull}")
        except sqlite3.Error:
            pass
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[4] Sample 25 lignes instrument_broker_mapping")
    try:
        rows = cur.execute(
            "SELECT * FROM instrument_broker_mapping LIMIT 25"
        ).fetchall()
        if not rows:
            print("  (vide)")
        else:
            col_names = [d[0] for d in cur.description]
            print("  cols:", " | ".join(col_names))
            for r in rows:
                print("  ", r)
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[5] Cherche les 20 tickers Thesium")
    try:
        # detecte la colonne thesium ticker
        cols = [c[1] for c in cur.execute(
            "PRAGMA table_info(instrument_broker_mapping)"
        ).fetchall()]
        ticker_col = None
        for cand in ("thesium_ticker", "ticker", "instrument_ticker"):
            if cand in cols:
                ticker_col = cand
                break
        if ticker_col is None:
            print("  [WARN] aucune colonne ticker reconnue dans le mapping")
        else:
            print(f"  colonne ticker = {ticker_col}")
            for t in THESIUM_TICKERS:
                r = cur.execute(
                    f"SELECT * FROM instrument_broker_mapping "
                    f"WHERE {ticker_col}=?",
                    (t,)
                ).fetchone()
                if r is None:
                    print(f"    {t:8s} : ABSENT")
                else:
                    print(f"    {t:8s} : {r}")
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[6] broker_universe_activtrades (controle)")
    try:
        n = cur.execute(
            "SELECT COUNT(*) FROM broker_universe_activtrades"
        ).fetchone()[0]
        print(f"  total broker_universe_activtrades : {n}")
        # quelques exemples critiques
        for sym in ("AAPL.US", "LINKUSD", "BTCUSD", "ETHUSD", "SOLUSD"):
            r = cur.execute(
                "SELECT * FROM broker_universe_activtrades "
                "WHERE symbol=?",
                (sym,)
            ).fetchone()
            print(f"    {sym:10s} -> {r}")
    except sqlite3.Error as e:
        print("  [ERR]", e)

    banner("[7] DB pragmas")
    for p in ("journal_mode", "busy_timeout"):
        v = cur.execute(f"PRAGMA {p}").fetchone()
        print(f"  {p} = {v}")

    con.close()


if __name__ == "__main__":
    main()
