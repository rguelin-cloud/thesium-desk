# -*- coding: utf-8 -*-
# nextones-diag-memo-generator-humanize.py
# Marker : [DIAG_MEMO_GENERATOR_HUMANIZE]
#
# Dump complet du bloc _humanize / mapping blocked_by dans memo_generator.py
# pour comprendre exactement quoi patcher.

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(PROD, "memo_generator.py")

with open(MG, "r", encoding="utf-8-sig", errors="replace") as fh:
    lines = fh.read().split("\n")

print()
print("=" * 78)
print("DIAG memo_generator.py : bloc humanize/blocked_by autour L235")
print("-" * 78)

start = max(0, 220)
end = min(len(lines), 320)
for i in range(start, end):
    print("L%-4d | %s" % (i + 1, lines[i][:170].rstrip()))

print()
print("-" * 78)
print("Recherche fonctions clefs (def + risk_check + blocked_by + verdict)")
print("-" * 78)
for i, line in enumerate(lines, 1):
    s = line.strip()
    if s.startswith("def "):
        if any(k in s.lower() for k in ("risk", "humanize", "verdict", "block", "pretrade")):
            print("L%-4d | %s" % (i, line[:170].rstrip()))
    if "blocked_by" in line and "=" in line:
        print("L%-4d | %s" % (i, line[:170].rstrip()))
    if "_humanize" in line:
        print("L%-4d | %s" % (i, line[:170].rstrip()))

print()
print("=" * 78)
