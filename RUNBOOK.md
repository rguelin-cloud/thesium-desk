# Thesium Runbook

## Overview

Thesium.finance is an AI-native fund operating system ("Fund OS") where specialized research agents maintain live investment theses on every name and theme, and humans supervise via a workstation called **Thesium Desk**.

**Architecture:** FastAPI backend (Python) + Vanilla JS frontend + SQLite database.

---

## Quick Start

### Prerequisites
- Python 3.10+
- pip

### 1. Install Dependencies

```bash
cd thesium-desk
pip install fastapi uvicorn
```

### 2. Initialize Database & Seed Data

```bash
python seed_data.py
```

This creates `thesium.db` with:
- 14 instruments (AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META, JPM, BAC, XOM, JNJ, UNH, SPY, QQQ)
- 30 days of price history per instrument
- Starting portfolio: $1M+ AUM with 6 positions
- Active theses from all 4 agent types
- 3-4 historical IC memos
- Event log with audit trail

### 3. Start the Server

```bash
python api_server.py
```

Server starts on `http://0.0.0.0:8000`. Open the frontend at your deployment URL or serve `index.html` locally.

---

## Environment Variables & API Keys

### Current Configuration (MVP)
- **No API keys required** — the MVP uses synthetic data and deterministic agent logic
- **SQLite** — zero-config database, stored as `thesium.db` in the project directory

### For Production (Future)
```env
# Market Data
YAHOO_FINANCE_API_KEY=       # Not needed (yfinance is free)
POLYGON_API_KEY=             # Optional: polygon.io for real-time data
ALPHA_VANTAGE_KEY=           # Optional: alternative data source

# Broker Integration
IBKR_ACCOUNT=                # Interactive Brokers paper trading account
IBKR_HOST=127.0.0.1
IBKR_PORT=7497

# Database (if migrating from SQLite)
DATABASE_URL=postgresql://user:pass@host:5432/thesium
```

---

## Running Components

### Data Ingestion

```bash
# Manual ingestion trigger
curl -X POST http://localhost:8000/api/run-ingestion

# Or via Python
python -c "from data_ingestion import run_ingestion; run_ingestion()"
```

The ingestion module fetches OHLCV data from Yahoo Finance for all tracked instruments and normalizes it into the `prices` table.

### Research Agent Cycle

```bash
# Run all agents (macro, factor, microstructure, alt-data)
curl -X POST http://localhost:8000/api/run-agents

# Full decision cycle (agents → risk → execution → memo)
curl -X POST http://localhost:8000/api/orders/execute-cycle
```

Each agent:
1. Reads latest normalized price data
2. Analyzes using technical indicators (SMA, RSI, momentum, volume)
3. Generates/updates thesis objects with conviction scores
4. Proposes trading actions

### Thesium Desk UI

Open the deployed URL. The dashboard provides 4 views:

1. **Today** — Portfolio value, P&L, positions, risk metrics, activity feed
2. **Theses** — All active theses with conviction scores, filterable by agent/horizon
3. **Orders & Fills** — Open orders and execution history
4. **IC Memos** — Investment committee memos with full markdown content

### Paper Trading vs Real Broker

**Default mode is paper trading.** The `execution_engine.py` uses a `PaperBroker` that simulates fills with configurable slippage (default 0.1%).

To switch to a real broker:

1. Implement the `BrokerAdapter` interface in `execution_engine.py`:
```python
class IBKRBroker(BrokerAdapter):
    def submit_order(self, order) -> Fill:
        # Connect to IBKR TWS API
        pass
    
    def get_positions(self) -> list:
        pass
```

2. Update the broker selection in the execution engine configuration
3. **CRITICAL**: Set `LIVE_TRADING=true` environment variable AND confirm via Thesium Desk UI

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/dashboard` | Portfolio summary + positions + events |
| GET | `/api/portfolio/history` | 30-day equity curve |
| GET | `/api/theses` | List active theses (filter: agent, status, ticker) |
| GET | `/api/theses/{id}` | Thesis detail with linked orders |
| POST | `/api/theses/{id}/approve` | Approve a thesis action |
| GET | `/api/orders` | List orders (filter: status, ticker) |
| GET | `/api/fills` | List recent fills |
| POST | `/api/orders/execute-cycle` | Run full decision cycle |
| GET | `/api/memos` | List IC memos (filter: date, ticker, agent) |
| GET | `/api/memos/{id}` | Full memo detail |
| GET | `/api/memos/{id}/markdown` | Download memo as markdown |
| GET | `/api/events` | Event log entries |
| POST | `/api/run-ingestion` | Trigger data ingestion |
| POST | `/api/run-agents` | Run research agents |
| GET | `/api/risk-config` | Get risk configuration |
| PUT | `/api/risk-config` | Update risk limits |
| GET | `/api/instruments` | List all instruments |

---

## Risk Configuration

Default risk limits (editable via API or directly in DB):

| Parameter | Default | Description |
|-----------|---------|-------------|
| max_position_pct | 10% | Max single position as % of portfolio |
| max_sector_pct | 25% | Max sector concentration |
| max_single_name_pct | 10% | Max single name exposure |
| max_var_pct | 5% | Max portfolio VaR (95%, 1-day) |
| stop_loss_pct | 8% | Stop-loss trigger per position |

---

## Database Schema

All data is stored in SQLite (`thesium.db`). Key tables:

- `instruments` — Tracked tickers with sector/asset class
- `prices` — Daily OHLCV data
- `theses` — Agent-generated investment theses
- `portfolio_positions` — Current holdings
- `portfolio_state` — Aggregate portfolio metrics
- `orders` / `fills` — Order lifecycle and execution
- `ic_memos` — Investment committee memos
- `event_log` — Append-only audit trail (every action logged)
- `risk_config` — Risk limits

---

## Disclaimer

Thesium.finance does not provide investment advice. It is a research and execution automation tool operated under user control. All trading decisions require human confirmation. Default mode is paper trading — real execution requires explicit configuration.
