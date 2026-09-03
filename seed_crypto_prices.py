"""
seed_crypto_prices.py — Fetch 30-day OHLCV from CoinGecko and seed the prices table.
Only seeds instruments that have fewer than 5 existing price records.
"""
import json
import sqlite3
import time
import urllib.request
from datetime import datetime, timedelta

DB_PATH = "thesium.db"

# Must match data_crypto.py CG_MAP
CG_MAP = {
    'BTC': 'bitcoin', 'ETH': 'ethereum', 'XRP': 'ripple',
    'BNB': 'binancecoin', 'SOL': 'solana', 'DOGE': 'dogecoin',
    'ADA': 'cardano', 'TRX': 'tron', 'LINK': 'chainlink',
    'AVAX': 'avalanche-2', 'SUI': 'sui', 'XLM': 'stellar',
    'TON': 'the-open-network', 'SHIB': 'shiba-inu',
    'HBAR': 'hedera-hashgraph', 'DOT': 'polkadot',
    'BCH': 'bitcoin-cash', 'LTC': 'litecoin', 'UNI': 'uniswap',
    'NEAR': 'near', 'APT': 'aptos', 'ICP': 'internet-computer',
    'POL': 'polygon-ecosystem-token', 'ATOM': 'cosmos',
    'RENDER': 'render-token',
}


def fetch_ohlcv(cg_id: str, days: int = 30) -> list:
    """Fetch daily OHLCV from CoinGecko (free, no key)."""
    url = (
        f"https://api.coingecko.com/api/v3/coins/{cg_id}/ohlc"
        f"?vs_currency=usd&days={days}"
    )
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    })
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    # CoinGecko OHLC returns [[timestamp, open, high, low, close], ...]
    # For days=30, returns 4-hourly candles. We'll aggregate to daily.
    daily = {}
    for candle in data:
        ts, o, h, l, c = candle
        date_str = datetime.utcfromtimestamp(ts / 1000).strftime('%Y-%m-%d')
        if date_str not in daily:
            daily[date_str] = {'open': o, 'high': h, 'low': l, 'close': c}
        else:
            d = daily[date_str]
            d['high'] = max(d['high'], h)
            d['low'] = min(d['low'], l)
            d['close'] = c  # last candle of the day
    return daily


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Get crypto instruments that need price data
    instruments = conn.execute("""
        SELECT i.id, i.ticker, COUNT(p.id) as cnt
        FROM instruments i
        LEFT JOIN prices p ON i.id = p.instrument_id
        WHERE i.asset_class = 'crypto'
        GROUP BY i.id
        HAVING cnt < 5
    """).fetchall()

    if not instruments:
        print("[seed_crypto] All crypto instruments already have price data.")
        conn.close()
        return

    print(f"[seed_crypto] {len(instruments)} instruments need price data.")

    for inst in instruments:
        ticker = inst['ticker']
        cg_id = CG_MAP.get(ticker)
        if not cg_id:
            print(f"  [skip] {ticker}: no CoinGecko mapping")
            continue

        try:
            print(f"  [fetch] {ticker} ({cg_id})...", end=" ", flush=True)
            daily = fetch_ohlcv(cg_id, days=30)

            inserted = 0
            for date_str, ohlc in sorted(daily.items()):
                # Simulate volume (CoinGecko OHLC doesn't include volume)
                # Use a rough estimate based on price level
                est_volume = int(ohlc['close'] * 1000000 / max(ohlc['close'], 0.001))
                conn.execute(
                    """INSERT OR IGNORE INTO prices
                       (instrument_id, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (inst['id'], date_str,
                     ohlc['open'], ohlc['high'], ohlc['low'], ohlc['close'],
                     est_volume)
                )
                inserted += 1

            conn.commit()
            print(f"{inserted} daily candles")

            # Rate limit: CoinGecko free = ~10-30 req/min
            time.sleep(12)

        except Exception as e:
            print(f"ERROR: {e}")
            time.sleep(15)

    conn.close()
    print("[seed_crypto] Done!")


if __name__ == "__main__":
    seed()
