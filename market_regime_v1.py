# -*- coding: utf-8 -*-
"""
[MARKET_REGIME_V1]
Module de detection de regime marche pour Nextones.

Architecture :
  - 2 regimes paralleles : equity (SPY-based) et crypto (BTC-based)
  - 3 etats par classe : CALM / NORMAL / STRESS
  - Signaux internes (prices DB) + VIX externe (FRED) pour equity
  - Output : multiplicateurs caps BUY/SELL + seuil convergence dynamique

Inputs :
  equity  : VIX (FRED VIXCLS) + SPY realized vol 20j + SPY drawdown 5j
  crypto  : BTC realized vol 14j + BTC drawdown 5j (pas de VIX equivalent)

Output regimes :
  CALM    : marche tranquille -> on prend des profits (cap SELL larges)
  NORMAL  : etat courant, caps neutres
  STRESS  : peur / volatilite haute -> on achete la peur (cap BUY larges, cap SELL serres)

Garde-fous :
  - Si donnees manquantes / stales -> fallback NORMAL
  - Pas de cache regime > 4h (anti-whipsaw via persistance log)
  - Kill-switch via env var NEXTONES_MARKET_REGIME_DISABLE=1
"""
import os
import json
import math
import sqlite3
import datetime
from typing import Dict, Any, Optional, List, Tuple

try:
    import requests
except ImportError:
    requests = None

# =============================================================================
# Constants (calibres MVP - a ajuster apres observation)
# =============================================================================

FRED_API_KEY = "8d8ef4b05a6d63cec4d7abb7a6031d84"
FRED_VIX_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
    "?series_id=VIXCLS&api_key={key}&file_type=json&sort_order=desc&limit=10"
)

# Seuils EQUITY (calibres sur marches US)
EQUITY_VIX_CALM = 15.0           # VIX < 15 = complaisance
EQUITY_VIX_STRESS = 22.0         # VIX > 22 = stress
EQUITY_VOL_CALM_PCT = 12.0       # vol realisee 20j < 12% = calme
EQUITY_VOL_STRESS_PCT = 20.0     # vol realisee 20j > 20% = stress
EQUITY_DD_CALM_PCT = 2.0         # drawdown 5j < 2% = calme
EQUITY_DD_STRESS_PCT = 5.0       # drawdown 5j > 5% = stress

# Seuils CRYPTO (vol naturellement plus haute)
CRYPTO_VOL_CALM_PCT = 40.0       # vol 14j < 40% = calme pour crypto
CRYPTO_VOL_STRESS_PCT = 70.0     # vol 14j > 70% = stress crypto
CRYPTO_DD_CALM_PCT = 5.0
CRYPTO_DD_STRESS_PCT = 12.0

# Multiplicateurs caps par regime
REGIME_CAPS = {
    "CALM": {
        "buy_mult":  0.7,     # achete moins (marche cher)
        "sell_mult": 1.5,     # vend plus (prend profits)
        "convergence_thresh": 0.65,
    },
    "NORMAL": {
        "buy_mult":  1.0,
        "sell_mult": 1.0,
        "convergence_thresh": 0.60,
    },
    "STRESS": {
        "buy_mult":  1.8,     # achete plus (la peur cree des opportunites)
        "sell_mult": 0.5,     # vend moins (anti-capitulation)
        "convergence_thresh": 0.50,
    },
}


# [REGIME_CAPS_CONFIG_V1] Source unique des multiplicateurs de regime.
# Avant ce patch, REGIME_CAPS etait code en dur (CALM 0.7/1.5) et
# alimentait market_regime_log, la justification des ordres, le memo IC
# et le sizing. La grille revisee du 2026-09-03 vit desormais dans
# regime_multiplier_config ; cette fonction en fait la seule source.
#
# Repli en cascade :
#   1. regime_multiplier_config (asset_class, regime, active=1)
#   2. REGIME_CAPS[regime]
#   3. REGIME_CAPS["NORMAL"]
#
# Corrige aussi un KeyError latent : REGIME_CAPS n'a pas de cle ALERT
# alors que les classifieurs et la config peuvent la produire.

