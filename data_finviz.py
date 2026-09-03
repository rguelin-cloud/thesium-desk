"""
data_finviz.py — Finviz data module for Thesium Desk
Fetches stock signals and sector data via the finvizfinance library.
Cache TTL: 15 minutes (900 seconds).
"""

import time
import traceback
from typing import Any

# ---------------------------------------------------------------------------
# Simple in-memory cache
# ---------------------------------------------------------------------------

_cache: dict[str, dict[str, Any]] = {}
CACHE_TTL = 900  # 15 minutes


def _is_fresh(key: str) -> bool:
    entry = _cache.get(key)
    if not entry:
        return False
    return (time.time() - entry["ts"]) < CACHE_TTL


def _set(key: str, data: Any) -> None:
    _cache[key] = {"ts": time.time(), "data": data}


def _get(key: str) -> Any:
    return _cache[key]["data"]


# ---------------------------------------------------------------------------
# Helper — parse a Finviz percentage / float string
# ---------------------------------------------------------------------------

def _pct(val: Any) -> float | None:
    """Parse a Finviz value like '3.45%', '-1.20%', '3.45', '-', '' → float or None."""
    if val is None:
        return None
    s = str(val).strip().rstrip("%")
    if s in ("-", "", "N/A", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _f(val: Any) -> float | None:
    """Parse a plain float string; returns None for missing values."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("-", "", "N/A", "None"):
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. fetch_stock_signals
# ---------------------------------------------------------------------------

def fetch_stock_signals(tickers: list[str]) -> list[dict]:
    """Stock signals V2 - calcule tout depuis la table prices maison.  # [STOCK_SIGNALS_V2]

    Remplace l'ancienne implementation basee sur finvizfinance qui casse
    depuis le HTML rewrite Finviz (T1 2026). Ancienne version conservee
    en _fetch_stock_signals_legacy_finviz() en dessous.
    """
    cache_key = "stock_signals:" + ",".join(sorted(tickers))
    if _is_fresh(cache_key):
        return _get(cache_key)

    try:
        import signals_calculator  # noqa: PLC0415
        results = signals_calculator.compute_signals(tickers)
    except Exception as e:
        print(f"[data_finviz] compute_signals error: {e}")
        # Fallback : rows vides mais structure preservee
        results = []
        for t in tickers:
            row = {"ticker": t}
            for field in ("price", "change", "rsi", "sma20", "sma50", "sma200",
                          "recom", "target", "short_float", "rel_volume", "beta",
                          "perf_week", "perf_month", "perf_ytd", "sector"):
                row[field] = None
            results.append(row)

    _set(cache_key, results)
    return results


def _fetch_stock_signals_legacy_finviz(tickers: list[str]) -> list[dict]:
    """
    For each ticker, fetch RSI, SMA20/50/200, analyst Recom, Target Price,
    Short Float, Perf Week/Month/YTD, Rel Volume, Beta, Change, Sector.

    Returns a list of dicts (one per ticker).  On Finviz error for a given
    ticker the row is still returned but fields will be None.
    """
    cache_key = "stock_signals:" + ",".join(sorted(tickers))
    if _is_fresh(cache_key):
        return _get(cache_key)

    try:
        from finvizfinance.quote import finvizfinance  # noqa: PLC0415
    except ImportError:
        print("[data_finviz] finvizfinance not installed")
        return []

    results: list[dict] = []

    for ticker in tickers:
        row: dict = {"ticker": ticker}
        try:
            stock = finvizfinance(ticker)
            info = stock.ticker_fundament()

            row["price"]      = _f(info.get("Price"))
            row["change"]     = _pct(info.get("Change"))          # already %
            row["rsi"]        = _f(info.get("RSI (14)"))
            row["sma20"]      = _pct(info.get("SMA20"))           # % above/below
            row["sma50"]      = _pct(info.get("SMA50"))
            row["sma200"]     = _pct(info.get("SMA200"))
            row["recom"]      = _f(info.get("Recom"))             # 1–5 scale
            row["target"]     = _f(info.get("Target Price"))
            row["short_float"]= _pct(info.get("Short Float"))
            row["rel_volume"] = _f(info.get("Rel Volume"))
            row["beta"]       = _f(info.get("Beta"))
            row["perf_week"]  = _pct(info.get("Perf Week"))
            row["perf_month"] = _pct(info.get("Perf Month"))
            row["perf_ytd"]   = _pct(info.get("Perf YTD"))
            row["sector"]     = info.get("Sector", "")
        except Exception:
            print(f"[data_finviz] Error fetching {ticker}:\n{traceback.format_exc()}")
            # Leave all fields as None — row still present so UI can show it
            for field in ("price", "change", "rsi", "sma20", "sma50", "sma200",
                          "recom", "target", "short_float", "rel_volume", "beta",
                          "perf_week", "perf_month", "perf_ytd", "sector"):
                row.setdefault(field, None)

        results.append(row)

    _set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# 2. fetch_sector_performance
# ---------------------------------------------------------------------------

def fetch_sector_performance() -> list[dict]:
    """
    Fetch sector performance table: Perf Week/Month/Quarter/YTD, Change.
    Returns a list of dicts keyed by sector Name.
    """
    cache_key = "sector_performance"
    if _is_fresh(cache_key):
        return _get(cache_key)

    try:
        from finvizfinance.group.performance import Performance  # noqa: PLC0415
        fperf = Performance()
        df = fperf.screener_view(group="Sector")
    except Exception:
        print(f"[data_finviz] Error fetching sector performance:\n{traceback.format_exc()}")
        _set(cache_key, [])
        return []

    results: list[dict] = []
    for _, row in df.iterrows():
        results.append({
            "name":       str(row.get("Name", "")),
            "change":     _pct(row.get("Change")),
            "perf_week":  _pct(row.get("Perf Week")),
            "perf_month": _pct(row.get("Perf Month")),
            "perf_quart": _pct(row.get("Perf Quart")),
            "perf_half":  _pct(row.get("Perf Half")),
            "perf_year":  _pct(row.get("Perf Year")),
            "perf_ytd":   _pct(row.get("Perf YTD")),
        })

    _set(cache_key, results)
    return results


# ---------------------------------------------------------------------------
# 3. fetch_sector_overview
# ---------------------------------------------------------------------------

def fetch_sector_overview() -> list[dict]:
    """
    Fetch sector overview table: P/E, Fwd P/E, Dividend yield, etc.
    Returns a list of dicts keyed by sector Name.
    """
    cache_key = "sector_overview"
    if _is_fresh(cache_key):
        return _get(cache_key)

    try:
        from finvizfinance.group.overview import Overview  # noqa: PLC0415
        foverview = Overview()
        df = foverview.screener_view(group="Sector")
    except Exception:
        print(f"[data_finviz] Error fetching sector overview:\n{traceback.format_exc()}")
        _set(cache_key, [])
        return []

    results: list[dict] = []
    for _, row in df.iterrows():
        results.append({
            "name":     str(row.get("Name", "")),
            "stocks":   _f(row.get("Stocks")),
            "mktcap":   str(row.get("Market Cap", "")),
            "dividend": _pct(row.get("Dividend")),
            "pe":       _f(row.get("P/E")),
            "fwd_pe":   _f(row.get("Fwd P/E")),
            "peg":      _f(row.get("PEG")),
            "change":   _pct(row.get("Change")),
        })

    _set(cache_key, results)
    return results
