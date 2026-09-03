#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Affiche le bloc precis de calcul Total P&L dans api_server.py
# Cible : L210-L310 (autour de L241 total_pnl = total_market_value - total_cost)

import os
import sys

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

def main():
    if not os.path.isfile(TARGET):
        print("ERR :", TARGET)
        sys.exit(1)
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    print("Total lignes :", len(lines))
    print()
    print("=== Bloc L210-L310 (calcul total_pnl) ===")
    for i in range(210, min(310, len(lines))):
        ln = lines[i].rstrip()
        mark = ""
        if "total_pnl" in ln or "INITIAL_CAPITAL" in ln or "total_market_value" in ln:
            mark = "  <<<"
        print(f"L{i+1:4d}: {ln}{mark}")
    print()
    print("=== DONE ===")


if __name__ == "__main__":
    main()
