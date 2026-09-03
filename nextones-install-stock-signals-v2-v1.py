"""
Install : Stock Signals V2 - calcul maison RSI/SMA/Perf depuis table prices.

Remplace fetch_stock_signals() dans data_finviz.py qui casse depuis Finviz HTML rewrite.
Backend calcule tout depuis la table `prices` locale + sector via instruments.

Livrables :
1. Cree /home/user/workspace/signals_calculator.py -> a copier vers ThesiumDesk
   (Ce script installe la version ThesiumDesk directement)
2. Patch data_finviz.py : ajoute fetch_stock_signals_v2() apres fetch_stock_signals()
3. Bascule fetch_stock_signals() -> alias vers V2 (compat UI/endpoint intacte)
4. Marker # [STOCK_SIGNALS_V2] pour idempotence
5. Test runtime AAPL apres patch : doit retourner un dict avec RSI/SMA/... peuples
"""
import os
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
F_DATA = os.path.join(ROOT, "data_finviz.py")
F_CALC = os.path.join(ROOT, "signals_calculator.py")
MARK = "# [STOCK_SIGNALS_V2]"
TS = time.strftime("%Y%m%d_%H%M%S")


# =============================================================================
# CONTENU 1 : signals_calculator.py (nouveau module)
# =============================================================================

