# -*- coding: utf-8 -*-
# nextones-diag-cycle-handler-name.py
# Trouve le nom EXACT du handler du Run Cycle dans api_server.py
# pour repatcher proprement le hook HISTORY_SNAPSHOT_V1.

import re

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

with open(API, "r", encoding="utf-8-sig") as f:
    src = f.read()

print("=" * 70)
print("1) Marker [EXECUTE_CYCLE_TRACE_V1] location")
print("=" * 70)
for m in re.finditer(r"\[EXECUTE_CYCLE_TRACE_V1\]", src):
    line = src[:m.start()].count("\n") + 1
    print(f"  found at line {line}")

print()
print("=" * 70)
print("2) Toutes les def/async def avec 'cycle' dans le nom")
print("=" * 70)
for m in re.finditer(r"^(\s*)(async\s+def|def)\s+(\w*cycle\w*)\s*\(([^)]*)\)", src, re.MULTILINE):
    line = src[:m.start()].count("\n") + 1
    indent = len(m.group(1))
    kind = m.group(2)
    name = m.group(3)
    args = m.group(4)[:80]
    print(f"  L{line:5d}  indent={indent:2d}  {kind} {name}({args})")

print()
print("=" * 70)
print("3) Routes FastAPI contenant 'cycle'")
print("=" * 70)
for m in re.finditer(r'@app\.(get|post|put|delete)\(\s*["\']([^"\']*cycle[^"\']*)["\']', src, re.IGNORECASE):
    line = src[:m.start()].count("\n") + 1
    method = m.group(1).upper()
    route = m.group(2)
    # Recupere le nom de fonction qui suit
    after = src[m.end():m.end() + 500]
    fn = re.search(r"(async\s+def|def)\s+(\w+)\s*\(", after)
    fname = fn.group(2) if fn else "?"
    print(f"  L{line:5d}  {method:6s} {route:40s} -> {fname}")

print()
print("=" * 70)
print("4) Fonction contenant [EXECUTE_CYCLE_TRACE_V1] (remontee jusqu'a la def)")
print("=" * 70)
trace_pos = src.find("[EXECUTE_CYCLE_TRACE_V1]")
if trace_pos > 0:
    # Remonte ligne par ligne pour trouver la def englobante
    before = src[:trace_pos]
    lines = before.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        l = lines[i]
        if re.match(r"^(\s*)(async\s+def|def)\s+(\w+)", l):
            indent = len(l) - len(l.lstrip())
            m = re.match(r"^(\s*)(async\s+def|def)\s+(\w+)\s*\(([^)]*)\)", l)
            if m:
                print(f"  L{i+1}  indent={indent}  def {m.group(3)}({m.group(4)[:80]})")
                # Affiche 3 lignes avant pour voir le decorateur
                for j in range(max(0, i-3), i):
                    print(f"  L{j+1}   {lines[j]}")
                break

print()
print("=" * 70)
print("5) Contexte autour du marker (40 lignes avant + 5 apres)")
print("=" * 70)
if trace_pos > 0:
    start = src.rfind("\n", 0, trace_pos - 2000)
    end = src.find("\n", trace_pos + 500)
    snippet = src[start:end]
    base_line = src[:start].count("\n") + 1
    for i, l in enumerate(snippet.split("\n")):
        print(f"  L{base_line+i:5d}  {l}")