_REGIME_CAPS_CACHE = {}
_REGIME_CAPS_CACHE_TS = 0.0
_REGIME_CAPS_TTL_SEC = 60.0


def _caps_fallback(regime):
    """Repli sur la table codee en dur, sans jamais lever KeyError."""
    return REGIME_CAPS.get(regime) or REGIME_CAPS.get("NORMAL") or {
        "buy_mult": 1.0, "sell_mult": 1.0, "convergence_thresh": 0.60}


def _caps_for(regime, asset_class="equity", conn=None):
    """
    Retourne {"buy_mult", "sell_mult", "convergence_thresh"} pour
    (asset_class, regime), lu depuis regime_multiplier_config.

    Ne leve jamais : tout echec retombe sur REGIME_CAPS.
    """
    import os as _os_c
    import sqlite3 as _sq_c
    import time as _tm_c

    global _REGIME_CAPS_CACHE, _REGIME_CAPS_CACHE_TS

    _reg = str(regime or "NORMAL").upper()
    _ac = str(asset_class or "equity").lower()
    if _ac in ("etf", "stock", "equities"):
        _ac = "equity"
    elif _ac not in ("crypto", "equity"):
        _ac = "equity"

    if str(_os_c.getenv("NEXTONES_REGIME_CONFIG_DISABLE", "")).strip() == "1":
        return _caps_fallback(_reg)

    _now = _tm_c.time()
    if _now - _REGIME_CAPS_CACHE_TS > _REGIME_CAPS_TTL_SEC:
        _REGIME_CAPS_CACHE = {}
        _REGIME_CAPS_CACHE_TS = _now

    _ck = (_ac, _reg)
    if _ck in _REGIME_CAPS_CACHE:
        return dict(_REGIME_CAPS_CACHE[_ck])

    _own = False
    _c = conn
    try:
        if _c is None:
            _dbp = _os_c.environ.get(
                "THESIUM_DB",
                _os_c.path.join(
                    _os_c.path.dirname(_os_c.path.abspath(__file__)),
                    "thesium.db"))
            _c = _sq_c.connect(_dbp, timeout=10.0)
            _own = True

        _cols = [r[1] for r in _c.execute(
            "PRAGMA table_info(regime_multiplier_config)")]
        if not _cols:
            return _caps_fallback(_reg)

        _has_conv = "conv_thresh" in _cols
        _has_active = "active" in _cols

        _sel = "buy_mult, sell_mult"
        if _has_conv:
            _sel += ", conv_thresh"
        _q = ("SELECT " + _sel + " FROM regime_multiplier_config"
              " WHERE asset_class = ? AND regime = ?")
        if _has_active:
            _q += " AND active = 1"
        _q += " LIMIT 1"

        _r = _c.execute(_q, (_ac, _reg)).fetchone()
        if _r is None:
            return _caps_fallback(_reg)

        _fb = _caps_fallback(_reg)
        _out = {
            "buy_mult": float(_r[0]),
            "sell_mult": float(_r[1]),
            "convergence_thresh": (
                float(_r[2]) if (_has_conv and _r[2] is not None)
                else float(_fb.get("convergence_thresh", 0.60))),
        }
        _REGIME_CAPS_CACHE[_ck] = dict(_out)
        return _out
    except Exception:
        return _caps_fallback(_reg)
    finally:
        if _own and _c is not None:
            try:
                _c.close()
            except Exception:
                pass


# Tickers references
EQUITY_BENCHMARK = "SPY"
CRYPTO_BENCHMARK = "BTC"

# Fenetres de calcul
VOL_WINDOW_EQUITY = 20    # jours
VOL_WINDOW_CRYPTO = 14    # jours
DD_WINDOW = 5             # jours

# Freshness max
MAX_PRICE_STALE_DAYS = 5

# Kill switch
DISABLED = os.environ.get("NEXTONES_MARKET_REGIME_DISABLE", "").strip() == "1"


