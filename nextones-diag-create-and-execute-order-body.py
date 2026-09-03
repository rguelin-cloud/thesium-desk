#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : affiche le corps complet de create_and_execute_order
# (execution_engine.py L1174 -> debut, jusqu apres l INSERT INTO orders L1264)
# pour preparer le patch anti-doublon

import os
import sys
import re

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

def main():
    if not os.path.isfile(TARGET):
        print("ERR introuvable :", TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    print("Total lignes :", len(lines))
    print()

    # Find def create_and_execute_order
    start_line = None
    for i, ln in enumerate(lines, 1):
        if re.search(r"^def\s+create_and_execute_order\b", ln):
            start_line = i
            break

    if start_line is None:
        print("ERR : def create_and_execute_order introuvable")
        sys.exit(2)

    print(f"=== def create_and_execute_order at L{start_line} ===")
    print()

    # Print until line 100 after start OR next top-level def
    end_line = min(start_line + 130, len(lines))
    for i in range(start_line, end_line):
        ln = lines[i - 1].rstrip()
        marker = ""
        if "INSERT INTO orders" in ln:
            marker = "  <<< INSERT INTO orders"
        if re.match(r"^def\s+\w", ln) and i > start_line:
            print(f"L{i:5d}: {ln}  <<< NEXT TOP-LEVEL DEF, stop")
            break
        print(f"L{i:5d}: {ln}{marker}")

    print()
    print("=== Recherche markers existants ===")
    full = "".join(lines)
    for marker in ["[ANTI_DUPLICATE_ORDER_V1]", "[RISK_V2_WIRED",
                   "[SELL_OVERSHOOT_CAP_V1]", "[STOP_LOSS_BLOCK"]:
        n = full.count(marker)
        print(f"  {marker} : {n}")

    print()
    print("=== DONE ===")


if __name__ == "__main__":
    main()
