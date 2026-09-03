# nextones-fetch-mis-history.py
# Fetch 120 jours d'historique pour les tickers MIS (XLE, XLK, XLI, XLB via Yahoo + HYPE via CoinGecko)
# Insertion idempotente dans prices(instrument_id, date, open, high, low, close, volume)
# ASCII pur. Read utf-8-sig, write utf-8 sans BOM.

import sqlite3
import os
import sys
import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if not os.path.exists(DB):
    print(f"DB introuvable: {DB}")
    sys.exit(1)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0 Safari/537.36"

# Mapping ticker -> source/id
JOBS = [
    {"ticker": "XLE", "source": "yahoo", "yahoo_symbol": "XLE"},
    {"ticker": "XLK", "source": "yahoo", "yahoo_symbol": "XLK"},
    {"ticker": "XLI", "source": "yahoo", "yahoo_symbol": "XLI"},
    {"ticker": "XLB", "source": "yahoo", "yahoo_symbol": "XLB"},
    {"ticker": "HYPE", "source": "coingecko", "cg_id": "hyperliquid"},
]

DAYS = 120

# -------- HTTP helpers --------

def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} on {url}")
        return resp.read().decode("utf-8")

# -------- Yahoo Finance --------

def fetch_yahoo(symbol, days):
    # range=6mo donne ~125 barres jours ouvres
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=6mo&interval=1d"
    body = http_get(url)
    data = json.loads(body)
    res = data.get("chart", {}).get("result")
    if not res:
        err = data.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo empty result for {symbol}: {err}")
    r0 = res[0]
    timestamps = r0.get("timestamp") or []
    ind = r0.get("indicators", {}).get("quote", [{}])[0]
    opens = ind.get("open") or []
    highs = ind.get("high") or []
    lows = ind.get("low") or []
    closes = ind.get("close") or []
    vols = ind.get("volume") or []
    bars = []
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        v = vols[i] if i < len(vols) else None
        if c is None:
            continue
        bars.append((dt, o, h, l, c, v))
    return bars

# -------- CoinGecko --------

CG_LAST_CALL = 0.0
CG_THROTTLE_S = 2.5

def cg_get(url, max_retries=3):
    global CG_LAST_CALL
    delays = [10, 20, 40]
    for attempt in range(max_retries + 1):
        wait = CG_THROTTLE_S - (time.time() - CG_LAST_CALL)
        if wait > 0:
            time.sleep(wait)
        try:
            body = http_get(url, timeout=25)
            CG_LAST_CALL = time.time()
            return json.loads(body)
        except urllib.error.HTTPError as e:
            CG_LAST_CALL = time.time()
            if e.code == 429 and attempt < max_retries:
                d = delays[attempt]
                print(f"  CG 429, backoff {d}s (attempt {attempt+1}/{max_retries})")
                time.sleep(d)
                continue
            raise
        except Exception as e:
            CG_LAST_CALL = time.time()
            raise

def fetch_coingecko(cg_id, days):
    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart?vs_currency=usd&days={days}&interval=daily"
    data = cg_get(url)
    prices = data.get("prices") or []
    vols = data.get("total_volumes") or []
    # daily granularity -> 1 point par jour, on a close uniquement
    # Pour OHLC reel on devrait appeler /ohlc mais on se contente de close=open=high=low pour HYPE
    vol_map = {}
    for ts_ms, v in vols:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        vol_map[dt] = v
    bars = []
    for ts_ms, p in prices:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        v = vol_map.get(dt)
        bars.append((dt, p, p, p, p, v))
    # dedupe par date (CG renvoie parfois 2x la meme date)
    seen = {}
    for b in bars:
        seen[b[0]] = b
    return sorted(seen.values(), key=lambda x: x[0])

# -------- DB helpers --------

def get_instrument_id(cur, ticker):
    r = cur.execute("SELECT id FROM instruments WHERE ticker = ?", (ticker,)).fetchone()
    return r[0] if r else None

def count_bars(cur, iid):
    r = cur.execute("SELECT COUNT(*) FROM prices WHERE instrument_id = ?", (iid,)).fetchone()
    return r[0] if r else 0

