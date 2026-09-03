# -*- coding: utf-8 -*-
# [DIAG_SUMMARY_ROUTE_AND_KPIS]
# 1. Trouver la route API qui sert les donnees de la carte Portfolio (total_pnl/total_value).
# 2. Dumper le bloc HTML L955-1015 (les 4 kpi-card + canvas) pour voir leur structure exacte.
# 3. Dumper app.js L1030-1075 (renderDashboard P&L block) pour voir comment les valeurs sont injectees.
# 4. Lister TOUTES les routes @app.get/@app.post de api_server.py qui contiennent "portfolio" ou "summary" ou "dashboard".

import re
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace")

def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)

# ---- 1. Routes api_server.py ----
section("1. Routes API contenant 'portfolio', 'summary', 'dashboard'")
api = read_text(BASE / "api_server.py")
api_lines = api.splitlines()
route_rgx = re.compile(r'@app\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
for i, line in enumerate(api_lines, 1):
    m = route_rgx.search(line)
    if m:
        path = m.group(2)
        if any(kw in path.lower() for kw in ("portfolio", "summary", "dashboard", "state", "nav")):
            # affiche route + 2 lignes suivantes (def func)
            print(f"\n  L{i}: {line.strip()}")
            for j in range(i, min(i + 3, len(api_lines))):
                print(f"  L{j+1}: {api_lines[j].strip()[:120]}")

# ---- 2. Bloc HTML kpi cards ----
section("2. index.html L955-1020 (zone KPI cards)")
html = read_text(BASE / "index.html").splitlines()
start, end = 955, 1020
for i in range(start - 1, min(end, len(html))):
    print(f"  L{i+1}: {html[i]}")

# ---- 3. app.js renderDashboard P&L block ----
section("3. app.js L1025-1075 (renderDashboard P&L injection)")
js = read_text(BASE / "app.js").splitlines()
for i in range(1024, min(1075, len(js))):
    print(f"  L{i+1}: {js[i]}")

# ---- 4. Localise renderDashboard signature ----
section("4. Localisation renderDashboard / fetchDashboard / fetchPortfolio")
js_text = "\n".join(js)
for pat in [
    r"function renderDashboard",
    r"function fetchDashboard",
    r"function loadDashboard",
    r"function loadPortfolio",
    r"function renderPortfolioSummary",
    r"async function load",
    r"fetch\(['\"]/api/portfolio",
    r"fetch\(['\"]/api/dashboard",
    r"fetch\(['\"]/api/summary",
]:
    for m in re.finditer(pat, js_text):
        ln = js_text[:m.start()].count("\n") + 1
        print(f"  L{ln}: {js[ln-1].strip()[:130]}")

# ---- 5. fix_crypto_prices.py : voir le bloc UPDATE complet ----
section("5. fix_crypto_prices.py L175-210 (le writer divergent)")
fcp = read_text(BASE / "fix_crypto_prices.py").splitlines()
for i in range(174, min(210, len(fcp))):
    print(f"  L{i+1}: {fcp[i]}")

# ---- 6. Schema portfolio_state ----
section("6. Schema portfolio_state")
import sqlite3
db = BASE / "thesium.db"
conn = sqlite3.connect(str(db), timeout=5)
cur = conn.cursor()
cur.execute("PRAGMA table_info(portfolio_state)")
for r in cur.fetchall():
    print(f"  {r}")
# Lit la ligne actuelle pour reference
cur.execute("SELECT * FROM portfolio_state WHERE id=1")
row = cur.fetchone()
cur.execute("PRAGMA table_info(portfolio_state)")
cols = [c[1] for c in cur.fetchall()]
print()
print("Valeurs actuelles portfolio_state id=1:")
if row:
    for c, v in zip(cols, row):
        print(f"  {c} = {v}")
conn.close()

print("\nDONE [DIAG_SUMMARY_ROUTE_AND_KPIS]")
