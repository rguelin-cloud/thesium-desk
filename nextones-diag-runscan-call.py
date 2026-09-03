# -*- coding: utf-8 -*-
"""
nextones-diag-runscan-call.py
Trouve TOP_N dans universe_expansion_agent.py + qui appelle run_scan() depuis l'API.
"""

import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

def main():
    section("1) TOP_N et constantes globales dans universe_expansion_agent.py")
    agent = os.path.join(ROOT, "universe_expansion_agent.py")
    with open(agent, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().splitlines()
    for i, line in enumerate(lines, 1):
        if re.match(r"^[A-Z_]+\s*[:=]", line):
            print(f"  L{i}: {line.strip()[:140]}")

    section("2) Corps de run_scan (lignes 677-816)")
    for i in range(676, min(816, len(lines))):
        print(f"  L{i+1}: {lines[i][:140]}")

    section("3) Cherche les fichiers qui appellent run_scan")
    for root, dirs, files in os.walk(ROOT):
        if any(x in root for x in ["__pycache__", ".venv", "venv", "node_modules", ".git"]):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                    c = f.read()
            except Exception:
                continue
            if "run_scan" in c and fn != "universe_expansion_agent.py":
                print(f"\n  {os.path.relpath(p, ROOT)}")
                for i, line in enumerate(c.splitlines(), 1):
                    if "run_scan" in line:
                        print(f"    L{i}: {line.strip()[:140]}")

    section("4) Cherche les routes /api/universe/* dans tous les .py")
    for root, dirs, files in os.walk(ROOT):
        if any(x in root for x in ["__pycache__", ".venv", "venv", "node_modules", ".git"]):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            try:
                with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                    c = f.read()
            except Exception:
                continue
            if "/api/universe" in c or re.search(r"@\w+\.(post|get).*universe", c):
                print(f"\n  {os.path.relpath(p, ROOT)}")
                for i, line in enumerate(c.splitlines(), 1):
                    if "/api/universe" in line or re.search(r"@\w+\.(post|get).*universe", line):
                        print(f"    L{i}: {line.strip()[:140]}")

if __name__ == "__main__":
    main()
