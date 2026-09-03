"""
agents.py - Research agents for Thesium.finance
Four specialized agents: MacroAgent, FactorAgent, MicrostructureAgent, AltDataAgent.
All use deterministic technical analysis rules on stored price data - NOT random.
"""
import json
import math
import sqlite3
from datetime import datetime
from models import get_db, log_event, rows_to_list

# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------


# [FACTOR_PPLX_V1] Import optionnel du contexte qualite Perplexity (tolerant a l'absence)
try:
    from pplx_factor_agent import get_quality_context as _pplx_get_quality
except Exception:
    _pplx_get_quality = None

def _get_prices(conn: sqlite3.Connection, instrument_id: int, limit: int = 60) -> list[dict]:
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume
           FROM prices
           WHERE instrument_id = ?
           ORDER BY date DESC LIMIT ?""",
        (instrument_id, limit)
    ).fetchall()
    return list(reversed([dict(r) for r in rows]))  # oldest first


def _sma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _ema(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = closes[-period]
    for price in closes[-period + 1:]:
        ema = price * k + ema * (1 - k)
    return ema


def _rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(-period, 0):
        delta = closes[i] - closes[i - 1]
        if delta > 0:
            gains.append(delta)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(delta))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _atr(prices: list[dict], period: int = 14) -> float | None:
    if len(prices) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        h = prices[i]["high"]
        l = prices[i]["low"]
        prev_c = prices[i - 1]["close"]
        trs.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
    return sum(trs) / period


def _volatility(closes: list[float], period: int = 20) -> float | None:
    """Annualized daily return volatility."""
    if len(closes) < period + 1:
        return None
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(-period, 0)]
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    return math.sqrt(variance) * math.sqrt(252)  # annualize


def _save_thesis(conn: sqlite3.Connection, instrument_id: int | None, agent_type: str,
                 thesis_text: str, conviction: float, horizon: str,
                 key_drivers: list, proposed_action: str, status: str = "active") -> int:
    """Insert a thesis and return its ID. Supersedes previous active theses for same agent+instrument."""
    now = datetime.utcnow().isoformat()
    # Archive previous active theses for the same agent + instrument combo
    if instrument_id is not None:
        conn.execute(
            """UPDATE theses SET status='superseded', updated_at=?
               WHERE agent_type=? AND instrument_id=? AND status='active'""",
            (now, agent_type, instrument_id)
        )
    else:
        conn.execute(
            """UPDATE theses SET status='superseded', updated_at=?
               WHERE agent_type=? AND instrument_id IS NULL AND status='active'""",
            (now, agent_type)
        )
    cur = conn.execute(
        """INSERT INTO theses
               (instrument_id, agent_type, thesis_text, conviction_score, horizon,
                key_drivers, proposed_action, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (instrument_id, agent_type, thesis_text, conviction, horizon,
         json.dumps(key_drivers), proposed_action, status, now, now)
    )
    return cur.lastrowid


# ---------------------------------------------------------------------------
# MacroAgent
# ---------------------------------------------------------------------------

