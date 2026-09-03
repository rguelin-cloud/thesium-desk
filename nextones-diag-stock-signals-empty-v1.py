"""
Diag : Stock Signals card vide (tous tickers --). Cause probable :
finvizfinance ne recupere plus rien depuis Finviz (lib cassee ou blocage anti-bot).

3 tests :
1. Import finvizfinance + verifier version installee
2. Appel direct fetch_stock_signals(['AAPL']) pour voir si la fonction retourne vide/None
3. Test brut : requete HTTP directe sur Finviz pour AAPL, check status + snippet HTML
"""
import os
import sys
import subprocess

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, ROOT)

print("[STAGE 1] finvizfinance version installee")
print("-" * 70)
try:
    r = subprocess.run(
        ["py", "-3.13", "-m", "pip", "show", "finvizfinance"],
        capture_output=True, text=True, timeout=15
    )
    if r.returncode == 0:
        print(r.stdout[:400])
    else:
        print("[NOT INSTALLED]", r.stderr[:400])
except Exception as e:
    print(f"[ERR] pip show: {e}")

print()
print("[STAGE 2] Test import et appel direct fetch_stock_signals")
print("-" * 70)
try:
    from data_finviz import fetch_stock_signals
    print("  [OK] import fetch_stock_signals")

    # Test avec un ticker liquide connu
    rows = fetch_stock_signals(["AAPL"])
    print(f"  [OK] fetch_stock_signals(['AAPL']) -> len={len(rows)}")
    if rows:
        row = rows[0]
        # Compte les fields None
        n_none = sum(1 for v in row.values() if v is None)
        n_total = len(row)
        print(f"  [ROW] {n_none}/{n_total} fields sont None")
        print(f"  [ROW dump] {row}")
except Exception as e:
    import traceback
    print(f"  [ERR] {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("[STAGE 3] Test brut finvizfinance + HTTP direct")
print("-" * 70)
try:
    from finvizfinance.quote import finvizfinance
    print("  [OK] import finvizfinance.quote")

    stock = finvizfinance("AAPL")
    print("  [OK] finvizfinance('AAPL') instancie")

    try:
        info = stock.ticker_fundament()
        print(f"  [OK] ticker_fundament() -> {type(info).__name__} len={len(info) if info else 0}")
        if info:
            print(f"  [SAMPLE 3 keys] Price={info.get('Price')} RSI={info.get('RSI (14)')} SMA20={info.get('SMA20')}")
    except Exception as e:
        print(f"  [ERR ticker_fundament] {type(e).__name__}: {e}")
except Exception as e:
    print(f"  [ERR finvizfinance] {type(e).__name__}: {e}")

print()
print("[STAGE 4] HTTP direct vers Finviz (bypass la lib)")
print("-" * 70)
try:
    import urllib.request
    url = "https://finviz.com/quote.ashx?t=AAPL"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )
    resp = urllib.request.urlopen(req, timeout=15)
    body = resp.read().decode("utf-8", errors="replace")
    status = resp.getcode()
    print(f"  [HTTP] status={status} content-length={len(body)}")

    # Signals of anti-bot / block
    lower = body.lower()
    signals = []
    if "cloudflare" in lower and "challenge" in lower:
        signals.append("CLOUDFLARE_CHALLENGE")
    if "captcha" in lower:
        signals.append("CAPTCHA")
    if "access denied" in lower or "forbidden" in lower:
        signals.append("ACCESS_DENIED")
    if "rate limit" in lower:
        signals.append("RATE_LIMIT")

    print(f"  [BLOCKS] {signals if signals else 'aucun signal anti-bot'}")

    # Snippet de key indicators (RSI dans une table)
    idx = lower.find("rsi (14)")
    if idx >= 0:
        snippet = body[idx:idx + 300]
        print(f"  [FOUND 'RSI (14)'] a offset {idx}")
        print(f"  {snippet[:280]!r}")
    else:
        print("  [MISS] 'RSI (14)' not found in response body")
        # dump 500 premiers chars
        print(f"  [HTML START] {body[:500]!r}")

except Exception as e:
    print(f"  [ERR HTTP] {type(e).__name__}: {e}")

print()
print("[STAGE 5] Endpoint API qui sert la carte Stock Signals")
print("-" * 70)
for fn in ["api_server.py", "api_server_with_static.py"]:
    fp = os.path.join(ROOT, fn)
    if not os.path.exists(fp):
        continue
    import re
    with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()
    for m in re.finditer(r'(fetch_stock_signals|/api/finviz/signals|/api/stock_signals)', src):
        ln = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        print(f"  {fn}:L{ln}: {src[line_start:line_end].strip()[:180]}")
