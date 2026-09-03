# Finviz Integration Spec for Thesium Desk

## Available Data via finvizfinance library (already installed)

### Per-stock data (finvizfinance.quote.finvizfinance)
```python
from finvizfinance.quote import finvizfinance
stock = finvizfinance('AAPL')
info = stock.ticker_fundament()
```
Key fields: RSI (14), SMA20, SMA50, SMA200, Recom (analyst rating 1-5), 
Target Price, Perf Week/Month/Quarter/Half/Year/YTD, Beta, P/E, Fwd P/E,
Short Float, Rel Volume, Volatility W/M, Change, Sector, Industry, Market Cap,
EPS (ttm), EPS next Y Percentage, Insider Trans, Inst Trans

### Sector overview (finvizfinance.group.overview.Overview)
```python
from finvizfinance.group.overview import Overview
foverview = Overview()
df = foverview.screener_view(group='Sector')
```
Columns: Name, Stocks, Market Cap, Dividend, P/E, Fwd P/E, PEG, Float Short, Change, Volume

### Sector performance (finvizfinance.group.performance.Performance)
```python
from finvizfinance.group.performance import Performance
fperf = Performance()
df = fperf.screener_view(group='Sector')
```
Columns: Name, Perf Week, Perf Month, Perf Quart, Perf Half, Perf Year, Perf YTD, Change, Volume

## Portfolio tickers in DB
AAPL, MSFT, NVDA, TSLA, JPM, SPY (positions)
Full universe: AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, BAC, XOM, JNJ, UNH, SPY, QQQ

## What to build

### 1. data_finviz.py module
- `fetch_stock_signals(tickers: list) -> list[dict]`: For each ticker, fetch RSI, SMA20/50/200, 
  analyst Recom, Target Price, Short Float, Perf Week/Month/YTD, Rel Volume, Beta, Change, Sector
- `fetch_sector_performance() -> list[dict]`: Sector performance table with weekly/monthly/quarterly/YTD perf
- `fetch_sector_overview() -> list[dict]`: Sector fundamentals (P/E, Div yield, etc)
- Add caching (dict + timestamp) to avoid hammering Finviz. Cache for 15 min.

### 2. New API endpoints in api_server.py
- `GET /api/finviz/signals` — stock signals for portfolio tickers
- `GET /api/finviz/sectors` — sector performance + overview merged

### 3. New "Market Intel" tab in frontend
Add a new tab "Market Intel" (between "Orders" and "IC Memos" in sidebar).

Content layout (single scrollable tab):

**Section 1: Stock Signals** (table)
Columns: Ticker, Price, Change, RSI(14), SMA20, SMA50, SMA200, Analyst Rating, Target, Short%, Rel Vol, Perf W/M/YTD
- Color RSI: red if >70 (overbought), green if <30 (oversold), neutral otherwise
- Color SMA%: green if price above SMA, red if below
- Analyst Rating: show as badge (1=Strong Buy green, 2=Buy lightgreen, 3=Hold gold, 4-5=Sell red)
- Target: color green if target > price, red if below

**Section 2: Sector Dynamics** (table)
Columns: Sector, Change, Perf Week, Perf Month, Perf Quarter, Perf YTD, P/E, Fwd P/E, Dividend
- Highlight the sectors that our portfolio is exposed to (Technology, Financials, Consumer Discretionary, Broad Market)
- Color perf values: green positive, red negative
- Sort by Perf Week descending by default

Both sections should match the existing dashboard dark theme styling exactly.

## Existing code patterns to follow
- API uses `def db()` for connections from api_server.py 
- Frontend uses `apiFetch('/api/...')` helper
- Tab system: add nav-item to sidebar, tab-content div, wire in initRouter
- Use existing badge/table CSS classes from style.css
- TAB_TITLES dict in app.js needs the new tab