class MacroAgent:
    """
    Analyzes broad-market ETFs (SPY, QQQ, DIA) to produce a macro-outlook thesis.
    Rules: 50-day vs 200-day SMA (Golden/Death Cross), trend slope, RSI.
    """
    NAME = "MacroAgent"
    MACRO_TICKERS = ["SPY", "QQQ", "DIA"]

    def run(self, conn: sqlite3.Connection) -> dict:
        results = {}
        signals = {}

        for ticker in self.MACRO_TICKERS:
            inst = conn.execute(
                "SELECT id FROM instruments WHERE ticker = ?", (ticker,)
            ).fetchone()
            if not inst:
                continue
            prices = _get_prices(conn, inst["id"], limit=210)
            if len(prices) < 20:
                continue
            closes = [p["close"] for p in prices]

            sma50  = _sma(closes, 50)
            sma200 = _sma(closes, 200)
            rsi14  = _rsi(closes, 14)
            vol    = _volatility(closes, 20)
            current = closes[-1]

            # Trend signal: golden cross = bullish, death cross = bearish
            if sma50 and sma200:
                cross = "golden" if sma50 > sma200 else "death"
            else:
                cross = "neutral"

            # RSI signal
            rsi_sig = "neutral"
            if rsi14:
                if rsi14 > 65:
                    rsi_sig = "overbought"
                elif rsi14 < 35:
                    rsi_sig = "oversold"

            # Momentum: 20-day return
            momentum = (current - closes[-21]) / closes[-21] * 100 if len(closes) > 21 else 0

            signals[ticker] = {
                "sma50": round(sma50, 2) if sma50 else None,
                "sma200": round(sma200, 2) if sma200 else None,
                "cross": cross,
                "rsi14": round(rsi14, 1) if rsi14 else None,
                "rsi_signal": rsi_sig,
                "momentum_20d": round(momentum, 2),
                "annualized_vol": round(vol * 100, 1) if vol else None,
                "current_price": round(current, 2),
            }

        # Aggregate macro stance
        bullish_count = sum(1 for s in signals.values() if s["cross"] == "golden")
        bearish_count = sum(1 for s in signals.values() if s["cross"] == "death")
        overbought_count = sum(1 for s in signals.values() if s["rsi_signal"] == "overbought")

        if bullish_count >= 2:
            stance = "risk-on"
            conviction = min(7 + bullish_count - overbought_count, 9)
            horizon = "medium"
            proposed = "Maintain or increase equity exposure to 70-75% of portfolio"
        elif bearish_count >= 2:
            stance = "risk-off"
            conviction = min(7 + bearish_count, 9)
            horizon = "medium"
            proposed = "Reduce equity exposure; rotate to cash and defensive sectors"
        else:
            stance = "neutral"
            conviction = 5
            horizon = "short"
            proposed = "Hold current allocations; monitor for trend clarification"

        avg_momentum = (
            sum(s["momentum_20d"] for s in signals.values()) / len(signals) if signals else 0
        )

        key_drivers = [
            f"SPY/QQQ/DIA moving average crosses: {bullish_count} bullish, {bearish_count} bearish",
            f"Average 20-day momentum across indices: {avg_momentum:+.1f}%",
            f"RSI condition: {overbought_count} index ETFs in overbought territory",
            f"Macro stance: {stance}",
        ]

        thesis_text = (
            f"## Macro Outlook – {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
            f"**Stance:** {stance.upper()}\n\n"
            f"Analysis of broad-market ETFs (SPY, QQQ, DIA) indicates a **{stance}** environment. "
            f"Moving average analysis shows {bullish_count} of 3 indices on golden-cross configuration "
            f"and {bearish_count} in death-cross territory. "
            f"Average 20-day price momentum across indices is {avg_momentum:+.1f}%, "
            f"suggesting {'positive' if avg_momentum > 0 else 'negative'} near-term trend. "
            f"{'RSI signals caution with overbought conditions in ' + str(overbought_count) + ' ETFs. ' if overbought_count else ''}"
            f"\n\n**Recommended posture:** {proposed}"
        )

        thesis_id = _save_thesis(
            conn, None, self.NAME, thesis_text,
            conviction, horizon, key_drivers, proposed
        )

        log_event(conn, "agent_thesis_generated", "thesis", thesis_id,
                  {"stance": stance, "conviction": conviction, "signals": signals}, self.NAME)

        results = {
            "thesis_id": thesis_id,
            "stance": stance,
            "conviction": conviction,
            "horizon": horizon,
            "signals": signals,
            "proposed_action": proposed,
        }
        return results


# ---------------------------------------------------------------------------
# FactorAgent
# ---------------------------------------------------------------------------

