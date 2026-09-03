# Crypto Integration Spec

## Goal
Add BTC, ETH, LINK crypto assets to Thesium Desk. They are already in the instruments table (ids 15, 16, 17) with price history. Now we need:
1. A data module for live crypto data
2. API endpoints
3. A "Crypto" section in the Market Intel tab
4. Full paper-trading support

## 1. CREATE /home/user/workspace/thesium-desk/data_crypto.py

```python
"""
data_crypto.py — Crypto market data for Thesium Desk
Combines CoinGecko (live prices) with Finviz ETF proxies (technical signals).
"""
import json
import time
import urllib.request
from typing import Optional

# --- Cache ---
_cache = {}
_CACHE_TTL = 300  # 5 min for crypto (faster-moving)

def _cached(key):
    if key in _cache and (time.time() - _cache[key]['ts']) < _CACHE_TTL:
        return _cache[key]['data']
    return None

def _set_cache(key, data):
    _cache[key] = {'data': data, 'ts': time.time()}

# CoinGecko ID mapping
CG_MAP = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum', 
    'LINK': 'chainlink',
}

# Finviz ETF proxy tickers (for technical signals)
ETF_MAP = {
    'BTC': 'IBIT',   # iShares Bitcoin Trust
    'ETH': 'ETHA',   # iShares Ethereum Trust
    'LINK': 'GLNK',  # Grayscale Chainlink Trust
}

def fetch_crypto_prices() -> list:
    """Fetch live crypto prices from CoinGecko."""
    cached = _cached('crypto_prices')
    if cached:
        return cached
    
    try:
        url = ("https://api.coingecko.com/api/v3/simple/price"
               "?ids=bitcoin,ethereum,chainlink"
               "&vs_currencies=usd"
               "&include_24hr_change=true"
               "&include_market_cap=true"
               "&include_24hr_vol=true")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        
        result = []
        for ticker, cg_id in CG_MAP.items():
            if cg_id in data:
                d = data[cg_id]
                result.append({
                    'ticker': ticker,
                    'price': d.get('usd'),
                    'change_24h': round(d.get('usd_24h_change', 0), 2),
                    'market_cap': d.get('usd_market_cap'),
                    'volume_24h': d.get('usd_24h_vol'),
                })
        
        _set_cache('crypto_prices', result)
        return result
    except Exception as e:
        print(f"[data_crypto] CoinGecko error: {e}")
        return []


def fetch_crypto_signals() -> list:
    """Fetch technical signals from Finviz ETF proxies for each crypto."""
    cached = _cached('crypto_signals')
    if cached:
        return cached
    
    try:
        from finvizfinance.quote import finvizfinance
    except ImportError:
        return []
    
    result = []
    for crypto_ticker, etf_ticker in ETF_MAP.items():
        try:
            stock = finvizfinance(etf_ticker)
            info = stock.ticker_fundament()
            
            def parse_pct(val):
                if val is None:
                    return None
                if isinstance(val, str):
                    return float(val.replace('%', ''))
                return float(val)
            
            result.append({
                'ticker': crypto_ticker,
                'etf_proxy': etf_ticker,
                'etf_price': float(info.get('Price', 0)),
                'rsi': parse_pct(info.get('RSI (14)')),
                'sma20': parse_pct(info.get('SMA20')),
                'sma50': parse_pct(info.get('SMA50')),
                'sma200': parse_pct(info.get('SMA200')),
                'perf_week': parse_pct(info.get('Perf Week')),
                'perf_month': parse_pct(info.get('Perf Month')),
                'perf_ytd': parse_pct(info.get('Perf YTD')),
                'rel_volume': parse_pct(info.get('Rel Volume')),
                'volatility_w': info.get('Volatility W'),
                'volatility_m': info.get('Volatility M'),
                'beta': parse_pct(info.get('Beta')),
            })
        except Exception as e:
            print(f"[data_crypto] Finviz error for {etf_ticker}: {e}")
    
    _set_cache('crypto_signals', result)
    return result


def fetch_crypto_combined() -> list:
    """Merge CoinGecko prices with Finviz ETF signals."""
    prices = fetch_crypto_prices()
    signals = fetch_crypto_signals()
    
    # Index signals by ticker
    sig_map = {s['ticker']: s for s in signals}
    
    combined = []
    for p in prices:
        ticker = p['ticker']
        sig = sig_map.get(ticker, {})
        combined.append({
            **p,
            'etf_proxy': sig.get('etf_proxy'),
            'rsi': sig.get('rsi'),
            'sma20': sig.get('sma20'),
            'sma50': sig.get('sma50'),
            'sma200': sig.get('sma200'),
            'perf_week': sig.get('perf_week'),
            'perf_month': sig.get('perf_month'),
            'perf_ytd': sig.get('perf_ytd'),
            'rel_volume': sig.get('rel_volume'),
            'volatility_w': sig.get('volatility_w'),
            'volatility_m': sig.get('volatility_m'),
            'beta': sig.get('beta'),
        })
    
    return combined
```

