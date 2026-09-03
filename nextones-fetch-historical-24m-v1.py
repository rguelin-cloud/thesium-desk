#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-jalon 8A.0 : Fetch historique 24 mois pour backtest replay.

Sources:
  - yfinance (equity/ETF) : SPY/QQQ + univers prod
  - CoinGecko free (crypto) : BTC/ETH/LINK/SOL/HYPE/ZEC
  - FRED (VIX + 10Y + 2Y + 3M) : nouvelle table macro_history

Stockage:
  - prices (existant) : equity/ETF/crypto rows ajoutees si manquantes
  - macro_history (nouvelle) : VIX, US10Y, US2Y, US3M, T10Y2Y daily

Fenetre: 2024-06-12 -> aujourd'hui (~24 mois)

Idempotent: INSERT OR IGNORE par (instrument_id, date).
ASCII pur. Write DB en mode WAL.

Dependances: pip install yfinance pycoingecko fredapi pandas
"""
import io
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
START_DATE = "2024-06-12"
END_DATE = datetime.now().strftime("%Y-%m-%d")

# Univers cible (coherent avec prod actuelle + benchmarks)
EQUITY_TICKERS = [
    "SPY", "QQQ",  # benchmarks
    "AAPL", "AMZN", "AMD", "ARM", "BAC", "CAT", "COP", "CSCO",
    "GOOGL", "GS", "JNJ", "JPM", "META", "MRK", "MS", "MSFT",
    "NVDA", "PLD", "TSLA", "TXN", "UNH", "UNP", "XOM",
]
ETF_TICKERS = ["REET", "XLB", "XLE", "XLI", "XLK"]
CRYPTO_TICKERS = {
    # ticker_db: coingecko_id
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "LINK": "chainlink",
    "SOL": "solana",
    "HYPE": "hyperliquid",
    "ZEC": "zcash",
}

# FRED series
FRED_SERIES = {
    "VIX": "VIXCLS",      # CBOE Volatility Index
    "US10Y": "DGS10",     # 10-Year Treasury
    "US2Y": "DGS2",       # 2-Year Treasury
    "US3M": "DGS3MO",     # 3-Month Treasury
    "T10Y2Y": "T10Y2Y",   # 10Y-2Y spread
}

# FRED key (read from env or hardcoded fallback)
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

print("=" * 70)
print("FETCH HISTORIQUE 24 MOIS - PRE-JALON 8A.0")
print("=" * 70)
print("Fenetre:", START_DATE, "->", END_DATE)
print("Equity:", len(EQUITY_TICKERS), "/ ETF:", len(ETF_TICKERS), "/ Crypto:", len(CRYPTO_TICKERS))
print()

# =====================================================================
# Step 0: connexion DB + WAL + migration macro_history
# =====================================================================
print("[STEP 0] Init DB + migration macro_history")
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=10000")
cur = conn.cursor()

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
print("  table macro_history OK")
print()

# =====================================================================
# Helper: get or create instrument_id
# =====================================================================
def get_or_create_instrument(ticker, asset_class, name=None, sector=None):
    cur.execute("SELECT id FROM instruments WHERE ticker = ?", (ticker,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute(
        "INSERT INTO instruments (ticker, name, sector, asset_class, created_at) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (ticker, name or ticker, sector or "", asset_class),
    )
    conn.commit()
    return cur.lastrowid

def insert_prices(instrument_id, rows):
    """rows: list of (date, open, high, low, close, volume)"""
    n_ins = 0
    for r in rows:
        try:
            cur.execute(
                "INSERT OR IGNORE INTO prices (instrument_id, date, open, high, low, close, volume) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (instrument_id, r[0], r[1], r[2], r[3], r[4], r[5]),
            )
            if cur.rowcount > 0:
                n_ins += 1
        except Exception as e:
            print("    insert err", r[0], e)
    conn.commit()
    return n_ins

# =====================================================================
# Step 1: yfinance equity + ETF
# =====================================================================
print("[STEP 1] Fetch yfinance equity + ETF")
try:
    import yfinance as yf
except ImportError:
    print("  [ERR] yfinance non installe -> pip install yfinance")
    sys.exit(1)

stocks = [(t, "equity") for t in EQUITY_TICKERS] + [(t, "etf") for t in ETF_TICKERS]
total_yf = 0
for ticker, klass in stocks:
    try:
        t0 = time.time()
        df = yf.Ticker(ticker).history(start=START_DATE, end=END_DATE, auto_adjust=False)
        if df is None or len(df) == 0:
            print(f"  {ticker:<8} {klass:<6} EMPTY")
            continue
        inst_id = get_or_create_instrument(ticker, klass)
        rows = []
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
            rows.append((d_str, o, h, lo, c, v))
        n_ins = insert_prices(inst_id, rows)
        dt_s = time.time() - t0
        print(f"  {ticker:<8} {klass:<6} fetched={len(df):4d} inserted={n_ins:4d} ({dt_s:.1f}s)")
        total_yf += n_ins
    except Exception as e:
        print(f"  {ticker:<8} ERR: {e}")

print(f"  Total yfinance inserts: {total_yf}")
print()

# =====================================================================
# Step 2: CoinGecko crypto
# =====================================================================
print("[STEP 2] Fetch CoinGecko crypto")
try:
    from pycoingecko import CoinGeckoAPI
except ImportError:
    print("  [ERR] pycoingecko non installe -> pip install pycoingecko")
    sys.exit(1)

cg = CoinGeckoAPI()
# unix timestamps
ts_start = int(datetime.fromisoformat(START_DATE).timestamp())
ts_end = int(datetime.fromisoformat(END_DATE).timestamp())

total_cg = 0
for ticker_db, cg_id in CRYPTO_TICKERS.items():
    try:
        t0 = time.time()
        data = cg.get_coin_market_chart_range_by_id(
            id=cg_id, vs_currency="usd",
            from_timestamp=ts_start, to_timestamp=ts_end,
        )
        if not data or "prices" not in data:
            print(f"  {ticker_db:<6} EMPTY")
            continue
        prices = data["prices"]  # [[ts_ms, price], ...]
        volumes = {p[0]: 0.0 for p in prices}
        if "total_volumes" in data:
            for ts_ms, v in data["total_volumes"]:
                volumes[ts_ms] = v
        inst_id = get_or_create_instrument(ticker_db, "crypto")
        # Dedupe par jour (CoinGecko renvoie potentiellement hourly)
        by_day = {}
        for ts_ms, price in prices:
            d_str = datetime.fromtimestamp(ts_ms / 1000.0).strftime("%Y-%m-%d")
            v = volumes.get(ts_ms, 0.0)
            # keep last sample of each day
            by_day[d_str] = (price, v)
        rows = []
        for d_str in sorted(by_day.keys()):
            price, v = by_day[d_str]
            # CoinGecko free renvoie pas OHL, on duplique close
            rows.append((d_str, price, price, price, price, v))
        n_ins = insert_prices(inst_id, rows)
        dt_s = time.time() - t0
        print(f"  {ticker_db:<6} fetched={len(by_day):4d} inserted={n_ins:4d} ({dt_s:.1f}s)")
        total_cg += n_ins
        # Rate limit free tier: 30 calls/min -> 2s entre calls safe
        time.sleep(2.5)
    except Exception as e:
        print(f"  {ticker_db:<6} ERR: {e}")
        time.sleep(5)

print(f"  Total CoinGecko inserts: {total_cg}")
print()

# =====================================================================
# Step 3: FRED macro (VIX + yields)
# =====================================================================
print("[STEP 3] Fetch FRED macro_history")

if not FRED_API_KEY:
    print("  [WARN] FRED_API_KEY non defini dans env")
    print("  Tentative via fred_client local s'il existe...")
    try:
        sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
        from fred_client import FREDClient  # type: ignore
        fc = FREDClient()
        FRED_FETCH_FN = lambda code: fc.get_series(code, observation_start=START_DATE)
        print("  fred_client local OK")
    except Exception as e:
        print(f"  [ERR] fred_client introuvable: {e}")
        print("  Defini FRED_API_KEY ou installe fredapi: pip install fredapi")
        print("  Skip step 3 (le replay sans VIX devra fallback sur vol proxy)")
        FRED_FETCH_FN = None
else:
    try:
        from fredapi import Fred
        fred = Fred(api_key=FRED_API_KEY)
        FRED_FETCH_FN = lambda code: fred.get_series(code, observation_start=START_DATE)
        print("  fredapi OK")
    except ImportError:
        print("  [ERR] fredapi non installe -> pip install fredapi")
        FRED_FETCH_FN = None

total_fred = 0
if FRED_FETCH_FN:
    for name, code in FRED_SERIES.items():
        try:
            t0 = time.time()
            series = FRED_FETCH_FN(code)
            if series is None or len(series) == 0:
                print(f"  {name:<8} ({code:<8}) EMPTY")
                continue
            n_ins = 0
            for dt, val in series.items():
                try:
                    d_str = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
                    if val is None or (isinstance(val, float) and val != val):  # NaN check
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
            total_fred += n_ins
        except Exception as e:
            print(f"  {name:<8} ERR: {e}")

print(f"  Total FRED inserts: {total_fred}")
print()

# =====================================================================
# Step 4: verification finale
# =====================================================================
print("[STEP 4] Verification finale")
print()

cur.execute("""
    SELECT i.ticker, i.asset_class, COUNT(p.id) AS n, MIN(p.date) AS dmin, MAX(p.date) AS dmax
    FROM instruments i LEFT JOIN prices p ON p.instrument_id = i.id
    GROUP BY i.id ORDER BY n DESC
""")
print(f"{'TICKER':<10} {'CLASS':<8} {'N':>6} {'MIN':<12} {'MAX':<12} MOIS")
print("-" * 60)
for row in cur.fetchall():
    ticker, klass, n, dmin, dmax = row
    if not dmin or not dmax:
        continue
    try:
        d1 = datetime.fromisoformat(str(dmin)[:10])
        d2 = datetime.fromisoformat(str(dmax)[:10])
        months = (d2 - d1).days / 30.4
    except Exception:
        months = 0
    print(f"{ticker:<10} {klass:<8} {n:>6} {str(dmin)[:10]:<12} {str(dmax)[:10]:<12} {months:5.1f}")

print()
cur.execute("SELECT series_code, COUNT(*), MIN(date), MAX(date) FROM macro_history GROUP BY series_code")
print("macro_history:")
for r in cur.fetchall():
    print(f"  {r[0]:<8} n={r[1]:>5}  {r[2]} -> {r[3]}")

conn.close()
print()
print("[DONE]")
print()
print("Prochaine etape: re-run nextones-diag-prices-coverage-v2.py pour confirmer")
print("Puis lancer jalon 8A (schema replay + adapters + fill_simulator)")
