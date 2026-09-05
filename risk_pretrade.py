"""
risk_pretrade.py - [RISK_V2]
Trois controles pre-trade conformes Guide v1.0 sec 3.3 et spec sec 3.3 + sec 6.

V2 - Schema-aware (NEXTONES reel) :
  - NAV               : portfolio_state.total_value (fallback portfolio_history)
  - Positions         : portfolio_positions JOIN instruments (ticker, qty=quantity, price=current_price)
  - Returns           : prices JOIN instruments WHERE ticker = ?
  - Trace MiFID II    : risk_pretrade_log (table creee si absente)

Controles :
  1. Concentration 15% par position (post-trade simule)
  2. VaR historique 99% / 1j : budget portefeuille + delta marginal
  3. Correlation Pearson 60j returns daily : block si max > seuil

API publique :
    decision = run_pretrade_checks(ticker, qty, price, side, db_path=None, params=None)

ASCII only - aucun caractere accentue dans le source.
Compatible py 3.13 - timezone-aware datetime.
"""
from __future__ import annotations

import math
import sqlite3
import json
import datetime as _dt
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# Marker idempotent
MARKER = "[RISK_V2]"

# Parametres par defaut - surchargeables via params=
DEFAULT_PARAMS = {
    "concentration_max_pct": 0.15,
    "var_confidence": 0.99,
    "var_window_days": 60,
    "var_budget_pct_nav": 0.02,
    "var_marginal_block_pct": 0.005,
    "correl_window_days": 60,
    "correl_block_threshold": 0.85,
    "correl_min_overlap_days": 30,
}


# --------------------------------------------------------------
# Connexion + bootstrap log
# --------------------------------------------------------------
def _conn(db_path: str) -> sqlite3.Connection:  # [RISK_V2_DBLOCK_FIX_V2]
    import time as _t
    _last = None
    for _attempt in range(3):
        try:
            c = sqlite3.connect(db_path, timeout=30.0)
            c.row_factory = sqlite3.Row
            try:
                c.execute("PRAGMA busy_timeout=30000")
            except Exception:
                pass
            return c
        except sqlite3.OperationalError as _e:
            _last = _e
            if "locked" not in str(_e).lower():
                raise
            _t.sleep([0.1, 0.3, 0.9][_attempt])
    raise _last if _last is not None else sqlite3.OperationalError("unknown lock")


def _ensure_log_table(c: sqlite3.Connection) -> None:
    c.execute("""
        CREATE TABLE IF NOT EXISTS risk_pretrade_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ts           TEXT    NOT NULL,
            symbol       TEXT    NOT NULL,
            side         TEXT    NOT NULL,
            qty          REAL    NOT NULL,
            price        REAL    NOT NULL,
            passed       INTEGER NOT NULL,
            blocked_by   TEXT,
            details_json TEXT    NOT NULL,
            marker       TEXT    NOT NULL DEFAULT '[RISK_V2]'
        )
    """)
    c.commit()


