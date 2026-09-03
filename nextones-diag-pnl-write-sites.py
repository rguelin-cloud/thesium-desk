#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diag : trouver TOUS les points d'ecriture de total_pnl
- INSERT/UPDATE portfolio_history.total_pnl
- INSERT/UPDATE portfolio_state.total_pnl
- Tout calcul "total_pnl = ..."
- Verifier que le marker [TOTAL_PNL_NAV_BASED_V1] est bien present
"""
import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

PATTERNS = [
    re.compile(r"total_pnl\s*=", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO\s+portfolio_history", re.IGNORECASE),
    re.compile(r"UPDATE\s+portfolio_history", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO\s+portfolio_state", re.IGNORECASE),
    re.compile(r"UPDATE\s+portfolio_state", re.IGNORECASE),
]

MARKER = "[TOTAL_PNL_NAV_BASED_V1]"


def scan_file(path):
    hits = []
    try:
        with open(path, "rb") as f:
            data = f.read()
        if data.startswith(b"\xef\xbb\xbf"):
            data = data[3:]
        text = data.decode("utf-8", errors="replace")
    except Exception as e:
        return [("ERROR", 0, str(e))]
    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        for pat in PATTERNS:
            if pat.search(line):
                hits.append((pat.pattern[:40], i, line.rstrip()))
                break
    has_marker = MARKER in text
    return hits, has_marker, len(text)


def main():
    py_files = []
    for root, dirs, files in os.walk(ROOT):
        # skip backups and venv
        if ".bak." in root or "__pycache__" in root or ".venv" in root or "venv" in root:
            continue
        for f in files:
            if f.endswith(".py") and ".bak." not in f:
                py_files.append(os.path.join(root, f))

    print("Scanning " + str(len(py_files)) + " .py files in " + ROOT)
    print("=" * 80)

    files_with_hits = 0
    for p in py_files:
        result = scan_file(p)
        if isinstance(result, list):
            continue
        hits, has_marker, size = result
        if hits or has_marker:
            files_with_hits += 1
            rel = os.path.relpath(p, ROOT)
            tag = " [MARKER PRESENT]" if has_marker else ""
            print()
            print(">>> " + rel + tag + "  (" + str(size) + " bytes)")
            for pat, lineno, line in hits:
                print("  L" + str(lineno) + " [" + pat + "]")
                print("    " + line[:160])

    print()
    print("=" * 80)
    print("Files with hits: " + str(files_with_hits))
    print()
    print("MARKER " + MARKER + " check:")
    for p in py_files:
        try:
            with open(p, "rb") as f:
                if MARKER.encode("ascii") in f.read():
                    print("  PRESENT in " + os.path.relpath(p, ROOT))
        except Exception:
            pass


if __name__ == "__main__":
    main()
