# -*- coding: utf-8 -*-
# Diag : dump precis de risk_pretrade.py L497-L625
# pour preparer l insertion du check stop-loss

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RP = os.path.join(PROD, "risk_pretrade.py")

with open(RP, "r", encoding="utf-8-sig") as fh:
    lines = fh.read().split("\n")

print()
print("=" * 72)
print("DIAG : dump L495-L625 (convergence + run_pretrade_checks)")
print("=" * 72)

START = 495 - 1
END = 625
for i in range(START, min(END, len(lines))):
    print("  L%d: %s" % (i + 1, lines[i][:200].rstrip()))

print()
print("=" * 72)