def insert_bars(con, cur, iid, bars):
    """Insert OR IGNORE - suppose un unique index sur (instrument_id, date) ou on tolere les doublons."""
    # On utilise INSERT OR REPLACE pour ecraser les valeurs existantes (seed Jalon 4)
    inserted = 0
    for (dt, o, h, l, c, v) in bars:
        try:
            cur.execute(
                "INSERT INTO prices(instrument_id, date, open, high, low, close, volume) "
                "VALUES(?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(instrument_id, date) DO UPDATE SET "
                "open=excluded.open, high=excluded.high, low=excluded.low, "
                "close=excluded.close, volume=excluded.volume",
                (iid, dt, o, h, l, c, v)
            )
            inserted += 1
        except sqlite3.IntegrityError:
            # Pas de contrainte UNIQUE -> on tente un INSERT classique avec check manuel
            r = cur.execute(
                "SELECT id FROM prices WHERE instrument_id = ? AND date = ?",
                (iid, dt)
            ).fetchone()
            if r:
                cur.execute(
                    "UPDATE prices SET open=?, high=?, low=?, close=?, volume=? WHERE id = ?",
                    (o, h, l, c, v, r[0])
                )
            else:
                cur.execute(
                    "INSERT INTO prices(instrument_id, date, open, high, low, close, volume) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (iid, dt, o, h, l, c, v)
                )
            inserted += 1
        except sqlite3.OperationalError as e:
            # ON CONFLICT pas supporte (pas d'index unique) -> fallback manuel
            r = cur.execute(
                "SELECT id FROM prices WHERE instrument_id = ? AND date = ?",
                (iid, dt)
            ).fetchone()
            if r:
                cur.execute(
                    "UPDATE prices SET open=?, high=?, low=?, close=?, volume=? WHERE id = ?",
                    (o, h, l, c, v, r[0])
                )
            else:
                cur.execute(
                    "INSERT INTO prices(instrument_id, date, open, high, low, close, volume) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (iid, dt, o, h, l, c, v)
                )
            inserted += 1
    con.commit()
    return inserted

# -------- Main --------

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    print("=" * 70)
    print(f"FETCH MIS HISTORY (target {DAYS} jours)")
    print("=" * 70)

    results = []
    for job in JOBS:
        t = job["ticker"]
        src = job["source"]
        print()
        print(f"--- {t} via {src} ---")
        iid = get_instrument_id(cur, t)
        if iid is None:
            print(f"  ERREUR: {t} absent de instruments")
            results.append((t, "NO_INSTRUMENT", 0, 0))
            continue
        before = count_bars(cur, iid)
        print(f"  instrument_id={iid}, bars avant={before}")
        try:
            if src == "yahoo":
                bars = fetch_yahoo(job["yahoo_symbol"], DAYS)
            elif src == "coingecko":
                bars = fetch_coingecko(job["cg_id"], DAYS)
            else:
                bars = []
            print(f"  bars fetchees: {len(bars)}")
            if bars:
                print(f"  range: {bars[0][0]} -> {bars[-1][0]}")
                print(f"  sample close: open={bars[-1][1]} close={bars[-1][4]}")
                ins = insert_bars(con, cur, iid, bars)
                after = count_bars(cur, iid)
                print(f"  apres insert: {after} barres en DB (delta {after - before})")
                results.append((t, "OK", before, after))
            else:
                print("  AUCUNE barre recuperee")
                results.append((t, "EMPTY_FETCH", before, before))
        except Exception as e:
            print(f"  ERREUR fetch {t}: {type(e).__name__}: {e}")
            results.append((t, f"ERR:{type(e).__name__}", before, before))

    print()
    print("=" * 70)
    print("RESUME")
    print("=" * 70)
    print(f"{'TICKER':<8} {'STATUS':<20} {'BEFORE':>8} {'AFTER':>8} {'DELTA':>8}")
    print("-" * 60)
    for (t, st, b, a) in results:
        print(f"{t:<8} {st:<20} {b:>8} {a:>8} {a-b:>+8}")

    con.close()
    print()
    print("Done. Relance ensuite /api/construction/run pour rebuild le snapshot.")

if __name__ == "__main__":
    main()
