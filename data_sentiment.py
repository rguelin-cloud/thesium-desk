"""
Sentiment indicators for Nextones Desk.
- Crypto: Fear & Greed Index (alternative.me) — 0 = Extreme Fear, 100 = Extreme Greed
- Equities: VIX-based sentiment (FRED VIXCLS) — inverted: low VIX = Greed, high VIX = Fear
"""

import time
import requests

FRED_API_KEY = "8d8ef4b05a6d63cec4d7abb7a6031d84"

# Cache (TTL 1 hour)
_cache = {"data": None, "ts": 0}
CACHE_TTL = 3600


def _vix_to_sentiment(vix: float) -> dict:
    """Convert VIX level to a 0-100 sentiment score (inverted: low VIX = high score = Greed)."""
    # VIX ranges: 10-15 = very low vol (extreme greed), 15-20 = low (greed),
    # 20-25 = moderate (neutral), 25-35 = high (fear), 35+ = extreme fear
    if vix <= 12:
        score = 95
    elif vix <= 20:
        # Linear: 12->90, 20->55
        score = 90 - (vix - 12) * (35 / 8)
    elif vix <= 30:
        # Linear: 20->50, 30->20
        score = 50 - (vix - 20) * 3
    elif vix <= 40:
        # Linear: 30->20, 40->5
        score = 20 - (vix - 30) * 1.5
    else:
        score = max(0, 5 - (vix - 40) * 0.5)

    score = max(0, min(100, round(score)))

    if score >= 75:
        label = "Extreme Greed"
    elif score >= 55:
        label = "Greed"
    elif score >= 45:
        label = "Neutral"
    elif score >= 25:
        label = "Fear"
    else:
        label = "Extreme Fear"

    return {"score": score, "label": label, "vix": round(vix, 1)}


def _sentiment_color(score: int) -> str:
    """Return color based on sentiment score."""
    if score >= 75:
        return "#70AD47"   # Green — Extreme Greed
    if score >= 55:
        return "#9DC3E6"   # Light blue — Greed
    if score >= 45:
        return "#FFD966"   # Yellow — Neutral
    if score >= 25:
        return "#F4B942"   # Orange — Fear
    return "#C00000"       # Red — Extreme Fear


def get_sentiment() -> dict:
    """Return combined sentiment data for crypto and equities."""
    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < CACHE_TTL:
        return _cache["data"]

    result = {
        "crypto": None,
        "equities": None,
        "updated_at": None,
    }

    # ---- 1. Crypto Fear & Greed (alternative.me) ----
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=8", timeout=8)
        if resp.status_code == 200:
            fng_data = resp.json().get("data", [])
            if fng_data:
                latest = fng_data[0]
                score = int(latest["value"])
                # History for sparkline (last 7 days, oldest first)
                history = [{"date": d["timestamp"], "score": int(d["value"])} for d in reversed(fng_data[1:])]
                prev_score = int(fng_data[1]["value"]) if len(fng_data) > 1 else score
                result["crypto"] = {
                    "score": score,
                    "label": latest["value_classification"],
                    "color": _sentiment_color(score),
                    "delta_1d": score - prev_score,
                    "history": history,
                    "source": "alternative.me",
                }
    except Exception:
        pass

    # ---- 2. Equities Sentiment (VIX-based) ----
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id=VIXCLS&api_key={FRED_API_KEY}&file_type=json"
            f"&sort_order=desc&limit=8"
        )
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            obs = [o for o in resp.json().get("observations", []) if o["value"] != "."]
            if obs:
                latest_vix = float(obs[0]["value"])
                sent = _vix_to_sentiment(latest_vix)
                # History for sparkline
                history = []
                for o in reversed(obs[1:]):
                    try:
                        v = float(o["value"])
                        s = _vix_to_sentiment(v)
                        history.append({"date": o["date"], "score": s["score"], "vix": v})
                    except (ValueError, KeyError):
                        pass
                prev_vix = float(obs[1]["value"]) if len(obs) > 1 else latest_vix
                prev_sent = _vix_to_sentiment(prev_vix)
                result["equities"] = {
                    "score": sent["score"],
                    "label": sent["label"],
                    "color": _sentiment_color(sent["score"]),
                    "vix": sent["vix"],
                    "delta_1d": sent["score"] - prev_sent["score"],
                    "history": history,
                    "source": "FRED (CBOE VIX)",
                }
    except Exception:
        pass

    from datetime import datetime
    result["updated_at"] = datetime.utcnow().isoformat()

    _cache["data"] = result
    _cache["ts"] = now

    return result