CALC_MODULE = '''"""
signals_calculator.py - Stock signals calcul maison depuis table prices.

Remplace finvizfinance.ticker_fundament() qui ne fonctionne plus depuis
Finviz HTML rewrite (T1 2026 approximatif).

Chaque fonction retourne None si donnees insuffisantes (pas de crash).
Toutes les fonctions attendent une liste de (date_str, close, volume) triee
par date croissante (le plus recent en dernier).
'''.lstrip() + f'''
Marker : {MARK}
"""
import sqlite3
import os
from datetime import datetime, timedelta

_DB = os.environ.get("THESIUM_DB", r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db")


def _get_prices(conn, ticker, days=250):
    """Retourne [(date, open, high, low, close, volume), ...] tries ASC. Vide si ticker inconnu."""
    row = conn.execute("SELECT id FROM instruments WHERE ticker = ?", (ticker,)).fetchone()
    if not row:
        return []
    iid = row[0] if not hasattr(row, "keys") else row["id"]
    rows = conn.execute(
        """SELECT date, open, high, low, close, volume FROM prices
           WHERE instrument_id = ?
           ORDER BY date ASC""",
        (iid,),
    ).fetchall()
    if not rows:
        return []
    # Ne garder que les {{days}} derniers
    if len(rows) > days:
        rows = rows[-days:]
    return [
        (r[0], float(r[1] or 0), float(r[2] or 0), float(r[3] or 0),
         float(r[4] or 0), float(r[5] or 0))
        for r in rows
    ]


def _rsi14(closes):
    """RSI(14) standard Wilder. Retourne None si <15 closes."""
    if len(closes) < 15:
        return None
    gains = []
    losses = []
    for i in range(1, 15):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(abs(min(diff, 0)))
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    # Smoothing Wilder pour les points suivants
    for i in range(15, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = max(diff, 0)
        loss = abs(min(diff, 0))
        avg_gain = (avg_gain * 13 + gain) / 14
        avg_loss = (avg_loss * 13 + loss) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _sma_pct(closes, period):
    """% du dernier close par rapport a la SMA(period). None si <period closes."""
    if len(closes) < period:
        return None
    sma = sum(closes[-period:]) / period
    if sma == 0:
        return None
    last = closes[-1]
    return round((last / sma - 1.0) * 100.0, 2)


def _perf_pct(rows, days_back):
    """Perf% du dernier close vs close il y a N jours ouvres. rows = list de tuples (date, o, h, l, c, v)."""
    if len(rows) < days_back + 1:
        return None
    last = rows[-1][4]
    old = rows[-1 - days_back][4]
    if old == 0:
        return None
    return round((last / old - 1.0) * 100.0, 2)


def _perf_ytd(rows):
    """Perf% YTD : dernier close vs close du 1er trading day de l'annee courante."""
    if not rows:
        return None
    last_date = rows[-1][0]
    try:
        year = int(last_date[:4])
    except Exception:
        return None
    # Cherche premier close de l'annee
    ref = None
    for r in rows:
        if r[0][:4] == str(year):
            ref = r[4]
            break
    if ref is None or ref == 0:
        return None
    last = rows[-1][4]
    return round((last / ref - 1.0) * 100.0, 2)


def _rel_volume(rows):
    """Rel Volume : volume dernier jour / moyenne 30 derniers jours."""
    if len(rows) < 31:
        return None
    last_vol = rows[-1][5]
    avg_vol = sum(r[5] for r in rows[-31:-1]) / 30
    if avg_vol == 0:
        return None
    return round(last_vol / avg_vol, 2)


def _change_pct(rows):
    """Change% du jour : (close - open) / open * 100."""
    if not rows:
        return None
    o = rows[-1][1]
    c = rows[-1][4]
    if o == 0:
        return None
    return round((c / o - 1.0) * 100.0, 2)


def _beta_vs_spy(closes, spy_closes, window=60):
    """Beta = cov(r, r_spy) / var(r_spy) sur les <window> derniers jours."""
    if len(closes) < window + 1 or len(spy_closes) < window + 1:
        return None
    # Aligne : on prend les window+1 derniers points de chaque
    c = closes[-(window + 1):]
    s = spy_closes[-(window + 1):]
    if len(c) != len(s):
        return None
    # Returns
    ra = [(c[i] - c[i - 1]) / c[i - 1] for i in range(1, len(c)) if c[i - 1]]
    rs = [(s[i] - s[i - 1]) / s[i - 1] for i in range(1, len(s)) if s[i - 1]]
    if len(ra) < 10 or len(rs) < 10:
        return None
    n = min(len(ra), len(rs))
    ra, rs = ra[-n:], rs[-n:]
    ma = sum(ra) / n
    ms = sum(rs) / n
    cov = sum((ra[i] - ma) * (rs[i] - ms) for i in range(n)) / n
    var = sum((rs[i] - ms) ** 2 for i in range(n)) / n
    if var == 0:
        return None
    return round(cov / var, 2)


def compute_signals(tickers):
    """Point d'entree principal. Retourne list[dict] compat fetch_stock_signals()."""
    conn = sqlite3.connect(_DB, timeout=10.0)
    conn.row_factory = sqlite3.Row

    # Precharge SPY pour beta
    spy_rows = _get_prices(conn, "SPY", days=250)
    spy_closes = [r[4] for r in spy_rows]

    results = []
    for ticker in tickers:
        rows = _get_prices(conn, ticker, days=250)
        row = {{"ticker": ticker}}
        if not rows:
            for field in ("price", "change", "rsi", "sma20", "sma50", "sma200",
                          "recom", "target", "short_float", "rel_volume", "beta",
                          "perf_week", "perf_month", "perf_ytd", "sector"):
                row[field] = None
            results.append(row)
            continue

        closes = [r[4] for r in rows]

        # Sector via instruments table
        sr = conn.execute(
            "SELECT sector FROM instruments WHERE ticker = ?", (ticker,)
        ).fetchone()
        sector = (sr["sector"] if sr and sr["sector"] else "") if sr else ""

        row["price"]       = round(closes[-1], 2)
        row["change"]      = _change_pct(rows)
        row["rsi"]         = _rsi14(closes)
        row["sma20"]       = _sma_pct(closes, 20)
        row["sma50"]       = _sma_pct(closes, 50)
        row["sma200"]      = _sma_pct(closes, 200)
        row["perf_week"]   = _perf_pct(rows, 5)
        row["perf_month"]  = _perf_pct(rows, 21)
        row["perf_ytd"]    = _perf_ytd(rows)
        row["rel_volume"]  = _rel_volume(rows)
        row["beta"]        = _beta_vs_spy(closes, spy_closes, window=60)
        row["sector"]      = sector
        # Champs Finviz-only qu'on n'a pas encore : recom / target / short_float
        row["recom"]       = None
        row["target"]      = None
        row["short_float"] = None

        results.append(row)

    conn.close()
    return results
'''


# =============================================================================
# PATCH data_finviz.py : ajoute alias fetch_stock_signals -> compute_signals
# =============================================================================

