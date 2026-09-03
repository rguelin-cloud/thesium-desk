"""
Diag : compter toutes les occurrences de 'pass; conn.row_factory'
       dans api_server_with_static.py et afficher leur contexte.
ASCII pur.
"""
import os
import re

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"

with open(TARGET, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

print("=== Occurrences de 'pass; conn.row_factory' ===\n")
hits = []
for i, line in enumerate(lines, 1):
    if "pass; conn.row_factory" in line:
        hits.append(i)
        start = max(0, i - 6)
        end = min(len(lines), i + 3)
        print("--- L{} ---".format(i))
        for j in range(start, end):
            mark = ">>" if (j + 1) == i else "  "
            print("{} L{}: {}".format(mark, j + 1, lines[j].rstrip()))
        print()

print("\nTotal occurrences : {}".format(len(hits)))

print("\n=== Occurrences de 'row_factory' (toutes) ===")
for i, line in enumerate(lines, 1):
    if "row_factory" in line:
        print("  L{}: {}".format(i, line.rstrip()))

print("\n=== Marker [ROW_FACTORY_CONSTRUCTION_V1] ===")
for i, line in enumerate(lines, 1):
    if "ROW_FACTORY_CONSTRUCTION_V1" in line:
        print("  L{}: {}".format(i, line.rstrip()))