class FactorAgent:
    """
    Evaluates factor exposures across all equity instruments.
    Factors: momentum (12-1 month), value proxy (P/E not available -> use relative vol),
    quality (low vol = higher quality proxy).
    """
    NAME = "FactorAgent"

    def _score_momentum(self, closes: list[float]) -> float:
        """12-1 month momentum (returns excluding last month)."""
        if len(closes) < 252:
            # Use available data: returns over available - 1 day (skip last day)
            if len(closes) < 5:
                return 0.0
            lookback = max(2, min(len(closes) - 1, 21))  # up to 21 days back
            ret = (closes[-2] - closes[-lookback]) / closes[-lookback]
        else:
            ret = (closes[-22] - closes[-252]) / closes[-252]
        return ret * 100

    def run(self, conn: sqlite3.Connection) -> list[dict]:
        instruments = conn.execute(
            "SELECT id, ticker, name, sector FROM instruments WHERE asset_class = 'equity'"
        ).fetchall()

        factor_scores = []
        for inst in instruments:
            prices = _get_prices(conn, inst["id"], limit=260)
            if len(prices) < 5:
                continue
            closes = [p["close"] for p in prices]
            volumes = [p["volume"] for p in prices]

            momentum = self._score_momentum(closes)
            vol_20    = _volatility(closes, 20) or 0.3
            rsi       = _rsi(closes, 14) or 50

            # Quality proxy: lower volatility = higher quality score (0-10)
            # PATCH 2026-05-22 : formule logistique robuste, calibrée pour
            # rester sensible jusqu'à vol annuelle de 100%
            # vol_20 < 0.15 (faible vol) → score ~10
            # vol_20 = 0.30 (vol normale) → score ~5
            # vol_20 > 0.60 (forte vol) → score ~0
            quality_score = 10 / (1 + math.exp((vol_20 - 0.30) * 12))
            quality_inv_vol = quality_score  # snapshot avant mix Perplexity
            # [FACTOR_PPLX_V1] Mix Perplexity quality if available
            quality_narrative = None
            red_flags_count = 0
            if _pplx_get_quality is not None:
                try:
                    _pq = _pplx_get_quality(inst['ticker'])
                    if _pq and _pq.get('quality_score') is not None:
                        quality_narrative = float(_pq['quality_score']) / 10.0  # 0-100 -> 0-10
                        red_flags_count = len(_pq.get('red_flags') or [])
                        # Mix 50/50 quality
                        quality_score = 0.5 * quality_inv_vol + 0.5 * quality_narrative
                        # Penalite red flags (max -3)
                        quality_score = max(0.0, quality_score - min(red_flags_count, 3))
                except Exception as _e:
                    print(f"[FactorAgent] PPLX quality fetch echec pour {inst['ticker']}: {_e}")

            # Momentum score (0-10)
            # Map -30% to +30% range to 0-10
            momentum_score = max(0, min(10, (momentum + 30) / 6))

            # Combined factor score
            # PATCH : momentum 60% (au lieu de 50%) pour booster sensibilité signal
            combined = momentum_score * 0.6 + quality_score * 0.25 + (10 - rsi / 10) * 0.15

            # Conviction based on how extreme the combined score is
            extreme = abs(combined - 5)
            conviction = min(9, 4 + extreme)

            # PATCH : seuils ramenés à 6/4 (au lieu de 7/3) pour générer
            # des thèses actionnables sur marché normal
            if combined >= 6:
                tilt = "overweight"
                proposed = f"Increase {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            elif combined <= 4:
                tilt = "underweight"
                proposed = f"Reduce {inst['ticker']} allocation by 2-3%; factor composite score {combined:.1f}/10"
            else:
                tilt = "neutral"
                proposed = f"Maintain current {inst['ticker']} allocation; no factor edge"

            key_drivers = [
                f"Momentum (12-1m): {momentum:+.1f}%",
                f"Quality proxy (inv-vol): {quality_score:.1f}/10",
                f"RSI(14): {rsi:.1f}",
                f"Factor composite: {combined:.1f}/10",
                f"Tilt recommendation: {tilt}",
            ]

            thesis_text = (
                f"## Factor Analysis – {inst['ticker']} – {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
                f"**Tilt:** {tilt.upper()} | **Composite Score:** {combined:.1f}/10\n\n"
                f"Factor analysis for **{inst['name']}** ({inst['ticker']}) indicates a **{tilt}** stance. "
                f"Price momentum of {momentum:+.1f}% over the medium term "
                f"{'supports' if momentum > 0 else 'weighs against'} the position. "
                f"Quality proxy (inverse volatility) scores {quality_score:.1f}/10. "
                f"RSI at {rsi:.1f} indicates {'overbought conditions' if rsi > 65 else 'oversold conditions' if rsi < 35 else 'neutral momentum'}.\n\n"
                f"**Proposed action:** {proposed}"
            )

            thesis_id = _save_thesis(
                conn, inst["id"], self.NAME, thesis_text,
                round(conviction, 1), "medium", key_drivers, proposed
            )
            log_event(conn, "agent_thesis_generated", "thesis", thesis_id,
                      {"ticker": inst["ticker"],
                "quality_inv_vol": round(quality_inv_vol, 2),
                "quality_narrative": round(quality_narrative, 2) if quality_narrative is not None else None,
                "red_flags_count": red_flags_count, "tilt": tilt, "combined_score": round(combined, 2)},
                      self.NAME)

            factor_scores.append({
                "thesis_id": thesis_id,
                "ticker": inst["ticker"],
                "tilt": tilt,
                "combined_score": round(combined, 2),
                "conviction": round(conviction, 1),
                "proposed_action": proposed,
            })

        return sorted(factor_scores, key=lambda x: x["combined_score"], reverse=True)


