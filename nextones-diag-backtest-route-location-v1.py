"""
Diag : trouver le fichier qui definit POST /api/backtest et POST/GET /api/backtest/presets.
Le diag-backtest-backend-v1 n'a rien trouve dans api_server_with_static.py => router separe.
ASCII pur.
"""
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def rd(p):
    with io.open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()

print("=" * 70)
print("DIAG BACKTEST ROUTE LOCATION")
print("=" * 70)

# Liste tous les .py a la racine et cherche dans chacun "/api/backtest"
hits = []
for f in sorted(os.listdir(ROOT)):
    if not f.endswith(".py"):
        continue
    full = os.path.join(ROOT, f)
    try:
        src = rd(full)
    except Exception:
        continue
    if "/api/backtest" not in src:
        continue
    lines = src.splitlines()
    hits.append((f, full, len(lines)))
    print(f"\n--- {f} ({len(lines)} lignes) ---")
    for i, ln in enumerate(lines, 1):
        if "/api/backtest" in ln or '"/api/backtest' in ln or "@router" in ln or "@app." in ln:
            if "backtest" in ln.lower() or "@router" in ln or "@app." in ln:
                # Filtre : on veut juste les decorators et lignes pertinentes
                if "/api/backtest" in ln or ("@" in ln and "backtest" in ln.lower()):
                    print(f"  L{i}: {ln.rstrip()[:160]}")

print("\n[Recap] Fichiers contenant '/api/backtest':")
for f, _, n in hits:
    print(f"  {f} ({n} lignes)")

# Cherche router include ou mount dans api_server_with_static.py
api = os.path.join(ROOT, "api_server_with_static.py")
if os.path.exists(api):
    src = rd(api)
    print("\n[include_router / mount] dans api_server_with_static.py :")
    for i, ln in enumerate(src.splitlines(), 1):
        s = ln.strip()
        if "include_router" in s or s.startswith("from ") and "backtest" in s.lower():
            print(f"  L{i}: {s[:160]}")

print("\nDONE")
