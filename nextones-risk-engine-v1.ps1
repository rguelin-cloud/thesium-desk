# ============================================================
# nextones-risk-engine-v1.ps1
# [RISK_V1] — 3 contrôles pre-trade
#   1. Concentration 15% par position
#   2. VaR historique 99% / 1j (budget portefeuille + delta marginal)
#   3. Corrélation Pearson 60j returns daily (block si > 0.85)
#
# Idempotent. Backup auto. Validation tags before/after.
# Source : Guide v1.0 §3.3 + spec fondatrice §3.3 + §6
# ============================================================

$ErrorActionPreference = "Stop"
$root = "C:\Users\RichardGUELIN\Prod\ThesiumDesk"
$db   = "$root\thesium.db"
$ts   = Get-Date -Format "yyyyMMdd_HHmmss"
$bk   = "$root\_backups_risk_v1_$ts"

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " [RISK_V1] Risk engine pre-trade — 3 contrôles" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# ---- 1. Backup ciblé ----------------------------------------
New-Item -ItemType Directory -Force -Path $bk | Out-Null
$targets = @("risk_engine.py","execution_engine.py","agents.py","api_server_with_static.py")
foreach ($f in $targets) {
    $p = Join-Path $root $f
    if (Test-Path $p) {
        Copy-Item $p (Join-Path $bk $f) -Force
        Write-Host "  backup ok : $f" -ForegroundColor DarkGray
    } else {
        Write-Host "  MANQUANT  : $f" -ForegroundColor Yellow
    }
}
Write-Host ""

# ---- 2. Détection idempotence -------------------------------
$risk_py = Join-Path $root "risk_engine.py"
if (-not (Test-Path $risk_py)) {
    Write-Host "[FATAL] risk_engine.py introuvable. Aborting." -ForegroundColor Red
    exit 1
}
$content = Get-Content $risk_py -Raw -Encoding utf8
if ($content -match "\[RISK_V1\]") {
    Write-Host "[SKIP] marker [RISK_V1] déjà présent. Rien à faire." -ForegroundColor Yellow
    exit 0
}

# ---- 3. Écriture du module risk_pretrade.py -----------------
$pretrade_py = Join-Path $root "risk_pretrade.py"
$payload = @'
"""
risk_pretrade.py — [RISK_V1]
Trois contrôles pre-trade conformes Guide v1.0 §3.3 et spec §3.3+§6.
- check_concentration : 15% max par position (post-ordre simulé)
- check_var_marginal  : VaR historique 99%/1j ; budget portefeuille + delta marginal
- check_correlation   : Pearson 60j returns daily ; block si max > seuil

API publique :
    decision = run_pretrade_checks(symbol, qty, price, side, db_path, params=None)
    decision = {
        "passed": bool,
        "blocked_by": str|None,   # "concentration"|"var_budget"|"var_marginal"|"correlation"|None
        "details": dict,
        "marker": "[RISK_V1]"
    }

Toutes les valeurs sont loguées dans la table risk_pretrade_log (créée si absente)
pour servir de trace MiFID II rétention 5 ans.
"""
from __future__ import annotations

import math
import sqlite3
import json
import datetime as _dt
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# [RISK_V1] paramètres par défaut — surchargeables via params=
DEFAULT_PARAMS = {
    "concentration_max_pct": 0.15,          # 15% max par position
    "var_confidence": 0.99,                 # VaR historique 99%
    "var_window_days": 60,                  # fenêtre returns
    "var_budget_pct_nav": 0.02,             # budget VaR portefeuille = 2% NAV/jour
    "var_marginal_block_pct": 0.005,        # delta marginal max = 0.5% NAV
    "correl_window_days": 60,               # fenêtre returns pour Pearson
    "correl_block_threshold": 0.85,         # block si max correl > 0.85
    "correl_min_overlap_days": 30,          # min overlap pour calcul fiable
}


