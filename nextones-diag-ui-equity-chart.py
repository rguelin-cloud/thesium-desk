#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : trouver le chart equity dans l'UI (static files).
On cherche :
  - fetch('/api/portfolio/history')
  - canvas id chart equity
  - Chart.js init
"""
import os
import re

ROOTS = [
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\static",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\frontend",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\ui",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk",  # fallback
]

PATTERNS = [
    re.compile(r"/api/portfolio/history", re.IGNORECASE),
    re.compile(r"equity", re.IGNORECASE),
    re.compile(r"new\s+Chart\(", re.IGNORECASE),
    re.compile(r"<canvas[^>]*id\s*=", re.IGNORECASE),
]

EXTS = (".html", ".js", ".css")


def main():
    files_scanned = 0
    hits_per_file = {}
    for root in ROOTS:
        if not os.path.isdir(root):
            continue
        for r, dirs, files in os.walk(root):
            if ".bak." in r or "__pycache__" in r or ".venv" in r or "node_modules" in r:
                continue
            for f in files:
                if not f.lower().endswith(EXTS):
                    continue
                if ".bak." in f:
                    continue
                p = os.path.join(r, f)
                try:
                    with open(p, "rb") as fp:
                        data = fp.read()
                    if data.startswith(b"\xef\xbb\xbf"):
                        data = data[3:]
                    text = data.decode("utf-8", errors="replace")
                except Exception:
                    continue
                files_scanned += 1
                file_hits = []
                lines = text.split("\n")
                for i, line in enumerate(lines, 1):
                    for pat in PATTERNS:
                        if pat.search(line):
                            file_hits.append((pat.pattern[:35], i, line.rstrip()))
                            break
                if file_hits:
                    hits_per_file[p] = file_hits
        # do not break: scan ROOTS in order, but each path is distinct
        break  # only first existing root, else duplicates

    print("Files scanned: " + str(files_scanned))
    print("Files with hits: " + str(len(hits_per_file)))
    print("=" * 80)
    for p, hits in hits_per_file.items():
        print()
        print(">>> " + p)
        for pat, lineno, line in hits[:40]:
            print("  L" + str(lineno) + " [" + pat + "] " + line[:140])
        if len(hits) > 40:
            print("  ... " + str(len(hits) - 40) + " more")


if __name__ == "__main__":
    main()
