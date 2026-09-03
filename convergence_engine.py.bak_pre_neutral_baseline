"""
[CONVERGENCE_ENGINE_V1]
Convergence Engine L1-L5 pour Nextones / ThesiumDesk.

Mapping :
  L1 - Regime       : MacroAgent (stance global)
  L2 - Positioning  : FactorAgent (tilt per ticker)
  L3 - Structure    : MicrostructureAgent (RSI / BB / vol)
                      remplace par CryptoAgent si ticker crypto
  L4 - Liquidite    : AltDataAgent (sentiment per ticker)
                      remplace par CryptoAgent si ticker crypto (merged)
  L5 - Risque       : ExitAgent (STOP_LOSS / DRIFT / HOLD)
                      enrichi par crypto_context.red_flags pour cryptos

Regles :
  - Convergence valide : n_aligned >= 3 parmi les buckets renseignes
  - sizing_multiplier :
      5/5 -> 1.5 | 4/5 -> 1.25 | 3/5 -> 1.0
      2/5 -> 0.5 | <=1/5 -> 0.25
  - Override : L5 STOP_LOSS -> forced_exit=True, multiplier=0
  - DRIFT -> compte comme short + multiplier *= 0.5

API publique :
  compute_convergence(conn, cycle_id) -> List[dict] (un par ticker)
  parse_*(theses_row) -> dict bucket
"""

from __future__ import annotations

import re
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

CRYPTO_UNIVERSE = {"BTC", "ETH", "LINK", "SOL", "HYPE", "ZEC"}

BURST_TOLERANCE_MIN = 5  # fenetre pour grouper une rafale d'inserts

# Multipliers par n_aligned (sur buckets renseignes)
SIZING_TABLE = {
    5: 1.5,
    4: 1.25,
    3: 1.0,
    2: 0.5,
    1: 0.25,
    0: 0.25,
}

DIRECTION_LONG = "long"
DIRECTION_SHORT = "short"
DIRECTION_NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# PARSE HELPERS
# ---------------------------------------------------------------------------

_RE_STANCE = re.compile(r"\*\*Stance:?\*\*\s*([A-Z_]+)", re.IGNORECASE)
_RE_TILT = re.compile(r"\*\*Tilt:?\*\*\s*([A-Z_]+)", re.IGNORECASE)
_RE_SIGNAL = re.compile(r"\*\*Signal\s*:?\*\*\s*([A-Z_]+)", re.IGNORECASE)
_RE_SENTIMENT = re.compile(
    r"\*\*Sentiment:?\*\*\s*([A-Z_]+)", re.IGNORECASE
)


def _norm(val: Optional[str]) -> str:
    if val is None:
        return ""
    return str(val).strip().upper()


def _extract_first(pattern: re.Pattern, text: str) -> str:
    if not text:
        return ""
    m = pattern.search(text)
    return m.group(1).upper() if m else ""


# ---------------------------------------------------------------------------
# PER-AGENT PARSERS
#   chaque parser retourne :
#     {"bucket": "Lx", "source": "...", "direction": long|short|neutral,
#      "conviction": float, "driver": str, "raw_signal": str}
# ---------------------------------------------------------------------------

def parse_macro(row: Dict[str, Any]) -> Dict[str, Any]:
    """L1 - MacroAgent : stance global."""
    text = row.get("thesis_text", "") or ""
    stance = _extract_first(_RE_STANCE, text)
    action = _norm(row.get("proposed_action"))

    if stance in ("RISK_ON", "BULLISH", "POSITIVE"):
        direction = DIRECTION_LONG
    elif stance in ("RISK_OFF", "BEARISH", "NEGATIVE"):
        direction = DIRECTION_SHORT
    else:
        # fallback action
        if "increase" in action.lower() or "buy" in action.lower():
            direction = DIRECTION_LONG
        elif "reduce" in action.lower() or "sell" in action.lower():
            direction = DIRECTION_SHORT
        else:
            direction = DIRECTION_NEUTRAL

    return {
        "bucket": "L1",
        "source": "MacroAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": _first_driver(row.get("key_drivers")),
        "raw_signal": stance or "NEUTRAL",
    }