# =============================================================================
# Helpers
# =============================================================================

def _fetch_vix_from_fred(timeout: int = 8) -> Optional[float]:
    """Fetch latest VIX value from FRED. Returns float or None on failure."""
    if requests is None:
        return None
    try:
        url = FRED_VIX_URL.format(key=FRED_API_KEY)
        r = requests.get(url, timeout=timeout)
        if r.status_code != 200:
            return None
        data = r.json()
        obs = data.get("observations") or []
        for o in obs:
            v = o.get("value")
            if v and v != ".":
                try:
                    return float(v)
                except (ValueError, TypeError):
                    continue
        return None
    except Exception:
        return None


def _fetch_recent_closes(conn: sqlite3.Connection, ticker: str, n_days: int = 30) -> List[Tuple[str, float]]:
    """Recupere les n derniers closes pour un ticker. Retourne liste [(date, close), ...] ASC."""
    rows = conn.execute("""
        SELECT p.date, p.close
        FROM prices p
        JOIN instruments i ON i.id = p.instrument_id
        WHERE i.ticker = ?
          AND p.close IS NOT NULL
        ORDER BY p.date DESC
        LIMIT ?
    """, (ticker, n_days)).fetchall()
    result = [(r[0], float(r[1])) for r in rows if r[1] is not None]
    result.reverse()
    return result


def _compute_realized_vol_pct(closes: List[Tuple[str, float]], window: int) -> Optional[float]:
    """Volatilite realisee annualisee en %. Returns None si pas assez de data."""
    if len(closes) < window + 1:
        return None
    prices = [c[1] for c in closes[-(window + 1):]]
    rets = []
    for i in range(1, len(prices)):
        if prices[i-1] <= 0:
            return None
        rets.append(math.log(prices[i] / prices[i-1]))
    if not rets:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    std = math.sqrt(var)
    return std * math.sqrt(252) * 100.0


def _compute_drawdown_pct(closes: List[Tuple[str, float]], window: int) -> Optional[float]:
    """Drawdown sur fenetre = (last - max(window)) / max(window) * 100. Negatif si baisse."""
    if len(closes) < window:
        return None
    recent = [c[1] for c in closes[-window:]]
    peak = max(recent)
    last = recent[-1]
    if peak <= 0:
        return None
    return (last - peak) / peak * 100.0


def _check_freshness(closes: List[Tuple[str, float]]) -> bool:
    """True si dernier close < MAX_PRICE_STALE_DAYS."""
    if not closes:
        return False
    try:
        last_date = closes[-1][0]
        # Date au format YYYY-MM-DD
        if "T" in last_date:
            last_date = last_date.split("T")[0]
        dt = datetime.datetime.strptime(last_date[:10], "%Y-%m-%d")
        age = (datetime.datetime.utcnow() - dt).days
        return age <= MAX_PRICE_STALE_DAYS
    except Exception:
        return False


# =============================================================================
# Logique de classification
# =============================================================================

def _classify_equity(vix: Optional[float], vol: Optional[float], dd: Optional[float]) -> Tuple[str, float, Dict]:
    """
    Classifie le regime equity.
    Retourne (regime, score, details).
    Score = nb de signaux STRESS - nb de signaux CALM (range -3 a +3).
    """
    signals_calm = 0
    signals_stress = 0
    details = {"vix": vix, "vol": vol, "dd": dd}

    if vix is not None:
        if vix < EQUITY_VIX_CALM:
            signals_calm += 1
            details["vix_signal"] = "CALM"
        elif vix > EQUITY_VIX_STRESS:
            signals_stress += 1
            details["vix_signal"] = "STRESS"
        else:
            details["vix_signal"] = "NORMAL"

    if vol is not None:
        if vol < EQUITY_VOL_CALM_PCT:
            signals_calm += 1
            details["vol_signal"] = "CALM"
        elif vol > EQUITY_VOL_STRESS_PCT:
            signals_stress += 1
            details["vol_signal"] = "STRESS"
        else:
            details["vol_signal"] = "NORMAL"

    if dd is not None:
        # dd est negatif si baisse
        if dd > -EQUITY_DD_CALM_PCT:
            signals_calm += 1
            details["dd_signal"] = "CALM"
        elif dd < -EQUITY_DD_STRESS_PCT:
            signals_stress += 1
            details["dd_signal"] = "STRESS"
        else:
            details["dd_signal"] = "NORMAL"

    score = signals_stress - signals_calm  # range -3 a +3
    details["signals_calm"] = signals_calm
    details["signals_stress"] = signals_stress

    # Majorite simple
    if signals_stress >= 2:
        return "STRESS", score, details
    if signals_calm >= 2:
        return "CALM", score, details
    return "NORMAL", score, details


