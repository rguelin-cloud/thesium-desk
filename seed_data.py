"""
seed_data.py - Populate Nextones DB with realistic demo data.
Generates 30 days of believable OHLCV data using sine-wave + trend + noise model.
Creates a fund with $1M starting capital, 5-6 positions, historical memos, and events.
"""
import json
import math
import random
import sqlite3
from datetime import datetime, timedelta

from models import get_db, init_db, log_event
from risk_engine import refresh_portfolio_state

# Seed for determinism
random.seed(42)


# ---------------------------------------------------------------------------
# Price Generation
# ---------------------------------------------------------------------------

def generate_price_series(
    start_price: float,
    days: int = 35,
    annual_drift: float = 0.08,
    annual_vol: float = 0.20,
    cycle_amplitude: float = 0.04,
    cycle_period: float = 20,
) -> list[dict]:
    """
    Generate OHLCV data using a sine-wave + trend + noise model.
    Produces realistic-looking price series.
    """
    daily_drift = annual_drift / 252
    daily_vol   = annual_vol / math.sqrt(252)
    prices = []
    price = start_price

    base_volume = random.uniform(5_000_000, 80_000_000)

    today = datetime.utcnow().date()
    start_date = today - timedelta(days=days)

    day_idx = 0
    for d in range(days):
        current_date = start_date + timedelta(days=d)

        # Skip weekends
        if current_date.weekday() >= 5:
            continue

        # Sine wave component (market cycle)
        cycle = cycle_amplitude * math.sin(2 * math.pi * day_idx / cycle_period)

        # Random daily return with drift + cycle
        daily_return = daily_drift + cycle / cycle_period + random.gauss(0, daily_vol)
        price = max(price * (1 + daily_return), 1.0)

        # Intraday range based on volatility
        intraday_range = price * random.uniform(daily_vol * 0.5, daily_vol * 2.5)
        high  = price + intraday_range * random.uniform(0.3, 0.7)
        low   = price - intraday_range * random.uniform(0.3, 0.7)
        open_ = low + (high - low) * random.uniform(0.2, 0.8)

        # Volume with occasional spikes
        vol_multiplier = 1.0
        if random.random() < 0.08:  # 8% chance of high-volume day
            vol_multiplier = random.uniform(2.0, 4.0)
        volume = int(base_volume * vol_multiplier * random.uniform(0.7, 1.3))

        prices.append({
            "date":   current_date.isoformat(),
            "open":   round(open_, 2),
            "high":   round(max(open_, high, price), 2),
            "low":    round(min(open_, low, price), 2),
            "close":  round(price, 2),
            "volume": volume,
        })
        day_idx += 1

    return prices


# ---------------------------------------------------------------------------
# Instruments
# ---------------------------------------------------------------------------

