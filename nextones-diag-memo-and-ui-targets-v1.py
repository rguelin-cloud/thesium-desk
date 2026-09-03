# -*- coding: utf-8 -*-
"""
Diag combine pour preparer :
  A) Phase 2-ter : section "Regime de marche" dans memo IC PDF
  B) Observabilite UI : panneau "Regime Marche" dans le dashboard

Cherche :
  1. Tous les modules / fonctions qui generent un memo (recherche large)
  2. memo_generator(.py) : structure / sections existantes
  3. Comment regime_info est passe au memo (si deja)
  4. Pour UI : fichiers index.html / app.js / *.html dans frontend ou static
  5. Endpoints API exposes pour le regime (regime_log / market_regime_log)
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# ---------- A) MEMO IC ----------
print("=" * 78)
print("A.1 Recherche fichiers memo_*")
print("=" * 78)
for root, dirs, files in os.walk(ROOT):
    # Skip noisy dirs
    rel = os.path.relpath(root, ROOT)
    if any(p in rel for p in (".git", "__pycache__", ".bak", "node_modules", "venv", ".venv")):
        continue
    if rel.count(os.sep) > 3:
        continue
    for f in files:
        if "memo" in f.lower() and (f.endswith(".py") or f.endswith(".html")):
            print(f"  {os.path.relpath(os.path.join(root, f), ROOT)}")

print()
print("=" * 78)
print("A.2 Recherche fonctions def *memo* / def generate_memo / def build_memo")
print("=" * 78)
patterns = [r"def\s+\w*memo\w*\s*\(", r"def\s+generate_\w+\s*\(", r"def\s+build_memo"]
for root, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(root, ROOT)
    if any(p in rel for p in (".git", "__pycache__", ".bak", "node_modules", "venv", ".venv")):
        continue
    if rel.count(os.sep) > 3:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                lines = fh.read().splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for pat in patterns:
                if re.search(pat, line):
                    print(f"  {os.path.relpath(path, ROOT)}:L{i} | {line.rstrip()[:140]}")

print()
print("=" * 78)
print("A.3 memo_generator.py : sections existantes (recherche markdown headers)")
print("=" * 78)
mg = os.path.join(ROOT, "memo_generator.py")
if os.path.isfile(mg):
    with open(mg, "r", encoding="utf-8-sig") as f:
        content = f.read()
    print(f"  Taille : {len(content)} chars, {content.count(chr(10))} lignes")
    # Cherche les chaines "## " et "### " dans le code
    for i, line in enumerate(content.splitlines(), 1):
        if re.search(r'["\']##\s+', line) or re.search(r'["\']###\s+', line):
            print(f"  L{i:5} | {line.strip()[:160]}")
else:
    print("  memo_generator.py absent. Chercher ailleurs.")

print()
print("=" * 78)
print("A.4 Recherche 'regime_info' ou 'regime_log' dans memo*.py")
print("=" * 78)
for root, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(root, ROOT)
    if any(p in rel for p in (".git", "__pycache__", ".bak", "node_modules", "venv")):
        continue
    if rel.count(os.sep) > 3:
        continue
    for f in files:
        if "memo" in f.lower() and f.endswith(".py"):
            path = os.path.join(root, f)
            try:
                with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                    lines = fh.read().splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                if "regime_info" in line or "regime_log" in line or "market_regime" in line:
                    print(f"  {os.path.relpath(path, ROOT)}:L{i} | {line.rstrip()[:140]}")

# ---------- B) UI ----------
print()
print("=" * 78)
print("B.1 Recherche fichiers HTML et JS principaux")
print("=" * 78)
ui_dirs_candidates = []
for root, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(root, ROOT)
    if any(p in rel for p in (".git", "__pycache__", ".bak", "node_modules", "venv")):
        continue
    if rel.count(os.sep) > 2:
        continue
    for f in files:
        if f.endswith((".html",)) and ("index" in f.lower() or "dashboard" in f.lower() or "app" in f.lower()):
            print(f"  HTML : {os.path.relpath(os.path.join(root, f), ROOT)}")
            ui_dirs_candidates.append(root)

print()
print("=" * 78)
print("B.2 Recherche app.js / *.js principal dans dossiers UI")
print("=" * 78)
seen = set()
for d in ui_dirs_candidates:
    if d in seen:
        continue
    seen.add(d)
    for f in os.listdir(d):
        if f.endswith(".js"):
            full = os.path.join(d, f)
            size = os.path.getsize(full)
            print(f"  JS : {os.path.relpath(full, ROOT)}  ({size} bytes)")

print()
print("=" * 78)
print("B.3 Endpoints API exposes lies au regime (api_server*.py)")
print("=" * 78)
for root, dirs, files in os.walk(ROOT):
    rel = os.path.relpath(root, ROOT)
    if any(p in rel for p in (".git", "__pycache__", ".bak", "node_modules", "venv")):
        continue
    if rel.count(os.sep) > 2:
        continue
    for f in files:
        if not (f.endswith(".py") and ("api_server" in f or "api_" in f)):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as fh:
                lines = fh.read().splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if re.search(r"@\w+\.(get|post|put|delete)\s*\(", line):
                if "regime" in line.lower() or "market" in line.lower():
                    print(f"  {os.path.relpath(path, ROOT)}:L{i} | {line.rstrip()[:140]}")

print()
print("=" * 78)
print("B.4 Recherche app.mount StaticFiles (zone interdite pour ajouter route)")
print("=" * 78)
for f in os.listdir(ROOT):
    if not f.endswith(".py") or "api_server" not in f:
        continue
    path = os.path.join(ROOT, f)
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            lines = fh.read().splitlines()
    except Exception:
        continue
    for i, line in enumerate(lines, 1):
        if "app.mount" in line and "StaticFiles" in line:
            print(f"  {f}:L{i} | {line.rstrip()[:140]}")
            print("  -> Les routes ajoutees doivent etre AVANT cette ligne.")

print()
print("=" * 78)
print("FIN DIAG")
print("=" * 78)
