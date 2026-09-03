#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : localiser le point d insertion d ordres pour patch anti-doublon
# Cherche les INSERT INTO orders et les fonctions create_*order* dans le repo

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

PATTERNS = [
    r"INSERT\s+INTO\s+orders",
    r"def\s+create_and_execute_order",
    r"def\s+create_order",
    r"def\s+_insert_order",
    r"def\s+place_order",
]

def main():
    print("=== Recherche patterns INSERT/create order ===")
    print()
    matches = {}
    for fname in os.listdir(ROOT):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(ROOT, fname)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for pat in PATTERNS:
                if re.search(pat, line, re.IGNORECASE):
                    matches.setdefault(fname, []).append((i, pat, line.rstrip()))

    for fname, hits in sorted(matches.items()):
        print(f"--- {fname} ({len(hits)} hits)")
        for i, pat, line in hits[:20]:
            print(f"  L{i} [{pat[:30]}] : {line[:140]}")
        print()

    print()
    print("=== Recherche execute_cycle endpoint ===")
    for fname in os.listdir(ROOT):
        if not fname.endswith(".py"):
            continue
        path = os.path.join(ROOT, fname)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        if "execute-cycle" in content or "execute_cycle" in content:
            for i, line in enumerate(content.splitlines(), 1):
                if "execute-cycle" in line or "execute_cycle" in line:
                    print(f"  {fname}:L{i} : {line.strip()[:140]}")

    print()
    print("=== DONE ===")


if __name__ == "__main__":
    main()
