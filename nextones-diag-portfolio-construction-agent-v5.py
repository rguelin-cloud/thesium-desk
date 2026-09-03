# -*- coding: utf-8 -*-
"""
[DIAG_PCA_V5] Dump du body de run_construction_agent + reperage precis
des points d'injection pour CONVERGENCE_SIZING_V1.

Sortie :
  1. Lignes L800-L1100 du fichier (tout le body de la fonction)
  2. Toutes les occurrences de : softmax_allocate, apply_caps_floors,
     smooth_vs_previous, write_targets, write_history, cycle_id, allocations
  3. Contexte +/- 3 lignes autour de chaque appel cle

Lance :
  py -3.13 nextones-diag-portfolio-construction-agent-v5.py
"""
import sys
import io
import os
import re

# Force UTF-8 stdout (Windows cp1252 safe)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"

if not os.path.exists(TARGET):
    print(f"[ERR] Fichier introuvable : {TARGET}")
    sys.exit(1)

with open(TARGET, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

total = len(lines)
print(f"[INFO] Fichier : {TARGET}")
print(f"[INFO] Total lignes : {total}")
print("=" * 80)

# --- 1. Dump body L800-L1100 (ou jusqu'a la fin)
START = 800
END = min(1100, total)
print(f"\n### BODY L{START}-L{END} ###\n")
for i in range(START - 1, END):
    print(f"{i+1:4d} | {lines[i].rstrip()}")

print("\n" + "=" * 80)

# --- 2. Occurrences des appels cles dans tout le fichier
KEYWORDS = [
    "softmax_allocate",
    "apply_caps_floors",
    "smooth_vs_previous",
    "write_targets",
    "write_history",
    "cycle_id",
    "allocations",
    "def run_construction_agent",
]

print("\n### OCCURRENCES KEYWORDS (tout le fichier) ###\n")
for kw in KEYWORDS:
    matches = []
    for i, ln in enumerate(lines):
        if kw in ln:
            matches.append((i + 1, ln.rstrip()))
    print(f"\n-- {kw} ({len(matches)} match) --")
    for lineno, content in matches:
        print(f"  L{lineno:4d} | {content}")

print("\n" + "=" * 80)

# --- 3. Contexte +/- 3 lignes autour des appels critiques
CRITICAL = ["softmax_allocate(", "apply_caps_floors(", "smooth_vs_previous("]
print("\n### CONTEXTE +/- 3 LIGNES AUTOUR DES APPELS CRITIQUES ###\n")
for kw in CRITICAL:
    for i, ln in enumerate(lines):
        if kw in ln:
            lo = max(0, i - 3)
            hi = min(total, i + 4)
            print(f"\n--- {kw} appel a L{i+1} ---")
            for j in range(lo, hi):
                marker = ">>>" if j == i else "   "
                print(f"  {marker} {j+1:4d} | {lines[j].rstrip()}")

print("\n" + "=" * 80)
print("[OK] Diag termine.")
