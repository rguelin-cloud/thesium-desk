#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : dump api_server.py L220-L310 pour confirmer l'etat exact du bloc P&L
et verifier la presence/absence du marker [TOTAL_PNL_NAV_BASED_V1].
"""
import os

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[TOTAL_PNL_NAV_BASED_V1]"


def main():
    with open(TARGET, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8")

    print("MARKER present in api_server.py ? " + str(MARKER in text))
    print("File size: " + str(len(text)) + " chars")
    print()
    print("=" * 70)
    print("Dump L220-L310 :")
    print("=" * 70)
    lines = text.split("\n")
    for i in range(219, min(310, len(lines))):
        print("L" + str(i+1).rjust(4) + " | " + lines[i])

    print()
    print("=" * 70)
    print("Recherche exacte anchor 'total_pnl = total_market_value - total_cost' :")
    print("=" * 70)
    for i, line in enumerate(lines, 1):
        if "total_pnl = total_market_value - total_cost" in line:
            print("FOUND at L" + str(i) + " : " + repr(line))

    print()
    print("Recherche exacte 'total_pnl = total_value - INITIAL_CAPITAL' :")
    for i, line in enumerate(lines, 1):
        if "total_pnl = total_value - INITIAL_CAPITAL" in line:
            print("FOUND at L" + str(i) + " : " + repr(line))


if __name__ == "__main__":
    main()