# ---------------------------------------------------------------------------
# MicrostructureAgent
# ---------------------------------------------------------------------------

class MicrostructureAgent:
    """
    Analyzes price action, volume, support/resistance for each instrument.
    Rules: Bollinger Bands, VWAP proxy, volume trend, ATR-based stop levels.
    """
    NAME = "MicrostructureAgent"

    def run(self, conn: sqlite3.Connection) -> list[dict]:
        instruments = conn.execute(
            "SELECT id, ticker, name, sector FROM instruments"
        ).fetchall()

        results = []
        for inst in instruments:
            prices = _get_prices(conn, inst["id"], limit=60)
            if len(prices) < 10:
                continue

            closes  = [p["close"] for p in prices]
            volumes = [p["volume"] for p in prices]
            highs   = [p["high"] for p in prices]
            lows    = [p["low"] for p in prices]

            current_price = closes[-1]
            period20 = min(20, len(closes))
            sma20 = _sma(closes, period20)
            std20 = math.sqrt(sum((c - sma20) ** 2 for c in closes[-period20:]) / period20) if sma20 else 0
            bb_upper = sma20 + 2 * std20 if sma20 else None
            bb_lower = sma20 - 2 * std20 if sma20 else None
            atr14    = _atr(prices, 14)
            rsi14    = _rsi(closes, 14)

            # Volume trend: recent 5d avg vs available history avg
            vol_5d  = sum(volumes[-5:])  / min(5, len(volumes))
            vol_base_period = min(20, len(volumes))
            vol_20d = sum(volumes[-vol_base_period:]) / vol_base_period
            vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0

            # Support (recent low) / resistance (recent high)
            lookback = min(10, len(lows))
            support    = min(lows[-lookback:])
            resistance = max(highs[-lookback:])

            # Microstructure signal
            bb_pct = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper and bb_lower and (bb_upper - bb_lower) > 0 else 0.5

            if bb_pct > 0.95 and vol_ratio > 1.2:
                signal = "sell / take profit"
                conviction = 7.5
                horizon = "short"
                proposed = f"Consider trimming {inst['ticker']}; price near upper Bollinger Band with elevated volume (ratio {vol_ratio:.1f}x)"
            elif bb_pct < 0.05 and vol_ratio < 0.9:
                signal = "buy / add"
                conviction = 7.5
                horizon = "short"
                proposed = f"Consider adding {inst['ticker']}; price near lower Bollinger Band on declining volume (capitulation)"
            elif rsi14 and rsi14 > 70:
                signal = "reduce"
                conviction = 6.5
                horizon = "short"
                proposed = f"RSI overbought ({rsi14:.1f}); reduce position or set trailing stop at {current_price * 0.95:.2f}"
            elif rsi14 and rsi14 < 30:
                signal = "accumulate"
                conviction = 6.5
                horizon = "short"
                proposed = f"RSI oversold ({rsi14:.1f}); accumulate on weakness, stop below {support:.2f}"
            else:
                signal = "hold"
                conviction = 5.0
                horizon = "medium"
                proposed = f"No microstructure edge; hold {inst['ticker']} with stop at {current_price * 0.92:.2f}"

            stop_level = current_price - (atr14 * 2 if atr14 else current_price * 0.08)

            key_drivers = [
                f"Price vs BB: {bb_pct * 100:.0f}th percentile of 20-day range",
                f"Volume ratio (5d/20d): {vol_ratio:.2f}x",
                f"RSI(14): {rsi14:.1f}" if rsi14 else "RSI: insufficient data",
                f"10-day support: {support:.2f} | resistance: {resistance:.2f}",
                f"ATR-based stop: {stop_level:.2f}",
            ]

            thesis_text = (
                f"## Microstructure Signal – {inst['ticker']} – {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
                f"**Signal:** {signal.upper()} | **Conviction:** {conviction}/10\n\n"
                f"Technical analysis of **{inst['name']}** ({inst['ticker']}) current price "
                f"${current_price:.2f} is at the {bb_pct * 100:.0f}th percentile of its 20-day "
                f"Bollinger Band range. Volume is {vol_ratio:.2f}x the 20-day average, "
                f"indicating {'elevated' if vol_ratio > 1.1 else 'subdued'} market participation. "
                f"RSI(14) at {(f'{rsi14:.1f}' if rsi14 is not None else 'N/A')} shows {('overbought conditions' if rsi14 is not None and rsi14 > 65 else 'oversold conditions' if rsi14 is not None and rsi14 < 35 else 'neutral momentum' if rsi14 is not None else 'insufficient data')}. "  # [MICRO_RSI_NONE_FIX_V2]
                f"10-day support at ${support:.2f}, resistance at ${resistance:.2f}. "
                f"ATR-derived stop loss at ${stop_level:.2f}.\n\n"
                f"**Proposed action:** {proposed}"
            )

            thesis_id = _save_thesis(
                conn, inst["id"], self.NAME, thesis_text,
                conviction, horizon, key_drivers, proposed
            )
            log_event(conn, "agent_thesis_generated", "thesis", thesis_id,
                      {"ticker": inst["ticker"], "signal": signal, "bb_pct": round(bb_pct, 3)},
                      self.NAME)

            results.append({
                "thesis_id": thesis_id,
                "ticker": inst["ticker"],
                "signal": signal,
                "conviction": conviction,
                "proposed_action": proposed,
            })

        return results


