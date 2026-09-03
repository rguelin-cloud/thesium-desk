# -*- coding: utf-8 -*-
# replay_adapters.py
# Jalon 8A - Adapters pour le backtest event-driven
# 3 classes : MarketDataAdapter, FREDAdapter, PPLXNeutralAdapter
# GARANTIE no look-ahead : tout get_*_up_to(day_t) filtre strict date <= day_t

import os
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, date

DB_PATH_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def _ensure_replay_mode():
    """Soft check : log warning si NEXTONES_REPLAY_MODE != 1."""
    mode = os.environ.get("NEXTONES_REPLAY_MODE", "0")
    if mode != "1":
        import sys
        print(
            "[WARN] NEXTONES_REPLAY_MODE != 1 (val=%s). Adapters utilisables mais hors replay officiel."
            % mode,
            file=sys.stderr,
        )


def _open_ro(db_path: str) -> sqlite3.Connection:
    """Ouvre la DB en read-only pour eviter toute ecriture accidentelle prod."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=15.0)
    conn.row_factory = sqlite3.Row
    return conn


def _norm_day(day_t: Any) -> str:
    """Normalise day_t en 'YYYY-MM-DD' (accepte str ou date/datetime)."""
    if isinstance(day_t, (datetime, date)):
        return day_t.strftime("%Y-%m-%d")
    s = str(day_t)
    # Tolere 'YYYY-MM-DD HH:MM:SS' -> garde la date seule
    return s[:10]


class MarketDataAdapter:
    """
    Adapter read-only pour la table prices.
    Schema : (id, instrument_id, date, open, high, low, close, volume)
    JOIN avec instruments(id, ticker, asset_class).

    Garantie no look-ahead : get_prices_up_to(day_t) renvoie uniquement les
    lignes avec date <= day_t.
    """

    def __init__(self, db_path: str = DB_PATH_DEFAULT):
        self.db_path = db_path
        _ensure_replay_mode()

    def get_prices_up_to(
        self, day_t: Any, ticker: Optional[str] = None, lookback_days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retourne les prix <= day_t. Si ticker None : tous les tickers."""
        day_str = _norm_day(day_t)
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        sql = """
            SELECT i.ticker, i.asset_class, p.date, p.open, p.high, p.low, p.close, p.volume
            FROM prices p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE p.date <= ?
        """
        params: List[Any] = [day_str]
        if ticker is not None:
            sql += " AND i.ticker = ?"
            params.append(ticker)
        sql += " ORDER BY i.ticker, p.date"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if lookback_days is not None and rows:
            # Filtre les N derniers jours par ticker (cote python pour eviter sous-requetes)
            by_t: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                by_t.setdefault(r["ticker"], []).append(r)
            out: List[Dict[str, Any]] = []
            for t, lst in by_t.items():
                lst.sort(key=lambda x: x["date"])
                out.extend(lst[-lookback_days:])
            out.sort(key=lambda x: (x["ticker"], x["date"]))
            return out

        return rows

    def get_close_at(self, day_t: Any, ticker: str) -> Optional[float]:
        """Close exact au day_t (ou None si pas de cours ce jour)."""
        day_str = _norm_day(day_t)
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.close
            FROM prices p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE i.ticker = ? AND p.date = ?
            """,
            (ticker, day_str),
        )
        row = cur.fetchone()
        conn.close()
        return float(row["close"]) if row and row["close"] is not None else None

    def get_open_after(self, day_t: Any, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Premier open strictement APRES day_t (= J+1 trading) pour fill_simulator.
        Retourne {date, open, high, low, close, volume} ou None.
        """
        day_str = _norm_day(day_t)
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.date, p.open, p.high, p.low, p.close, p.volume
            FROM prices p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE i.ticker = ? AND p.date > ?
            ORDER BY p.date ASC
            LIMIT 1
            """,
            (ticker, day_str),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def list_tickers(self, asset_class: Optional[str] = None) -> List[str]:
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        if asset_class is None:
            cur.execute("SELECT DISTINCT ticker FROM instruments ORDER BY ticker")
        else:
            cur.execute(
                "SELECT DISTINCT ticker FROM instruments WHERE asset_class = ? ORDER BY ticker",
                (asset_class,),
            )
        out = [r["ticker"] for r in cur.fetchall()]
        conn.close()
        return out


class FREDAdapter:
    """
    Adapter read-only pour la table macro_history.
    Schema attendu : (series_id, date, value) ou similaire.
    Garantie no look-ahead : date <= day_t strict.
    """

    def __init__(self, db_path: str = DB_PATH_DEFAULT):
        self.db_path = db_path
        _ensure_replay_mode()

    def get_macro_up_to(
        self,
        day_t: Any,
        series_id: Optional[str] = None,
        lookback_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        day_str = _norm_day(day_t)
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        # Detecte le nom de colonne pour series_id (parfois 'series_id', parfois 'series')
        cur.execute("PRAGMA table_info(macro_history)")
        cols = [r["name"] for r in cur.fetchall()]
        sid_col = None
        for cand in ("series_id", "series_code", "series", "code", "ticker"):
            if cand in cols:
                sid_col = cand
                break
        if sid_col is None:
            conn.close()
            return []
        val_col = "value" if "value" in cols else ("val" if "val" in cols else None)
        if val_col is None:
            conn.close()
            return []

        sql = f"SELECT {sid_col} AS series_id, date, {val_col} AS value FROM macro_history WHERE date <= ?"
        params: List[Any] = [day_str]
        if series_id is not None:
            sql += f" AND {sid_col} = ?"
            params.append(series_id)
        sql += " ORDER BY series_id, date"
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        if lookback_days is not None and rows:
            by_s: Dict[str, List[Dict[str, Any]]] = {}
            for r in rows:
                by_s.setdefault(r["series_id"], []).append(r)
            out: List[Dict[str, Any]] = []
            for s, lst in by_s.items():
                lst.sort(key=lambda x: x["date"])
                out.extend(lst[-lookback_days:])
            out.sort(key=lambda x: (x["series_id"], x["date"]))
            return out

        return rows

    def get_value_at(self, day_t: Any, series_id: str) -> Optional[float]:
        """Derniere valeur <= day_t (forward fill weekend/holiday)."""
        day_str = _norm_day(day_t)
        conn = _open_ro(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(macro_history)")
        cols = [r["name"] for r in cur.fetchall()]
        sid_col = None
        for cand in ("series_id", "series_code", "series", "code", "ticker"):
            if cand in cols:
                sid_col = cand
                break
        if sid_col is None:
            conn.close()
            return None
        val_col = "value" if "value" in cols else "val"
        cur.execute(
            f"""
            SELECT {val_col} AS value FROM macro_history
            WHERE {sid_col} = ? AND date <= ?
            ORDER BY date DESC LIMIT 1
            """,
            (series_id, day_str),
        )
        row = cur.fetchone()
        conn.close()
        return float(row["value"]) if row and row["value"] is not None else None


class PPLXNeutralAdapter:
    """
    Stub neutre : remplace tous les agents PPLX en replay.
    Aucun appel reseau, scores fixes pour reproductibilite stricte.
    Couvre : crypto-agent, factor-agent, geo-agent, memo-agent, thesis-agent.
    """

    NEUTRAL_SCORE = 50.0  # /100
    NEUTRAL_SENTIMENT = "neutral"
    NEUTRAL_CONFIDENCE = 0.5
    NEUTRAL_VERDICT = "neutral"

    def __init__(self):
        _ensure_replay_mode()

    def get_crypto_context(self, day_t: Any, ticker: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "day_t": _norm_day(day_t),
            "score": self.NEUTRAL_SCORE,
            "sentiment": self.NEUTRAL_SENTIMENT,
            "confidence": self.NEUTRAL_CONFIDENCE,
            "stub": True,
        }

    def get_factor_quality(self, day_t: Any, ticker: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "day_t": _norm_day(day_t),
            "score": self.NEUTRAL_SCORE,
            "factor_quality": self.NEUTRAL_SCORE,
            "stub": True,
        }

    def get_geo_context(self, day_t: Any) -> Dict[str, Any]:
        return {
            "day_t": _norm_day(day_t),
            "score": self.NEUTRAL_SCORE,
            "sentiment": self.NEUTRAL_SENTIMENT,
            "tensions": [],
            "stub": True,
        }

    def get_memo_summary(self, day_t: Any, ticker: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "day_t": _norm_day(day_t),
            "summary": "neutral / no-op in replay",
            "verdict": self.NEUTRAL_VERDICT,
            "confidence": self.NEUTRAL_CONFIDENCE,
            "stub": True,
        }

    def get_thesis_challenge(self, day_t: Any, ticker: Optional[str] = None) -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "day_t": _norm_day(day_t),
            "challenge": "neutral",
            "score": self.NEUTRAL_SCORE,
            "stub": True,
        }


__all__ = ["MarketDataAdapter", "FREDAdapter", "PPLXNeutralAdapter"]
