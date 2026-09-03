#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-jalon 8A.0 v2 : Fetch historique 24 mois - crypto via yfinance.

V1 utilisait CoinGecko free -> limite a 365 jours.
V2 utilise yfinance pour crypto (pair-USD), pas de limite historique.

Reprend uniquement crypto + FRED. yfinance equity/ETF deja en DB (V1 OK).

ASCII pur, idempotent (INSERT OR IGNORE).
"""
import io
import os
import sqlite3
import sys
import time
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
START_DATE = "2024-06-12"
END_DATE = datetime.now().strftime("%Y-%m-%d")

# yfinance crypto symbols
CRYPTO_YF = {
    "BTC":  "BTC-USD",
    "ETH":  "ETH-USD",
    "LINK": "LINK-USD",
    "SOL":  "SOL-USD",
    "ZEC":  "ZEC-USD",
    # HYPE: hyperliquid - peut-etre absent yfinance, on tente
    "HYPE": "HYPE-USD",
}

FRED_SERIES = {
    "VIX": "VIXCLS",
    "US10Y": "DGS10",
    "US2Y": "DGS2",
    "US3M": "DGS3MO",
    "T10Y2Y": "T10Y2Y",
}

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

print("=" * 70)
print("FETCH HISTORIQUE 24 MOIS V2 - crypto via yfinance")
print("=" * 70)
print("Fenetre:", START_DATE, "->", END_DATE)
print()

conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=10000")
cur = conn.cursor()

# Ensure macro_history exists
cur.execute("""
    CREATE TABLE IF NOT EXISTS macro_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        series_code TEXT NOT NULL,
        date TEXT NOT NULL,
        value REAL,
        source TEXT DEFAULT 'FRED',
        fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(series_code, date)
    )
