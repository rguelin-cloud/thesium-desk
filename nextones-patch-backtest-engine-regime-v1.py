"""
[PATCH_BACKTEST_ENGINE_REGIME_V1]
Etend run_backtest() de backtest_engine.py avec un mode "regime-aware".

Quand apply_regime=True :
  - Calcule un mini-regime equity (VIX SPY proxy + vol realisee 20j + drawdown 5j)
    et crypto (vol 20j + drawdown 5j) pour chaque date du backtest.
  - Applique un exposure tilt : equity_weight_t *= equity_buy_mult,
    crypto_weight_t *= crypto_buy_mult. Cash residuel place a Rf=4.5%/an.
  - Genere portfolio_equity_regime, stats_regime, regime_timeline,
    regime_summary (calm_days / normal_days / stress_days, delta sharpe, delta dd).

Ce patch :
  - Backup .py.bak.<timestamp>
  - Idempotent (skip si [PATCH_BACKTEST_ENGINE_REGIME_V1] deja present)
  - Read utf-8-sig / Write utf-8 sans BOM
  - Validation ast.parse + py_compile avant ecriture
  - INJECTE du code ASCII pur dans le fichier hote
"""
import io
import os
import sys
import re
import ast
import py_compile
import shutil
import datetime

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "backtest_engine.py")
MARKER = "[PATCH_BACKTEST_ENGINE_REGIME_V1]"


def read_utf8_sig(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="strict") as f:
        return f.read()