# ---------------------------------------------------------------------------
# AltDataAgent
# ---------------------------------------------------------------------------

class AltDataAgent:
    """
    Simulates alternative data analysis using deterministic rules:
    - Price-volume divergence as a sentiment proxy
    - Relative performance vs sector ETF
    - Trend consistency (days above/below 20-SMA)
    """
    NAME = "AltDataAgent"
    SECTOR_ETFS = {
        "Technology": "QQQ",
        "Financials": "XLF",
        "Healthcare": "XLV",
        "Energy": "XLE",
        "Consumer Discretionary": "XLY",
    }

    def run(self, conn: sqlite3.Connection) -> list[dict]:
        instruments = conn.execute(
            "SELECT id, ticker, name, sector FROM instruments WHERE asset_class = 'equity'"
        ).fetchall()

        results = []
        for inst in instruments:
            prices = _get_prices(conn, inst["id"], limit=30)
            if len(prices) < 5:
                continue

            closes  = [p["close"] for p in prices]
            volumes = [p["volume"] for p in prices]
            current = closes[-1]
            sma20   = _sma(closes, min(20, len(closes)))

            # 1. Price-volume divergence sentiment proxy
            # Rising price + falling volume = weak momentum (distribution)
            # Falling price + rising volume = capitulation (potential buy)
            price_change_5d = (closes[-1] - closes[-min(6, len(closes))]) / closes[-min(6, len(closes))] if len(closes) > 2 else 0
            vol5_period = min(5, len(volumes))
            vol_prev_period = min(5, len(volumes) - vol5_period) if len(volumes) > vol5_period else 1
            vol_curr = sum(volumes[-vol5_period:]) / vol5_period
            vol_prev = sum(volumes[-(vol5_period + vol_prev_period):-vol5_period]) / vol_prev_period if vol_prev_period > 0 else vol_curr
            vol_change_5d   = (vol_curr - vol_prev) / (vol_prev + 1e-9)

            if price_change_5d > 0.02 and vol_change_5d > 0.2:
                sentiment = "strong_bullish"  # price up + volume up = healthy rally
            elif price_change_5d > 0.02 and vol_change_5d < -0.1:
                sentiment = "weak_bullish"    # price up but volume falling = distribution risk
            elif price_change_5d < -0.02 and vol_change_5d > 0.2:
                sentiment = "capitulation"    # price down + volume surge = exhaustion / buy
            elif price_change_5d < -0.02 and vol_change_5d < -0.1:
                sentiment = "weak_bearish"    # price down + volume drying = lack of conviction
            else:
                sentiment = "neutral"

            # 2. Trend consistency: % of last N days above 20-SMA
            sma_period = min(20, len(closes))
            sma20   = _sma(closes, sma_period)
            lookback_n = min(10, len(closes))
            if sma20:
                days_above = sum(1 for c in closes[-lookback_n:] if c > sma20)
                trend_consistency = days_above / lookback_n
            else:
                trend_consistency = 0.5

            # 3. Social/news sentiment proxy via price anomaly detection
            # Unusual moves (>2 std devs) suggest newsflow
            returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
            mean_r = sum(returns) / len(returns) if returns else 0
            std_r  = math.sqrt(sum((r - mean_r)**2 for r in returns) / len(returns)) if len(returns) > 1 else 0.01
            last_return = returns[-1] if returns else 0
            z_score = (last_return - mean_r) / std_r if std_r > 0 else 0

            # Derive conviction from signals
            conviction_map = {
                "strong_bullish": 8.0,
                "weak_bullish": 5.5,
                "capitulation": 7.5,
                "weak_bearish": 6.0,
                "neutral": 5.0,
            }
            conviction = conviction_map[sentiment]

            # Adjust for trend consistency
            if sentiment in ("strong_bullish", "weak_bullish"):
                conviction += (trend_consistency - 0.5) * 2
            elif sentiment in ("weak_bearish", "capitulation"):
                conviction -= (trend_consistency - 0.5) * 1.5
            conviction = round(max(3, min(9.5, conviction)), 1)

            # Proposed action
            if sentiment in ("strong_bullish", "capitulation") and trend_consistency > 0.6:
                proposed = f"Alt-data signal supports accumulating {inst['ticker']}; sentiment {sentiment}, trend consistency {trend_consistency:.0%}"
                horizon = "short"
            elif sentiment in ("weak_bullish", "weak_bearish"):
                proposed = f"Mixed alt-data signals for {inst['ticker']}; monitor for clarification"
                horizon = "short"
            else:
                proposed = f"No actionable alt-data edge for {inst['ticker']} at this time"
                horizon = "medium"

            key_drivers = [
                f"Price-volume sentiment: {sentiment}",
                f"5-day price change: {price_change_5d * 100:+.1f}%",
                f"5-day volume change: {vol_change_5d * 100:+.1f}%",
                f"Trend consistency (10d above SMA20): {trend_consistency:.0%}",
                f"Last-day return z-score: {z_score:+.2f} ({'unusual' if abs(z_score) > 2 else 'normal'})",
            ]

            thesis_text = (
                f"## Alt-Data Signal – {inst['ticker']} – {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
                f"**Sentiment:** {sentiment.replace('_', ' ').upper()} | **Conviction:** {conviction}/10\n\n"
                f"Alternative data analysis of **{inst['name']}** ({inst['ticker']}) using "
                f"price-volume dynamics and trend consistency indicators. "
                f"5-day price change of {price_change_5d * 100:+.1f}% with "
                f"volume {'+' if vol_change_5d >= 0 else ''}{vol_change_5d * 100:.1f}% vs prior 5-day average "
                f"generates a **{sentiment.replace('_', ' ')}** sentiment signal. "
                f"Price has been above its 20-day SMA on {int(trend_consistency * 10)} of the last 10 days. "
                f"Latest session return z-score of {z_score:+.2f} "
                f"{'suggests unusual news-driven activity' if abs(z_score) > 2 else 'indicates normal trading conditions'}.\n\n"
                f"**Proposed action:** {proposed}"
            )

            thesis_id = _save_thesis(
                conn, inst["id"], self.NAME, thesis_text,
                conviction, horizon, key_drivers, proposed
            )
            log_event(conn, "agent_thesis_generated", "thesis", thesis_id,
                      {"ticker": inst["ticker"], "sentiment": sentiment, "conviction": conviction},
                      self.NAME)

            results.append({
                "thesis_id": thesis_id,
                "ticker": inst["ticker"],
                "sentiment": sentiment,
                "conviction": conviction,
                "proposed_action": proposed,
            })

        return results


