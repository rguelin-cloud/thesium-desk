# -*- coding: utf-8 -*-
# [FIND_CONSTRUCTION_ENDPOINT_V1]
# Cherche dans api_server_with_static.py les endpoints de construction
# (run, snapshot, targets) + leur signature pour savoir lequel relance
# la construction.
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")

with open(API, "r", encoding="utf-8-sig") as f:
    src = f.read()

print("=" * 72)
print("  Endpoints /api/construction/* trouves")
print("=" * 72)

# Cherche tous les endpoints construction
pat = re.compile(
    r"@app\.(post|get|put|delete)\([\"'](/api/construction[^\"']*)[\"'].*?\n(async\s+)?def\s+(\w+)\s*\(([^)]*)\)",
    re.DOTALL,
)
for m in pat.finditer(src):
    verb = m.group(1).upper()
    path = m.group(2)
    fname = m.group(4)
    args = m.group(5).strip().replace("\n", " ")[:80]
    print("  {:6s} {:45s} -> def {}({}) ".format(verb, path, fname, args))

print()
print("=" * 72)
print("  Endpoints /api/cycle/* / /api/run/* / /api/execute/*")
print("=" * 72)
pat2 = re.compile(
    r"@app\.(post|get|put|delete)\([\"'](/api/(?:cycle|run|execute|decision)[^\"']*)[\"'].*?\n(async\s+)?def\s+(\w+)",
    re.DOTALL,
)
for m in pat2.finditer(src):
    verb = m.group(1).upper()
    path = m.group(2)
    fname = m.group(4)
    print("  {:6s} {:45s} -> def {}".format(verb, path, fname))

print()
print("=" * 72)
print("  Endpoints universe (pour memoire)")
print("=" * 72)
pat3 = re.compile(
    r"@app\.(post|get|put|delete)\([\"'](/api/universe[^\"']*)[\"'].*?\n(async\s+)?def\s+(\w+)",
    re.DOTALL,
)
for m in pat3.finditer(src):
    verb = m.group(1).upper()
    path = m.group(2)
    fname = m.group(4)
    print("  {:6s} {:45s} -> def {}".format(verb, path, fname))
