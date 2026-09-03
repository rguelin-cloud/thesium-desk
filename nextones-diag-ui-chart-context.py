#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : extraire le contexte exact autour de :
  - app.js L1630-1760 (appel API + init Chart)
  - index.html L970-1010 (canvas portfolioChart + parent card)
"""
import os

APP_JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
INDEX_HTML = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html"


def dump(path, start, end):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    lines = data.decode("utf-8", errors="replace").split("\n")
    print("=" * 80)
    print(path + " L" + str(start) + "-L" + str(end))
    print("=" * 80)
    for i in range(start - 1, min(end, len(lines))):
        print("L" + str(i + 1).rjust(5) + " | " + lines[i])


def main():
    dump(APP_JS, 1630, 1760)
    print()
    dump(INDEX_HTML, 965, 1015)


if __name__ == "__main__":
    main()
