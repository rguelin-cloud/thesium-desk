# -*- coding: utf-8 -*-
"""
Diag pour preparer :
  - Endpoint /api/regime/current dans api_server_with_static.py
    (avant app.mount L476)
  - Panneau 'Regime Marche' dans index.html
  - Fetch dans app.js

Cherche :
  1. Structure api_server_with_static.py : section des routes, position de
     app.mount, exemple d'endpoint existant
  2. index.html : section des panneaux/cards dans 'today' tab
  3. app.js : pattern de fetch/render des cards (factor, risk_v2, convergence,
     pplx, etc.) pour reproduire
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")
INDEX = os.path.join(ROOT, "index.html")
APPJS = os.path.join(ROOT, "app.js")

# ---------- 1) api_server_with_static.py ----------
print("=" * 78)
print("1. api_server_with_static.py : routes et mount")
print("=" * 78)
with open(API, "r", encoding="utf-8-sig") as f:
    api_lines = f.read().splitlines()

print(f"  Total : {len(api_lines)} lignes")
print()
print("  Toutes les routes @app.get / @app.post :")
for i, line in enumerate(api_lines, 1):
    if re.search(r"@app\.(get|post|put|delete)\s*\(", line):
        print(f"    L{i:5} | {line.rstrip()[:130]}")

print()
print("  app.mount L (zone limite) :")
for i, line in enumerate(api_lines, 1):
    if "app.mount" in line:
        print(f"    L{i:5} | {line.rstrip()[:130]}")

print()
print("  Recherche pattern endpoint similaire (regime / portfolio simple) :")
# On cherche un endpoint simple recent et son corps complet pour modele
for i, line in enumerate(api_lines, 1):
    if "/api/portfolio/state" in line or "/api/portfolio/summary" in line:
        print(f"    L{i:5} | {line.rstrip()[:130]}")
        # Affiche 25 lignes suivantes pour avoir le corps
        for j in range(i, min(i + 25, len(api_lines))):
            print(f"    L{j+1:5} | {api_lines[j][:140]}")
        print("    ---")
        break

# ---------- 2) index.html ----------
print()
print("=" * 78)
print("2. index.html : structure des panneaux 'today'")
print("=" * 78)
with open(INDEX, "r", encoding="utf-8-sig") as f:
    html = f.read()
html_lines = html.splitlines()
print(f"  Total : {len(html_lines)} lignes")
print()
print("  Recherche tab 'today' et anchors id pour cards :")
for i, line in enumerate(html_lines, 1):
    s = line.strip()
    if re.search(r'id="today', line) or re.search(r'data-tab="today"', line):
        print(f"    L{i:5} | {s[:130]}")
    if re.search(r'class="[^"]*card[^"]*"\s+id=', line):
        print(f"    L{i:5} | {s[:130]}")
    if re.search(r'<section[^>]*id=', line):
        print(f"    L{i:5} | {s[:130]}")

print()
print("  Recherche cards specifiques (risk-controls, convergence, factor) :")
for needle in ("risk-controls-card", "convergence-card", "factor-quality",
               "pplx-cycle", "regime-card"):
    for i, line in enumerate(html_lines, 1):
        if needle in line:
            print(f"    L{i:5} ({needle:20}) | {line.strip()[:120]}")
            break

# ---------- 3) app.js ----------
print()
print("=" * 78)
print("3. app.js : patterns de fetch + render")
print("=" * 78)
with open(APPJS, "r", encoding="utf-8-sig") as f:
    js_text = f.read()
js_lines = js_text.splitlines()
print(f"  Total : {len(js_lines)} lignes")

# Recherche des fetches existants pour /api/portfolio ou /api/construction etc.
print()
print("  Echantillon de fetch existants :")
patterns_js = [
    r"apiFetch\(['\"]/api/portfolio",
    r"apiFetch\(['\"]/api/construction",
    r"apiFetch\(['\"]/api/convergence",
    r"fetch\(['\"]/api/portfolio",
    r"fetch\(['\"]/api/convergence",
]
seen = 0
for i, line in enumerate(js_lines, 1):
    for pat in patterns_js:
        if re.search(pat, line):
            print(f"    L{i:6} | {line.strip()[:120]}")
            seen += 1
            break
    if seen >= 8:
        break

# Recherche de la fonction de boot principale (init / renderDashboard / loadAll)
print()
print("  Fonctions d'initialisation / render top-level :")
for i, line in enumerate(js_lines, 1):
    if re.match(r"\s*(async\s+)?function\s+(init|loadAll|loadDashboard|renderDashboard|renderTodayTab|refreshAll)", line):
        print(f"    L{i:6} | {line.strip()[:130]}")

# Recherche de fonctions render*Card
print()
print("  Fonctions render*Card :")
for i, line in enumerate(js_lines, 1):
    if re.search(r"function\s+render\w*Card\s*\(", line) or re.search(r"function\s+update\w*Card\s*\(", line):
        print(f"    L{i:6} | {line.strip()[:130]}")

# Recherche apiFetch helper
print()
print("  Helper apiFetch :")
for i, line in enumerate(js_lines, 1):
    if re.search(r"function\s+apiFetch\b|const\s+apiFetch\s*=", line):
        print(f"    L{i:6} | {line.strip()[:130]}")
        break

print()
print("=" * 78)
print("FIN DIAG")
print("=" * 78)
