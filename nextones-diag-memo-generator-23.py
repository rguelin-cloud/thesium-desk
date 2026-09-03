# -*- coding: utf-8 -*-
# Diag complet pour Etape 2.3 : ou est genere le full_markdown du memo IC ?
#
# Objectifs :
#   1. Localiser le module qui ecrit dans ic_memos.full_markdown
#   2. Identifier la fonction qui assemble le markdown
#   3. Trouver un point d'insertion stable pour notre section "Ce qui a change"
#   4. Verifier qu'on a acces au cycle_id et a conn dans ce scope
#
# Aucune modification, lecture seule.

import os
import re
import glob

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print("=" * 70)
print("1) Fichiers Python avec 'memo' dans le nom")
print("=" * 70)
for f in glob.glob(os.path.join(ROOT, "*.py")):
    name = os.path.basename(f)
    if "memo" in name.lower():
        size = os.path.getsize(f)
        print(f"  {name}  ({size} bytes)")

print()
print("=" * 70)
print("2) Recherche 'full_markdown' dans tous les .py du root")
print("=" * 70)
for f in glob.glob(os.path.join(ROOT, "*.py")):
    try:
        with open(f, "r", encoding="utf-8-sig") as fp:
            src = fp.read()
    except Exception:
        continue
    if "full_markdown" not in src:
        continue
    name = os.path.basename(f)
    for m in re.finditer(r"full_markdown", src):
        line = src[:m.start()].count("\n") + 1
        ctx_start = max(0, m.start() - 50)
        ctx_end = min(len(src), m.end() + 50)
        ctx = src[ctx_start:ctx_end].replace("\n", " | ")
        print(f"  {name}:L{line}  ...{ctx}...")

print()
print("=" * 70)
print("3) Recherche 'INSERT INTO ic_memos' / 'UPDATE ic_memos'")
print("=" * 70)
for f in glob.glob(os.path.join(ROOT, "*.py")):
    try:
        with open(f, "r", encoding="utf-8-sig") as fp:
            src = fp.read()
    except Exception:
        continue
    for m in re.finditer(r"(INSERT INTO ic_memos|UPDATE ic_memos|ic_memos\s*\()", src, re.IGNORECASE):
        line = src[:m.start()].count("\n") + 1
        ctx_start = max(0, m.start() - 80)
        ctx_end = min(len(src), m.end() + 200)
        name = os.path.basename(f)
        ctx = src[ctx_start:ctx_end]
        print(f"  {name}:L{line}")
        for cl in ctx.split("\n")[:6]:
            print(f"      {cl}")
        print()

print("=" * 70)
print("4) Recherche def generate_memo / build_memo / make_memo / *memo*")
print("=" * 70)
for f in glob.glob(os.path.join(ROOT, "*.py")):
    try:
        with open(f, "r", encoding="utf-8-sig") as fp:
            src = fp.read()
    except Exception:
        continue
    for m in re.finditer(r"^(\s*)(async\s+def|def)\s+(\w*memo\w*)\s*\(([^)]*)\)", src, re.MULTILINE):
        line = src[:m.start()].count("\n") + 1
        name = os.path.basename(f)
        print(f"  {name}:L{line:5d}  {m.group(2)} {m.group(3)}({m.group(4)[:80]})")

print()
print("=" * 70)
print("5) Si memo_generator.py existe, dump les 30 premieres lignes")
print("=" * 70)
mg_path = os.path.join(ROOT, "memo_generator.py")
if os.path.exists(mg_path):
    with open(mg_path, "r", encoding="utf-8-sig") as fp:
        lines = fp.readlines()
    for i, l in enumerate(lines[:50]):
        print(f"  L{i+1:4d}  {l.rstrip()}")
    print(f"  ... ({len(lines)} lignes au total)")
else:
    print("  memo_generator.py NOT FOUND")

print()
print("=" * 70)
print("6) Recherche dans execution_engine.py / run_decision_cycle de l'appel memo")
print("=" * 70)
exe_path = os.path.join(ROOT, "execution_engine.py")
if os.path.exists(exe_path):
    with open(exe_path, "r", encoding="utf-8-sig") as fp:
        src = fp.read()
    for m in re.finditer(r"(memo_generator|generate_memo|make_memo|build_memo|create_memo|_memo|memo_id)", src):
        line = src[:m.start()].count("\n") + 1
        ctx_start = max(0, m.start() - 30)
        ctx_end = min(len(src), m.end() + 80)
        ctx = src[ctx_start:ctx_end].replace("\n", " | ")
        print(f"  execution_engine.py:L{line}  {ctx[:200]}")
else:
    print("  execution_engine.py NOT FOUND in root")
