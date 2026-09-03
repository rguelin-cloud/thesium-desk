#!/usr/bin/env python3
# Affiche les lignes connect() dans risk_pretrade.py avec contexte
from pathlib import Path
src = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\risk_pretrade.py").read_text(encoding="utf-8-sig", errors="replace")
lines = src.splitlines()
for i, ln in enumerate(lines, 1):
    if "sqlite3.connect" in ln or "connect(" in ln:
        # contexte 3 avant/3 apres
        for j in range(max(0,i-4), min(len(lines), i+3)):
            marker = ">>> " if j == i-1 else "    "
            print(f"{marker}L{j+1}: {lines[j].rstrip()[:130]}")
        print("---")