def write_utf8_no_bom(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def assert_ascii(snippet, label):
    bad = [(i, b) for i, b in enumerate(snippet.encode("utf-8")) if b > 127]
    if bad:
        raise RuntimeError(
            "Snippet %s contient %d bytes non-ASCII (premier @ offset %d byte=%d)"
            % (label, len(bad), bad[0][0], bad[0][1])
        )


def main():
    print("=" * 70)
    print("PATCH backtest_engine.py - REGIME V1")
    print("=" * 70)

    if not os.path.exists(TARGET):
        print("[FAIL] introuvable: " + TARGET)
        sys.exit(1)

    src = read_utf8_sig(TARGET)
    if MARKER in src:
        print("[SKIP] marker deja present " + MARKER)
        return

    # ---- BACKUP ----
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP] " + bak)

    lines = src.splitlines(keepends=False)

    # ---- 1) Modifier signature de run_backtest pour ajouter apply_regime ----
    sig_open_idx = None
    sig_close_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("def run_backtest("):
            sig_open_idx = i
            break
    if sig_open_idx is None:
        print("[FAIL] def run_backtest introuvable")
        sys.exit(2)

    for j in range(sig_open_idx, min(sig_open_idx + 15, len(lines))):
        if ") -> dict:" in lines[j] or ")->dict:" in lines[j]:
            sig_close_idx = j
            break
    if sig_close_idx is None:
        print("[FAIL] fermeture signature run_backtest introuvable")
        sys.exit(3)

    # Inserer une nouvelle ligne de param "    apply_regime: bool = False,"
    # juste AVANT la ligne de fermeture ") -> dict:"
    new_param_line = "    apply_regime: bool = False,"
    lines.insert(sig_close_idx, new_param_line)
    print("[INJECT] param apply_regime ajoute a la signature (L%d)" % (sig_close_idx + 1))

    # ---- 2) Trouver la ligne juste avant le return final pour injecter le bloc regime ----
    # On veut inserer apres "stats = _compute_stats(port_returns, initial_capital, port_equity)"
    # et AVANT le return {...}.
    return_idx = None
    stats_idx = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith("stats = _compute_stats(port_returns"):
            stats_idx = i
        if ln.strip().startswith("return {") and stats_idx is not None and i > stats_idx:
            return_idx = i
            break
    if return_idx is None or stats_idx is None:
        print("[FAIL] points d'injection introuvables (stats=%s, return=%s)" % (stats_idx, return_idx))
        sys.exit(4)

    # ---- 3) Bloc a injecter : calcul regime + equity_regime + stats_regime + timeline ----
    block = [
        "",
        "    # " + MARKER + " - regime-aware overlay",
        "    regime_overlay = None",
        "    if apply_regime:",
        "        regime_overlay = _compute_regime_overlay(",
        "            dates=dates,",
        "            price_maps=price_maps,",
        "            asset_classes=asset_classes,",
        "            available=available,",
        "            avail_weights=avail_weights,",
        "            daily_returns=daily_returns,",
        "            initial_capital=initial_capital,",
        "            benchmark=benchmark,",
        "        )",
        "",
    ]
    for k, ln in enumerate(block):
        lines.insert(return_idx + k, ln)
    return_idx += len(block)
    print("[INJECT] bloc regime_overlay avant le return (L%d)" % (return_idx + 1))

    # ---- 4) Etendre le dict retourne avec les cles regime ----
    # Trouver la fermeture du return { ... } : c'est la prochaine ligne "}" seule.
    close_idx = None
    for i in range(return_idx, len(lines)):
        s = lines[i].strip()
        if s == "}":
            close_idx = i
            break
    if close_idx is None:
        print("[FAIL] fermeture du return dict introuvable")
        sys.exit(5)

    extra = [
        "        # " + MARKER,
        "        \"portfolio_equity_regime\": regime_overlay[\"equity\"] if regime_overlay else None,",
        "        \"stats_regime\": regime_overlay[\"stats\"] if regime_overlay else None,",
        "        \"regime_timeline\": regime_overlay[\"timeline\"] if regime_overlay else None,",
        "        \"regime_summary\": regime_overlay[\"summary\"] if regime_overlay else None,",
        "        \"apply_regime\": bool(apply_regime),",
    ]
    for k, ln in enumerate(extra):
        lines.insert(close_idx + k, ln)
    print("[INJECT] 5 cles regime dans return dict (avant L%d)" % (close_idx + 1))

    # ---- 5) Helper _compute_regime_overlay a la fin du fichier ----
    helper = [
        "",
        "",
        "# " + MARKER,
        "def _compute_regime_overlay(",
        "    dates,",
        "    price_maps,",
        "    asset_classes,",
        "    available,",
        "    avail_weights,",
        "    daily_returns,",
        "    initial_capital,",
        "    benchmark,",
        "):",
        "    \"\"\"Compute regime-aware equity curve overlay.",
        "",
        "    Rules (proxy of detect_market_regime in production):",
        "      Equity regime per day t based on rolling SPY (or first equity available):",
        "        - realized vol annualized over last 20d",
        "        - drawdown over last 5d (% from rolling peak)",
        "        - VIX proxy = max(20d realized vol, 15.0)  # synthetic when no FRED",
        "      Score:",
        "        - vol >= 25% -> stress signal, vol <= 15% -> calm signal",
        "        - dd <= -5% -> stress, dd >= -2% -> calm",
        "        - vix proxy >= 25 -> stress, <= 15 -> calm",
        "      Regime = STRESS if n_stress >= 2, CALM if n_calm >= 2, else NORMAL",
        "",
        "    Crypto regime per day t based on first crypto ticker available:",
        "      vol 20d (annualized), drawdown 5d. Same thresholds but vol 30%/20%.",
        "",
        "    Multipliers (must match production market_regime_v1):",
        "        equity:  CALM buy=0.7 sell=1.5 | NORMAL 1.0/1.0 | STRESS buy=1.8 sell=0.5",
        "        crypto:  CALM buy=0.7 sell=1.5 | NORMAL 1.0/1.0 | STRESS buy=1.8 sell=0.5",
        "    Exposure tilt: each ticker weight is multiplied by buy_mult of its regime,",
        "    capped at the base weight (no leverage in backtest), residual goes to cash@Rf.",
        "    \"\"\"",
        "    import math",
        "",
        "    MULTS = {",
        "        'CALM':   {'buy': 0.7, 'sell': 1.5},",
        "        'NORMAL': {'buy': 1.0, 'sell': 1.0},",
        "        'STRESS': {'buy': 1.8, 'sell': 0.5},",
        "    }",
        "    RF_DAILY = (1.0 + 0.045) ** (1.0 / 252.0) - 1.0",
        "",
        "    # Pick a proxy ticker for equity regime: prefer SPY benchmark, else first equity",
        "    spy_key = '__bench_' + benchmark",
        "    equity_proxy = None",
        "    if spy_key in price_maps:",
        "        equity_proxy = spy_key",
        "    else:",
        "        for t in available:",
        "            ac = asset_classes.get(t, 'equity')",
        "            if ac in ('equity', 'etf'):",
        "                equity_proxy = t",
        "                break",
        "",
        "    # Pick a proxy ticker for crypto regime: first crypto",
        "    crypto_proxy = None",
        "    for t in available:",
        "        if asset_classes.get(t, 'equity') == 'crypto':",
        "            crypto_proxy = t",
        "            break",
        "",
        "    def _classify(vol_pct, dd_pct, vix_proxy, asset_class):",
        "        if asset_class == 'crypto':",
        "            vol_stress, vol_calm = 30.0, 20.0",
        "            dd_stress, dd_calm = -8.0, -3.0",
        "        else:",
        "            vol_stress, vol_calm = 25.0, 15.0",
        "            dd_stress, dd_calm = -5.0, -2.0",
        "        n_stress = 0",
        "        n_calm = 0",
        "        if vol_pct is not None:",
        "            if vol_pct >= vol_stress: n_stress += 1",
        "            elif vol_pct <= vol_calm: n_calm += 1",
        "        if dd_pct is not None:",
        "            if dd_pct <= dd_stress: n_stress += 1",
        "            elif dd_pct >= dd_calm: n_calm += 1",
        "        if asset_class != 'crypto' and vix_proxy is not None:",
        "            if vix_proxy >= 25.0: n_stress += 1",
        "            elif vix_proxy <= 15.0: n_calm += 1",
        "        if n_stress >= 2: return 'STRESS'",
        "        if n_calm >= 2: return 'CALM'",
        "        return 'NORMAL'",
        "",
        "    def _rolling_metrics(prices_list, lookback_vol=20, lookback_dd=5):",
        "        # prices_list = [p_t-N, ..., p_t]",
        "        if len(prices_list) < 2:",
        "            return None, None",
        "        rets = []",
        "        n = len(prices_list)",
        "        start = max(0, n - lookback_vol - 1)",
        "        sub = prices_list[start:]",
        "        for i in range(1, len(sub)):",
        "            prev = sub[i - 1]",
        "            curr = sub[i]",
        "            if prev > 0:",
        "                rets.append((curr - prev) / prev)",
        "        if not rets:",
        "            return None, None",
        "        mean = sum(rets) / len(rets)",
        "        var = sum((r - mean) ** 2 for r in rets) / len(rets)",
        "        vol_daily = math.sqrt(var)",
        "        vol_ann = vol_daily * math.sqrt(252) * 100.0",
        "        # drawdown over lookback_dd from peak",
        "        dd_window = prices_list[-min(lookback_dd + 1, len(prices_list)):]",
        "        peak = max(dd_window)",
        "        last = dd_window[-1]",
        "        dd = ((last - peak) / peak) * 100.0 if peak > 0 else 0.0",
        "        return vol_ann, dd",
        "",
        "    # Pre-extract proxy price series",
        "    eq_prices = []",
        "    cr_prices = []",
        "    if equity_proxy:",
        "        for d in dates:",
        "            eq_prices.append(price_maps[equity_proxy][d])",
        "    if crypto_proxy:",
        "        for d in dates:",
        "            cr_prices.append(price_maps[crypto_proxy][d])",
        "",
        "    timeline = []",
        "    eq_regimes = []  # per-day regime classification (equity)",
        "    cr_regimes = []  # per-day regime classification (crypto)",
        "    # Need at least 21 days of history for vol_20; before that, default NORMAL",
        "    for i, d in enumerate(dates):",
        "        if equity_proxy and i >= 21:",
        "            vol_e, dd_e = _rolling_metrics(eq_prices[:i + 1], 20, 5)",
        "            vix_proxy = max(vol_e, 15.0) if vol_e is not None else None",
        "            eq_reg = _classify(vol_e, dd_e, vix_proxy, 'equity')",
        "        else:",
        "            vol_e, dd_e, vix_proxy = None, None, None",
        "            eq_reg = 'NORMAL'",
        "        if crypto_proxy and i >= 21:",
        "            vol_c, dd_c = _rolling_metrics(cr_prices[:i + 1], 20, 5)",
        "            cr_reg = _classify(vol_c, dd_c, None, 'crypto')",
        "        else:",
        "            vol_c, dd_c = None, None",
        "            cr_reg = 'NORMAL'",
        "        eq_regimes.append(eq_reg)",
        "        cr_regimes.append(cr_reg)",
        "        timeline.append({",
        "            'date': d,",
        "            'equity_regime': eq_reg,",
        "            'crypto_regime': cr_reg,",
        "            'equity_vol_pct': round(vol_e, 2) if vol_e is not None else None,",
        "            'equity_dd_pct': round(dd_e, 2) if dd_e is not None else None,",
        "            'equity_vix_proxy': round(vix_proxy, 2) if vix_proxy is not None else None,",
        "            'crypto_vol_pct': round(vol_c, 2) if vol_c is not None else None,",
        "            'crypto_dd_pct': round(dd_c, 2) if dd_c is not None else None,",
        "        })",
        "",
        "    # Build regime-tilted equity curve",
        "    # exposure_eq_t = sum(base_weight[t]) for equity tickers * eq_buy_mult, capped at base",
        "    # exposure_cr_t idem crypto, residual to cash @ RF_DAILY",
        "    base_eq_w = sum(avail_weights[t] for t in available if asset_classes.get(t, 'equity') in ('equity', 'etf'))",
        "    base_cr_w = sum(avail_weights[t] for t in available if asset_classes.get(t, 'equity') == 'crypto')",
        "",
        "    # Pre-compute per-bucket daily portfolio returns",
        "    eq_tickers = [t for t in available if asset_classes.get(t, 'equity') in ('equity', 'etf')]",
        "    cr_tickers = [t for t in available if asset_classes.get(t, 'equity') == 'crypto']",
        "",
        "    eq_w_norm = {t: (avail_weights[t] / base_eq_w) if base_eq_w > 0 else 0.0 for t in eq_tickers}",
        "    cr_w_norm = {t: (avail_weights[t] / base_cr_w) if base_cr_w > 0 else 0.0 for t in cr_tickers}",
        "",
        "    # daily_returns[t] has len = len(dates) - 1, index i = return between dates[i] and dates[i+1]",
        "    eq_bucket_ret = []  # equity bucket pure return at day i+1",
        "    cr_bucket_ret = []",
        "    for i in range(len(dates) - 1):",
        "        eq_r = sum(eq_w_norm[t] * daily_returns[t][i] for t in eq_tickers) if eq_tickers else 0.0",
        "        cr_r = sum(cr_w_norm[t] * daily_returns[t][i] for t in cr_tickers) if cr_tickers else 0.0",
        "        eq_bucket_ret.append(eq_r)",
        "        cr_bucket_ret.append(cr_r)",
        "",
        "    # Build equity curve regime: apply exposure tilt using PREVIOUS day regime (no look-ahead)",
        "    port_equity_regime = [{'date': dates[0], 'value': initial_capital}]",
        "    port_returns_regime = []",
        "    value = initial_capital",
        "    trades_avoided = 0  # cumul of |delta_exposure| / day where mult != 1",
        "    take_profits = 0",
        "    for i in range(len(dates) - 1):",
        "        # Use regime at day i (prior to return between i and i+1)",
        "        eq_reg = eq_regimes[i]",
        "        cr_reg = cr_regimes[i]",
        "        eq_mult = MULTS[eq_reg]['buy']",
        "        cr_mult = MULTS[cr_reg]['buy']",
        "        # Cap mult at 1.0 (no leverage in backtest)",
        "        eq_expo = min(base_eq_w * eq_mult, base_eq_w + (1.0 - base_eq_w - base_cr_w))  # cap at 1.0 total",
        "        cr_expo = min(base_cr_w * cr_mult, base_cr_w + (1.0 - base_eq_w - base_cr_w))",
        "        if eq_expo + cr_expo > 1.0:",
        "            scale = 1.0 / (eq_expo + cr_expo)",
        "            eq_expo *= scale",
        "            cr_expo *= scale",
        "        cash_expo = max(0.0, 1.0 - eq_expo - cr_expo)",
        "        day_r = eq_expo * eq_bucket_ret[i] + cr_expo * cr_bucket_ret[i] + cash_expo * RF_DAILY",
        "        port_returns_regime.append(day_r)",
        "        value *= (1.0 + day_r)",
        "        port_equity_regime.append({'date': dates[i + 1], 'value': round(value, 2)})",
        "        # Count actions",
        "        if eq_reg == 'CALM' or cr_reg == 'CALM':",
        "            take_profits += 1",
        "        if eq_reg == 'STRESS' or cr_reg == 'STRESS':",
        "            trades_avoided += 1",
        "",
        "    stats_regime = _compute_stats(port_returns_regime, initial_capital, port_equity_regime)",
        "",
        "    # Summary",
        "    eq_counts = {'CALM': 0, 'NORMAL': 0, 'STRESS': 0}",
        "    cr_counts = {'CALM': 0, 'NORMAL': 0, 'STRESS': 0}",
        "    for r in eq_regimes:",
        "        eq_counts[r] = eq_counts.get(r, 0) + 1",
        "    for r in cr_regimes:",
        "        cr_counts[r] = cr_counts.get(r, 0) + 1",
        "",
        "    summary = {",
        "        'equity': {",
        "            'calm_days': eq_counts['CALM'],",
        "            'normal_days': eq_counts['NORMAL'],",
        "            'stress_days': eq_counts['STRESS'],",
        "        },",
        "        'crypto': {",
        "            'calm_days': cr_counts['CALM'],",
        "            'normal_days': cr_counts['NORMAL'],",
        "            'stress_days': cr_counts['STRESS'],",
        "        },",
        "        'trades_avoided_days': trades_avoided,",
        "        'take_profits_days': take_profits,",
        "        'base_equity_weight_pct': round(base_eq_w * 100, 2),",
        "        'base_crypto_weight_pct': round(base_cr_w * 100, 2),",
        "    }",
        "",
        "    return {",
        "        'equity': port_equity_regime,",
        "        'stats': stats_regime,",
        "        'timeline': timeline,",
        "        'summary': summary,",
        "    }",
        "",
    ]
    # Validation ASCII du snippet entier injecte
    snippet_full = "\n".join(block + extra + helper)
    assert_ascii(snippet_full, "regime_overlay block")

    # Append helper at end of file
    lines.extend(helper)
    print("[INJECT] helper _compute_regime_overlay ajoute en fin de fichier")

    new_src = "\n".join(lines) + "\n"

    # ---- VALIDATION ----
    try:
        ast.parse(new_src)
        print("[VALIDATE] ast.parse OK")
    except SyntaxError as e:
        print("[FAIL] ast.parse: %s" % e)
        sys.exit(10)

    # Write temp file then py_compile
    tmp = TARGET + ".tmp"
    write_utf8_no_bom(tmp, new_src)
    try:
        py_compile.compile(tmp, doraise=True)
        print("[VALIDATE] py_compile OK")
    except py_compile.PyCompileError as e:
        print("[FAIL] py_compile: %s" % e)
        os.remove(tmp)
        sys.exit(11)

    os.replace(tmp, TARGET)
    print("[WRITE] %s (lignes: %d)" % (TARGET, len(lines)))
    print("[OK] " + MARKER)


if __name__ == "__main__":
    main()