def parse_factor(row: Dict[str, Any]) -> Dict[str, Any]:
    """L2 - FactorAgent : tilt per ticker."""
    text = row.get("thesis_text", "") or ""
    tilt = _extract_first(_RE_TILT, text)
    action = (row.get("proposed_action") or "").lower()

    if tilt in ("POSITIVE", "BULLISH", "LONG"):
        direction = DIRECTION_LONG
    elif tilt in ("NEGATIVE", "BEARISH", "SHORT"):
        direction = DIRECTION_SHORT
    elif "increase" in action:
        direction = DIRECTION_LONG
    elif "reduce" in action:
        direction = DIRECTION_SHORT
    else:
        direction = DIRECTION_NEUTRAL

    return {
        "bucket": "L2",
        "source": "FactorAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": _first_driver(row.get("key_drivers")),
        "raw_signal": tilt or "NEUTRAL",
    }


def parse_microstructure(row: Dict[str, Any]) -> Dict[str, Any]:
    """L3 - MicrostructureAgent : RSI / BB / structure technique."""
    action = (row.get("proposed_action") or "").lower()

    if "oversold" in action or "accumulate" in action:
        direction = DIRECTION_LONG
    elif "overbought" in action or "reduce" in action or "trailing" in action:
        direction = DIRECTION_SHORT
    else:
        direction = DIRECTION_NEUTRAL

    return {
        "bucket": "L3",
        "source": "MicrostructureAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": _first_driver(row.get("key_drivers")),
        "raw_signal": (row.get("proposed_action") or "")[:80],
    }


def parse_altdata(row: Dict[str, Any]) -> Dict[str, Any]:
    """L4 - AltDataAgent : sentiment per ticker."""
    text = row.get("thesis_text", "") or ""
    sentiment = _extract_first(_RE_SENTIMENT, text)
    action = (row.get("proposed_action") or "").lower()

    if sentiment == "BULLISH":
        direction = DIRECTION_LONG
    elif sentiment == "BEARISH":
        direction = DIRECTION_SHORT
    elif "mixed" in action:
        direction = DIRECTION_NEUTRAL
    elif "no actionable" in action:
        direction = DIRECTION_NEUTRAL
    else:
        direction = DIRECTION_NEUTRAL

    return {
        "bucket": "L4",
        "source": "AltDataAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": _first_driver(row.get("key_drivers")),
        "raw_signal": sentiment or "NEUTRAL",
    }


def parse_crypto(row: Dict[str, Any]) -> Dict[str, Any]:
    """CryptoAgent : remplace L3+L4 pour les tickers crypto."""
    text = row.get("thesis_text", "") or ""
    sig = _extract_first(_RE_SIGNAL, text)
    action = (row.get("proposed_action") or "").lower()

    if sig in ("ACCUMULATE", "BUY", "LONG"):
        direction = DIRECTION_LONG
    elif sig in ("REDUCE", "SELL", "SHORT", "EXIT"):
        direction = DIRECTION_SHORT
    elif "accumulation" in action or "accumuler" in action:
        direction = DIRECTION_LONG
    elif "reduire" in action or "alleger" in action or "sell" in action:
        direction = DIRECTION_SHORT
    else:
        direction = DIRECTION_NEUTRAL

    return {
        "bucket": "L3-L4",
        "source": "CryptoAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": _first_driver(row.get("key_drivers")),
        "raw_signal": sig or "NEUTRAL",
    }


def parse_exit(row: Dict[str, Any]) -> Dict[str, Any]:
    """L5 - ExitAgent : STOP_LOSS / DRIFT."""
    action = _norm(row.get("proposed_action"))

    if action == "STOP_LOSS":
        direction = DIRECTION_SHORT
        forced = True
    elif action == "DRIFT":
        direction = DIRECTION_SHORT
        forced = False
    elif action in ("HOLD", "MAINTAIN"):
        direction = DIRECTION_NEUTRAL
        forced = False
    else:
        direction = DIRECTION_NEUTRAL
        forced = False

    return {
        "bucket": "L5",
        "source": "ExitAgent",
        "direction": direction,
        "conviction": float(row.get("conviction_score") or 5.0),
        "driver": (row.get("thesis_text") or "")[:100],
        "raw_signal": action or "HOLD",
        "forced_exit": forced,
        "drift_attenuation": action == "DRIFT",
    }


def _first_driver(key_drivers: Any) -> str:
    """Extrait le premier driver d'une key_drivers JSON ou string."""
    if not key_drivers:
        return ""
    if isinstance(key_drivers, str):
        try:
            arr = json.loads(key_drivers)
            if isinstance(arr, list) and arr:
                return str(arr[0])[:100]
        except Exception:
            return key_drivers[:100]
    if isinstance(key_drivers, list) and key_drivers:
        return str(key_drivers[0])[:100]
    return ""