""")
cur.execute("CREATE INDEX IF NOT EXISTS idx_macro_code_date ON macro_history(series_code, date)")
conn.commit()

def get_or_create_instrument(ticker, asset_class, name=None):
    cur.execute("SELECT id FROM instruments WHERE ticker = ?", (ticker,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO instruments (ticker, name, sector, asset_class, created_at) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (ticker, name or ticker, "", asset_class),
    )
    conn.commit()
    return cur.lastrowid

# =====================================================================
# Step 1: yfinance crypto
# =====================================================================
print("[STEP 1] Fetch yfinance crypto")
try:
    import yfinance as yf
except ImportError:
    print("  [ERR] yfinance non installe")
    sys.exit(1)

total_crypto = 0
for ticker_db, yf_symbol in CRYPTO_YF.items():
    try:
        t0 = time.time()
        df = yf.Ticker(yf_symbol).history(start=START_DATE, end=END_DATE, auto_adjust=False)
        if df is None or len(df) == 0:
            print(f"  {ticker_db:<6} ({yf_symbol:<10}) EMPTY")
            continue
        inst_id = get_or_create_instrument(ticker_db, "crypto")
        n_ins = 0
        for dt, row in df.iterrows():
            d_str = dt.strftime("%Y-%m-%d")
            try:
                o = float(row["Open"])
                h = float(row["High"])
                lo = float(row["Low"])
                c = float(row["Close"])
                v = float(row["Volume"]) if "Volume" in row and row["Volume"] is not None else 0.0
            except Exception:
                continue
            cur.execute(
                "INSERT OR IGNORE INTO prices (instrument_id, date, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (inst_id, d_str, o, h, lo, c, v),
            )
            if cur.rowcount > 0:
                n_ins += 1
        conn.commit()
        dt_s = time.time() - t0
        print(f"  {ticker_db:<6} ({yf_symbol:<10}) fetched={len(df):4d} inserted={n_ins:4d} ({dt_s:.1f}s)")
        total_crypto += n_ins
    except Exception as e:
        print(f"  {ticker_db:<6} ({yf_symbol:<10}) ERR: {e}")

print(f"  Total crypto inserts: {total_crypto}")
print()

# =====================================================================
# Step 2: FRED macro
# =====================================================================
print("[STEP 2] Fetch FRED macro_history")

FRED_FETCH_FN = None
if FRED_API_KEY:
    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
        FRED_FETCH_FN = lambda code: fred.get_series(code, observation_start=START_DATE)
        print("  fredapi avec env var OK")
    except Exception as e:
        print(f"  [ERR] fredapi: {e}")
else:
    print("  [WARN] FRED_API_KEY non defini")
    # Fallback yfinance: ^VIX existe sur Yahoo Finance
    print("  Fallback: tentative yfinance ^VIX + ^TNX (10Y) + ^IRX (3M)")
    try:
        yf_fallback = {
            "VIX":   "^VIX",
            "US10Y": "^TNX",  # 10Y yield (divise par 10 vs FRED)
            "US3M":  "^IRX",  # 3M yield (divise par 10)
        }
        for name, yf_sym in yf_fallback.items():
            try:
                df = yf.Ticker(yf_sym).history(start=START_DATE, end=END_DATE)
                if df is None or len(df) == 0:
                    print(f"  {name:<8} ({yf_sym:<6}) EMPTY")
                    continue
                n_ins = 0
                for dt, row in df.iterrows():
                    try:
                        val = float(row["Close"])
                        d_str = dt.strftime("%Y-%m-%d")
                        cur.execute(
                            "INSERT OR IGNORE INTO macro_history (series_code, date, value, source) "
                            "VALUES (?, ?, ?, 'yfinance')",
                            (name, d_str, val),
                        )
                        if cur.rowcount > 0:
                            n_ins += 1
                    except Exception:
                        continue
                conn.commit()
                print(f"  {name:<8} ({yf_sym:<6}) fetched={len(df):4d} inserted={n_ins:4d}")
            except Exception as e:
                print(f"  {name:<8} ERR: {e}")
    except Exception as e:
        print(f"  [ERR] yfinance fallback: {e}")

if FRED_FETCH_FN:
    for name, code in FRED_SERIES.items():
        try:
            t0 = time.time()
            series = FRED_FETCH_FN(code)
            n_ins = 0
            for dt, val in series.items():
                try:
                    d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                    if val is None or (isinstance(val, float) and val != val):
                        continue
                    cur.execute(
                        "INSERT OR IGNORE INTO macro_history (series_code, date, value, source) "
                        "VALUES (?, ?, ?, 'FRED')",
                        (name, d_str, float(val)),
                    )
                    if cur.rowcount > 0:
                        n_ins += 1
                except Exception:
                    continue
            conn.commit()
            dt_s = time.time() - t0
            print(f"  {name:<8} ({code:<8}) fetched={len(series):4d} inserted={n_ins:4d} ({dt_s:.1f}s)")
        except Exception as e:
            print(f"  {name:<8} ERR: {e}")

print()

# =====================================================================
# Step 3: verification finale
# =====================================================================
print("[STEP 3] Verification finale")
print()

cur.execute("""
    SELECT i.ticker, i.asset_class, COUNT(p.id) AS n, MIN(p.date) AS dmin, MAX(p.date) AS dmax
    FROM instruments i LEFT JOIN prices p ON p.instrument_id = i.id
    GROUP BY i.id ORDER BY n DESC
""")
print(f"{'TICKER':<10} {'CLASS':<8} {'N':>6} {'MIN':<12} {'MAX':<12} MOIS")
print("-" * 60)
n12 = 0
n24 = 0
n_total = 0
for row in cur.fetchall():
    ticker, klass, n, dmin, dmax = row
    if not dmin or not dmax or n == 0:
        continue
    try:
        d1 = datetime.fromisoformat(str(dmin)[:10])
        d2 = datetime.fromisoformat(str(dmax)[:10])
        months = (d2 - d1).days / 30.4
    except Exception:
        months = 0
    print(f"{ticker:<10} {klass:<8} {n:>6} {str(dmin)[:10]:<12} {str(dmax)[:10]:<12} {months:5.1f}")
    n_total += 1
    if months >= 12: n12 += 1
    if months >= 24: n24 += 1

print()
print(f"Total: {n_total} | >= 12 mois: {n12} | >= 24 mois: {n24}")
print()
cur.execute("SELECT series_code, COUNT(*), MIN(date), MAX(date) FROM macro_history GROUP BY series_code")
rows = cur.fetchall()
print("macro_history:")
if rows:
    for r in rows:
        print(f"  {r[0]:<8} n={r[1]:>5}  {r[2]} -> {r[3]}")
else:
    print("  (vide)")

conn.close()
print()
print("[DONE]")
