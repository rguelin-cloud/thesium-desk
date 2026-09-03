# -*- coding: utf-8 -*-
"""
Verifier ou vivent VRAIMENT les endpoints (routers FastAPI ?)
2 seulement dans api_server_with_static.py = suspect.
"""
import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def head(t): print("\n" + "="*70); print(t); print("="*70)

# 1) Tous les fichiers .py contenant @app. / @router. / APIRouter
head("1) Fichiers .py avec endpoints (@app. ou @router.) + include_router")
candidates = []
for root, dirs, files in os.walk(ROOT):
    if "_backup" in root or "__pycache__" in root or ".git" in root:
        continue
    for f in files:
        if not f.endswith(".py"): continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
        except Exception: continue
        n_app    = len(re.findall(r'@app\.(get|post|put|delete|patch)\(', src))
        n_router = len(re.findall(r'@router\.(get|post|put|delete|patch)\(', src))
        n_apirouter = len(re.findall(r'APIRouter\s*\(', src))
        n_include = len(re.findall(r'\.include_router\(', src))
        if n_app or n_router or n_apirouter or n_include:
            candidates.append((p, n_app, n_router, n_apirouter, n_include))

candidates.sort(key=lambda x: -(x[1]+x[2]))
print(f"  {'@app':>5} {'@router':>7} {'APIRouter':>9} {'include':>7}  file")
for p, a, r, ar, inc in candidates[:20]:
    print(f"  {a:>5} {r:>7} {ar:>9} {inc:>7}  {os.path.relpath(p, ROOT)}")

# 2) Verifier include_router dans api_server_with_static.py
head("2) include_router dans api_server_with_static.py")
api = os.path.join(ROOT, "api_server_with_static.py")
if os.path.exists(api):
    with open(api, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    for m in re.finditer(r'(?:from\s+(\S+)\s+import\s+(\w+(?:_router|_app)?))|(?:\.include_router\([^)]+\))', src):
        line = src.count("\n", 0, m.start()) + 1
        print(f"  L{line}: {m.group(0)[:120]}")

print("\nDone.")
