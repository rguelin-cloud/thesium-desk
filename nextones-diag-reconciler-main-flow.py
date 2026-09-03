# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-RECONCILER-MAIN-FLOW]
# Affiche les lignes 450-500 de nextones-broker-reconciler.py pour voir
# l'ordre complet des appels dans main().

import os

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "nextones-broker-reconciler.py")


def main():
    with open(TARGET, "r", encoding="utf-8-sig") as fh:
        lines = fh.read().splitlines()
    # cherche def main(
    main_start = None
    for i, ln in enumerate(lines):
        if ln.startswith("def main("):
            main_start = i
            break
    print(f"def main() trouve a L{main_start+1 if main_start else '?'}")
    print()
    print("=" * 70)
    print("Lines 450-510 :")
    print("=" * 70)
    for i in range(449, min(510, len(lines))):
        print(f"L{i+1:4d}: {lines[i]}")


if __name__ == "__main__":
    main()
