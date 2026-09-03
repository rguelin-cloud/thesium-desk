#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [SMOOTHING_VARNAMES_FIX_V2]
# Corrige NameError introduit par SMOOTHING_FORCED_EXIT_BYPASS_V1 :
# - L753 : new_alloc.items() -> new_targets.items()
# - L758 : prev.get(...)     -> prev_targets.get(...)
# Modifications chirurgicales ligne par ligne, pas de regex de bloc.
# Backup .py.bak.<ts> + ast.parse + py_compile avant ecriture.

import os
import sys
import ast
import time
import shutil
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "portfolio_construction_agent_jalon2.py")
MARKER = "# [SMOOTHING_VARNAMES_FIX_V2]"

OLD_LINE_1 = "    for ticker, new_w in new_alloc.items():"
NEW_LINE_1 = "    for ticker, new_w in new_targets.items():  # [SMOOTHING_VARNAMES_FIX_V2]"

OLD_LINE_2 = "        prev_w = prev.get(ticker, 0.0)"
NEW_LINE_2 = "        prev_w = prev_targets.get(ticker, 0.0)  # [SMOOTHING_VARNAMES_FIX_V2]"


def main():
    if not os.path.isfile(TARGET):
        print("ERR : fichier introuvable :", TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("SKIP : marker deja present, patch idempotent")
        sys.exit(0)

    # Verifications pre-patch
    checks = []
    checks.append(("OLD_LINE_1 present", OLD_LINE_1 in src))
    checks.append(("OLD_LINE_2 present", OLD_LINE_2 in src))
    checks.append(("new_targets in signature", "def smooth_vs_previous(new_targets" in src))
    checks.append(("prev_targets in signature", "prev_targets:" in src))

    print("=== Pre-checks ===")
    for label, ok in checks:
        print("  ", "OK " if ok else "KO ", label)
    if not all(ok for _, ok in checks):
        print("ERR : pre-checks failed, abort")
        sys.exit(2)

    # Compte occurrences pour s assurer qu on touche qu un seul endroit
    n1 = src.count(OLD_LINE_1)
    n2 = src.count(OLD_LINE_2)
    print("=== Occurrences ===")
    print("  OLD_LINE_1 :", n1)
    print("  OLD_LINE_2 :", n2)
    if n1 != 1 or n2 != 1:
        print("ERR : occurrences != 1, ambigu, abort")
        sys.exit(3)

    # Substitution
    new_src = src.replace(OLD_LINE_1, NEW_LINE_1, 1)
    new_src = new_src.replace(OLD_LINE_2, NEW_LINE_2, 1)

    # Validation AST
    try:
        ast.parse(new_src)
        print("AST OK")
    except SyntaxError as e:
        print("ERR AST :", e)
        sys.exit(4)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("Backup :", bak)

    # Ecriture utf-8 sans BOM
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("Ecrit :", TARGET)

    # py_compile final
    try:
        py_compile.compile(TARGET, doraise=True)
        print("py_compile OK")
    except py_compile.PyCompileError as e:
        print("ERR py_compile :", e)
        sys.exit(5)

    print("=== DONE [SMOOTHING_VARNAMES_FIX_V2] ===")


if __name__ == "__main__":
    main()
