#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[TOTAL_PNL_NAV_BASED_V1] (v2 du script, indent 8 espaces)

Fix Total P&L : passer de (unrealized only) a (NAV - K_initial) pour inclure
le realized P&L des SELL passes.

api_server.py L240-L244 :
    AVANT :
        total_cost = sum(u[4] * u[5] for u in updates)
        total_pnl = total_market_value - total_cost
        # PATCH: ...
        INITIAL_CAPITAL = 1000000
        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) ...

    APRES :
        total_cost = sum(u[4] * u[5] for u in updates)
        # [TOTAL_PNL_NAV_BASED_V1] NAV-based: inclut realized P&L des SELL passes
        # AVANT: total_pnl = total_market_value - total_cost  (unrealized only)
        total_pnl = total_value - INITIAL_CAPITAL
        # PATCH: ...
        INITIAL_CAPITAL = 1000000
        total_pnl_pct = ...

ATTENTION: INITIAL_CAPITAL est defini APRES total_pnl dans le code original.
Il faut donc DEPLACER INITIAL_CAPITAL=1000000 AVANT le calcul total_pnl.
"""
import ast
import os
import py_compile
import shutil
import sys
import time

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[TOTAL_PNL_NAV_BASED_V1]"

# Anchor : 5 lignes consecutives (indent 8 espaces)
ANCHOR = (
    "        total_cost = sum(u[4] * u[5] for u in updates)\n"
    "        total_pnl = total_market_value - total_cost\n"
    "        # PATCH: % rapporte au capital initial (NAV), pas au cost basis des positions ouvertes\n"
    "        INITIAL_CAPITAL = 1000000\n"
    "        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0\n"
)

REPLACEMENT = (
    "        total_cost = sum(u[4] * u[5] for u in updates)\n"
    "        # [TOTAL_PNL_NAV_BASED_V1] NAV-based: inclut realized P&L des SELL passes\n"
    "        # AVANT: total_pnl = total_market_value - total_cost  (unrealized only)\n"
    "        INITIAL_CAPITAL = 1000000\n"
    "        total_pnl = total_value - INITIAL_CAPITAL\n"
    "        total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0\n"
)


def read_utf8_sig(path):
    with open(path, "rb") as f:
        data = f.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8")


def write_utf8_no_bom(path, text):
    with open(path, "wb") as f:
        f.write(text.encode("utf-8"))


def main():
    if not os.path.isfile(TARGET):
        print("ERROR: target not found: " + TARGET)
        sys.exit(2)

    src = read_utf8_sig(TARGET)

    if MARKER in src:
        print("SKIP: marker already present, patch is idempotent")
        return

    # Le commentaire original contient 'rapporte' avec accent dans le source.
    # On essaie d'abord avec ASCII pur, sinon avec une recherche tolerante.
    if ANCHOR in src:
        new_src = src.replace(ANCHOR, REPLACEMENT, 1)
        print("ANCHOR matched (ASCII)")
    else:
        # Fallback: rechercher en ignorant le commentaire (qui peut contenir
        # des accents non-ASCII). On utilise une regex sur les 3 lignes
        # significatives.
        import re
        pat = re.compile(
            r"        total_cost = sum\(u\[4\] \* u\[5\] for u in updates\)\n"
            r"        total_pnl = total_market_value - total_cost\n"
            r"        # PATCH:[^\n]*\n"
            r"        INITIAL_CAPITAL = 1000000\n"
            r"        total_pnl_pct = \(total_pnl / INITIAL_CAPITAL \* 100\) if INITIAL_CAPITAL > 0 else 0\n"
        )
        matches = pat.findall(src)
        if len(matches) == 0:
            print("ERROR: anchor not found, neither exact nor regex")
            # Dump indices for debug
            for needle in ("total_pnl = total_market_value - total_cost",
                           "INITIAL_CAPITAL = 1000000",
                           "total_pnl_pct = (total_pnl / INITIAL_CAPITAL"):
                idx = src.find(needle)
                print("  " + needle[:60] + " : pos=" + str(idx))
            sys.exit(3)
        if len(matches) > 1:
            print("ERROR: regex anchor not unique, " + str(len(matches)) + " matches")
            sys.exit(4)
        new_src = pat.sub(REPLACEMENT.replace("\\", "\\\\"), src, count=1)
        print("ANCHOR matched (regex fallback)")

    # Validate Python syntax via AST
    try:
        ast.parse(new_src, filename=TARGET)
    except SyntaxError as e:
        print("ERROR: ast.parse failed after patch")
        print(str(e))
        sys.exit(5)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("BACKUP: " + backup)

    # Write
    write_utf8_no_bom(TARGET, new_src)
    print("WRITE OK: " + TARGET)

    # py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
        print("PY_COMPILE OK")
    except py_compile.PyCompileError as e:
        print("ERROR: py_compile failed, restoring backup")
        shutil.copy2(backup, TARGET)
        print(str(e))
        sys.exit(6)

    print("DONE " + MARKER)


if __name__ == "__main__":
    main()