# ---------------------------------------------------------------------------
# DB LOADERS
# ---------------------------------------------------------------------------

def _get_burst_window(
    conn: sqlite3.Connection, agent_type: str
) -> Optional[Tuple[str, str]]:
    """Retourne (lo_ts, hi_ts) du dernier burst de cet agent."""
    cur = conn.execute(
        "SELECT MAX(created_at) FROM theses WHERE agent_type = ?",
        (agent_type,),
    )
    last_ts = cur.fetchone()[0]
    if not last_ts:
        return None

    try:
        # Tolere ISO et "YYYY-MM-DD HH:MM:SS"
        ts_clean = last_ts.replace("T", " ").split(".")[0]
        dt = datetime.strptime(ts_clean, "%Y-%m-%d %H:%M:%S")
        lo = (dt - timedelta(minutes=BURST_TOLERANCE_MIN)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        lo = last_ts
    return (lo, last_ts)


def _load_agent_burst(
    conn: sqlite3.Connection, agent_type: str
) -> List[Dict[str, Any]]:
    """Charge le dernier burst d'un agent (toutes lignes en JOIN ticker)."""
    win = _get_burst_window(conn, agent_type)
    if not win:
        return []
    lo, hi = win

    sql = """
        SELECT t.id, t.instrument_id, t.agent_type, t.thesis_text,
               t.conviction_score, t.horizon, t.key_drivers,
               t.proposed_action, t.status, t.created_at,
               i.ticker
        FROM theses t
        LEFT JOIN instruments i ON i.id = t.instrument_id
        WHERE t.agent_type = ?
          AND t.created_at BETWEEN ? AND ?
    """
    cur = conn.execute(sql, (agent_type, lo, hi))
    cols = [d[0] for d in cur.description]
    rows = []
    for r in cur.fetchall():
        rows.append(dict(zip(cols, r)))
    return rows


def _load_crypto_context(
    conn: sqlite3.Connection,
) -> Dict[str, Dict[str, Any]]:
    """Charge crypto_context (1 ligne par symbol)."""
    try:
        cur = conn.execute(
            "SELECT symbol, narrative_score, red_flags, social_sentiment "
            "FROM crypto_context"
        )
    except sqlite3.OperationalError:
        return {}
    out = {}
    for r in cur.fetchall():
        sym = r[0]
        out[sym] = {
            "narrative_score": r[1],
            "red_flags": r[2],
            "social_sentiment": r[3],
        }
    return out


# ---------------------------------------------------------------------------
# AGGREGATION
# ---------------------------------------------------------------------------

def _direction_to_int(d: str) -> int:
    if d == DIRECTION_LONG:
        return 1
    if d == DIRECTION_SHORT:
        return -1
    return 0


def _consensus(directions: List[str]) -> Tuple[str, int, int]:
    """Retourne (direction_consensus, n_aligned, n_present). Legacy, conserve pour compat."""
    present = [d for d in directions if d in (DIRECTION_LONG, DIRECTION_SHORT)]
    total_present = sum(
        1
        for d in directions
        if d in (DIRECTION_LONG, DIRECTION_SHORT, DIRECTION_NEUTRAL)
    )

    if not present:
        return (DIRECTION_NEUTRAL, 0, total_present)

    long_n = sum(1 for d in present if d == DIRECTION_LONG)
    short_n = sum(1 for d in present if d == DIRECTION_SHORT)

    if long_n > short_n:
        return (DIRECTION_LONG, long_n, total_present)
    if short_n > long_n:
        return (DIRECTION_SHORT, short_n, total_present)
    return (DIRECTION_NEUTRAL, max(long_n, short_n), total_present)


def _sizing(n_aligned: int) -> float:
    return SIZING_TABLE.get(n_aligned, 0.25)


# [PATCH_NEUTRAL_BASELINE_V1]
NEUTRAL_MAJORITY_THRESHOLD = 0.6  # >=60% neutres -> regime 'neutre stable'


def _consensus_and_sizing(directions: List[str]) -> Tuple[str, int, int, str, float]:
    """
    Retourne (consensus, n_aligned, n_present, regime, multiplier_base).

    regime in {'strong', 'neutral_stable', 'conflict'}
    multiplier_base : avant override forced_exit / drift

    Regles :
      - n_directional=0 -> neutral_stable, baseline 1.0
      - >=60% neutres   -> neutral_stable, baseline 1.0 (signal directionnel minoritaire indicatif)
      - long==short (egalite avec presence des deux) -> conflict, 0.25
      - n_aligned>=3 et opposition presente ou non -> strong, SIZING_TABLE
      - n_aligned 1-2 avec opposition -> conflict, 0.5
      - n_aligned 1-2 sans opposition -> neutral_stable, 1.0
    """
    long_n = sum(1 for d in directions if d == DIRECTION_LONG)
    short_n = sum(1 for d in directions if d == DIRECTION_SHORT)
    neutral_n = sum(1 for d in directions if d == DIRECTION_NEUTRAL)
    n_present = long_n + short_n + neutral_n
    n_directional = long_n + short_n

    if n_present == 0:
        return (DIRECTION_NEUTRAL, 0, 0, "neutral_stable", 1.0)

    if n_directional == 0:
        return (DIRECTION_NEUTRAL, n_present, n_present, "neutral_stable", 1.0)

    if (neutral_n / n_present) >= NEUTRAL_MAJORITY_THRESHOLD:
        if long_n > short_n:
            return (DIRECTION_LONG, long_n, n_present, "neutral_stable", 1.0)
        if short_n > long_n:
            return (DIRECTION_SHORT, short_n, n_present, "neutral_stable", 1.0)
        return (DIRECTION_NEUTRAL, neutral_n, n_present, "neutral_stable", 1.0)

    if long_n == short_n and n_directional > 0:
        return (DIRECTION_NEUTRAL, max(long_n, short_n), n_present, "conflict", 0.25)

    if long_n > short_n:
        consensus = DIRECTION_LONG
        n_aligned = long_n
        opposite = short_n
    else:
        consensus = DIRECTION_SHORT
        n_aligned = short_n
        opposite = long_n

    if n_aligned >= 3:
        return (consensus, n_aligned, n_present, "strong",
                SIZING_TABLE.get(n_aligned, 1.0))

    if opposite >= 1:
        return (consensus, n_aligned, n_present, "conflict", 0.5)

    return (consensus, n_aligned, n_present, "neutral_stable", 1.0)


def compute_convergence(
    conn: sqlite3.Connection, cycle_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Agregation principale.

    Pour chaque ticker present dans au moins 1 bucket :
      - assemble L1-L5
      - calcule consensus + sizing
      - applique override exit
    """
    macro_rows = _load_agent_burst(conn, "MacroAgent")
    factor_rows = _load_agent_burst(conn, "FactorAgent")
    micro_rows = _load_agent_burst(conn, "MicrostructureAgent")
    alt_rows = _load_agent_burst(conn, "AltDataAgent")
    crypto_rows = _load_agent_burst(conn, "CryptoAgent")
    exit_rows = _load_agent_burst(conn, "ExitAgent")

    crypto_ctx = _load_crypto_context(conn)

    # Macro = global (instrument_id = NULL, on prend la derniere ligne)
    macro_parsed = None
    if macro_rows:
        active = [r for r in macro_rows if r.get("status") == "active"]
        chosen = active[0] if active else macro_rows[-1]
        macro_parsed = parse_macro(chosen)

    # Index par ticker
    by_ticker = {}

    def _idx(rows, parser, bucket_key):
        for r in rows:
            tk = r.get("ticker")
            if not tk:
                continue
            tk = tk.upper()
            entry = by_ticker.setdefault(
                tk, {"ticker": tk, "buckets": {}}
            )
            entry["buckets"][bucket_key] = parser(r)

    _idx(factor_rows, parse_factor, "L2")
    _idx(micro_rows, parse_microstructure, "L3")
    _idx(alt_rows, parse_altdata, "L4")
    _idx(exit_rows, parse_exit, "L5")

    # Crypto : remplace L3 et L4 (meme signal, marque "merged")
    for r in crypto_rows:
        tk = r.get("ticker")
        if not tk:
            continue
        tk = tk.upper()
        if tk not in CRYPTO_UNIVERSE:
            continue
        parsed = parse_crypto(r)
        entry = by_ticker.setdefault(tk, {"ticker": tk, "buckets": {}})
        entry["buckets"]["L3"] = dict(parsed, note="merged_crypto_L3")
        entry["buckets"]["L4"] = dict(parsed, note="merged_crypto_L4")

    # Macro broadcast en L1 pour tous
    for tk, entry in by_ticker.items():
        if macro_parsed:
            entry["buckets"]["L1"] = dict(macro_parsed)
        # Enrichissement L5 via crypto_context (red_flags)
        if tk in CRYPTO_UNIVERSE and tk in crypto_ctx:
            ctx = crypto_ctx[tk]
            rf = ctx.get("red_flags")
            l5 = entry["buckets"].get("L5")
            if l5 and rf:
                try:
                    flags = json.loads(rf) if isinstance(rf, str) else rf
                    if flags and isinstance(flags, list):
                        l5["crypto_red_flags"] = flags[:3]
                except Exception:
                    pass

    # Aggregation finale
    results = []
    for tk in sorted(by_ticker.keys()):
        entry = by_ticker[tk]
        buckets = entry["buckets"]
        is_crypto = tk in CRYPTO_UNIVERSE

        # Pour les cryptos : L3 et L4 contiennent le meme signal (merged)
        # -> ne compter qu'une fois dans le consensus
        directions = []
        counted_keys = []
        for key in ("L1", "L2", "L3", "L4", "L5"):
            b = buckets.get(key)
            if not b:
                continue
            # Merge crypto : si L3 et L4 sont mergees, ne compter L3
            if (
                is_crypto
                and key == "L4"
                and b.get("note") == "merged_crypto_L4"
            ):
                continue
            directions.append(b["direction"])
            counted_keys.append(key)

        consensus, n_aligned, n_present, regime, multiplier_base = \
            _consensus_and_sizing(directions)

        # Override exit
        l5 = buckets.get("L5") or {}
        forced_exit = bool(l5.get("forced_exit", False))
        drift = bool(l5.get("drift_attenuation", False))

        if forced_exit:
            multiplier = 0.0
            consensus = DIRECTION_SHORT
        else:
            multiplier = multiplier_base
            if drift:
                multiplier *= 0.5

        conv_pct = (n_aligned / n_present) if n_present > 0 else 0.0

        results.append(
            {
                "cycle_id": cycle_id,
                "ticker": tk,
                "is_crypto": is_crypto,
                "direction_consensus": consensus,
                "n_aligned": n_aligned,
                "n_present": n_present,
                "convergence_pct": round(conv_pct, 3),
                "regime": regime,
                "sizing_multiplier": round(multiplier, 3),
                "forced_exit": forced_exit,
                "drift": drift,
                "buckets": buckets,
                "counted_buckets": counted_keys,
            }
        )

    return results


# ---------------------------------------------------------------------------
# RENDERING (helpers UI / memo)
# ---------------------------------------------------------------------------

def render_convergence_summary(results: List[Dict[str, Any]]) -> str:
    """Petit rendu textuel pour debug / memo."""
    lines = []
    lines.append("Ticker  | Dir      | n/N | Conv% | Sizing | Notes")
    lines.append("--------|----------|-----|-------|--------|------")
    for r in results:
        notes = []
        if r["forced_exit"]:
            notes.append("STOP_LOSS")
        if r["drift"]:
            notes.append("DRIFT")
        if r["is_crypto"]:
            notes.append("crypto")
        lines.append(
            "%-7s | %-8s | %d/%d | %.0f%%  | %.2fx  | %s"
            % (
                r["ticker"],
                r["direction_consensus"],
                r["n_aligned"],
                r["n_present"],
                r["convergence_pct"] * 100,
                r["sizing_multiplier"],
                ", ".join(notes),
            )
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PERSISTENCE
# ---------------------------------------------------------------------------

def save_convergence_snapshot(
    conn: sqlite3.Connection,
    cycle_id: str,
    results: List[Dict[str, Any]],
) -> int:
    """Persiste les resultats dans convergence_snapshots. Retourne n_inserted."""
    now = datetime.now().isoformat(" ", "seconds")
    n = 0
    for r in results:
        conn.execute(
            "INSERT OR REPLACE INTO convergence_snapshots "
            "(cycle_id, ticker, direction_consensus, n_aligned, n_present, "
            " convergence_pct, sizing_multiplier, forced_exit, drift, "
            " is_crypto, buckets_json, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                cycle_id,
                r["ticker"],
                r["direction_consensus"],
                r["n_aligned"],
                r["n_present"],
                r["convergence_pct"],
                r["sizing_multiplier"],
                int(bool(r["forced_exit"])),
                int(bool(r["drift"])),
                int(bool(r["is_crypto"])),
                json.dumps(r["buckets"], ensure_ascii=False, default=str),
                now,
            ),
        )
        n += 1
    conn.commit()
    return n
