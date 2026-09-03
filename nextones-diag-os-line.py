# -*- coding: utf-8 -*-
# Dump bytes-by-bytes des lignes contenant _os pour identifier le caractere bizarre
import os

RPT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\risk_pretrade.py"

with open(RPT, "r", encoding="utf-8-sig") as fh:
    lines = fh.readlines()

print("Total lignes : %d" % len(lines))
print()

for i, l in enumerate(lines, 1):
    if "_os" in l:
        print("--- L%d ---" % i)
        print("RAW  : %r" % l)
        print("REPR : %r" % l)
        # Dump des codepoints des 80 premiers chars
        cps = [(c, ord(c)) for c in l[:120]]
        print("Codepoints (char, ord) :")
        for c, o in cps:
            if o > 127 or o < 32:
                print("  '%s' = U+%04X (non-ASCII)" % (c if c.isprintable() else "?", o))
        print()
