# -*- coding: utf-8 -*-
"""
Diag precis : montre la structure de generate_ic_memo() pour identifier
le point d'injection de la section market_regime.

Egalement : montre les 30 premieres lignes apres "## Pre-trade Controls"
et l'ordre des sections dans le memo final.
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(ROOT, "memo_generator.py")

with open(MG, "r", encoding="utf-8-sig") as f:
    content = f.read()
lines = content.splitlines()

print("=" * 78)
print("1. Bornes de la fonction generate_ic_memo")
print("=" * 78)
start = None
for i, line in enumerate(lines):
    if re.match(r"def\s+generate_ic_memo\s*\(", line):
        start = i
        break
end = len(lines)
if start is not None:
    indent = len(lines[start]) - len(lines[start].lstrip())
    for j in range(start + 1, len(lines)):
        if re.match(r"^\s*def\s+\w+", lines[j]):
            j_indent = len(lines[j]) - len(lines[j].lstrip())
            if j_indent <= indent:
                end = j
                break
    print(f"  L{start+1} a L{end} ({end-start} lignes)")
else:
    print("  generate_ic_memo non trouvee")

print()
print("=" * 78)
print("2. Corps de generate_ic_memo (tronque a 120 lignes)")
print("=" * 78)
if start is not None:
    for i in range(start, min(end, start + 120)):
        marker = ""
        l = lines[i]
        if "_section_" in l or "_format_" in l or "_build_" in l:
            marker = "  <-- helper call"
        if "sections.append" in l or "sections =" in l or "sections.extend" in l:
            marker = "  <-- sections list"
        if re.search(r'"##\s+', l):
            marker = "  <-- inline section header"
        if "INSERT" in l.upper() and "memos" in l.lower():
            marker = "  <-- INSERT memo"
        print(f"  L{i+1:5} | {l.rstrip()[:170]}{marker}")

print()
print("=" * 78)
print("3. Toutes les fonctions _section_ ou _format_ definies (helpers)")
print("=" * 78)
for i, line in enumerate(lines, 1):
    if re.match(r"def\s+_(section|format|build)_\w+\s*\(", line):
        print(f"  L{i:5} | {line.rstrip()[:170]}")

print()
print("=" * 78)
print("4. Noms des sections markdown dans l'ordre")
print("=" * 78)
for i, line in enumerate(lines, 1):
    m = re.search(r'"(##\s+[^"]{1,80})"', line)
    if m:
        print(f"  L{i:5} | {m.group(1)}")

print()
print("=" * 78)
print("5. Recherche du point d'insertion ideal : apres Pre-trade Controls,")
print("   avant Convergence Engine ou avant Audit Trail")
print("=" * 78)
for i, line in enumerate(lines, 1):
    if "Pre-trade Controls" in line or "RISK_V2" in line and "##" in line:
        print(f"  L{i:5} | {line.rstrip()[:170]}")
    if "Convergence Engine" in line and "##" in line:
        print(f"  L{i:5} | {line.rstrip()[:170]}")
    if "Audit Trail" in line and "##" in line:
        print(f"  L{i:5} | {line.rstrip()[:170]}")
