#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[TOTAL_PNL_NAV_BASED_V1]

Fix Total P&L : passer de (unrealized only) a (NAV - K_initial) pour inclure
le realized P&L des SELL passes.

AVANT :
    total_cost = sum(u[4] * u[5] for u in updates)
    total_pnl = total_market_value - total_cost
    INITIAL_CAPITAL = 1000000
    total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0

APRES :
    INITIAL_CAPITAL = 1000000
    total_pnl = total_value - INITIAL_CAPITAL  # NAV - K_initial inclut realized
    total_pnl_pct = (total_pnl / INITIAL_CAPITAL * 100) if INITIAL_CAPITAL > 0 else 0

Effet : -$21,077 (-2.11%) -> -$38,427 (-3.84%)

ASCII pur, idempotent (skip si marker present), backup .bak.<timestamp>,
AST + py_compile avant ecriture, anchor unique sur la ligne du calcul fautif.
"""
import ast
import os
import py_compile
import shutil
import sys
import time

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[TOTAL_PNL_NAV_BASED_V1]"

ANCHOR = "    total_pnl = total_market_value - total_cost\n"

REPLACEMENT = (
    "    # [TOTAL_PNL_NAV_BASED_V1] NAV-based: inclut realized P&L des SELL passes\n"
    "    # AVANT: total_pnl = total_market_value - total_cost  (unrealized only)\n"
    "    total_pnl = total_value - INITIAL_CAPITAL\n"
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

    count = src.count(ANCHOR)
    if count == 0:
        print("ERROR: anchor not found in " + TARGET)
        print("Looking for: " + repr(ANCHOR))
        sys.exit(3)
    if count > 1:
        print("ERROR: anchor not unique, found " + str(count) + " occurrences")
        print("Refusing to patch ambiguously")
        sys.exit(4)

    new_src = src.replace(ANCHOR, REPLACEMENT, 1)

    # The line that defines INITIAL_CAPITAL must still exist before our new
    # total_pnl line. The block kept the same ordering, only the formula moved.
    # We also keep the existing total_cost line above (unused now but harmless).

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

    # py_compile sanity
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
