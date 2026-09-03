# -*- coding: utf-8 -*-
# [DIAG_PNL_UI_CARD_STRUCTURE]
# Localise la carte Portfolio en haut de l'UI : ou sont affiches
# total_value, total_pnl, total_pnl_pct, et leur container parent
# (pour pouvoir y ajouter Unrealized P&L | Total Return + bouton flow).
#
# Aussi : structure /api/portfolio/state dans api_server.py pour savoir
# quels champs sont expose au front (= source d'affichage).

import re
import sys
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def read_text(p):
    with open(p, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace")

def find_lines(text, pattern, flags=0, max_hits=20):
    rgx = re.compile(pattern, flags)
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        if rgx.search(line):
            hits.append((i, line.rstrip()))
            if len(hits) >= max_hits:
                break
    return hits

def section(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)

# ---------- 1. index.html : reperer les ID/classes de la carte Portfolio ----------
section("1. index.html : elements P&L total")
html_path = BASE / "ui_static" / "index.html"
if not html_path.exists():
    html_path = BASE / "index.html"
html = read_text(html_path)
print(f"Fichier : {html_path}")
print(f"Taille  : {len(html)} chars / {len(html.splitlines())} lignes")

patterns = [
    r"total[-_]?pnl",
    r"total[-_]?value",
    r"totalPnl",
    r"totalValue",
    r"Total P&?L",
    r"Total Value",
    r"NAV",
    r"id=\"summary",
    r"id=\"portfolio[A-Z]",
    r"summary[-_]card",
    r"kpi[-_]?card",
]
for pat in patterns:
    hits = find_lines(html, pat, re.IGNORECASE, max_hits=8)
    print(f"\n[HTML] /{pat}/i  -> {len(hits)} hits")
    for ln, txt in hits:
        print(f"  L{ln}: {txt[:130]}")

# ---------- 2. app.js : ou les valeurs P&L sont-elles injectees dans le DOM ----------
section("2. app.js : injection P&L dans DOM")
js_path = BASE / "ui_static" / "app.js"
if not js_path.exists():
    js_path = BASE / "app.js"
js = read_text(js_path)
print(f"Fichier : {js_path}")
print(f"Taille  : {len(js)} chars / {len(js.splitlines())} lignes")

js_patterns = [
    r"total_pnl",
    r"totalPnl",
    r"total_value",
    r"totalValue",
    r"getElementById\(['\"](summary|portfolio|total|nav|pnl)",
    r"renderPortfolio(?!Ideal)",
    r"renderSummary",
    r"updateSummary",
    r"fetch.*/api/portfolio/state",
]
for pat in js_patterns:
    hits = find_lines(js, pat, re.IGNORECASE, max_hits=10)
    print(f"\n[JS] /{pat}/i  -> {len(hits)} hits")
    for ln, txt in hits:
        print(f"  L{ln}: {txt[:130]}")

# ---------- 3. api_server.py : endpoint /api/portfolio/state ----------
section("3. api_server.py : /api/portfolio/state body")
api_path = BASE / "api_server.py"
if not api_path.exists():
    api_path = BASE / "api_server_with_static.py"
api = read_text(api_path)
print(f"Fichier : {api_path}")
print(f"Taille  : {len(api)} chars / {len(api.splitlines())} lignes")

# Trouve la route /api/portfolio/state
route_pat = re.compile(r'@app\.(?:get|post)\(\s*["\']/api/portfolio/state["\']', re.IGNORECASE)
m = route_pat.search(api)
if m:
    start_line = api[:m.start()].count("\n") + 1
    # Lit ~80 lignes a partir de la
    lines = api.splitlines()
    print(f"\n[ROUTE] @app.get('/api/portfolio/state') trouve a L{start_line}")
    end = min(start_line + 90, len(lines))
    for i in range(start_line - 1, end):
        print(f"  L{i+1}: {lines[i]}")
else:
    print("\n[!] Route /api/portfolio/state NON trouvee. Recherche alternative...")
    alt = find_lines(api, r"portfolio/state", 0, 20)
    for ln, txt in alt:
        print(f"  L{ln}: {txt[:160]}")

# ---------- 4. Tous les UPDATE portfolio_state SET total_pnl ----------
section("4. WRITER portfolio_state.total_pnl (recursive scan)")
ROOT = BASE
hits_all = []
for py in ROOT.rglob("*.py"):
    # exclure venv / archives
    sp = str(py).lower()
    if any(x in sp for x in ("\\venv\\", "\\.venv\\", "\\backup", ".bak.", "\\__pycache__\\")):
        continue
    try:
        t = read_text(py)
    except Exception:
        continue
    # cherche les UPDATE portfolio_state ... total_pnl OU INSERT INTO portfolio_state
    for m2 in re.finditer(
        r"(UPDATE\s+portfolio_state[^;]{0,400}total_pnl|INSERT\s+INTO\s+portfolio_state[^;]{0,400})",
        t,
        re.IGNORECASE | re.DOTALL,
    ):
        ln = t[:m2.start()].count("\n") + 1
        snippet = m2.group(0)[:240].replace("\n", " \\n ")
        hits_all.append((py.relative_to(ROOT), ln, snippet))

print(f"\nTotal sites trouves : {len(hits_all)}")
for rel, ln, snip in hits_all:
    print(f"\n  {rel}  L{ln}")
    print(f"    {snip[:220]}")

# ---------- 5. capital_flows : table existe-t-elle deja ? ----------
section("5. capital_flows : table deja existante ?")
import sqlite3
db = BASE / "thesium.db"
if db.exists():
    try:
        conn = sqlite3.connect(str(db), timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        flow_tables = [t for t in tables if "flow" in t.lower() or "capital" in t.lower() or "deposit" in t.lower()]
        print(f"Tables 'flow/capital/deposit' : {flow_tables}")
        print(f"Total tables DB : {len(tables)}")
        conn.close()
    except Exception as e:
        print(f"[!] DB error : {e}")
else:
    print(f"[!] DB introuvable : {db}")

print("\nDONE [DIAG_PNL_UI_CARD_STRUCTURE]")
