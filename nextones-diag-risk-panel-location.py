# -*- coding: utf-8 -*-
"""
Diag: ou inserer la carte 'Controles pre-trade' dans l'UI.
Cherche:
 - panel/section existant 'risk' ou 'controles'
 - endpoint API renvoyant les 5 dernieres entrees de risk_pretrade_log
 - structure HTML de la page principale (api_server_with_static.py + static/*)
"""
import os, re, glob

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def head(t):
    print("\n" + "="*70); print(t); print("="*70)

# 1) Trouver les fichiers HTML principaux
head("1) Fichiers HTML candidats")
html_files = []
for root, dirs, files in os.walk(ROOT):
    # skip backups
    if "_backup" in root or "__pycache__" in root or ".git" in root:
        continue
    for f in files:
        if f.endswith(".html"):
            p = os.path.join(root, f)
            sz = os.path.getsize(p)
            html_files.append((p, sz))
html_files.sort(key=lambda x: -x[1])
for p, sz in html_files[:10]:
    print(f"  {sz:>8d}o  {p}")

# 2) Cherche markers risk/controles dans HTML
head("2) Mentions 'risk' / 'controle' / 'pre-trade' dans HTML")
patterns = [r"risk[-_ ]?check", r"contr[oô]le", r"pre[-_ ]?trade", r"risk[-_ ]?v2",
            r"risk[-_ ]?engine", r"panel.{0,20}risk"]
for p, _ in html_files[:5]:
    try:
        with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
            src = f.read()
    except Exception:
        continue
    hits = []
    for pat in patterns:
        for m in re.finditer(pat, src, re.IGNORECASE):
            hits.append((m.start(), m.group()))
    if hits:
        print(f"\n  --- {os.path.basename(p)} ---")
        for off, g in hits[:10]:
            line = src.count("\n", 0, off) + 1
            print(f"    L{line:>5}: ...{src[max(0,off-30):off+60]}...")

# 3) Endpoints API existants liens avec risk
head("3) Endpoints API contenant 'risk'")
api = os.path.join(ROOT, "api_server_with_static.py")
if os.path.exists(api):
    with open(api, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    for m in re.finditer(r'@app\.(get|post)\(\s*"([^"]+)"', src):
        path = m.group(2)
        if "risk" in path.lower() or "control" in path.lower() or "pretrade" in path.lower():
            line = src.count("\n", 0, m.start()) + 1
            print(f"  L{line:>5}: {m.group(1).upper():4s} {path}")
else:
    print("  api_server_with_static.py introuvable")

# 4) Structure: ou est le panel 'Today' / 'Aujourd'hui' / panneau principal
head("4) Structure HTML principale (premier gros HTML)")
if html_files:
    main_html = html_files[0][0]
    print(f"  Analyse: {main_html}")
    with open(main_html, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    # Cherche les sections/cartes principales
    for m in re.finditer(r'<(section|div)[^>]*(?:id|class)="([^"]*(?:panel|card|section|today|aujourd)[^"]*)"', src, re.IGNORECASE):
        line = src.count("\n", 0, m.start()) + 1
        print(f"    L{line:>5}: <{m.group(1)} ...{m.group(2)[:60]}...")

print("\nDone.")