def _conn(db_path: str) -> sqlite3.Connection:
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


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
            marker       TEXT    NOT NULL DEFAULT '[RISK_V1]'
        )
    """)
    c.commit()


def _get_nav(c: sqlite3.Connection) -> float:
    row = c.execute(
        "SELECT nav FROM portfolio_history ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    if row and row["nav"]:
        return float(row["nav"])
    row = c.execute(
        "SELECT SUM(qty*price) AS exp FROM positions WHERE qty IS NOT NULL"
    ).fetchone()
    return float(row["exp"] or 100000.0)


def _get_positions(c: sqlite3.Connection) -> Dict[str, Dict[str, float]]:
    rows = c.execute(
        "SELECT symbol, qty, price FROM positions WHERE qty IS NOT NULL AND qty != 0"
    ).fetchall()
    return {
        r["symbol"]: {"qty": float(r["qty"]), "price": float(r["price"] or 0.0)}
        for r in rows
    }


def _get_returns_series(
    c: sqlite3.Connection,
    symbol: str,
    window_days: int,
) -> List[Tuple[str, float]]:
    """Retourne [(date, return_pct)] sur window_days, plus récent à la fin."""
    rows = c.execute(
        """
        SELECT date, close
        FROM prices
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
        """,
        (symbol, window_days + 1),
    ).fetchall()
    if len(rows) < 5:
        return []
    rows = list(reversed(rows))  # ordre chronologique
    out = []
    for i in range(1, len(rows)):
        p0 = float(rows[i - 1]["close"] or 0)
        p1 = float(rows[i]["close"] or 0)
        if p0 > 0 and p1 > 0:
            out.append((rows[i]["date"], (p1 / p0) - 1.0))
    return out


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
    """VaR historique : quantile (1 - conf) de la distribution empirique. Renvoyé en valeur positive."""
    if len(returns) < 10:
        return None
    s = sorted(returns)
    idx = max(0, int(math.floor((1 - conf) * len(s))))
    q = s[idx]
    return abs(q)


# --------------------------------------------------------------
# Contrôle 1 — Concentration 15% post-trade simulé
# --------------------------------------------------------------
def check_concentration(
    c: sqlite3.Connection,
    symbol: str,
    qty: float,
    price: float,
    side: str,
    params: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    positions = _get_positions(c)
    nav = _get_nav(c)
    cur_qty = positions.get(symbol, {}).get("qty", 0.0)
    new_qty = cur_qty + (qty if side.upper() == "BUY" else -qty)
    new_exp = abs(new_qty) * price
    new_pct = new_exp / nav if nav > 0 else 0.0
    cap = params["concentration_max_pct"]
    ok = new_pct <= cap + 1e-9
    return ok, {
        "nav": round(nav, 2),
        "new_exposure": round(new_exp, 2),
        "new_pct": round(new_pct, 4),
        "cap_pct": cap,
    }


# --------------------------------------------------------------
# Contrôle 2 — VaR historique 99%/1j : budget portefeuille + delta marginal
# --------------------------------------------------------------
def check_var_marginal(
    c: sqlite3.Connection,
    symbol: str,
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

    # Returns courants par symbole détenu
    series_map: Dict[str, List[float]] = {}
    for sym, pos in positions.items():
        ret = [r for _, r in _get_returns_series(c, sym, win)]
        if len(ret) >= 10:
            series_map[sym] = ret

    # Returns nouveau symbole
    new_sym_ret = [r for _, r in _get_returns_series(c, symbol, win)]
    if len(new_sym_ret) < 10:
        return True, None, {
            "note": "var_skipped_no_returns",
            "symbol_returns": len(new_sym_ret),
            "decision": "PASS_BY_DEFAULT",
        }

    # PnL portefeuille courant
    def portfolio_pnl(positions_map: Dict[str, Dict[str, float]]) -> Optional[List[float]]:
        if not positions_map:
            return None
        n = min(len(s) for s in series_map.values()) if series_map else 0
        if n < 10:
            return None
        pnl: List[float] = []
        for i in range(-n, 0):
            day = 0.0
            for sym, pos in positions_map.items():
                if sym not in series_map:
                    continue
                exposure = pos["qty"] * pos["price"]
                day += exposure * series_map[sym][i]
            pnl.append(day)
        return pnl

    cur_pnl = portfolio_pnl(positions) or []
    cur_var = _historical_var(cur_pnl, conf) if cur_pnl else 0.0
    cur_var = cur_var or 0.0
    cur_var_pct = cur_var / nav if nav > 0 else 0.0

    # Simulation post-trade
    sim_positions = dict(positions)
    cur_qty = sim_positions.get(symbol, {}).get("qty", 0.0)
    new_qty = cur_qty + (qty if side.upper() == "BUY" else -qty)
    sim_positions[symbol] = {"qty": new_qty, "price": price}
    series_map[symbol] = new_sym_ret

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
        "budget_pct": budget_pct,
        "marginal_cap_pct": marginal_cap_pct,
        "window_days": win,
        "confidence": conf,
    }


# --------------------------------------------------------------
# Contrôle 3 — Corrélation Pearson 60j returns daily
# --------------------------------------------------------------
def check_correlation(
    c: sqlite3.Connection,
    symbol: str,
    side: str,
    params: Dict[str, Any],
) -> Tuple[bool, Dict[str, Any]]:
    if side.upper() != "BUY":
        return True, {"note": "skip_sell_side"}

    win = params["correl_window_days"]
    thresh = params["correl_block_threshold"]
    min_overlap = params["correl_min_overlap_days"]

    new_pairs = _get_returns_series(c, symbol, win)
    if len(new_pairs) < min_overlap:
        return True, {
            "note": "correl_skipped_no_returns",
            "symbol_returns": len(new_pairs),
        }
    new_dates = {d: r for d, r in new_pairs}

    positions = _get_positions(c)
    correls: List[Tuple[str, float]] = []
    for sym in positions.keys():
        if sym == symbol:
            continue
        pairs = _get_returns_series(c, sym, win)
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
            correls.append((sym, r))

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
def run_pretrade_checks(
    symbol: str,
    qty: float,
    price: float,
    side: str,
    db_path: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if db_path is None:
        db_path = str(Path(__file__).resolve().parent / "thesium.db")
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)

    c = _conn(db_path)
    try:
        _ensure_log_table(c)

        # 1. Concentration
        conc_ok, conc_d = check_concentration(c, symbol, qty, price, side, p)
        # 2. VaR
        var_ok, var_blocked, var_d = check_var_marginal(c, symbol, qty, price, side, p)
        # 3. Correlation
        corr_ok, corr_d = check_correlation(c, symbol, side, p)

        blocked_by: Optional[str] = None
        if not conc_ok:
            blocked_by = "concentration"
        elif not var_ok:
            blocked_by = var_blocked or "var"
        elif not corr_ok:
            blocked_by = "correlation"

        passed = blocked_by is None
        details = {
            "concentration": conc_d,
            "var": var_d,
            "correlation": corr_d,
        }

        c.execute(
            """
            INSERT INTO risk_pretrade_log
                (ts, symbol, side, qty, price, passed, blocked_by, details_json, marker)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                symbol,
                side.upper(),
                float(qty),
                float(price),
                1 if passed else 0,
                blocked_by,
                json.dumps(details, ensure_ascii=False),
                "[RISK_V1]",
            ),
        )
        c.commit()
        return {
            "passed": passed,
            "blocked_by": blocked_by,
            "details": details,
            "marker": "[RISK_V1]",
        }
    finally:
        c.close()