OLD_FUNC_START = 'def fetch_stock_signals(tickers: list[str]) -> list[dict]:'
NEW_FUNC = f'''def fetch_stock_signals(tickers: list[str]) -> list[dict]:
    """Stock signals V2 - calcule tout depuis la table prices maison.  {MARK}

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
        print(f"[data_finviz] compute_signals error: {{e}}")
        # Fallback : rows vides mais structure preservee
        results = []
        for t in tickers:
            row = {{"ticker": t}}
            for field in ("price", "change", "rsi", "sma20", "sma50", "sma200",
                          "recom", "target", "short_float", "rel_volume", "beta",
                          "perf_week", "perf_month", "perf_ytd", "sector"):
                row[field] = None
            results.append(row)

    _set(cache_key, results)
    return results


def _fetch_stock_signals_legacy_finviz(tickers: list[str]) -> list[dict]:'''


def main():
    print(f"[TS] {TS}")
    print()

    # Ecrire signals_calculator.py
    if os.path.exists(F_CALC):
        with open(F_CALC, "r", encoding="utf-8-sig") as fh:
            existing = fh.read()
        if MARK in existing:
            print(f"[SKIP calc] {F_CALC} deja patch (marker present)")
        else:
            bak = F_CALC + ".bak." + TS
            shutil.copy2(F_CALC, bak)
            print(f"[BAK calc] {bak}")
            with open(F_CALC, "w", encoding="utf-8", newline="") as fh:
                fh.write(CALC_MODULE)
            print(f"[OK] wrote {F_CALC}")
    else:
        with open(F_CALC, "w", encoding="utf-8", newline="") as fh:
            fh.write(CALC_MODULE)
        print(f"[OK] created {F_CALC}")

    # Validation calc module
    try:
        compile(CALC_MODULE, F_CALC, "exec")
        print("[OK] signals_calculator.py compile OK")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError signals_calculator: {e}")
        return 1

    print()

    # Patcher data_finviz.py
    if not os.path.exists(F_DATA):
        print(f"[ERR] {F_DATA} not found")
        return 2

    with open(F_DATA, "r", encoding="utf-8-sig") as fh:
        src = fh.read()

    if MARK in src:
        print(f"[SKIP data_finviz] deja patch")
        return 0

    if OLD_FUNC_START not in src:
        print(f"[ERR] OLD_FUNC_START not found : {OLD_FUNC_START!r}")
        return 3

    new_src = src.replace(OLD_FUNC_START, NEW_FUNC, 1)
    if new_src == src:
        print("[ERR] no change produced")
        return 4

    # Compile check
    try:
        compile(new_src, F_DATA, "exec")
        print("[OK] data_finviz.py compile OK apres patch")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        return 5

    # Backup + write
    bak = F_DATA + ".bak." + TS
    shutil.copy2(F_DATA, bak)
    print(f"[BAK] {bak}")
    with open(F_DATA, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print(f"[OK] wrote {F_DATA}")

    # Post-write checks
    with open(F_DATA, "r", encoding="utf-8-sig") as fh:
        check = fh.read()
    print()
    print("[POST-WRITE CHECKS]")
    checks = [
        ("import signals_calculator", "import calc module"),
        ("_fetch_stock_signals_legacy_finviz", "legacy function renommee"),
        ("compute_signals(tickers)", "call V2 present"),
        (MARK, "marker present"),
    ]
    for needle, label in checks:
        n = check.count(needle)
        tag = "OK" if n > 0 else "MISSING"
        print(f"  [{tag}] {label}: {n}")

    # Test runtime
    print()
    print("[STAGE FINAL] Runtime test signals_calculator")
    print("-" * 70)
    try:
        sys.path.insert(0, ROOT)
        import importlib
        if "signals_calculator" in sys.modules:
            importlib.reload(sys.modules["signals_calculator"])
        import signals_calculator
        res = signals_calculator.compute_signals(["AAPL", "SPY", "NVDA"])
        for row in res:
            t = row["ticker"]
            print(f"  {t}:")
            print(f"    price={row['price']} change={row['change']}% rsi={row['rsi']}")
            print(f"    sma20={row['sma20']}% sma50={row['sma50']}% sma200={row['sma200']}%")
            print(f"    perf_w={row['perf_week']}% perf_m={row['perf_month']}% ytd={row['perf_ytd']}%")
            print(f"    rel_vol={row['rel_volume']} beta={row['beta']} sector={row['sector']!r}")
    except Exception as e:
        import traceback
        print(f"  [ERR] {type(e).__name__}: {e}")
        traceback.print_exc()
        return 6

    print()
    print("[NEXT] Restart uvicorn pour recharger data_finviz")
    print("[NEXT] Ctrl+F5 dans le navigateur -> Stock Signals doit se peupler")
    return 0


if __name__ == "__main__":
    sys.exit(main())
