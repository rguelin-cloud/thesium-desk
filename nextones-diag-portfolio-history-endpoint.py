#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : extraire l'endpoint /api/portfolio/history actuel d'api_server.py
pour preparer le patch Phase 2 (period + benchmarks).
"""
import re

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"


def main():
    with open(TARGET, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8")
    lines = text.split("\n")

    print("=" * 70)
    print("Recherche tous les routes contenant 'portfolio/history' ou 'portfolio-history'")
    print("=" * 70)
    for i, line in enumerate(lines, 1):
        if "portfolio/history" in line.lower() or "portfolio_history" in line:
            print("L" + str(i).rjust(4) + " | " + line.rstrip()[:160])

    print()
    print("=" * 70)
    print("Dump L480-L560 (autour du supposed endpoint history)")
    print("=" * 70)
    for i in range(479, min(560, len(lines))):
        print("L" + str(i+1).rjust(4) + " | " + lines[i])


if __name__ == "__main__":
    main()