# --------------------------------------------------------------
# Acces donnees - aligne schema NEXTONES
# --------------------------------------------------------------
def _get_nav(c: sqlite3.Connection) -> float:
    # priorite : portfolio_state.total_value (temps reel)
    try:
        row = c.execute(
            "SELECT total_value FROM portfolio_state ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row and row["total_value"]:
            return float(row["total_value"])
    except Exception:
        pass
    # fallback : portfolio_history.total_value (snapshot end-of-day)
    try:
        row = c.execute(
            "SELECT total_value FROM portfolio_history ORDER BY date DESC, id DESC LIMIT 1"
        ).fetchone()
        if row and row["total_value"]:
            return float(row["total_value"])
    except Exception:
        pass
    return 100000.0


def _get_positions(c: sqlite3.Connection) -> Dict[str, Dict[str, float]]:
    """
    Retourne {ticker : {qty, price}} a partir de portfolio_positions JOIN instruments.
    """
    try:
        rows = c.execute("""
            SELECT i.ticker AS ticker,
                   pp.quantity AS qty,
                   pp.current_price AS price
            FROM portfolio_positions pp
            JOIN instruments i ON i.id = pp.instrument_id
            WHERE pp.quantity IS NOT NULL AND pp.quantity != 0
        """).fetchall()
        return {
            r["ticker"]: {
                "qty": float(r["qty"]),
                "price": float(r["price"] or 0.0),
            }
            for r in rows
        }
    except Exception:
        return {}


def _get_returns_series(
    c: sqlite3.Connection,
    ticker: str,
    window_days: int,
) -> List[Tuple[str, float]]:
    """Returns chronologiques [(date, return_pct)] pour un ticker."""
    try:
        rows = c.execute("""
            SELECT p.date AS date, p.close AS close
            FROM prices p
            JOIN instruments i ON i.id = p.instrument_id
            WHERE i.ticker = ?
            ORDER BY p.date DESC
            LIMIT ?
        """, (ticker, window_days + 1)).fetchall()
    except Exception:
        return []
    if len(rows) < 5:
        return []
    rows = list(reversed(rows))  # ordre chronologique
    out: List[Tuple[str, float]] = []
    for i in range(1, len(rows)):
        p0 = float(rows[i - 1]["close"] or 0)
        p1 = float(rows[i]["close"] or 0)
        if p0 > 0 and p1 > 0:
            out.append((rows[i]["date"], (p1 / p0) - 1.0))
    return out


# --------------------------------------------------------------
# Utilitaires stats
# --------------------------------------------------------------
def _pearson(a: List[float], b: List[float]) -> Optional[float]:
    n = min(len(a), len(b))
    if n < 5:
        return None
    a = a[-n:]
    b = b[-n:]
    ma = sum(a) / n
    mb = sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a))
    sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    if sa == 0 or sb == 0:
        return None
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / (sa * sb)


def _historical_var(returns: List[float], conf: float) -> Optional[float]:
    """VaR historique : abs(quantile (1-conf)). Convention positive."""
    if len(returns) < 10:
        return None
    s = sorted(returns)
    idx = max(0, int(math.floor((1 - conf) * len(s))))
    q = s[idx]
    return abs(q)


