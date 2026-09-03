# -*- coding: utf-8 -*-
"""
DIAG : pourquoi /api/shadow/variants retourne 500
Verifie :
- imports sqlite3, json dans api_server.py
- variable DB_PATH (existe ? quel nom exact ?)
- pattern utilise dans une route existante qui marche (ex /api/regime/current)
- bloc SHADOW_API_V1 actuellement en place
"""
import os
import re

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(BASE, "api_server.py")


def header(t):
    print("=" * 78)
    print(t)
    print("=" * 78)


with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()
lines = src.split("\n")
print("Total lines :", len(lines))

# 1. Imports
header("[1] Imports en tete de api_server.py (top 50 lignes)")
for i, ln in enumerate(lines[:50], start=1):
    if ln.strip().startswith("import ") or ln.strip().startswith("from "):
        print("  L{:3d} | {}".format(i, ln.strip()))

# 2. Variables DB_PATH / db_path / DB / etc.
header("[2] Toutes occurrences de variables DB-path-like (top 100 lignes)")
db_candidates = []
for i, ln in enumerate(lines[:200], start=1):
    m = re.search(r'\b(DB_PATH|DB|db_path|DATABASE|database_path|DB_FILE)\s*=', ln)
    if m and not ln.strip().startswith("#"):
        db_candidates.append((i, ln.strip()))
for ln, txt in db_candidates[:20]:
    print("  L{:3d} | {}".format(ln, txt))

# 3. Usage de sqlite3.connect dans une route qui marche
header("[3] Pattern sqlite3.connect dans /api/regime/current ou similaire")
regime_lines = []
in_regime = False
for i, ln in enumerate(lines, start=1):
    if "/api/regime/current" in ln:
        in_regime = True
        regime_lines.append((i, ln))
        continue
    if in_regime:
        regime_lines.append((i, ln))
        if len(regime_lines) > 30:
            break
        if ln.startswith("@app.") or ln.startswith("def ") and len(regime_lines) > 5:
            break
for ln, txt in regime_lines[:25]:
    print("  L{:5d} | {}".format(ln, txt.rstrip()[:140]))

# 4. Toutes les occurrences de "sqlite3.connect(" (premiere)
header("[4] Pattern sqlite3.connect(...) - premiers 6 hits")
hits = []
for i, ln in enumerate(lines, start=1):
    if "sqlite3.connect" in ln:
        hits.append((i, ln.strip()))
for ln, txt in hits[:6]:
    print("  L{:5d} | {}".format(ln, txt[:140]))

# 5. Bloc SHADOW_API_V1 actuel
header("[5] Bloc [SHADOW_API_V1] tel qu'il est dans api_server.py")
begin_idx = None
end_idx = None
for i, ln in enumerate(lines, start=1):
    if "[SHADOW_API_V1] BEGIN" in ln and begin_idx is None:
        begin_idx = i
    if "[SHADOW_API_V1] END" in ln:
        end_idx = i

if begin_idx and end_idx:
    print("BEGIN L{} END L{}".format(begin_idx, end_idx))
    for k in range(begin_idx - 1, end_idx):
        print("  L{:5d} | {}".format(k + 1, lines[k]))
else:
    print("[ERR] markers non trouves")

# 6. Check imports JSON + sqlite3 explicites
header("[6] sqlite3 et json importes ?")
has_sqlite3 = any(re.match(r"^\s*import\s+sqlite3", ln) or
                  re.match(r"^\s*from\s+sqlite3\b", ln) for ln in lines)
has_json = any(re.match(r"^\s*import\s+json", ln) or
               re.match(r"^\s*from\s+json\b", ln) for ln in lines)
print("import sqlite3 :", has_sqlite3)
print("import json    :", has_json)

print()
print("=" * 78)
print("DIAG DONE")
print("=" * 78)