# ---------------------------------------------------------------------------
# CryptoAgent
# ---------------------------------------------------------------------------


# [CRYPTO_RSI_NONE_V1] helper top-level: format-safe sur valeurs potentiellement None
def _safe_fmt(v, spec='.1f'):
    try:
        if v is None:
            return 'N/A'
        return format(float(v), spec)
    except (TypeError, ValueError):
        return 'N/A'

class CryptoAgent:
    """
    Specialized agent for cryptocurrency instruments (TOP 25 by market cap).
    Combines momentum, volatility regime, trend strength, and volume analysis
    with crypto-specific thresholds (higher vol tolerance, faster signals).
    """
    NAME = "CryptoAgent"

    def run(self, conn: sqlite3.Connection) -> list[dict]:
        instruments = conn.execute(
            "SELECT id, ticker, name, sector FROM instruments WHERE asset_class = 'crypto'"
        ).fetchall()

        results = []
        for inst in instruments:
            prices = _get_prices(conn, inst["id"], limit=60)
            if len(prices) < 5:
                continue

            closes  = [p["close"] for p in prices]
            volumes = [p["volume"] for p in prices]
            highs   = [p["high"] for p in prices]
            lows    = [p["low"] for p in prices]
            current = closes[-1]

            # --- 1. Trend: SMA 7 / SMA 21 (faster than equity) ---
            sma7  = _sma(closes, min(7, len(closes)))
            sma21 = _sma(closes, min(21, len(closes)))
            rsi14 = _rsi(closes, 14)
            atr14 = _atr(prices, 14)
            vol20 = _volatility(closes, min(20, len(closes) - 1)) if len(closes) > 2 else None

            # Trend direction
            if sma7 and sma21:
                trend = "bullish" if sma7 > sma21 else "bearish"
                trend_strength = abs(sma7 - sma21) / sma21 * 100 if sma21 > 0 else 0
            else:
                trend = "neutral"
                trend_strength = 0

            # --- 2. Momentum score (7d return) ---
            lookback = min(7, len(closes) - 1)
            momentum_7d = (current - closes[-(lookback + 1)]) / closes[-(lookback + 1)] * 100 if lookback > 0 else 0

            # --- 3. Volatility regime (crypto: >80% annualized = high, <40% = low) ---
            ann_vol = (vol20 * 100) if vol20 else 50
            if ann_vol > 80:
                vol_regime = "high"
            elif ann_vol < 40:
                vol_regime = "low"
            else:
                vol_regime = "moderate"

            # --- 4. Volume trend ---
            vol_5d  = sum(volumes[-min(5, len(volumes)):]) / min(5, len(volumes))
            vol_base = min(20, len(volumes))
            vol_20d = sum(volumes[-vol_base:]) / vol_base
            vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1.0

            # --- 5. Bollinger position ---
            period = min(20, len(closes))
            sma_bb = _sma(closes, period)
            if sma_bb and period > 1:
                std_bb = math.sqrt(sum((c - sma_bb) ** 2 for c in closes[-period:]) / period)
                bb_upper = sma_bb + 2 * std_bb
                bb_lower = sma_bb - 2 * std_bb
                bb_pct = (current - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
            else:
                bb_pct = 0.5

            # --- Composite scoring ---
            # Momentum score 0-10 (crypto uses wider range: -50% to +50%)
            momentum_score = max(0, min(10, (momentum_7d + 50) / 10))

            # Trend score 0-10
            trend_score = 5 + (trend_strength if trend == "bullish" else -trend_strength)
            trend_score = max(0, min(10, trend_score))

            # Volume confirmation 0-10
            vol_score = min(10, vol_ratio * 5)  # >2x = 10

            # RSI contrarian component 0-10
            rsi_component = (10 - (rsi14 / 10)) if rsi14 else 5

            # Composite: momentum 35%, trend 30%, volume 15%, RSI contrarian 20%
            composite = (
                momentum_score * 0.35 +
                trend_score * 0.30 +
                vol_score * 0.15 +
                rsi_component * 0.20
            )
            composite = round(composite, 1)

            # --- Signal logic ---
            if composite >= 7.5 and trend == "bullish" and vol_ratio > 1.1:
                signal = "strong_buy"
                conviction = min(9, 7 + (composite - 7.5))
                horizon = "short"
                proposed = f"Signal d'achat fort sur {inst['ticker']} ; composite {composite}/10, tendance haussiere confirmee par le volume (ratio {(_safe_fmt(vol_ratio, '.1f'))}x)"
            elif composite >= 6.0 and trend == "bullish":
                signal = "buy"
                conviction = min(8, 6 + (composite - 6))
                horizon = "short"
                proposed = f"Accumuler {inst['ticker']} ; composite {composite}/10, momentum 7j {momentum_7d:+.1f}%"
            elif composite <= 3.0 and trend == "bearish":
                signal = "sell"
                conviction = min(8.5, 6 + (3 - composite))
                horizon = "short"
                proposed = f"Reduire l'exposition sur {inst['ticker']} ; composite {composite}/10, tendance baissiere"
            elif rsi14 and rsi14 > 75:
                signal = "take_profit"
                conviction = 7.0
                horizon = "short"
                proposed = f"Prendre des profits sur {inst['ticker']} ; RSI surachete a {(_safe_fmt(rsi14, '.1f'))}"
            elif rsi14 and rsi14 < 25:
                signal = "accumulate"
                conviction = 7.0
                horizon = "short"
                proposed = f"Zone d'accumulation pour {inst['ticker']} ; RSI survendu a {(_safe_fmt(rsi14, '.1f'))}"
            else:
                signal = "hold"
                conviction = 5.0
                horizon = "medium"
                proposed = f"Maintenir la position {inst['ticker']} ; pas de signal directionnel clair (composite {composite}/10)"

            conviction = round(conviction, 1)
            stop_level = current - (atr14 * 2.5 if atr14 else current * 0.10)

            key_drivers = [
                f"Tendance SMA7/SMA21 : {trend} (ecart {(_safe_fmt(trend_strength, '.2f'))}%)",
                f"Momentum 7j : {momentum_7d:+.1f}%",
                f"Regime de volatilite : {vol_regime} ({(_safe_fmt(ann_vol, '.0f'))}% ann.)",
                f"Ratio volume 5j/20j : {(_safe_fmt(vol_ratio, '.2f'))}x",
                f"Bollinger : {bb_pct * 100:.0f}e percentile",
                f"RSI(14) : {(_safe_fmt(rsi14, '.1f'))}" if rsi14 else "RSI : donnees insuffisantes",
                f"Score composite : {composite}/10",
                f"Stop ATR (2.5x) : ${stop_level:,.2f}",
            ]

            thesis_text = (
                f"## Analyse Crypto – {inst['ticker']} – {datetime.utcnow().strftime('%Y-%m-%d')}\n\n"
                f"**Signal :** {signal.upper().replace('_', ' ')} | **Conviction :** {conviction}/10 | **Composite :** {composite}/10\n\n"
                f"Analyse specialisee de **{inst['name']}** ({inst['ticker']}). "
                f"Prix actuel ${current:,.2f}. "
                f"La tendance court terme (SMA7 vs SMA21) est **{trend}** avec un ecart de {(_safe_fmt(trend_strength, '.2f'))}%. "
                f"Le momentum sur 7 jours est de {momentum_7d:+.1f}%. "
                f"La volatilite annualisee de {(_safe_fmt(ann_vol, '.0f'))}% place l'actif en regime **{vol_regime}**. "
                f"Le volume recent represente {(_safe_fmt(vol_ratio, '.2f'))}x la moyenne 20 jours, "
                f"indiquant {'une participation elevee' if vol_ratio > 1.2 else 'une participation normale' if vol_ratio > 0.8 else 'une activite reduite'}. "
                f"RSI(14) a {(_safe_fmt(rsi14, '.1f'))} {'en zone de surachat' if rsi14 and rsi14 > 70 else 'en zone de survente' if rsi14 and rsi14 < 30 else 'en zone neutre'}.\n\n"
                f"**Action proposee :** {proposed}\n"
                f"**Stop loss (2.5x ATR) :** ${stop_level:,.2f}"
            )

            thesis_id = _save_thesis(
                conn, inst["id"], self.NAME, thesis_text,
                conviction, horizon, key_drivers, proposed
            )
            log_event(conn, "agent_thesis_generated", "thesis", thesis_id,
                      {"ticker": inst["ticker"], "signal": signal, "composite": composite,
                       "conviction": conviction, "trend": trend, "vol_regime": vol_regime},
                      self.NAME)

            results.append({
                "thesis_id": thesis_id,
                "ticker": inst["ticker"],
                "signal": signal,
                "composite_score": composite,
                "conviction": conviction,
                "trend": trend,
                "vol_regime": vol_regime,
                "proposed_action": proposed,
            })

        return results


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_all_agents(conn: sqlite3.Connection) -> dict:
    """Run all five agents and return aggregated results."""
    print("[agents] Running MacroAgent...")
    macro_result   = MacroAgent().run(conn)
    print("[agents] Running FactorAgent...")
    factor_results = FactorAgent().run(conn)
    print("[agents] Running MicrostructureAgent...")
    micro_results  = MicrostructureAgent().run(conn)
    print("[agents] Running AltDataAgent...")
    alt_results    = AltDataAgent().run(conn)
    print("[agents] Running CryptoAgent...")
    crypto_results = CryptoAgent().run(conn)

    log_event(conn, "agent_cycle_complete", details={
        "macro_conviction": macro_result.get("conviction"),
        "factor_theses": len(factor_results),
        "micro_theses": len(micro_results),
        "alt_theses": len(alt_results),
        "crypto_theses": len(crypto_results),
    }, agent="Orchestrator")

    return {
        "macro": macro_result,
        "factor": factor_results,
        "microstructure": micro_results,
        "altdata": alt_results,
        "crypto": crypto_results,
    }


if __name__ == "__main__":
    from models import init_db
    init_db()
    conn = get_db()
    results = run_all_agents(conn)
    conn.commit()
    conn.close()
    print("Agent cycle complete.")