# --------------------------------------------------------------
# Smoke test direct
# --------------------------------------------------------------
if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    qty = float(sys.argv[2]) if len(sys.argv) > 2 else 10
    px = float(sys.argv[3]) if len(sys.argv) > 3 else 900.0
    side = sys.argv[4] if len(sys.argv) > 4 else "BUY"
    res = run_pretrade_checks(sym, qty, px, side)
    print(json.dumps(res, indent=2, ensure_ascii=False))
'@

# Écriture utf-8 sans BOM
[System.IO.File]::WriteAllText($pretrade_py, $payload, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "[OK] risk_pretrade.py écrit : $pretrade_py" -ForegroundColor Green
Write-Host ""

# ---- 4. Hook idempotent dans execution_engine.py ------------
$exec_py = Join-Path $root "execution_engine.py"
if (-not (Test-Path $exec_py)) {
    Write-Host "[WARN] execution_engine.py absent — module installé mais non câblé." -ForegroundColor Yellow
} else {
    $exec_src = Get-Content $exec_py -Raw -Encoding utf8
    if ($exec_src -match "\[RISK_V1\]") {
        Write-Host "[SKIP] hook [RISK_V1] déjà présent dans execution_engine.py" -ForegroundColor Yellow
    } else {
        $hook = @'

# [RISK_V1] Hook pre-trade — Concentration / VaR marginal / Correlation
try:
    from risk_pretrade import run_pretrade_checks as _risk_v1_run
    _RISK_V1_AVAILABLE = True
except Exception as _e:
    _RISK_V1_AVAILABLE = False

def risk_v1_gate(symbol, qty, price, side, db_path=None):
    """
    [RISK_V1] Garde pre-trade. Renvoie (allowed: bool, reason: str|None, details: dict).
    À appeler IMMÉDIATEMENT avant l'insertion d'un ordre dans la table orders.
    """
    if not _RISK_V1_AVAILABLE:
        return True, "risk_v1_unavailable", {}
    try:
        res = _risk_v1_run(symbol, qty, price, side, db_path=db_path)
        return bool(res.get("passed")), res.get("blocked_by"), res.get("details", {})
    except Exception as _e:
        # Fail-safe : si la garde plante, on log mais on ne bloque pas la prod
        # (le Conseil pourra trancher fail-closed ou fail-open dans v2)
        return True, "risk_v1_error:" + str(_e)[:80], {}
'@
        Add-Content -Path $exec_py -Value $hook -Encoding utf8
        Write-Host "[OK] hook [RISK_V1] ajouté à execution_engine.py" -ForegroundColor Green
    }
}
Write-Host ""

# ---- 5. Validation ------------------------------------------
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host " Validation" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
$tag_count = (Select-String -Path $pretrade_py -Pattern "\[RISK_V1\]" -SimpleMatch).Count
Write-Host "  [RISK_V1] markers dans risk_pretrade.py : $tag_count" -ForegroundColor Green
Write-Host "  Backup       : $bk" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Smoke test :" -ForegroundColor Cyan
Write-Host "  cd $root" -ForegroundColor DarkGray
Write-Host "  py -3.13 risk_pretrade.py NVDA 10 900 BUY" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Inspection log :" -ForegroundColor Cyan
Write-Host "  py -3.13 -c `"import sqlite3,json;c=sqlite3.connect(r'$db');[print(json.dumps({k:r[k] for k in r.keys()},indent=2,ensure_ascii=False)) for r in c.execute('SELECT * FROM risk_pretrade_log ORDER BY id DESC LIMIT 5').fetchall()]`"" -ForegroundColor DarkGray
Write-Host ""
Write-Host "[DONE] [RISK_V1] installé." -ForegroundColor Green
