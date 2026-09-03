"""Lire le reste de fill_simulator.py : simulate_fill signature + body + compute_slippage_bps."""
import os
PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\fill_simulator.py"
with open(PATH, "rb") as f:
    text = f.read().decode("utf-8", errors="replace")
lines = text.splitlines()
print(f"Total lines : {len(lines)}")
print()
# Tout afficher de la ligne 60 a la fin
for i, ln in enumerate(lines[60:], 61):
    print(f"  {i:3d}| {ln[:140]}")
