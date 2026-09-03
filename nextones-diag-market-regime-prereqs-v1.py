# -*- coding: utf-8 -*-
"""
Diag pre-implementation market_regime_v1 :
  1. Verifier FRED client (cle, fonctions accessibles)
  2. Verifier prices DB : SPY + BTC presents avec assez d'historique (>= 30j)
  3. Verifier ou est appele detect_portfolio_regime() pour savoir ou injecter market_regime
"""
import sqlite3
import os
import re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 80)
print("1. PRIX SPY + BTC DISPONIBLES")
print("=" * 80)
# Verifier instruments pour SPY et BTC
for sym in ("SPY", "BTC", "BTCUSDT", "BTC-USD", "QQQ"):
    row = cur.execute("SELECT id, ticker, asset_class FROM instruments WHERE ticker = ?", (sym,)).fetchone()
    if row:
        # Compter prix
        n = cur.execute("SELECT COUNT(*) FROM prices WHERE instrument_id = ?", (row["id"],)).fetchone()[0]
        last = cur.execute("SELECT MAX(date) FROM prices WHERE instrument_id = ?", (row["id"],)).fetchone()[0]
        first = cur.execute("SELECT MIN(date) FROM prices WHERE instrument_id = ?", (row["id"],)).fetchone()[0]
        print(f"  {sym:<10} id={row['id']:<4} class={row['asset_class']:<10} n_prices={n:<5} first={first} last={last}")
    else:
        print(f"  {sym:<10} ABSENT")

print()
print("=" * 80)
print("2. TOUS LES INSTRUMENTS PAR ASSET_CLASS")
print("=" * 80)
rows = cur.execute("""
    SELECT asset_class, COUNT(*) AS n, GROUP_CONCAT(ticker, ',') AS tickers
    FROM instruments
    GROUP BY asset_class
""").fetchall()
for r in rows:
    tickers = (r["tickers"] or "")[:200]
    print(f"  {r['asset_class']:<12} n={r['n']:<3} tickers={tickers}")

print()
print("=" * 80)
print("3. FRED CLIENT : fichiers + cle")
print("=" * 80)
fred_files = []
for root, _, files in os.walk(ROOT):
    if any(skip in root for skip in (".git", "__pycache__", "venv", ".bak")):
        continue
    for f in files:
        if f.endswith(".py") and "fred" in f.lower():
            fred_files.append(os.path.join(root, f))
print(f"  Fichiers FRED trouves : {len(fred_files)}")
for f in fred_files:
    print(f"    {f}")

# Cle FRED
fred_key_locs = []
for root, _, files in os.walk(ROOT):
    if any(skip in root for skip in (".git", "__pycache__", "venv", ".bak")):
        continue
    for f in files:
        if f.endswith((".py", ".env", ".ini", ".cfg", ".yaml", ".yml", ".json")):
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8-sig", errors="ignore") as ff:
                    content = ff.read()
            except Exception:
                continue
            if re.search(r"FRED[_\s]*API[_\s]*KEY|fred_api_key|FRED_KEY", content, re.IGNORECASE):
                # Extraire la ligne
                for line in content.splitlines():
                    if re.search(r"FRED[_\s]*API[_\s]*KEY|fred_api_key|FRED_KEY", line, re.IGNORECASE):
                        # Masquer la valeur
                        masked = re.sub(r"=\s*['\"]?([a-z0-9]{4})[a-z0-9]+['\"]?", r"= \1******", line)
                        fred_key_locs.append((os.path.basename(fp), masked.strip()[:120]))
                        break
print(f"  Mentions cle FRED : {len(fred_key_locs)}")
for fname, line in fred_key_locs[:10]:
    print(f"    {fname} : {line}")

print()
print("=" * 80)
print("4. CHERCHER FONCTIONS FRED EXISTANTES (vix, series, get_)")
print("=" * 80)
fred_funcs = []
for fp in fred_files:
    try:
        with open(fp, "r", encoding="utf-8-sig", errors="ignore") as ff:
            content = ff.read()
    except Exception:
        continue
    for m in re.finditer(r"def\s+(\w+)\s*\(([^)]*)\)", content):
        fname = m.group(1)
        fred_funcs.append((os.path.basename(fp), fname, m.group(2)[:60]))
print(f"  Fonctions trouvees dans fichiers FRED : {len(fred_funcs)}")
for f, name, args in fred_funcs[:30]:
    print(f"    {f:<35} def {name}({args})")

print()
print("=" * 80)
print("5. CHERCHER USAGE VIX dans le code")
print("=" * 80)
vix_hits = []
for root, _, files in os.walk(ROOT):
    if any(skip in root for skip in (".git", "__pycache__", "venv", ".bak")):
        continue
    for f in files:
        if f.endswith(".py") and not f.startswith("nextones-"):
            fp = os.path.join(root, f)
            try:
                with open(fp, "r", encoding="utf-8-sig", errors="ignore") as ff:
                    content = ff.read()
            except Exception:
                continue
            for m in re.finditer(r"['\"]VIX(CLS)?['\"]|vix_value|get_vix|fetch_vix", content):
                vix_hits.append((os.path.basename(fp), m.group(0)[:50]))
                break
print(f"  Fichiers mentionnant VIX : {len(vix_hits)}")
for fname, snippet in vix_hits[:15]:
    print(f"    {fname:<40} : {snippet}")

print()
print("=" * 80)
print("6. WHERE detect_portfolio_regime IS CALLED (point d'injection)")
print("=" * 80)
ee_path = os.path.join(ROOT, "execution_engine.py")
if os.path.exists(ee_path):
    with open(ee_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        content = f.read()
    for i, line in enumerate(content.splitlines(), 1):
        if "detect_portfolio_regime(" in line and "def " not in line:
            print(f"  L{i:5} | {line.strip()[:150]}")

print()
print("=" * 80)
print("7. TABLE existante pour market data (vix, indicators) ?")
print("=" * 80)
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
candidates = [t for t in tables if any(k in t.lower() for k in ("vix", "macro", "market", "indicator", "fred"))]
print(f"  Tables candidates : {candidates}")
for t in candidates:
    cc = [r["name"] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"    {t} : n={n} cols={cc}")
    # Recent rows
    sample = cur.execute(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 3").fetchall()
    for r in sample:
        d = dict(r)
        short = {k: (str(v)[:50] if v is not None else None) for k, v in d.items()}
        print(f"      {short}")

con.close()
print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
