# -*- coding: utf-8 -*-
"""
Dump le bloc autour de agents.py L469 pour comprendre la structure de la f-string.
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

AGENTS = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\agents.py")
src = AGENTS.read_text(encoding="utf-8-sig", errors="replace")
lines = src.splitlines()

# On dump L440-L500 + on remonte jusqu'au 'def ' precedent
start = max(0, 440 - 1)
end = min(len(lines), 500)

# Trouve def ancestor
def_line = None
for i in range(468, -1, -1):
    s = lines[i].lstrip()
    if s.startswith("def ") or s.startswith("class "):
        def_line = i
        break

print(f"=== def/class ancestor : L{def_line+1 if def_line is not None else '?'}")
if def_line is not None:
    print(f"    {lines[def_line].strip()[:120]}")

print(f"\n=== Bloc L{start+1}-L{end} (ligne cible = L469) ===\n")
for i in range(start, end):
    marker = " >>> " if i == 468 else "     "
    print(f"{marker}L{i+1:4d} | {lines[i]}")
