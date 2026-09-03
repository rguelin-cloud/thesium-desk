# -*- coding: utf-8 -*-
# Dump le corps de generate_ic_memo (L290-L370) pour voir l'ordre des sections.

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"

with open(API, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

start, end = 285, 372
for i in range(start - 1, min(end, len(lines))):
    line = lines[i].rstrip("\n")
    tag = ""
    if "full_markdown" in line:
        tag = "  <-- FULL_MD"
    elif "sections" in line and "=" in line:
        tag = "  <-- SECTIONS"
    elif "_build_" in line:
        tag = "  <-- BUILD"
    print(f"L{i+1:4d}  {line}{tag}")