INSTRUMENTS = [
    # Equities
    {"ticker": "AAPL",  "name": "Apple Inc.",                     "sector": "Technology",              "asset_class": "equity",   "start_price": 182.5,  "annual_vol": 0.22, "annual_drift": 0.15},
    {"ticker": "MSFT",  "name": "Microsoft Corporation",          "sector": "Technology",              "asset_class": "equity",   "start_price": 415.8,  "annual_vol": 0.21, "annual_drift": 0.18},
    {"ticker": "GOOGL", "name": "Alphabet Inc.",                   "sector": "Technology",              "asset_class": "equity",   "start_price": 175.3,  "annual_vol": 0.24, "annual_drift": 0.12},
    {"ticker": "AMZN",  "name": "Amazon.com Inc.",                 "sector": "Consumer Discretionary",  "asset_class": "equity",   "start_price": 196.4,  "annual_vol": 0.26, "annual_drift": 0.20},
    {"ticker": "NVDA",  "name": "NVIDIA Corporation",              "sector": "Technology",              "asset_class": "equity",   "start_price": 875.2,  "annual_vol": 0.45, "annual_drift": 0.45},
    {"ticker": "TSLA",  "name": "Tesla Inc.",                      "sector": "Consumer Discretionary",  "asset_class": "equity",   "start_price": 245.6,  "annual_vol": 0.55, "annual_drift": 0.05},
    {"ticker": "META",  "name": "Meta Platforms Inc.",             "sector": "Technology",              "asset_class": "equity",   "start_price": 508.1,  "annual_vol": 0.32, "annual_drift": 0.22},
    {"ticker": "JPM",   "name": "JPMorgan Chase & Co.",            "sector": "Financials",              "asset_class": "equity",   "start_price": 195.7,  "annual_vol": 0.20, "annual_drift": 0.12},
    {"ticker": "BAC",   "name": "Bank of America Corporation",     "sector": "Financials",              "asset_class": "equity",   "start_price": 36.8,   "annual_vol": 0.22, "annual_drift": 0.10},
    {"ticker": "XOM",   "name": "Exxon Mobil Corporation",         "sector": "Energy",                  "asset_class": "equity",   "start_price": 112.3,  "annual_vol": 0.23, "annual_drift": 0.08},
    {"ticker": "JNJ",   "name": "Johnson & Johnson",               "sector": "Healthcare",              "asset_class": "equity",   "start_price": 158.4,  "annual_vol": 0.14, "annual_drift": 0.06},
    {"ticker": "UNH",   "name": "UnitedHealth Group Inc.",         "sector": "Healthcare",              "asset_class": "equity",   "start_price": 545.2,  "annual_vol": 0.18, "annual_drift": 0.10},
    # ETFs
    {"ticker": "SPY",   "name": "SPDR S&P 500 ETF Trust",          "sector": "Broad Market",            "asset_class": "etf",      "start_price": 507.3,  "annual_vol": 0.15, "annual_drift": 0.12},
    {"ticker": "QQQ",   "name": "Invesco QQQ Trust",               "sector": "Technology",              "asset_class": "etf",      "start_price": 443.7,  "annual_vol": 0.18, "annual_drift": 0.14},
]


# ---------------------------------------------------------------------------
# Starting Positions
# ---------------------------------------------------------------------------

INITIAL_POSITIONS = [
    {"ticker": "AAPL",  "quantity": 550,  "avg_cost_offset": -5.2},   # profitable
    {"ticker": "MSFT",  "quantity": 240,  "avg_cost_offset": -18.4},  # profitable
    {"ticker": "NVDA",  "quantity": 115,  "avg_cost_offset": 42.6},   # slightly underwater
    {"ticker": "JPM",   "quantity": 510,  "avg_cost_offset": -8.1},   # profitable
    {"ticker": "SPY",   "quantity": 195,  "avg_cost_offset": -12.7},  # profitable
    {"ticker": "TSLA",  "quantity": 420,  "avg_cost_offset": 32.1},   # underwater
]


# ---------------------------------------------------------------------------
# Seed Theses
# ---------------------------------------------------------------------------

