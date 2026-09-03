# -*- coding: utf-8 -*-
# Verifie si portfolio_construction_agent_jalon2.py contient le meme bug
# 'or 1.0' sur sizing_multiplier que celui qu'on vient de patcher dans
# portfolio_construction_agent.py

import os

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
CANDIDATES = [
    "portfolio_construction_agent.py",
    "portfolio_construction_agent_jalon2.py",
]

KEYWORDS = [
    "apply_convergence_sizing",
    "sizing_multiplier",
    "or 1.0",
    "[APPLY_CONVERGENCE_SIZING_FIX",
    "regime",
    "convergence_snapshots",
]


def scan(path):
    if not os.path.exists(path):
        print("[ABSENT] " + path)
        return
    print("\n" + "=" * 70)
    print(path + "  (taille=" + str(os.path.getsize(path)) + " bytes)")
    print("=" * 70)
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for i, ln in enumerate(f, 1):
            for kw in KEYWORDS:
                if kw in ln:
                    print("  L" + str(i) + " [" + kw + "] " + ln.rstrip()[:170])
                    break


def main():
    for c in CANDIDATES:
        scan(os.path.join(ROOT, c))


if __name__ == "__main__":
    main()