def _classify_crypto(vol: Optional[float], dd: Optional[float]) -> Tuple[str, float, Dict]:
    """Classifie le regime crypto (sans VIX). Score range -2 a +2."""
    signals_calm = 0
    signals_stress = 0
    details = {"vol": vol, "dd": dd}

    if vol is not None:
        if vol < CRYPTO_VOL_CALM_PCT:
            signals_calm += 1
            details["vol_signal"] = "CALM"
        elif vol > CRYPTO_VOL_STRESS_PCT:
            signals_stress += 1
            details["vol_signal"] = "STRESS"
        else:
            details["vol_signal"] = "NORMAL"

    if dd is not None:
        if dd > -CRYPTO_DD_CALM_PCT:
            signals_calm += 1
            details["dd_signal"] = "CALM"
        elif dd < -CRYPTO_DD_STRESS_PCT:
            signals_stress += 1
            details["dd_signal"] = "STRESS"
        else:
            details["dd_signal"] = "NORMAL"

    score = signals_stress - signals_calm
    details["signals_calm"] = signals_calm
    details["signals_stress"] = signals_stress

    # Crypto : un seul signal STRESS suffit pour basculer (plus reactif)
    if signals_stress >= 1 and signals_calm == 0:
        return "STRESS", score, details
    if signals_calm >= 1 and signals_stress == 0:
        return "CALM", score, details
    return "NORMAL", score, details


# =============================================================================
# API publique
# =============================================================================

