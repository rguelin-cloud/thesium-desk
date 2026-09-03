#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : extrait les seuils actuels de _compute_regime_overlay() dans backtest_engine.py.
Affiche les constantes (vol/dd thresholds), la logique CALM/NORMAL/STRESS,
et les exposure tilts pour equity et crypto.
"""
import io, os, re, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "backtest_engine.py")

if not os.path.isfile(TARGET):
    print("[ERR] introuvable:", TARGET)
    sys.exit(1)

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.split("\n")

# Trouver _compute_regime_overlay
idx_start = -1
for i, ln in enumerate(lines):
    if "_compute_regime_overlay" in ln and "def " in ln:
        idx_start = i
        break

if idx_start < 0:
    print("[ERR] _compute_regime_overlay introuvable")
    sys.exit(1)

# Trouver la fin (prochaine def au meme niveau d'indentation ou EOF)
indent_def = len(lines[idx_start]) - len(lines[idx_start].lstrip())
idx_end = len(lines)
for j in range(idx_start + 1, len(lines)):
    ln = lines[j]
    if ln.strip() == "":
        continue
    cur_indent = len(ln) - len(ln.lstrip())
    if cur_indent <= indent_def and ln.lstrip().startswith(("def ", "class ", "@")):
        idx_end = j
        break

print("=" * 70)
print("FONCTION _compute_regime_overlay")
print("=" * 70)
print("Lignes:", idx_start + 1, "->", idx_end)
print("Taille:", idx_end - idx_start, "lignes")
print()

# Dump corps
body = "\n".join(lines[idx_start:idx_end])
print(body)

print()
print("=" * 70)
print("EXTRACTION CONSTANTES NUMERIQUES")
print("=" * 70)

# Cherche les nombres associes aux mots-cles
keywords = ["CALM", "NORMAL", "STRESS", "vol", "dd", "vix", "drawdown",
            "threshold", "tilt", "weight", "exposure", "Rf", "cash"]

for i in range(idx_start, idx_end):
    ln = lines[i]
    low = ln.lower()
    if any(k.lower() in low for k in keywords):
        # Cherche nombres flottants ou pourcentages
        nums = re.findall(r"[-+]?\d+\.?\d*", ln)
        if nums and not ln.strip().startswith("#"):
            print(f"L{i+1:4d}: {ln.rstrip()}")

print()
print("[DONE]")
