# -*- coding: utf-8 -*-
"""[SHOW_ETF_HISTORY] affiche fetch_etf_history complet pour comprendre signature."""
from pathlib import Path
AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
txt = AGENT.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()
print("Lignes 180..230 :")
print("=" * 72)
for i in range(180, min(230, len(lines))):
    print(f"  L{i:4d}: {lines[i-1]}")
print("=" * 72)
# Aussi : fetch_crypto_history pour comparaison
print()
print("Lignes 140..200 (fetch_crypto_history) :")
for i in range(140, min(200, len(lines))):
    print(f"  L{i:4d}: {lines[i-1]}")
