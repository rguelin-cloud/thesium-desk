# -*- coding: utf-8 -*-
# nextones-fetch-reet-prices.py
# Fetch 400 jours de prix REET via yfinance -> table prices (instrument_id=31)
# Conforme schema NEXTONES : meme pattern que nextones-fetch-equity-history.py

import sqlite3
import sys
from datetime import datetime

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
TICKER = "REET"
DAYS = 400


def main():
    print(f"NEXTONES fetch REET prices - DB={DB_PATH}")
    print("=" * 72)

    try:
        import yfinance as yf
    except ImportError:
        print("[ERREUR] yfinance non installe. py -3.13 -m pip install yfinance")
        sys.exit(1)

    con = sqlite3.connect(DB_PATH, timeout=30)
    con.execute("PRAGMA journal_mode=WAL")
    cur = con.cursor()

    # 1. Recuperer instrument_id REET
    cur.execute("SELECT id, ticker, name, asset_class FROM instruments WHERE ticker=?", (TICKER,))
    row = cur.fetchone()
    if not row:
        print(f"[ERREUR] {TICKER} absent de table instruments.")
        con.close()
        sys.exit(1)
    instr_id, ticker, name, asset_class = row
    print(f"  Instrument trouve : id={instr_id} ticker={ticker} name={name} class={asset_class}")
    print()

    # 2. Etat avant
    print("=" * 72)
    print("  Etat avant")
    print("=" * 72)
    cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE instrument_id=?", (instr_id,))
    n_before, d_min, d_max = cur.fetchone()
    print(f"  {TICKER}  {n_before} prix" + (f" de {d_min} a {d_max}" if n_before else ""))
    print()

    # 3. Fetch yfinance
    print("=" * 72)
    print(f"  Backfill yfinance ({DAYS} jours)")
    print("=" * 72)
    print(f"  {TICKER} (id={instr_id}) telechargement...")

    try:
        t = yf.Ticker(TICKER)
        hist = t.history(period=f"{DAYS}d", auto_adjust=False)
    except Exception as e:
        print(f"    [ERREUR yfinance] {e}")
        con.close()
        sys.exit(1)

    if hist is None or hist.empty:
        print(f"    [ERREUR] aucune donnee retournee par yfinance pour {TICKER}")
        con.close()
        sys.exit(1)

    # 4. Insertion
    inserted = 0
    skipped = 0
    for idx, r in hist.iterrows():
        d = idx.strftime("%Y-%m-%d")
        try:
            cur.execute(
                """INSERT OR IGNORE INTO prices
                   (instrument_id, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    instr_id,
                    d,
                    float(r["Open"]) if r["Open"] == r["Open"] else None,
                    float(r["High"]) if r["High"] == r["High"] else None,
                    float(r["Low"]) if r["Low"] == r["Low"] else None,
                    float(r["Close"]) if r["Close"] == r["Close"] else None,
                    int(r["Volume"]) if r["Volume"] == r["Volume"] else 0,
                ),
            )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"    [WARN] insert {d} : {e}")

    con.commit()
    print(f"    {inserted} prix inseres, {skipped} ignores (deja en base)")
    print()

    # 5. Etat apres
    print("=" * 72)
    print("  Etat apres")
    print("=" * 72)
    cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE instrument_id=?", (instr_id,))
    n_after, d_min, d_max = cur.fetchone()
    print(f"  {TICKER}  {n_after} prix" + (f" de {d_min} a {d_max}" if n_after else ""))
    print()

    con.close()

    if n_after >= 250:
        print(f"[OK] {TICKER} : {n_after} prix dispo. Facteurs MOM12-1, Sharpe90, vol90 calculables.")
    elif n_after >= 90:
        print(f"[OK partiel] {TICKER} : {n_after} prix dispo (>=90j minimum). Certains facteurs longs indispo.")
    else:
        print(f"[KO] {TICKER} : seulement {n_after} prix. <90j minimum. Verifier yfinance.")


if __name__ == "__main__":
    main()
