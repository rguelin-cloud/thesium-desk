# -*- coding: utf-8 -*-
"""
Diag : structure de api_server_with_static.py
- Trouve tous les @app.<verb>(...) → liste routes
- Trouve toutes les def / async def
- Cherche pplx, cycle-snapshot, geo
- Vérifie présence du marker [PPLX_GEO_API_V1]
- Liste les autres fichiers .py qui pourraient contenir des routes pplx
"""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
target = ROOT / "api_server_with_static.py"

if not target.exists():
    print(f"[KO] {target} introuvable")
    raise SystemExit(1)

src = target.read_text(encoding="utf-8-sig", errors="replace")
print(f"=== {target.name} : {len(src):,} chars, {src.count(chr(10))} lignes ===\n")

# Routes
routes = re.findall(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']', src)
print(f"--- ROUTES ({len(routes)}) ---")
for verb, path in routes:
    print(f"  {verb.upper():6s} {path}")

# Recherche pplx + cycle-snapshot + geo
print("\n--- RECHERCHE pplx / geo / cycle-snapshot ---")
for kw in ["pplx", "geo", "cycle-snapshot", "cycle_snapshot", "Geo", "PPLX"]:
    cnt = src.count(kw)
    print(f"  '{kw}' : {cnt} occurrences")

# Marker
print("\n--- MARKERS ---")
for marker in ["[PPLX_GEO_API_V1]", "[PPLX_GEO_SNAPSHOT_ENRICH_V1]", "[PPLX_THESIS", "[PPLX_CRYPTO", "[PPLX_FACTOR"]:
    cnt = src.count(marker)
    print(f"  {marker} : {cnt}")

# Trouve la fin du fichier
print("\n--- DERNIERES 30 LIGNES ---")
lines = src.splitlines()
for i, line in enumerate(lines[-30:], start=len(lines)-30):
    print(f"  {i+1:5d} | {line}")

# Cherche autres fichiers .py contenant @app + pplx
print("\n--- AUTRES FICHIERS .py AVEC @app ET 'pplx' OU 'geo' ---")
for py in ROOT.glob("*.py"):
    if py.name == "api_server_with_static.py":
        continue
    try:
        s = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    if "@app." in s and ("pplx" in s.lower() or "geo" in s.lower() or "cycle-snapshot" in s):
        rts = re.findall(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']', s)
        print(f"\n  -> {py.name} ({len(s):,} chars)")
        for verb, path in rts:
            if "pplx" in path or "geo" in path or "cycle" in path:
                print(f"     {verb.upper():6s} {path}")

# Cherche aussi APIRouter / include_router
print("\n--- APIRouter / include_router ---")
for py in ROOT.glob("*.py"):
    try:
        s = py.read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    if "APIRouter" in s or "include_router" in s:
        rts = re.findall(r'(router|app)\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', s)
        relevant = [r for r in rts if "pplx" in r[2] or "geo" in r[2] or "cycle" in r[2]]
        if relevant or "include_router" in s:
            print(f"\n  -> {py.name}")
            inc = re.findall(r'include_router\([^)]+\)', s)
            for i in inc:
                print(f"     {i}")
            for r in relevant:
                print(f"     {r[1].upper():6s} {r[2]} (via {r[0]})")
