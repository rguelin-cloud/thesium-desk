# -*- coding: utf-8 -*-
# nextones-diag-humanize-block-reason.py
# Localise _humanize_block_reason dans memo_generator.py
# et affiche le dict de mapping actuel pour preparer l'enrichissement v6

import os

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG_PATH = os.path.join(PROD_ROOT, "memo_generator.py")


def main():
    print("=" * 70)
    print("DIAG _humanize_block_reason dans memo_generator.py")
    print("=" * 70)

    with open(MG_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")

    # 1. Trouver toutes les occurrences
    print("\n--- Occurrences _humanize_block_reason ---")
    for i, ln in enumerate(lines, 1):
        if "_humanize_block_reason" in ln or "humanize_block_reason" in ln:
            print("L" + str(i) + ": " + ln.rstrip())

    # 2. Trouver def et afficher 40 lignes
    print("\n--- Definition (40 lignes) ---")
    for i, ln in enumerate(lines, 1):
        if "def _humanize_block_reason" in ln or "def humanize_block_reason" in ln:
            for j in range(i - 1, min(len(lines), i + 50)):
                print("L" + str(j + 1) + ": " + lines[j].rstrip())
            print("...")
            break

    # 3. Chercher les markers existants memo
    print("\n--- Markers MEMO_VERDICT_REASON deja presents ---")
    for i, ln in enumerate(lines, 1):
        if "MEMO_VERDICT_REASON" in ln:
            print("L" + str(i) + ": " + ln.rstrip()[:150])


if __name__ == "__main__":
    main()