# --------------------------------------------------------------
# Controle 1 - Concentration 15%
# --------------------------------------------------------------
def check_concentration(
    c: sqlite3.Connection,
    ticker: str,
    qty: float,
    price: float,
    side: str,
    params: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    positions = _get_positions(c)
    nav = _get_nav(c)
    cur_qty = positions.get(ticker, {}).get("qty", 0.0)
    new_qty = cur_qty + (qty if side.upper() == "BUY" else -qty)
    new_exp = abs(new_qty) * price
    new_pct = new_exp / nav if nav > 0 else 0.0
    cap = params["concentration_max_pct"]
    ok = new_pct <= cap + 1e-9
    return ok, {
        "nav": round(nav, 2),
        "current_qty": round(cur_qty, 4),
        "new_qty": round(new_qty, 4),
        "new_exposure": round(new_exp, 2),
        "new_pct": round(new_pct, 4),
        "cap_pct": cap,
    }


# --------------------------------------------------------------
# Controle 2 - VaR historique 99%/1j budget + delta marginal
# --------------------------------------------------------------
def check_var_marginal(
    c: sqlite3.Connection,
    ticker: str,
    qty: float,
    price: float,
    side: str,
    params: Dict[str, Any],
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    nav = _get_nav(c)
    if nav <= 0:
        return False, "var_budget", {"reason": "nav<=0"}

    win = params["var_window_days"]
    conf = params["var_confidence"]
    budget_pct = params["var_budget_pct_nav"]
    marginal_cap_pct = params["var_marginal_block_pct"]

    positions = _get_positions(c)

    # Returns courants par ticker detenu
    series_map: Dict[str, List[float]] = {}
    for tk, pos in positions.items():
        ret = [r for _, r in _get_returns_series(c, tk, win)]
        if len(ret) >= 10:
            series_map[tk] = ret

    new_sym_ret = [r for _, r in _get_returns_series(c, ticker, win)]
    if len(new_sym_ret) < 10:
        return True, None, {
            "note": "var_skipped_no_returns",
            "symbol_returns": len(new_sym_ret),
            "decision": "PASS_BY_DEFAULT",
        }

    def portfolio_pnl(positions_map: Dict[str, Dict[str, float]]) -> Optional[List[float]]:
        if not positions_map or not series_map:
            return None
        valid = [s for s in series_map.values() if s]
        if not valid:
            return None
        n = min(len(s) for s in valid)
        if n < 10:
            return None
        pnl: List[float] = []
        for i in range(-n, 0):
            day = 0.0
            for tk, pos in positions_map.items():
                if tk not in series_map:
                    continue
                exposure = pos["qty"] * pos["price"]
                day += exposure * series_map[tk][i]
            pnl.append(day)
        return pnl

    cur_pnl = portfolio_pnl(positions) or []
    cur_var = _historical_var(cur_pnl, conf) if cur_pnl else 0.0
    cur_var = cur_var or 0.0
    cur_var_pct = cur_var / nav if nav > 0 else 0.0

    # Simulation post-trade
    sim_positions = dict(positions)
    cur_qty = sim_positions.get(ticker, {}).get("qty", 0.0)
    new_qty = cur_qty + (qty if side.upper() == "BUY" else -qty)
    sim_positions[ticker] = {"qty": new_qty, "price": price}
    series_map[ticker] = new_sym_ret

    sim_pnl = portfolio_pnl(sim_positions) or []
    sim_var = _historical_var(sim_pnl, conf) if sim_pnl else 0.0
    sim_var = sim_var or 0.0
    sim_var_pct = sim_var / nav if nav > 0 else 0.0

    delta_marginal_pct = sim_var_pct - cur_var_pct

    blocked_by: Optional[str] = None
    if sim_var_pct > budget_pct + 1e-9:
        blocked_by = "var_budget"
    elif delta_marginal_pct > marginal_cap_pct + 1e-9:
        blocked_by = "var_marginal"

    return blocked_by is None, blocked_by, {
        "current_var_pct": round(cur_var_pct, 5),
        "simulated_var_pct": round(sim_var_pct, 5),
        "delta_marginal_pct": round(delta_marginal_pct, 5),
        "current_var_eur": round(cur_var, 2),
        "simulated_var_eur": round(sim_var, 2),
        "budget_pct": budget_pct,
        "marginal_cap_pct": marginal_cap_pct,
        "window_days": win,
        "confidence": conf,
        "n_positions_with_returns": len([s for s in series_map.values() if s]),
    }


# --------------------------------------------------------------
# Controle 3 - Correlation Pearson 60j
# --------------------------------------------------------------
def check_correlation(
    c: sqlite3.Connection,
    ticker: str,
    side: str,
    params: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    if side.upper() != "BUY":
        return True, {"note": "skip_sell_side"}

    win = params["correl_window_days"]
    thresh = params["correl_block_threshold"]
    min_overlap = params["correl_min_overlap_days"]

    new_pairs = _get_returns_series(c, ticker, win)
    if len(new_pairs) < min_overlap:
        return True, {
            "note": "correl_skipped_no_returns",
            "symbol_returns": len(new_pairs),
        }
    new_dates = {d: r for d, r in new_pairs}

    positions = _get_positions(c)
    correls: List[Tuple[str, float]] = []
    for tk in positions.keys():
        if tk == ticker:
            continue
        pairs = _get_returns_series(c, tk, win)
        if not pairs:
            continue
        common_dates = sorted(set(d for d, _ in pairs) & set(new_dates.keys()))
        if len(common_dates) < min_overlap:
            continue
        a = [new_dates[d] for d in common_dates]
        sym_map = {d: r for d, r in pairs}
        b = [sym_map[d] for d in common_dates]
        r = _pearson(a, b)
        if r is not None:
            correls.append((tk, r))

    if not correls:
        return True, {"note": "no_peers_with_overlap"}

    max_sym, max_r = max(correls, key=lambda x: abs(x[1]))
    ok = abs(max_r) <= thresh + 1e-9
    return ok, {
        "max_correl_symbol": max_sym,
        "max_correl_value": round(max_r, 4),
        "threshold": thresh,
        "n_peers": len(correls),
        "all_correls": {s: round(r, 4) for s, r in correls},
    }


# --------------------------------------------------------------
# Orchestrateur
# --------------------------------------------------------------


# [NEXTONES-BROKER-CHECK-V1] - import lazy du module broker_check
def _nx_broker_check_load():
    """Charge nextones-risk-broker-check.py si present. Fail-safe : None sinon."""
    try:
        import importlib.util as _ilu
        import os as _os
        _p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                           "nextones-risk-broker-check.py")
        if not _os.path.exists(_p):
            return None
        _spec = _ilu.spec_from_file_location("_nx_broker_check", _p)
        if _spec is None or _spec.loader is None:
            return None
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        return _mod
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] nx_broker_check load: " + str(_e), file=_sys.stderr)
        except Exception:
            pass
        return None


_NX_BROKER_CHECK = None


# [BROKER_CHECK_CONN_FIX_V1] - propage conn= au broker_check pour eviter db lock
def _nx_broker_precheck(ticker, qty, price, side, db_path, conn=None):
    """
    Hook broker_mapping_ok EN PREMIER (Phase 2 - option A1, regle A strict).
    Renvoie:
      - None si broker autorise (le pretrade normal continue)
      - dict format risk_pretrade V2 si broker refuse l'instrument
    """
    global _NX_BROKER_CHECK
    if _NX_BROKER_CHECK is None:
        _NX_BROKER_CHECK = _nx_broker_check_load()
    if _NX_BROKER_CHECK is None:
        # module absent -> on n'interrompt pas la prod, mais on log warning
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] module absent, bypass",
                  file=_sys.stderr)
        except Exception:
            pass
        return None
    try:
        # [BROKER_CHECK_CONN_FIX_V1] - passe conn partagee si dispo
        result = _NX_BROKER_CHECK.check_broker_mapping({
            "thesium_ticker": ticker,
            "side": side,
            "qty": qty,
        }, conn=conn)
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] check error: " + str(_e),
                  file=_sys.stderr)
        except Exception:
            pass
        return None

    if result.get("ok"):
        return None  # broker OK -> on laisse pretrade continuer

        # [BROKER_POLICY_PAPER_V1] Mode degrade paper-trading.
        # ActivTrades ne propose pas ARM, HYPE, ZEC, JNJ, TMO, LIN, GE,
        # GS, JPM, KO, MS, SBUX, UNP, XLB, XLRE, LLY (156 359 USD).
        # A_strict_refuse a genere 87 rejets ARM sans capital engage.
        # En paper on journalise sans bloquer ; en live rien ne change.
        import os as _os_pol
        import sqlite3 as _sql_pol
        _live_pol = str(_os_pol.getenv('LIVE_TRADING', 'false')).lower() in (
            '1', 'true', 'yes', 'on')
        if not _live_pol:
            try:
                _dbp_pol = db_path or _os_pol.environ.get(
                    'THESIUM_DB',
                    _os_pol.path.join(
                        _os_pol.path.dirname(_os_pol.path.abspath(__file__)),
                        'thesium.db'))
                _cp_pol = _sql_pol.connect(_dbp_pol, timeout=10.0)
                _rp_pol = _cp_pol.execute(
                    'SELECT blocks_order FROM broker_policy_config'
                    " WHERE mode='paper' AND active=1").fetchone()
                _cp_pol.close()
                if _rp_pol is not None and int(_rp_pol[0]) == 0:
                    return None  # PAPER_WARN : la simulation continue
            except Exception:
                pass  # fail-safe : on poursuit vers le refus strict


    # Broker refuse : trace dans risk_pretrade_log + retour format V2
    import json as _json
    import sqlite3 as _sql
    import os as _os  # [BROKER_OS_IMPORT_FIX_V4]
    from datetime import datetime as _dt, timezone as _tz
    details = {
        "broker_mapping_ok": {
            "ok": False,
            "reason": result.get("reason"),
            "broker_symbol": result.get("broker_symbol"),
            "volume_lots": result.get("volume_lots"),
            "diagnostics": result.get("diagnostics"),
            "policy": "A_strict_refuse",
        }
    }
    # [BROKER_OS_UNDEFINED_FIX_V3] - _os.environ -> os.environ (os deja importe)
    ts = _dt.now(_tz.utc).isoformat(timespec="seconds")
    try:
        _c = _sql.connect(db_path or _os.environ.get("THESIUM_DB",
                                                     r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"))
        _c.execute(
            "INSERT INTO risk_pretrade_log("
            "  ts, symbol, side, qty, price, passed, blocked_by,"
            "  details_json, marker"
            ") VALUES(?,?,?,?,?,?,?,?,?)",
            (ts, ticker, side, float(qty or 0), float(price or 0), 0,
             "broker_mapping_ok", _json.dumps(details),
             "[NEXTONES-BROKER-CHECK-V1]"),
        )
        _c.commit()
        _c.close()
    except Exception as _e:
        try:
            import sys as _sys
            print("[WARN] [NEXTONES-BROKER-CHECK-V1] log insert: " + str(_e),
                  file=_sys.stderr)
        except Exception:
            pass

    return {
        "passed": 0,
        "blocked_by": "broker_mapping_ok",
        "details_json": _json.dumps(details),
        "marker": "[NEXTONES-BROKER-CHECK-V1]",
    }



# [CONVERGENCE_FORCED_EXIT_BLOCK_V1]
def check_convergence_forced_exit(c, ticker, side):
    """Bloque les BUY sur tickers marques forced_exit=1 dans convergence_snapshots.

    Lit le snapshot le plus recent (par created_at DESC) pour ce ticker.
    Failsafe : si table absente ou requete echoue, retourne (True, details) -> pas de block.

    Returns
    -------
    (ok: bool, details: dict)
        ok=True  -> pas de raison de bloquer (ou failsafe)
        ok=False -> BLOCK (BUY sur ticker en forced_exit)
    """
    details = {"check": "convergence_forced_exit", "ticker": ticker, "side": side}
    try:
        # SELL toujours autorise (on doit pouvoir sortir)
        if str(side).lower() != "buy":
            details["verdict"] = "skip_non_buy"
            return True, details
        row = c.execute(
            "SELECT cycle_id, forced_exit, sizing_multiplier, direction_consensus, created_at "
            "FROM convergence_snapshots "
            "WHERE ticker = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,)
        ).fetchone()
        if row is None:
            details["verdict"] = "no_snapshot"
            return True, details
        # sqlite3.Row -> dict-like
        forced = int(row["forced_exit"] or 0)
        details["snapshot"] = {
            "cycle_id": row["cycle_id"],
            "forced_exit": forced,
            "sizing_multiplier": float(row["sizing_multiplier"] or 0),
            "direction_consensus": row["direction_consensus"],
            "created_at": row["created_at"],
        }
        if forced == 1:
            details["verdict"] = "block_forced_exit"
            return False, details
        details["verdict"] = "pass"
        return True, details
    except Exception as _e:
        # Failsafe : table absente, schema decale, etc. -> ne bloque pas
        details["verdict"] = "failsafe"
        details["error"] = str(_e)[:160]
        return True, details




# ================================================================
# [STOP_LOSS_BLOCK_V1] check_stop_loss
# Bloque BUY si position existante avec PnL <= -8%
# SELL toujours autorise (laisse sortir)
# ================================================================
STOP_LOSS_PCT_THRESHOLD = -8.0

def check_stop_loss(c, ticker, side):
    """Stop-loss bloquant : refuse BUY si position en perte >= 8%.

    Returns (ok: bool, details: dict)
    """
    try:
        if str(side).lower() != "buy":
            return True, {"verdict": "pass", "reason": "sell_skip"}

        row = c.execute(
            """
            SELECT pp.avg_cost, pp.current_price, pp.quantity, pp.unrealized_pnl
            FROM portfolio_positions pp
            JOIN instruments i ON i.id = pp.instrument_id
            WHERE i.ticker = ?
            """,
            (ticker,),
        ).fetchone()

        if not row:
            return True, {"verdict": "pass", "reason": "no_position"}

        avg_cost = float(row[0] or 0.0)
        current_price = float(row[1] or 0.0)
        qty = float(row[2] or 0.0)

        if qty <= 0 or avg_cost <= 0 or current_price <= 0:
            return True, {"verdict": "pass", "reason": "invalid_data"}

        pnl_pct = (current_price - avg_cost) / avg_cost * 100.0

        if pnl_pct <= STOP_LOSS_PCT_THRESHOLD:
            return False, {
                "verdict": "block_stop_loss",
                "reason": "position_loss_exceeds_threshold",
                "pnl_pct": round(pnl_pct, 2),
                "threshold_pct": STOP_LOSS_PCT_THRESHOLD,
                "avg_cost": round(avg_cost, 6),
                "current_price": round(current_price, 6),
                "qty": qty,
            }

        return True, {
            "verdict": "pass",
            "reason": "pnl_above_threshold",
            "pnl_pct": round(pnl_pct, 2),
        }
    except Exception as e:
        # Failsafe : ne pas bloquer en cas d'erreur
        return True, {"verdict": "pass", "reason": "error", "error": str(e)[:200]}
# ================================================================
# [STOP_LOSS_BLOCK_V1] END
# ================================================================

def run_pretrade_checks(
    ticker: str,
    qty: float,
    price: float,
    side: str,
    db_path: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    conn: Optional[sqlite3.Connection] = None,  # [RISK_V2_DBLOCK_FIX_V2] accepte conn existante
) -> Dict[str, Any]:
    # [NEXTONES-BROKER-CHECK-V1] - 5e controle broker_mapping_ok EN PREMIER
    # [BROKER_CHECK_CONN_FIX_V1] - propage conn partagee
    _nx_pre = _nx_broker_precheck(ticker, qty, price, side, db_path, conn=conn)
    if _nx_pre is not None:
        return _nx_pre
    if db_path is None:
        db_path = str(Path(__file__).resolve().parent / "thesium.db")
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)

    # [RISK_V2_DBLOCK_FIX_V2] reutilise la conn existante pour eviter le 2e writer lock
    _own_conn = conn is None
    c = conn if conn is not None else _conn(db_path)
    if conn is not None:
        # [ROW_FACTORY_GUARD_V1] l'appelant peut ne pas avoir configure row_factory
        try:
            c.row_factory = sqlite3.Row
        except Exception:
            pass
    try:
        _ensure_log_table(c)

        # [CONVERGENCE_FORCED_EXIT_BLOCK_V1] - garde-fou convergence/forced_exit AVANT autres checks
        conv_ok, conv_d = check_convergence_forced_exit(c, ticker, side)
        sl_ok, sl_d = check_stop_loss(c, ticker, side)
        conc_ok, conc_d = check_concentration(c, ticker, qty, price, side, p)
        var_ok, var_blocked, var_d = check_var_marginal(c, ticker, qty, price, side, p)
        corr_ok, corr_d = check_correlation(c, ticker, side, p)

        blocked_by: Optional[str] = None
        if not conv_ok:
            blocked_by = "convergence_forced_exit"
        elif not sl_ok:
            blocked_by = "stop_loss"
        elif not conc_ok:
            blocked_by = "concentration"
        elif not var_ok:
            blocked_by = var_blocked or "var"
        elif not corr_ok:
            blocked_by = "correlation"

        passed = blocked_by is None
        details = {
            "convergence_forced_exit": conv_d,  # [CONVERGENCE_FORCED_EXIT_BLOCK_V1]
            "stop_loss": sl_d,
            "concentration": conc_d,
            "var": var_d,
            "correlation": corr_d,
        }

        # Timezone-aware (fix DeprecationWarning utcnow)
        ts = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

        c.execute(
            """
            INSERT INTO risk_pretrade_log
                (ts, symbol, side, qty, price, passed, blocked_by, details_json, marker)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ts,
                ticker,
                side.upper(),
                float(qty),
                float(price),
                1 if passed else 0,
                blocked_by,
                json.dumps(details, ensure_ascii=False),
                MARKER,
            ),
        )
        c.commit()
        return {
            "passed": passed,
            "blocked_by": blocked_by,
            "details": details,
            "marker": MARKER,
        }
    finally:
        if _own_conn:  # [RISK_V2_DBLOCK_FIX_V2] ne ferme pas la conn empruntee
            c.close()


# --------------------------------------------------------------
# Smoke test
# --------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    qty = float(sys.argv[2]) if len(sys.argv) > 2 else 10
    px = float(sys.argv[3]) if len(sys.argv) > 3 else 900.0
    side = sys.argv[4] if len(sys.argv) > 4 else "BUY"
    res = run_pretrade_checks(sym, qty, px, side)
    print(json.dumps(res, indent=2, ensure_ascii=False))