def _seed_theses(conn, instrument_map):
    now = datetime.utcnow()

    theses = [
        {
            "instrument_id": instrument_map.get("AAPL"),
            "agent_type": "FactorAgent",
            "thesis_text": (
                "## Factor Analysis – AAPL – 2026-02-10\n\n"
                "**Tilt:** OVERWEIGHT | **Composite Score:** 7.8/10\n\n"
                "Apple maintains strong quality and momentum scores. "
                "Services revenue diversification reduces hardware cycle risk. "
                "12-month momentum of +18.4% is well above sector median. "
                "Quality proxy (inverse volatility) scores 7.2/10 reflecting stable earnings profile.\n\n"
                "**Proposed action:** Maintain overweight; consider adding on pullbacks to $175 support."
            ),
            "conviction_score": 7.8,
            "horizon": "medium",
            "key_drivers": json.dumps([
                "Momentum (12-1m): +18.4%",
                "Quality proxy (inv-vol): 7.2/10",
                "Services revenue >30% of total, improving margin mix",
                "Factor composite: 7.8/10",
                "Tilt: overweight",
            ]),
            "proposed_action": "Maintain overweight; consider adding on pullbacks to $175 support",
            "status": "active",
            "created_at": (now - timedelta(days=14)).isoformat(),
        },
        {
            "instrument_id": instrument_map.get("NVDA"),
            "agent_type": "MacroAgent",
            "thesis_text": (
                "## Macro-Driven Thesis – NVDA – 2026-02-05\n\n"
                "**Stance:** RISK-ON | **Conviction:** 8.5/10\n\n"
                "AI infrastructure spending cycle remains intact. "
                "Data center GPU demand from hyperscalers running ahead of expectations. "
                "Risk: elevated valuation (NTM P/E ~35x) limits multiple expansion upside. "
                "Macro environment (golden cross on QQQ) supports continued tech exposure.\n\n"
                "**Proposed action:** Hold core position; trim 20% if RSI exceeds 80 on weekly chart."
            ),
            "conviction_score": 8.5,
            "horizon": "long",
            "key_drivers": json.dumps([
                "AI capex cycle: hyperscaler GPU orders up 40%+ YoY",
                "Data center revenue: ~80% of total, growing >100% YoY",
                "Macro: QQQ golden cross, risk-on environment",
                "Valuation risk: NTM P/E ~35x",
                "Sentiment: strong institutional accumulation",
            ]),
            "proposed_action": "Hold core position; trim 20% if RSI exceeds 80 on weekly chart",
            "status": "active",
            "created_at": (now - timedelta(days=22)).isoformat(),
        },
        {
            "instrument_id": instrument_map.get("TSLA"),
            "agent_type": "MicrostructureAgent",
            "thesis_text": (
                "## Microstructure Signal – TSLA – 2026-02-12\n\n"
                "**Signal:** REDUCE | **Conviction:** 6.8/10\n\n"
                "Tesla price action shows distribution pattern: price near upper Bollinger Band "
                "with declining volume. RSI(14) at 71.2 signals overbought conditions. "
                "10-day resistance at $262 has rejected twice. "
                "Current position is underwater by 13.1% from avg cost.\n\n"
                "**Proposed action:** Reduce TSLA by 30-40%; stop-loss at $230 (ATR 2x stop)."
            ),
            "conviction_score": 6.8,
            "horizon": "short",
            "key_drivers": json.dumps([
                "RSI(14): 71.2 (overbought)",
                "Price at 96th percentile of 20-day BB range",
                "Volume 20% below 5-day average (distribution signal)",
                "Resistance at $262 rejected twice in 10 days",
                "Position -13.1% underwater from avg cost $277.70",
            ]),
            "proposed_action": "Reduce TSLA by 30-40%; stop-loss at $230 (ATR 2x stop)",
            "status": "active",
            "created_at": (now - timedelta(days=8)).isoformat(),
        },
        {
            "instrument_id": instrument_map.get("JPM"),
            "agent_type": "AltDataAgent",
            "thesis_text": (
                "## Alt-Data Signal – JPM – 2026-02-15\n\n"
                "**Sentiment:** STRONG BULLISH | **Conviction:** 8.2/10\n\n"
                "JPMorgan price-volume dynamics show strong accumulation pattern: "
                "price up +6.2% over 5 days with volume 2.3x above 20-day average. "
                "Trend consistency at 90% (9 of last 10 days above 20-SMA). "
                "Earnings beat last quarter + net interest margin expansion thesis intact. "
                "Rising rate environment historically positive for bank earnings.\n\n"
                "**Proposed action:** Continue accumulating JPM; target $215 (10-12% upside from current)."
            ),
            "conviction_score": 8.2,
            "horizon": "medium",
            "key_drivers": json.dumps([
                "Price-volume sentiment: strong_bullish",
                "5-day price change: +6.2%",
                "5-day volume vs 20d avg: +130% (2.3x)",
                "Trend consistency (10d above SMA20): 90%",
                "NIM expansion tailwind from rate environment",
            ]),
            "proposed_action": "Continue accumulating JPM; target $215 (10-12% upside from current)",
            "status": "active",
            "created_at": (now - timedelta(days=5)).isoformat(),
        },
        {
            "instrument_id": instrument_map.get("MSFT"),
            "agent_type": "FactorAgent",
            "thesis_text": (
                "## Factor Analysis – MSFT – 2026-02-08\n\n"
                "**Tilt:** OVERWEIGHT | **Composite Score:** 8.1/10\n\n"
                "Microsoft scores highest on quality factor: consistent FCF margins >35%, "
                "low earnings volatility, and Azure cloud growth reaccelerating to 29% YoY. "
                "Momentum score 7.4/10 on 12-1m momentum. "
                "Copilot AI monetization represents significant optionality not yet priced in.\n\n"
                "**Proposed action:** Increase MSFT allocation by 2-3%; strong quality momentum compounder."
            ),
            "conviction_score": 8.1,
            "horizon": "long",
            "key_drivers": json.dumps([
                "Momentum (12-1m): +24.1%",
                "Quality: FCF margin >35%, Aaa credit rating",
                "Azure cloud growth: 29% YoY (reacceleration)",
                "Copilot AI optionality unpriced",
                "Factor composite: 8.1/10",
            ]),
            "proposed_action": "Increase MSFT allocation by 2-3%; strong quality momentum compounder",
            "status": "active",
            "created_at": (now - timedelta(days=18)).isoformat(),
        },
        {
            "instrument_id": instrument_map.get("XOM"),
            "agent_type": "MacroAgent",
            "thesis_text": (
                "## Macro Thesis – XOM – 2026-01-28\n\n"
                "**Stance:** NEUTRAL-TO-CAUTIOUS | **Conviction:** 5.5/10\n\n"
                "Energy sector faces headwinds from potential demand slowdown. "
                "Brent crude holding $75-80 range; insufficient catalyst for multiple expansion. "
                "XOM balance sheet strength (net debt/EBITDA <0.5x) provides downside cushion. "
                "Dividend yield at 3.4% offers income floor. Not a high-conviction position at current levels.\n\n"
                "**Proposed action:** No new position recommended; monitor oil for breakout above $85."
            ),
            "conviction_score": 5.5,
            "horizon": "medium",
            "key_drivers": json.dumps([
                "Macro: neutral stance on energy sector",
                "Brent crude range-bound $75-80",
                "Balance sheet: net debt/EBITDA <0.5x",
                "Dividend yield: 3.4% income floor",
                "Demand risk: potential macro slowdown",
            ]),
            "proposed_action": "No new position recommended; monitor oil for breakout above $85",
            "status": "active",
            "created_at": (now - timedelta(days=35)).isoformat(),
        },
    ]

    thesis_ids = {}
    for th in theses:
        cur = conn.execute(
            """INSERT INTO theses (instrument_id, agent_type, thesis_text, conviction_score,
                   horizon, key_drivers, proposed_action, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                th["instrument_id"], th["agent_type"], th["thesis_text"],
                th["conviction_score"], th["horizon"], th["key_drivers"],
                th["proposed_action"], th["status"],
                th.get("created_at", datetime.utcnow().isoformat()),
                datetime.utcnow().isoformat(),
            )
        )
        thesis_ids[th["agent_type"] + "_" + str(th["instrument_id"])] = cur.lastrowid

    return thesis_ids


# ---------------------------------------------------------------------------
# Seed Orders & Fills
# ---------------------------------------------------------------------------

def _seed_orders_and_fills(conn, instrument_map, thesis_ids):
    now = datetime.utcnow()

    # Historical orders (already filled)
    historical_orders = [
        {
            "ticker": "AAPL", "side": "buy",  "quantity": 200, "price": 178.40,
            "days_ago": 28, "thesis_key": f"FactorAgent_{instrument_map.get('AAPL')}",
            "risk_action": "approved",
        },
        {
            "ticker": "MSFT", "side": "buy",  "quantity": 100, "price": 408.20,
            "days_ago": 25, "thesis_key": f"FactorAgent_{instrument_map.get('MSFT')}",
            "risk_action": "approved",
        },
        {
            "ticker": "NVDA", "side": "buy",  "quantity": 50,  "price": 892.60,
            "days_ago": 20, "thesis_key": f"MacroAgent_{instrument_map.get('NVDA')}",
            "risk_action": "approved",
        },
        {
            "ticker": "TSLA", "side": "buy",  "quantity": 150, "price": 268.90,
            "days_ago": 18, "thesis_key": f"MicrostructureAgent_{instrument_map.get('TSLA')}",
            "risk_action": "approved",
        },
        {
            "ticker": "JPM",  "side": "buy",  "quantity": 200, "price": 189.10,
            "days_ago": 15, "thesis_key": f"AltDataAgent_{instrument_map.get('JPM')}",
            "risk_action": "approved",
        },
        {
            "ticker": "AAPL", "side": "sell", "quantity": 50,  "price": 185.20,
            "days_ago": 10, "thesis_key": f"FactorAgent_{instrument_map.get('AAPL')}",
            "risk_action": "approved",
        },
        {
            "ticker": "TSLA", "side": "sell", "quantity": 80,  "price": 251.40,
            "days_ago": 6, "thesis_key": f"MicrostructureAgent_{instrument_map.get('TSLA')}",
            "risk_action": "scaled_down",
        },
    ]

    for o in historical_orders:
        inst_id   = instrument_map.get(o["ticker"])
        thesis_id = thesis_ids.get(o["thesis_key"])
        order_dt  = (now - timedelta(days=o["days_ago"])).isoformat()
        risk_check = {
            "approved": True,
            "action": o["risk_action"],
            "approved_quantity": o["quantity"],
            "reasons": [],
            "metrics": {
                "order_value_usd": o["quantity"] * o["price"],
                "portfolio_var_pct": 2.1,
            }
        }
        order_id = conn.execute(
            """INSERT INTO orders (instrument_id, thesis_id, side, quantity, order_type,
                   status, risk_check_result, created_at)
               VALUES (?, ?, ?, ?, 'market', 'filled', ?, ?)""",
            (inst_id, thesis_id, o["side"], o["quantity"],
             json.dumps(risk_check), order_dt)
        ).lastrowid

        slippage = o["price"] * 0.001 * o["quantity"]
        fees     = o["quantity"] * 0.005
        fill_price = o["price"] * (1.001 if o["side"] == "buy" else 0.999)

        conn.execute(
            """INSERT INTO fills (order_id, fill_price, fill_quantity, slippage, fees, filled_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (order_id, round(fill_price, 2), o["quantity"],
             round(slippage, 2), round(fees, 2), order_dt)
        )


# ---------------------------------------------------------------------------
# Seed IC Memos
# ---------------------------------------------------------------------------

def _seed_memos(conn, instrument_map):
    now = datetime.utcnow()

    memos = [
        {
            "days_ago": 30,
            "title": "Nextones IC Memo – 2026-02-03",
            "macro_summary": "risk-on",
            "factor_tilts": {"overweight": ["AAPL", "MSFT", "NVDA"], "underweight": ["XOM"]},
            "thesis_summaries": [
                {"ticker": "AAPL",  "agent": "FactorAgent",        "conviction": 7.8, "action": "Add on pullbacks"},
                {"ticker": "NVDA",  "agent": "MacroAgent",         "conviction": 8.5, "action": "Hold; trim at RSI 80"},
                {"ticker": "MSFT",  "agent": "FactorAgent",        "conviction": 8.1, "action": "Increase allocation"},
            ],
            "proposed_changes": [
                {"order_id": 1, "ticker": "AAPL", "side": "buy",  "quantity": 200, "status": "filled"},
                {"order_id": 2, "ticker": "MSFT", "side": "buy",  "quantity": 100, "status": "filled"},
            ],
        },
        {
            "days_ago": 21,
            "title": "Nextones IC Memo – 2026-02-12",
            "macro_summary": "risk-on",
            "factor_tilts": {"overweight": ["AAPL", "MSFT", "NVDA", "META"], "underweight": ["TSLA", "XOM"]},
            "thesis_summaries": [
                {"ticker": "NVDA", "agent": "MacroAgent",          "conviction": 8.5, "action": "Hold core; add on weakness"},
                {"ticker": "JPM",  "agent": "AltDataAgent",        "conviction": 8.2, "action": "Accumulate to target $215"},
                {"ticker": "TSLA", "agent": "MicrostructureAgent", "conviction": 6.8, "action": "Reduce by 30-40%"},
            ],
            "proposed_changes": [
                {"order_id": 3, "ticker": "NVDA", "side": "buy",  "quantity": 50,  "status": "filled"},
                {"order_id": 4, "ticker": "TSLA", "side": "buy",  "quantity": 150, "status": "filled"},
            ],
        },
        {
            "days_ago": 12,
            "title": "Nextones IC Memo – 2026-02-21",
            "macro_summary": "neutral",
            "factor_tilts": {"overweight": ["MSFT", "JPM"], "underweight": ["TSLA"]},
            "thesis_summaries": [
                {"ticker": "JPM",  "agent": "AltDataAgent",        "conviction": 8.2, "action": "Continue accumulating"},
                {"ticker": "TSLA", "agent": "MicrostructureAgent", "conviction": 6.8, "action": "Reduce – RSI overbought"},
                {"ticker": "AAPL", "agent": "FactorAgent",         "conviction": 7.8, "action": "Trim 50 shares at resistance"},
            ],
            "proposed_changes": [
                {"order_id": 5, "ticker": "JPM",  "side": "buy",  "quantity": 200, "status": "filled"},
                {"order_id": 6, "ticker": "AAPL", "side": "sell", "quantity": 50,  "status": "filled"},
                {"order_id": 7, "ticker": "TSLA", "side": "sell", "quantity": 80,  "status": "filled"},
            ],
        },
    ]

    for m in memos:
        dt = (now - timedelta(days=m["days_ago"])).strftime("%Y-%m-%d")

        full_md = f"""# {m['title']}
**Generated:** {dt} 09:00 UTC
**Mode:** Paper Trading | **Disclaimer:** Not investment advice.

---

## Portfolio Snapshot
Nextones paper portfolio — weekly decision cycle.

## Macro Outlook
**Stance:** {m['macro_summary'].upper()}

## Factor Tilts
**Overweight:** {', '.join(m['factor_tilts']['overweight'])}
**Underweight:** {', '.join(m['factor_tilts']['underweight'])}

## Thesis Summaries
{chr(10).join(f"- **{t['ticker']}** ({t['agent']}): {t['action']} [Conviction {t['conviction']}/10]" for t in m['thesis_summaries'])}

## Proposed Changes
{chr(10).join(f"- {c['side'].upper()} {c['quantity']} {c['ticker']} → {c['status']}" for c in m['proposed_changes'])}

---
*Auto-generated by Nextones.finance*
"""
        conn.execute(
            """INSERT INTO ic_memos (date, title, macro_summary, factor_tilts,
                   thesis_summaries, proposed_changes, full_markdown, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                dt, m["title"], m["macro_summary"],
                json.dumps(m["factor_tilts"]),
                json.dumps(m["thesis_summaries"]),
                json.dumps(m["proposed_changes"]),
                full_md,
                (now - timedelta(days=m["days_ago"])).isoformat(),
            )
        )


# ---------------------------------------------------------------------------
# Portfolio History
# ---------------------------------------------------------------------------

def _seed_portfolio_history(conn, base_value: float = 1_000_000):
    """Generate 30 days of realistic portfolio value history."""
    now = datetime.utcnow().date()
    value = base_value * 0.95  # Start slightly below current (uptrend)

    for d in range(30, -1, -1):
        date = now - timedelta(days=d)
        if date.weekday() >= 5:
            continue

        # Realistic daily portfolio move: drift + noise
        daily_return = random.gauss(0.0006, 0.008)
        value = value * (1 + daily_return)

        pnl = value - base_value * 0.95
        conn.execute(
            """INSERT OR IGNORE INTO portfolio_history (date, total_value, cash, total_pnl)
               VALUES (?, ?, ?, ?)""",
            (date.isoformat(), round(value, 2),
             round(value * 0.18, 2),
             round(pnl, 2))
        )


# ---------------------------------------------------------------------------
# Event Log History
# ---------------------------------------------------------------------------

def _seed_event_log(conn, instrument_map):
    now = datetime.utcnow()

    events = [
        {"event_type": "data_ingestion_complete",  "agent": "DataIngestion",       "days_ago": 30, "details": {"tickers_updated": list(instrument_map.keys()), "rows_fetched": 420}},
        {"event_type": "agent_cycle_complete",      "agent": "Orchestrator",        "days_ago": 30, "details": {"macro_conviction": 7.5, "factor_theses": 12, "micro_theses": 14}},
        {"event_type": "ic_memo_generated",         "agent": "MemoGenerator",       "days_ago": 30, "details": {"date": "2026-02-03", "title": "Nextones IC Memo – 2026-02-03"}},
        {"event_type": "order_created",             "agent": "ExecutionEngine",     "days_ago": 28, "details": {"ticker": "AAPL", "side": "buy", "quantity": 200}},
        {"event_type": "risk_check",                "agent": "RiskEngine",          "days_ago": 28, "details": {"action": "approved", "instrument": "AAPL"}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 28, "details": {"ticker": "AAPL", "fill_price": 178.58, "quantity": 200}},
        {"event_type": "order_created",             "agent": "ExecutionEngine",     "days_ago": 25, "details": {"ticker": "MSFT", "side": "buy", "quantity": 100}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 25, "details": {"ticker": "MSFT", "fill_price": 408.61, "quantity": 100}},
        {"event_type": "agent_cycle_complete",      "agent": "Orchestrator",        "days_ago": 21, "details": {"macro_conviction": 8.0, "factor_theses": 12, "micro_theses": 14}},
        {"event_type": "ic_memo_generated",         "agent": "MemoGenerator",       "days_ago": 21, "details": {"date": "2026-02-12", "title": "Nextones IC Memo – 2026-02-12"}},
        {"event_type": "order_created",             "agent": "ExecutionEngine",     "days_ago": 20, "details": {"ticker": "NVDA", "side": "buy", "quantity": 50}},
        {"event_type": "risk_check",                "agent": "RiskEngine",          "days_ago": 20, "details": {"action": "approved", "instrument": "NVDA"}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 20, "details": {"ticker": "NVDA", "fill_price": 893.49, "quantity": 50}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 18, "details": {"ticker": "TSLA", "fill_price": 269.17, "quantity": 150}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 15, "details": {"ticker": "JPM", "fill_price": 189.29, "quantity": 200}},
        {"event_type": "agent_cycle_complete",      "agent": "Orchestrator",        "days_ago": 12, "details": {"macro_conviction": 6.5, "factor_theses": 12, "micro_theses": 14}},
        {"event_type": "ic_memo_generated",         "agent": "MemoGenerator",       "days_ago": 12, "details": {"date": "2026-02-21", "title": "Nextones IC Memo – 2026-02-21"}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 10, "details": {"ticker": "AAPL", "side": "sell", "fill_price": 185.39, "quantity": 50}},
        {"event_type": "order_filled",              "agent": "PaperBroker",         "days_ago": 6,  "details": {"ticker": "TSLA", "side": "sell", "fill_price": 251.15, "quantity": 80}},
        {"event_type": "data_ingestion_complete",   "agent": "DataIngestion",       "days_ago": 1,  "details": {"tickers_updated": list(instrument_map.keys()), "rows_fetched": 14}},
        {"event_type": "agent_thesis_generated",    "agent": "FactorAgent",         "days_ago": 1,  "details": {"ticker": "MSFT", "tilt": "overweight", "conviction": 8.1}},
        {"event_type": "agent_thesis_generated",    "agent": "MicrostructureAgent", "days_ago": 1,  "details": {"ticker": "TSLA", "signal": "reduce", "bb_pct": 0.91}},
    ]

    for e in events:
        dt = (now - timedelta(days=e["days_ago"])).isoformat()
        conn.execute(
            "INSERT INTO event_log (event_type, details, agent, created_at) VALUES (?, ?, ?, ?)",
            (e["event_type"], json.dumps(e["details"]), e["agent"], dt)
        )


# ---------------------------------------------------------------------------
# Main Seed Function
# ---------------------------------------------------------------------------

def seed():
    print("[seed] Connecting to database...")
    # NOTE: init_db() is already called by api_server.py lifespan — do NOT call it again here
    conn = get_db()

    # Check if already seeded
    count = conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0]
    if count > 0:
        print(f"[seed] Database already contains {count} instruments. Skipping seed.")
        conn.close()
        return

    print("[seed] Inserting instruments...")
    instrument_map = {}
    for inst in INSTRUMENTS:
        cur = conn.execute(
            """INSERT OR IGNORE INTO instruments (ticker, name, sector, asset_class)
               VALUES (?, ?, ?, ?)""",
            (inst["ticker"], inst["name"], inst["sector"], inst["asset_class"])
        )
        if cur.lastrowid:
            instrument_map[inst["ticker"]] = cur.lastrowid
        else:
            row = conn.execute("SELECT id FROM instruments WHERE ticker = ?", (inst["ticker"],)).fetchone()
            instrument_map[inst["ticker"]] = row[0]

    print("[seed] Generating price history...")
    for inst in INSTRUMENTS:
        inst_id = instrument_map[inst["ticker"]]
        prices = generate_price_series(
            start_price=inst["start_price"],
            days=35,
            annual_drift=inst["annual_drift"],
            annual_vol=inst["annual_vol"],
        )
        for p in prices:
            conn.execute(
                """INSERT OR IGNORE INTO prices
                       (instrument_id, date, open, high, low, close, volume)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (inst_id, p["date"], p["open"], p["high"],
                 p["low"], p["close"], p["volume"])
            )

    print("[seed] Setting up initial positions...")
    # Get current prices (most recent close)
    initial_cash = 1_000_000.0
    total_invested = 0.0
    for pos in INITIAL_POSITIONS:
        inst_id = instrument_map[pos["ticker"]]
        price_row = conn.execute(
            "SELECT close FROM prices WHERE instrument_id = ? ORDER BY date DESC LIMIT 1",
            (inst_id,)
        ).fetchone()
        if not price_row:
            continue
        current_price = price_row[0]
        avg_cost = current_price + pos["avg_cost_offset"]
        unrealized_pnl = pos["quantity"] * (current_price - avg_cost)

        conn.execute(
            """INSERT OR REPLACE INTO portfolio_positions
                   (instrument_id, quantity, avg_cost, current_price, unrealized_pnl, weight_pct)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (inst_id, pos["quantity"], round(avg_cost, 2), round(current_price, 2), round(unrealized_pnl, 2))
        )
        total_invested += pos["quantity"] * current_price

    # Calculate remaining cash after positions
    remaining_cash = max(initial_cash - total_invested * 0.72, 150_000)

    # Initialize portfolio state
    conn.execute("""
        INSERT OR REPLACE INTO portfolio_state (id, cash, total_value, total_pnl, total_pnl_pct,
            daily_pnl, daily_pnl_pct, var_95, max_drawdown, updated_at)
        VALUES (1, ?, ?, 0, 0, 0, 0, 0, 0, datetime('now'))
    """, (round(remaining_cash, 2), round(remaining_cash + total_invested * 0.72, 2)))

    # Risk config
    conn.execute("""
        INSERT OR REPLACE INTO risk_config (id, max_position_pct, max_sector_pct,
            max_single_name_pct, max_var_pct, stop_loss_pct)
        VALUES (1, 10.0, 25.0, 10.0, 5.0, 8.0)
    """)

    print("[seed] Creating theses...")
    thesis_ids = _seed_theses(conn, instrument_map)

    print("[seed] Creating historical orders & fills...")
    _seed_orders_and_fills(conn, instrument_map, thesis_ids)

    print("[seed] Creating IC memos...")
    _seed_memos(conn, instrument_map)

    print("[seed] Generating portfolio history...")
    _seed_portfolio_history(conn, base_value=remaining_cash + total_invested * 0.72)

    print("[seed] Writing event log...")
    _seed_event_log(conn, instrument_map)

    # Refresh portfolio metrics
    refresh_portfolio_state(conn)

    conn.commit()
    conn.close()
    print("[seed] Done! Nextones database seeded successfully.")


if __name__ == "__main__":
    seed()
