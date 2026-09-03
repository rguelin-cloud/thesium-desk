# -*- coding: utf-8 -*-
"""
Diag : trouve le point d'INSERT/UPDATE dans regime_log de execution_engine.py
afin d'y ajouter l'ecriture des colonnes equity_*, crypto_* depuis
regime_info['market'].
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(ROOT, "execution_engine.py")

with open(EE, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.splitlines()

print("=" * 78)
print("1. Toutes les references a regime_log dans execution_engine.py")
print("=" * 78)
for i, line in enumerate(lines, 1):
    if "regime_log" in line:
        print(f"  L{i:5} | {line.rstrip()[:170]}")

print()
print("=" * 78)
print("2. Pattern INSERT INTO regime_log (contexte +/- 5 lignes)")
print("=" * 78)
hits = []
for i, line in enumerate(lines, 1):
    if re.search(r"INSERT\s+(OR\s+\w+\s+)?INTO\s+regime_log", line, re.IGNORECASE):
        hits.append(i)
for h in hits:
    print(f"\n  --- INSERT regime_log a L{h} ---")
    a = max(0, h - 3)
    b = min(len(lines), h + 25)
    for k in range(a, b):
        print(f"  L{k+1:5} | {lines[k].rstrip()[:170]}")

print()
print("=" * 78)
print("3. Pattern UPDATE regime_log (au cas ou)")
print("=" * 78)
for i, line in enumerate(lines, 1):
    if re.search(r"UPDATE\s+regime_log", line, re.IGNORECASE):
        print(f"  L{i:5} | {line.rstrip()[:170]}")

print()
print("=" * 78)
print("4. Recherche du log [market_regime] (Phase 1) pour situer le contexte")
print("=" * 78)
for i, line in enumerate(lines, 1):
    if "market_regime" in line.lower() and ("[market" in line.lower() or "log_market_regime" in line):
        print(f"  L{i:5} | {line.rstrip()[:170]}")
