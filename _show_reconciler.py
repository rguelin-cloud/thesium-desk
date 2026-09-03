"""
Affiche le code actuel du Reconciler v6.3 + son point d'integration.
Utile pour preparer le patch v6.4.
"""
import os
import re

ROOT = "."

# 1. Trouver le fichier Reconciler actuel
print("=" * 78)
print("1. FICHIERS RECONCILER / EXECUTION ENGINE")
print("=" * 78)
candidates = []
for root, dirs, files in os.walk(ROOT):
    # ignore venv / node_modules / git
    dirs[:] = [d for d in dirs if d not in ('.venv', 'venv', 'node_modules', '.git', '__pycache__', '.idea')]
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                    head = fh.read(3000)
                if any(k in head for k in ('OrderReconciler', 'class Reconciler', 'execution_engine', 'reconcile_orders')):
                    candidates.append(p)
            except Exception:
                pass

for c in candidates:
    size = os.path.getsize(c)
    mtime = os.path.getmtime(c)
    import datetime as dt
    print(f"  {c}  ({size} octets, modifie {dt.datetime.fromtimestamp(mtime)})")

# 2. Cherche le point d'integration dans le serveur API
print()
print("=" * 78)
print("2. POINT D'INTEGRATION DU RECONCILER (api_server_with_static.py)")
print("=" * 78)
api_file = "api_server_with_static.py"
if os.path.exists(api_file):
    with open(api_file, 'r', encoding='utf-8', errors='ignore') as fh:
        content = fh.read()
    # cherche les references
    for pat in (r'reconcile\w*', r'Reconciler', r'execution_engine', r'run_cycle', r'decision_cycle',
                r'PortfolioConstruction'):
        print(f"\n--- pattern: {pat} ---")
        for m in re.finditer(pat, content, re.IGNORECASE):
            # contexte: 80 chars autour
            start = max(0, m.start() - 40)
            end = min(len(content), m.end() + 100)
            line_num = content[:m.start()].count('\n') + 1
            snippet = content[start:end].replace('\n', ' \\n ')
            print(f"  L{line_num}: ...{snippet}...")
else:
    print(f"[{api_file} introuvable]")

# 3. Si on trouve le fichier execution_engine, dump les 50 premieres lignes + signatures
print()
print("=" * 78)
print("3. SIGNATURE DES FONCTIONS RECONCILER")
print("=" * 78)
for f in candidates:
    print(f"\n### {f}")
    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
        for i, line in enumerate(fh, 1):
            stripped = line.strip()
            if stripped.startswith('def ') or stripped.startswith('class ') or stripped.startswith('async def '):
                print(f"  L{i}: {stripped}")
