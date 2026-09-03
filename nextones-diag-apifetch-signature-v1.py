# -*- coding: utf-8 -*-
"""
Dump la fonction apiFetch() exacte dans app.js pour comprendre :
  - signature (args)
  - retour (Response vs JSON direct)
  - gestion du token Bearer
  - gestion du 401
"""
import os
import re

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

print("Total lines :", len(lines))
print()

# Cherche la definition de apiFetch
print("=== Lignes contenant 'apiFetch' (premieres 30) ===")
hits = []
for i, line in enumerate(lines, 1):
    if "apiFetch" in line:
        hits.append(i)
        if len(hits) <= 30:
            print("  L{:5d} | {}".format(i, line.rstrip()))
print()
print("Total occurrences apiFetch:", len(hits))
print()

# Dump la zone autour de la 1ere definition (probable async function apiFetch ou const apiFetch = )
print("=== Recherche definition (async function | const | function) ===")
for i, line in enumerate(lines, 1):
    s = line.strip()
    if ("async function apiFetch" in s
        or "function apiFetch" in s
        or s.startswith("const apiFetch")
        or s.startswith("var apiFetch")
        or s.startswith("let apiFetch")
        or "apiFetch =" in s):
        print(">> DEF found at L{}".format(i))
        # dump 50 lignes autour
        start = max(0, i - 2)
        end = min(len(lines), i + 50)
        for k in range(start, end):
            print("  L{:5d} | {}".format(k+1, lines[k].rstrip()))
        print()
        break

print("DONE")
