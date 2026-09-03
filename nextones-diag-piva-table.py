#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : trouver le tableau 'Portfolio Ideal vs Actuel' (PIVA) dans index.html
et son rendu JS dans app.js.
"""
import os
import re

INDEX = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html"
APP_JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"


def scan(path, patterns):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    print("=" * 80)
    print(path)
    print("=" * 80)
    for pat in patterns:
        rx = re.compile(pat, re.IGNORECASE)
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                print("  [" + pat[:30] + "] L" + str(i) + " | " + line.rstrip()[:160])


def main():
    scan(INDEX, [
        r"Portfolio.*Ideal",
        r"Portfolio.*Id\xe9al",
        r"piva",
        r"poids.*cible",
        r"weight.*target",
        r"Cibles bas\xe9es",
        r"construction.*snapshot",
        r"target.*card",
    ])
    print()
    scan(APP_JS, [
        r"Portfolio.*Ideal",
        r"poids.*cible",
        r"construction.*snapshot",
        r"target.*weight",
        r"Memo IA",
        r"renderPiva",
        r"PIVA",
        r"NEUTRAL",
        r"BUFFER",
    ])


if __name__ == "__main__":
    main()
