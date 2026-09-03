# -*- coding: utf-8 -*-
"""
Affiche les lignes 1855-1900 de execution_engine.py
pour visualiser le bloc [BUILD_QTY1_V1] et son contexte.
"""
from pathlib import Path

EE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py")
lines = EE.read_text(encoding="utf-8-sig").splitlines()

print("=" * 90)
print(f"execution_engine.py - lignes 1855 a 1905")
print("=" * 90)
for i in range(1855, min(1906, len(lines) + 1)):
    if 1 <= i <= len(lines):
        print(f"{i:5d}  {lines[i-1]}")
print("=" * 90)