## 2. MODIFY /home/user/workspace/thesium-desk/api_server.py

Add at top with other imports:
```python
import data_crypto
```

Add new endpoint (near the other finviz endpoints):
```python
@app.get("/api/crypto/overview")
def get_crypto_overview():
    """Combined crypto prices (CoinGecko) + technical signals (Finviz ETF proxies)."""
    data = data_crypto.fetch_crypto_combined()
    return {"crypto": data, "total": len(data)}
```

## 3. MODIFY /home/user/workspace/thesium-desk/app.js

In the `loadMarketIntel()` function, add a THIRD parallel fetch for crypto:
```javascript
// In loadMarketIntel(), change:
const [signals, sectors] = await Promise.all([...])
// to:
const [signals, sectors, crypto] = await Promise.all([
    apiFetch('/api/finviz/signals'),
    apiFetch('/api/finviz/sectors'),
    apiFetch('/api/crypto/overview'),
]);
// Then render crypto:
renderCryptoOverview(crypto.crypto || []);
```

Add the `renderCryptoOverview(data)` function. It should render into `#cryptoBody` tbody.

The table has columns: Ticker, Prix, Chg 24h, Market Cap, Volume 24h, RSI(14), SMA20, SMA50, SMA200, Perf S, Perf M, Perf YTD, Vol W, Vol M

Coloring rules:
- Change 24h: green if positive, red if negative  
- RSI: red >70, green <30
- SMA%: green positive, red negative
- Perf: green positive, red negative

Format market cap with B/M suffixes ($1.46T for bitcoin etc).
Show the ETF proxy ticker in parentheses after the crypto ticker, e.g. "BTC (IBIT)".

## 4. MODIFY /home/user/workspace/thesium-desk/index.html

Add a Crypto section in the `#tab-market` content, BEFORE the Stock Signals section:

```html
<div class="section-header">
    <h2>Crypto</h2>
    <p class="text-muted" style="font-size:var(--text-xs)">Prix CoinGecko — Signaux techniques via ETF proxy (Finviz)</p>
</div>
<div class="table-scroll">
    <table>
        <thead>
            <tr>
                <th>Ticker</th><th>Prix</th><th>Chg 24h</th><th>Market Cap</th>
                <th>Vol 24h</th><th>RSI(14)</th><th>SMA20</th><th>SMA50</th>
                <th>SMA200</th><th>Perf S</th><th>Perf M</th><th>Perf YTD</th>
                <th>Vol S</th><th>Vol M</th>
            </tr>
        </thead>
        <tbody id="cryptoBody">
            <tr><td colspan="14" class="empty-state">Chargement...</td></tr>
        </tbody>
    </table>
</div>
```

## 5. The crypto instruments (BTC id=15, ETH id=16, LINK id=17) already exist in the DB with price data. 
They can already be used for:
- Paper trading (orders/fills) via existing execution engine
- Thesis generation by agents
- Portfolio positions

No changes needed to execution_engine.py or risk_engine.py — they work with instrument IDs.

## Important notes
- All user-facing text in FRENCH
- Match existing dark theme styling
- DO NOT modify style.css or base.css
- data_crypto.py must handle errors gracefully (return empty lists)
- Cache crypto prices for 5 minutes (300s), not 15 min like stocks
- Read all files before modifying to avoid breaking existing code
- After changes, verify Python imports work
