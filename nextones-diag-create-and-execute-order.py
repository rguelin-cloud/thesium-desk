# -*- coding: utf-8 -*-
# Diag : signature et corps de create_and_execute_order
# Pour determiner ou injecter le cap qty SELL <= position detenue

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD, "execution_engine.py")

with open(EE, "r", encoding="utf-8-sig") as fh:
    lines = fh.read().split("\n")

print()
print("=" * 72)
print("DIAG create_and_execute_order : signature + zone INSERT")
print("=" * 72)

# Dump L1174 -> L1260 (signature + corps jusqu apres INSERT)
START = 1174 - 1
END = 1260
for i in range(START, min(END, len(lines))):
    print("  L%d: %s" % (i + 1, lines[i][:180].rstrip()))

print()
print("-" * 72)
print("Helper get_position_qty L1156")
print("-" * 72)
for i in range(1155, 1175):
    print("  L%d: %s" % (i + 1, lines[i][:180].rstrip()))

print()
print("=" * 72)
