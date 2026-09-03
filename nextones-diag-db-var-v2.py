# -*- coding: utf-8 -*-
"""
Quick check : ou est definie la variable DB dans api_server.py ?
"""
import re

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

print("Definitions de 'DB' :")
for i, ln in enumerate(lines, start=1):
    if re.match(r"^\s*DB\s*=", ln):
        print("  L{:5d} | {}".format(i, ln.rstrip()))

print()
print("Usages de DB (sqlite3.connect ou similaire) - top 5 :")
hits = 0
for i, ln in enumerate(lines, start=1):
    if re.search(r"sqlite3\.connect\(\s*DB\b", ln):
        print("  L{:5d} | {}".format(i, ln.rstrip()[:140]))
        hits += 1
        if hits >= 5:
            break

print()
print("Context L3440-3445 (around c = sqlite3.connect(DB)) :")
for k in range(3435, 3445):
    if k <= len(lines):
        print("  L{:5d} | {}".format(k, lines[k-1].rstrip()[:140]))
