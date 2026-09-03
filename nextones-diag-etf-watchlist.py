# -*- coding: utf-8 -*-
# nextones-diag-etf-watchlist.py
# Affiche les blocs ETF watchlist dans universe_expansion_agent.py.

import os
import re

AGENT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py"


def main():
    if not os.path.exists(AGENT):
        print(f"FATAL {AGENT}")
        return
    content = open(AGENT, encoding="utf-8-sig").read()
    print(f"universe_expansion_agent.py : {len(content)} caracteres, "
          f"{content.count(chr(10))} lignes")

    # Recherche listes ETF connues
    for ticker in ("XLRE", "XLU", "XLY", "XLF", "XLP", "XLC", "XLB", "XLI", "XLK"):
        for m in re.finditer(re.escape(ticker), content):
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_end = content.find("\n", m.end())
            line = content[line_start:line_end]
            line_no = content[:m.start()].count("\n") + 1
            print(f"  L{line_no:4d} : {line.strip()[:120]}")

    print("\n--- Recherche du nom de variable WATCHLIST / ETF_LIST ---")
    for pat in (r"ETF_WATCHLIST\w*", r"ETF_TICKERS\w*", r"ETF_UNIVERSE\w*",
                r"ETF_LIST\w*", r"WATCHLIST_ETF\w*", r"ETF_CANDIDATES\w*",
                r"DEFAULT_ETFS?\b", r"SECTOR_ETFS?\b"):
        for m in re.finditer(pat, content):
            line_no = content[:m.start()].count("\n") + 1
            line_start = content.rfind("\n", 0, m.start()) + 1
            line_end = content.find("\n", m.end())
            line = content[line_start:line_end]
            print(f"  L{line_no:4d} : {line.strip()[:150]}")

    # Recherche du bloc qui contient XLRE pour voir la structure
    print("\n--- Bloc 30 lignes autour de XLRE ---")
    idx = content.find("XLRE")
    if idx >= 0:
        # 15 lignes avant + 15 apres
        before_lines = content[:idx].split("\n")
        start_line = max(0, len(before_lines) - 15)
        all_lines = content.split("\n")
        end_line = min(len(all_lines), len(before_lines) + 15)
        for i in range(start_line, end_line):
            marker = " <<<" if "XLRE" in all_lines[i] else ""
            print(f"  L{i+1:4d}{marker} | {all_lines[i]}")


if __name__ == "__main__":
    main()
