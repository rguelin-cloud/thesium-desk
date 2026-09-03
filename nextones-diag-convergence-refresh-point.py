# -*- coding: utf-8 -*-
# nextones-diag-convergence-refresh-point.py
# Marker : [DIAG_CONVERGENCE_REFRESH_POINT]
#
# But : trouver ou inserer convergence_engine.run() dans execute_cycle.
# On cherche :
#  1. Le fichier qui contient execute_cycle / run_decision_cycle
#  2. Les appels existants a convergence_engine
#  3. La signature de convergence_engine.run() (cycle_id requis ?)
#  4. L'ordre des etapes dans execute_cycle (agents -> ??? -> construction -> orders)
#  5. Comment cycle_id est genere (format 20260610-122322 ?)

import os
import re
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print()
print("=" * 78)
print("DIAG : ou inserer convergence_engine.run() dans execute_cycle")
print("=" * 78)

# --- 1) Fichiers candidats
CANDIDATES = [
    "api_server_with_static.py",
    "execution_engine.py",
    "portfolio_construction_agent_jalon2.py",
    "convergence_engine.py",
    "scheduler.py",
    "main.py",
]
existing = []
for f in CANDIDATES:
    p = os.path.join(PROD, f)
    if os.path.exists(p):
        existing.append(f)
        print("  [OK] %s (%d bytes)" % (f, os.path.getsize(p)))
    else:
        print("  [--] %s manquant" % f)

print()
print("-" * 78)
print("RECHERCHE 1 : 'def execute_cycle' / 'def run_decision_cycle' / 'execute-cycle' route")
print("-" * 78)

for f in existing:
    p = os.path.join(PROD, f)
    try:
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
    except Exception as e:
        print("  [ERR] %s : %s" % (f, e))
        continue
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        if re.search(r"def\s+(execute_cycle|run_decision_cycle|run_agents|run_cycle)\b", line):
            print("  %s L%d : %s" % (f, i, line.strip()[:120]))
        if "execute-cycle" in line and ("@app" in line or "@router" in line or ".post" in line):
            print("  %s L%d (route) : %s" % (f, i, line.strip()[:120]))

print()
print("-" * 78)
print("RECHERCHE 2 : import / usage de 'convergence_engine'")
print("-" * 78)

for f in existing:
    p = os.path.join(PROD, f)
    try:
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
    except Exception:
        continue
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        if "convergence_engine" in line or "convergence_snapshot" in line.lower():
            print("  %s L%d : %s" % (f, i, line.strip()[:120]))

print()
print("-" * 78)
print("RECHERCHE 3 : convergence_engine.py exports / signature run()")
print("-" * 78)

p = os.path.join(PROD, "convergence_engine.py")
if os.path.exists(p):
    with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
        content = fh.read()
    lines = content.split("\n")
    print("  Total lignes : %d" % len(lines))
    # Toutes les def top-level + class
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if indent == 0 and (stripped.startswith("def ") or stripped.startswith("class ")):
            print("  L%d : %s" % (i, stripped[:140]))
        if indent <= 4 and (stripped.startswith("def run") or stripped.startswith("def build") or stripped.startswith("def compute")):
            print("  L%d (indent=%d) : %s" % (i, indent, stripped[:140]))
    # Cherche cycle_id dans les signatures
    print()
    print("  Mentions de cycle_id dans convergence_engine.py :")
    for i, line in enumerate(lines, 1):
        if "cycle_id" in line:
            print("    L%d : %s" % (i, line.strip()[:140]))
            if i > 30:
                break
else:
    print("  [KO] convergence_engine.py absent")

print()
print("-" * 78)
print("RECHERCHE 4 : test_convergence existant (pour voir comment c'est appele)")
print("-" * 78)
for f in ("nextones-test-convergence-engine-v1.py", "test_convergence_engine.py"):
    p = os.path.join(PROD, f)
    if os.path.exists(p):
        print("  Fichier trouve : %s" % f)
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
        # Extraire les appels a convergence_engine.run / build
        for i, line in enumerate(content.split("\n"), 1):
            if "convergence_engine" in line and ("(" in line or "import" in line):
                print("    L%d : %s" % (i, line.strip()[:140]))

print()
print("-" * 78)
print("RECHERCHE 5 : flow execute_cycle (50 lignes autour de 'def execute_cycle')")
print("-" * 78)

# Cherche dans le fichier le + probable
for f in existing:
    p = os.path.join(PROD, f)
    try:
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
    except Exception:
        continue
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if re.search(r"def\s+execute_cycle\b", line):
            print()
            print("  >> %s : def execute_cycle a L%d" % (f, i + 1))
            print("  " + "-" * 70)
            # Dump 60 lignes apres
            for j in range(i, min(len(lines), i + 60)):
                print("  L%d: %s" % (j + 1, lines[j][:160].rstrip()))
            print("  " + "-" * 70)
            break

print()
print("-" * 78)
print("RECHERCHE 6 : generation du cycle_id (format)")
print("-" * 78)
for f in existing:
    p = os.path.join(PROD, f)
    try:
        with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
            content = fh.read()
    except Exception:
        continue
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        # Patterns probables pour cycle_id
        if re.search(r"cycle_id\s*=\s*", line) or re.search(r"strftime.*%Y%m%d", line):
            if "datetime" in line or "strftime" in line or "%Y" in line or "now" in line.lower():
                print("  %s L%d : %s" % (f, i, line.strip()[:140]))

print()
print("=" * 78)
print("DIAG TERMINE")
print("=" * 78)
