# -*- coding: utf-8 -*-
"""
Q2 - Trouver pourquoi cycles_daily n est pas insere.
 1) Lire le code autour des endpoints suspects (L633, L1608, L1620)
 2) Lire le code autour de L1633 (le guard) pour voir le flow
 3) Chercher tous les INSERT INTO cycles_daily dans le projet
 4) Trouver ce que le bouton UI appelle
"""
import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server.py")
HTML = os.path.join(ROOT, "index.html")

def head(t): print("\n"+"="*70); print(t); print("="*70)

with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    api_src = f.read()
api_lines = api_src.split("\n")

def show(start, end, label):
    print(f"\n--- {label} (L{start}-L{end}) ---")
    for i in range(start-1, min(end, len(api_lines))):
        print(f"  L{i+1:>5}: {api_lines[i]}")

# 1) Endpoint /api/run-agents (L1620)
head("1) /api/run-agents endpoint (L1620-L1720)")
show(1615, 1720, "run-agents")

# 2) Endpoint /api/orders/execute-cycle (L633)
head("2) /api/orders/execute-cycle endpoint (L633-L720)")
show(630, 720, "execute-cycle")

# 3) Tous les INSERT INTO cycles_daily
head("3) Tous les INSERT INTO cycles_daily")
for m in re.finditer(r'INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+cycles_daily', api_src, re.IGNORECASE):
    line = api_src.count("\n", 0, m.start()) + 1
    # contexte
    ctx_start = max(0, m.start() - 100)
    ctx_end = min(len(api_src), m.end() + 200)
    print(f"\n  L{line}: ...{api_src[ctx_start:ctx_end].replace(chr(10), ' / ')}...")

# Dans tout le projet aussi
print("\n--- Autres fichiers ---")
for root, dirs, files in os.walk(ROOT):
    if "_backup" in root or "__pycache__" in root or ".git" in root: continue
    for f in files:
        if not f.endswith(".py") or f == "api_server.py": continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
        except: continue
        for m in re.finditer(r'INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+cycles_daily', src, re.IGNORECASE):
            line = src.count("\n", 0, m.start()) + 1
            print(f"  {os.path.relpath(p, ROOT)}:L{line}")

# 4) Que dit le bouton 'Run Decision Cycle' dans le frontend ?
head("4) Bouton 'Run Decision Cycle' dans index.html")
with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
    html = f.read()
# Cherche le bouton
for m in re.finditer(r'Run Decision Cycle', html):
    start = max(0, m.start() - 300)
    end = min(len(html), m.end() + 100)
    print(f"\n  Position {m.start()}:")
    print(f"  ...{html[start:end]}...")

# Cherche les fetch/axios appelant cycle/run-agents
print("\n--- fetch() suspects ---")
for pat in [r'fetch\s*\(\s*[\'"][^\'"]*(?:cycle|run-agents|run-ingestion|execute)[^\'"]*[\'"]',
            r'/api/[^\'"\s]+(?:cycle|run-agents|run-ingestion|execute)[^\'"\s]*']:
    for m in re.finditer(pat, html, re.IGNORECASE):
        line = html.count("\n", 0, m.start()) + 1
        print(f"  L{line}: {html[max(0,m.start()-20):m.end()+80].replace(chr(10),' / ')[:200]}")

print("\nDone.")