def detect_market_regime(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Detecte les regimes marche (equity + crypto) en parallele.

    Retourne :
      {
        "equity": {
          "regime": "CALM" | "NORMAL" | "STRESS",
          "vix_value": float | None,
          "realized_vol_pct": float | None,
          "drawdown_5d_pct": float | None,
          "score": float,
          "buy_mult": float,
          "sell_mult": float,
          "convergence_thresh": float,
          "details": dict,
          "fallback": bool,
        },
        "crypto": { ... },
      }

    Si DISABLED ou erreur -> tous regimes = NORMAL avec fallback=True.
    """
    if DISABLED:
        return {
            "equity": _fallback_regime("equity", reason="disabled"),
            "crypto": _fallback_regime("crypto", reason="disabled"),
        }

    result = {}

    # ---------- EQUITY ----------
    try:
        eq_closes = _fetch_recent_closes(conn, EQUITY_BENCHMARK, 35)
        if not _check_freshness(eq_closes):
            result["equity"] = _fallback_regime("equity", reason="stale_prices")
        else:
            vix = _fetch_vix_from_fred()
            vol = _compute_realized_vol_pct(eq_closes, VOL_WINDOW_EQUITY)
            dd = _compute_drawdown_pct(eq_closes, DD_WINDOW)

            regime, score, details = _classify_equity(vix, vol, dd)
            caps = _caps_for(regime, "equity", conn=conn)
            result["equity"] = {
                "regime": regime,
                "vix_value": vix,
                "realized_vol_pct": vol,
                "drawdown_5d_pct": dd,
                "score": score,
                "buy_mult": caps["buy_mult"],
                "sell_mult": caps["sell_mult"],
                "convergence_thresh": caps["convergence_thresh"],
                "details": details,
                "fallback": False,
            }
    except Exception as e:
        result["equity"] = _fallback_regime("equity", reason=f"error:{e.__class__.__name__}")

    # ---------- CRYPTO ----------
    try:
        cr_closes = _fetch_recent_closes(conn, CRYPTO_BENCHMARK, 25)
        if not _check_freshness(cr_closes):
            result["crypto"] = _fallback_regime("crypto", reason="stale_prices")
        else:
            vol = _compute_realized_vol_pct(cr_closes, VOL_WINDOW_CRYPTO)
            dd = _compute_drawdown_pct(cr_closes, DD_WINDOW)

            regime, score, details = _classify_crypto(vol, dd)
            caps = _caps_for(regime, "crypto", conn=conn)
            result["crypto"] = {
                "regime": regime,
                "vix_value": None,
                "realized_vol_pct": vol,
                "drawdown_5d_pct": dd,
                "score": score,
                "buy_mult": caps["buy_mult"],
                "sell_mult": caps["sell_mult"],
                "convergence_thresh": caps["convergence_thresh"],
                "details": details,
                "fallback": False,
            }
    except Exception as e:
        result["crypto"] = _fallback_regime("crypto", reason=f"error:{e.__class__.__name__}")

    return result


def _fallback_regime(asset_class: str, reason: str = "unknown") -> Dict[str, Any]:
    """Fallback NORMAL avec flag fallback=True."""
    caps = _caps_for("NORMAL", asset_class)
    return {
        "regime": "NORMAL",
        "vix_value": None,
        "realized_vol_pct": None,
        "drawdown_5d_pct": None,
        "score": 0.0,
        "buy_mult": caps["buy_mult"],
        "sell_mult": caps["sell_mult"],
        "convergence_thresh": caps["convergence_thresh"],
        "details": {"fallback_reason": reason},
        "fallback": True,
    }


def log_market_regime(
    conn: sqlite3.Connection,
    cycle_id: str,
    market_info: Dict[str, Any],
) -> None:
    """Persiste le regime marche dans market_regime_log (une ligne par asset_class)."""
    for asset_class in ("equity", "crypto"):
        info = market_info.get(asset_class, {})
        if not info:
            continue
        notes = "fallback" if info.get("fallback") else ""
        try:
            conn.execute("""
                INSERT INTO market_regime_log
                  (cycle_id, asset_class, regime, vix_value, realized_vol_pct,
                   drawdown_5d_pct, score, buy_mult, sell_mult,
                   convergence_thresh, details_json, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(cycle_id or ""),
                asset_class,
                info.get("regime", "NORMAL"),
                info.get("vix_value"),
                info.get("realized_vol_pct"),
                info.get("drawdown_5d_pct"),
                info.get("score", 0.0),
                info.get("buy_mult", 1.0),
                info.get("sell_mult", 1.0),
                info.get("convergence_thresh", 0.60),
                json.dumps(info.get("details", {})),
                notes,
            ))
        except Exception as e:
            print(f"[market_regime] WARN log {asset_class} : {e}")
    try:
        conn.commit()
    except Exception:
        pass


def get_caps_for_proposal(market_info: Dict[str, Any], asset_class: str) -> Dict[str, float]:
    """Retourne les caps a appliquer pour un asset_class donne (equity|crypto|etf)."""
    # ETF traite comme equity
    key = "crypto" if asset_class == "crypto" else "equity"
    info = market_info.get(key, {})
    return {
        "buy_mult": info.get("buy_mult", 1.0),
        "sell_mult": info.get("sell_mult", 1.0),
        "convergence_thresh": info.get("convergence_thresh", 0.60),
        "regime": info.get("regime", "NORMAL"),
    }


# =============================================================================
# CLI standalone (test direct)
# =============================================================================

if __name__ == "__main__":
    import pprint
    DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    print("[market_regime_v1] Test standalone")
    info = detect_market_regime(conn)
    pprint.pprint(info)
    conn.close()
