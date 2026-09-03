# -*- coding: utf-8 -*-
# nextones-diag-run-decision-cycle-flow.py
# Marker : [DIAG_RUN_DECISION_CYCLE_FLOW]
#
# Dump complet du flow run_decision_cycle + signatures convergence_engine

import os
import re

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print()
print("=" * 78)
print("DIAG : flow run_decision_cycle + signatures convergence")
print("=" * 78)

# --- 1) Body complet de run_decision_cycle
EE = os.path.join(PROD, "execution_engine.py")
with open(EE, "r", encoding="utf-8-sig", errors="replace") as fh:
    ee_lines = fh.read().split("\n")

print()
print("-" * 78)
print("RUN_DECISION_CYCLE (L1812+) - dump jusqu'au prochain def top-level")
print("-" * 78)

start = None
for i, line in enumerate(ee_lines):
    if re.match(r"def\s+run_decision_cycle\b", line):
        start = i
        break

if start is None:
    print("  [KO] def run_decision_cycle introuvable")
else:
    end = len(ee_lines)
    for j in range(start + 1, len(ee_lines)):
        stripped = ee_lines[j].lstrip()
        # next def top-level
        if (ee_lines[j].startswith("def ") or ee_lines[j].startswith("class ") or ee_lines[j].startswith("async def ")) and j > start + 1:
            end = j
            break
    print("  Lignes %d -> %d (total %d lignes)" % (start + 1, end, end - start))
    print()
    for k in range(start, end):
        print("  L%d: %s" % (k + 1, ee_lines[k][:170].rstrip()))

# --- 2) Imports en haut de execution_engine.py
print()
print("-" * 78)
print("IMPORTS DEBUT de execution_engine.py (30 premieres lignes)")
print("-" * 78)
for i in range(min(30, len(ee_lines))):
    print("  L%d: %s" % (i + 1, ee_lines[i][:170].rstrip()))

# Cherche imports convergence
print()
print("  Imports mentionnant convergence dans tout le fichier :")
for i, line in enumerate(ee_lines, 1):
    if ("import" in line and "convergence" in line.lower()) or "from convergence" in line:
        print("    L%d : %s" % (i, line.strip()[:140]))

# --- 3) Signatures convergence_engine
print()
print("-" * 78)
print("SIGNATURES convergence_engine.py : compute_convergence + save")
print("-" * 78)

CE = os.path.join(PROD, "convergence_engine.py")
with open(CE, "r", encoding="utf-8-sig", errors="replace") as fh:
    ce_lines = fh.read().split("\n")

for marker_line in (443, 619):  # compute_convergence, save_convergence_snapshot
    print()
    print("  Bloc autour L%d :" % marker_line)
    for k in range(max(0, marker_line - 2), min(len(ce_lines), marker_line + 20)):
        print("    L%d: %s" % (k + 1, ce_lines[k][:170].rstrip()))

# --- 4) Cherche l'endroit ideal d'insertion dans run_decision_cycle
# On veut : APRES tous les agents (macro/factor/micro/alt/crypto/exit produits),
# AVANT portfolio_construction_agent_jalon2 (qui lit convergence_snapshots).
print()
print("-" * 78)
print("ANCRES POSSIBLES dans run_decision_cycle :")
print("-" * 78)

if start is not None:
    body = ee_lines[start:end]
    for k, line in enumerate(body):
        L = start + k + 1
        # mentions interessantes
        if any(kw in line for kw in (
            "portfolio_construction", "build_targets", "construction_agent",
            "agent_results", "memo", "save_convergence", "convergence",
            "macro_agent", "factor_agent", "micro_agent", "alt_agent", "crypto_agent",
            "exit_agent", "thesis", "return {", "memo_id"
        )):
            print("    L%d: %s" % (L, line.strip()[:160]))

print()
print("=" * 78)
print("DIAG TERMINE")
print("=" * 78)
