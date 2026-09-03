# -*- coding: utf-8 -*-
"""Affiche les lignes 50-135 de api_server.py pour voir les def refresh_*"""
from pathlib import Path

target = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
lines = target.read_text(encoding="utf-8-sig").splitlines()

for i in range(50, min(135, len(lines))):
    print(f"  L{i+1:4d} | {lines[i]}")
