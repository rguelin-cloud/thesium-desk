# -*- coding: utf-8 -*-
# [FETCH_EQUITY_HISTORY_V1]
# Backfill de 365 jours d'historique prix pour les 5 equity promus :
# CAT, CSCO, TXN, AMD, PLD
#
# Utilise yfinance (deja installe si l'agent universe l'utilise).
# Insere dans prices via instrument_id, INSERT OR IGNORE pour idempotence.
import os
import sys
import sqlite3
import datetime as dt

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
TICKERS = ["CAT", "CSCO", "TXN", "AMD", "PLD"]
DAYS = 400  # marge pour avoir au moins 252 jours ouvres


def header(t):
    print()
    print("=" * 72)
    print("  " + t)
    print("=" * 72)


def get_instrument_id(con, ticker):
    row = con.execute(
        "SELECT id FROM instruments WHERE ticker=?", (ticker,)
    ).fetchone()
    return row[0] if row else None


def fetch_via_yfinance(ticker, days):
    try:
        import yfinance as yf
    except ImportError:
        print("  [KO] yfinance non installe - pip install yfinance")
        return None
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    try:
        df = yf.download(
            ticker, start=start, end=end,
            progress=False, auto_adjust=False, threads=False,
        )
        if df is None or df.empty:
            print("  [KO] {}: yfinance vide".format(ticker))
            return None
        # MultiIndex columns si plusieurs tickers - on attaque 1 ticker, donc
        # squeeze a single index
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = [c[0] for c in df.columns]
        return df
    except Exception as e:
        print("  [KO] {}: yfinance exception : {}".format(ticker, e))
        return None


def insert_prices(con, instrument_id, df):
    cur = con.cursor()
    # Detecte le schema prices
    cols = [r[1] for r in cur.execute("PRAGMA table_info(prices)").fetchall()]
    has_open = "open" in cols
    has_volume = "volume" in cols
    inserted = 0
    skipped = 0
    for idx, row in df.iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        try:
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (close == close):  # NaN check
            continue
        open_v = float(row.get("Open", close)) if has_open else None
        high = float(row.get("High", close))
        low = float(row.get("Low", close))
        vol = int(row.get("Volume", 0) or 0) if has_volume else None

        try:
            if has_open and has_volume:
                cur.execute(
                    "INSERT OR IGNORE INTO prices "
                    "(instrument_id, date, open, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (instrument_id, date_str, open_v, high, low, close, vol),
                )
            elif has_volume:
                cur.execute(
                    "INSERT OR IGNORE INTO prices "
                    "(instrument_id, date, high, low, close, volume) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (instrument_id, date_str, high, low, close, vol),
                )
            else:
                cur.execute(
                    "INSERT OR IGNORE INTO prices "
                    "(instrument_id, date, close) "
                    "VALUES (?, ?, ?)",
                    (instrument_id, date_str, close),
                )
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except sqlite3.IntegrityError as e:
            skipped += 1
    con.commit()
    return inserted, skipped


def main():
    print("NEXTONES fetch equity history - DB=" + DB)
    con = sqlite3.connect(DB)

    header("Etat avant")
    placeholders = ",".join("?" * len(TICKERS))
    rows = con.execute(
        "SELECT i.ticker, COUNT(p.id) "
        "FROM instruments i LEFT JOIN prices p ON p.instrument_id=i.id "
        "WHERE i.ticker IN ({}) GROUP BY i.ticker ORDER BY i.ticker".format(placeholders),
        TICKERS,
    ).fetchall()
    for t, n in rows:
        print("  {:6s} {} prix".format(t, n))

    header("Backfill yfinance ({} jours)".format(DAYS))
    for tk in TICKERS:
        iid = get_instrument_id(con, tk)
        if iid is None:
            print("  {:6s} : pas d'id dans instruments - SKIP".format(tk))
            continue
        print("  {} (id={}) telechargement...".format(tk, iid))
        df = fetch_via_yfinance(tk, DAYS)
        if df is None:
            continue
        ins, skp = insert_prices(con, iid, df)
        print("    {} prix inseres, {} ignores (deja en base)".format(ins, skp))

    header("Etat apres")
    rows = con.execute(
        "SELECT i.ticker, COUNT(p.id), MIN(p.date), MAX(p.date) "
        "FROM instruments i LEFT JOIN prices p ON p.instrument_id=i.id "
        "WHERE i.ticker IN ({}) GROUP BY i.ticker ORDER BY i.ticker".format(placeholders),
        TICKERS,
    ).fetchall()
    for t, n, dmin, dmax in rows:
        print("  {:6s} {} prix de {} a {}".format(t, n, dmin, dmax))

    con.close()
    print()
    print("[FIN] Si tous les tickers ont 250+ prix, les facteurs MOM12-1, Sharpe90,")
    print("      vol90 seront calculables au prochain cycle de decision.")


if __name__ == "__main__":
    main()
