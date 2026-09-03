# -*- coding: utf-8 -*-
"""Dump signature complete de pplx_query (lignes 111 a 207) pour
construire le bon appel dans shadow_memo_generator."""
import os
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
client = os.path.join(ROOT, "pplx_client.py")
with open(client, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

print("=== pplx_query signature + body L111-L210 ===")
for k in range(110, min(210, len(lines))):
    print("  L{:5d} | {}".format(k+1, lines[k].rstrip()))

# Aussi : top imports + constantes (MODEL_*)
print()
print("=== Top imports + constantes (L1-L50) ===")
for k in range(0, min(50, len(lines))):
    s = lines[k]
    if s.strip().startswith("MODEL_") or s.strip().startswith("import") or s.strip().startswith("from") or "=" in s and s[0].isupper():
        print("  L{:5d} | {}".format(k+1, s.rstrip()))

# Pattern reel d'appel dans factor agent
print()
print("=== pplx_factor_agent : zone d'appel pplx_query ===")
fa = os.path.join(ROOT, "pplx_factor_agent.py")
with open(fa, "r", encoding="utf-8-sig", errors="replace") as f:
    fl = f.readlines()
for i, line in enumerate(fl, 1):
    if "pplx_query(" in line:
        # dump 25 lignes autour
        start = max(0, i-3)
        end = min(len(fl), i+25)
        print(">> Match at L{}".format(i))
        for k in range(start, end):
            print("  L{:5d} | {}".format(k+1, fl[k].rstrip()))
        break

print()
print("DONE")
