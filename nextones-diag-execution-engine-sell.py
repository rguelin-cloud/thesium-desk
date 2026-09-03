# -*- coding: utf-8 -*-
# nextones-diag-execution-engine-sell.py
# Diag : ou execution_engine.py decide side="SELL" et calcule qty
# Objectif : trouver le point d insertion pour le cap qty SELL <= position detenue.

import os
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD, "execution_engine.py")

print()
print("=" * 72)
print("DIAG execution_engine.py : logique side SELL + qty")
print("=" * 72)

with open(EE, "r", encoding="utf-8-sig") as fh:
    lines = fh.read().split("\n")

print()
print("  Fichier : %s (%d lignes)" % (EE, len(lines)))

# ------------------------------------------------------------------
# [1] Toutes les lignes contenant "SELL" string + contexte +/- 10
# ------------------------------------------------------------------
print()
print("-" * 72)
print("[1] Toutes les occurrences SELL avec contexte +/- 10 lignes")
print("-" * 72)

sell_indices = []
for i, ln in enumerate(lines):
    if '"SELL"' in ln or "'SELL'" in ln:
        sell_indices.append(i)

print()
print("  %d occurrences :" % len(sell_indices))
for idx in sell_indices:
    print()
    print("  --- Occurrence L%d ---" % (idx + 1))
    start = max(0, idx - 10)
    end = min(len(lines), idx + 11)
    for k in range(start, end):
        marker = " >>" if k == idx else "   "
        print("  %s L%d: %s" % (marker, k + 1, lines[k][:170].rstrip()))

# ------------------------------------------------------------------
# [2] Toutes les fonctions def avec leur ligne
# ------------------------------------------------------------------
print()
print("-" * 72)
print("[2] Fonctions definies dans execution_engine.py")
print("-" * 72)

for i, ln in enumerate(lines):
    s = ln.strip()
    if s.startswith("def ") or s.startswith("async def "):
        print("  L%d: %s" % (i + 1, s[:160]))

# ------------------------------------------------------------------
# [3] Logique target_qty / current_qty / qty (calcul du delta)
# ------------------------------------------------------------------
print()
print("-" * 72)
print("[3] Lignes calculant qty / target_qty / current_qty")
print("-" * 72)

kw_list = ["target_qty", "current_qty", "qty_to_trade", "delta_qty", "diff_qty"]
for i, ln in enumerate(lines):
    for kw in kw_list:
        if kw in ln:
            print("  L%d [%s]: %s" % (i + 1, kw, ln.strip()[:160]))
            break

# ------------------------------------------------------------------
# [4] Ou portfolio_positions est lu (pour connaitre la position)
# ------------------------------------------------------------------
print()
print("-" * 72)
print("[4] Lignes lisant portfolio_positions")
print("-" * 72)

for i, ln in enumerate(lines):
    if "portfolio_positions" in ln:
        print("  L%d: %s" % (i + 1, ln.strip()[:170]))

# ------------------------------------------------------------------
# [5] Ou INSERT INTO orders est fait
# ------------------------------------------------------------------
print()
print("-" * 72)
print("[5] INSERT INTO orders (point d insertion ordre)")
print("-" * 72)

for i, ln in enumerate(lines):
    low = ln.lower()
    if "insert" in low and "orders" in low:
        # Contexte +/- 5
        start = max(0, i - 5)
        end = min(len(lines), i + 12)
        print()
        print("  --- L%d ---" % (i + 1))
        for k in range(start, end):
            marker = " >>" if k == i else "   "
            print("  %s L%d: %s" % (marker, k + 1, lines[k][:170].rstrip()))

print()
print("=" * 72)
