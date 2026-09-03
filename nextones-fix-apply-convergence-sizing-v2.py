# -*- coding: utf-8 -*-
# nextones-fix-apply-convergence-sizing-v2.py
# Patch [APPLY_CONVERGENCE_SIZING_FIX_V2] dans portfolio_construction_agent.py
#
# Bug v2 : le code utilise "float(row['sizing_multiplier'] or 1.0)"
#          mais 0.0 est falsy en Python -> 0.0 or 1.0 == 1.0
#          Donc TOUS les sizing_multiplier=0 (forced_exit) sont ecrases en 1.0
#
# Fix : utiliser "x if x is not None else 1.0" au lieu de "x or 1.0"
#       3 occurrences a corriger : 2 dans branche Row factory, 1 dans branche tuple
#
# Idempotent, 100% ASCII, AST + py_compile

import ast
import os
import sys
import time
import shutil
import py_compile

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
MARKER_V2 = "[APPLY_CONVERGENCE_SIZING_FIX_V2]"

# Occurrence 1 : L651 mult_map[t] = float(row["sizing_multiplier"] or 1.0)
OLD_1 = 'mult_map[t] = float(row["sizing_multiplier"] or 1.0)'
NEW_1 = 'mult_map[t] = float(row["sizing_multiplier"] if row["sizing_multiplier"] is not None else 1.0)  # [APPLY_CONVERGENCE_SIZING_FIX_V2]'

# Occurrence 2 : L653 (meta_map, premiere coord)
OLD_2 = '''meta_map[t] = (
                        float(row["sizing_multiplier"] or 1.0),'''
NEW_2 = '''meta_map[t] = (
                        float(row["sizing_multiplier"] if row["sizing_multiplier"] is not None else 1.0),  # [APPLY_CONVERGENCE_SIZING_FIX_V2]'''

# Occurrence 3 : branche tuple - mult_map et meta_map sur les lignes voisines
# Apres le fix V1 le code est :
#   t, mult, forced, drift = row[0], row[1], row[2], row[3]
#   mult_map[t] = float(mult or 1.0)
#   meta_map[t] = (float(mult or 1.0), "", int(forced or 0), int(drift or 0))
OLD_3a = 'mult_map[t] = float(mult or 1.0)'
NEW_3a = 'mult_map[t] = float(mult if mult is not None else 1.0)  # [APPLY_CONVERGENCE_SIZING_FIX_V2]'

OLD_3b = 'meta_map[t] = (float(mult or 1.0), "", int(forced or 0), int(drift or 0))'
NEW_3b = 'meta_map[t] = (float(mult if mult is not None else 1.0), "", int(forced or 0), int(drift or 0))  # [APPLY_CONVERGENCE_SIZING_FIX_V2]'


def is_ascii_pure(s):
    return all(ord(ch) < 128 for ch in s)


def main():
    for nm, s in [("NEW_1", NEW_1), ("NEW_2", NEW_2), ("NEW_3a", NEW_3a), ("NEW_3b", NEW_3b)]:
        if not is_ascii_pure(s):
            print("[FATAL] " + nm + " non-ASCII")
            sys.exit(2)

    if not os.path.exists(TARGET):
        print("[FATAL] Fichier introuvable: " + TARGET)
        sys.exit(2)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER_V2 in src:
        print("[SKIP] " + MARKER_V2 + " deja present.")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[BACKUP] " + backup)

    new_src = src
    changes = []

    # 1. Row factory mult_map
    if OLD_1 in new_src:
        new_src = new_src.replace(OLD_1, NEW_1, 1)
        changes.append("L651 mult_map[t] (Row factory)")
    else:
        print("[FATAL] OLD_1 introuvable : " + OLD_1)
        sys.exit(2)

    # 2. Row factory meta_map first arg
    if OLD_2 in new_src:
        new_src = new_src.replace(OLD_2, NEW_2, 1)
        changes.append("L653 meta_map (Row factory)")
    else:
        print("[FATAL] OLD_2 introuvable")
        # Dump pour debug
        idx = new_src.find("meta_map[t] = (")
        if idx >= 0:
            print("Contexte present autour de meta_map[t] = ( :")
            print(new_src[idx:idx + 200])
        sys.exit(2)

    # 3a. Tuple branche mult_map
    if OLD_3a in new_src:
        new_src = new_src.replace(OLD_3a, NEW_3a, 1)
        changes.append("mult_map (tuple branche)")
    else:
        print("[FATAL] OLD_3a introuvable")
        sys.exit(2)

    # 3b. Tuple branche meta_map
    if OLD_3b in new_src:
        new_src = new_src.replace(OLD_3b, NEW_3b, 1)
        changes.append("meta_map (tuple branche)")
    else:
        print("[FATAL] OLD_3b introuvable")
        sys.exit(2)

    # Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("[FATAL] AST : " + str(e))
        lines = new_src.split("\n")
        ln = e.lineno or 0
        for i in range(max(0, ln - 5), min(len(lines), ln + 5)):
            print(("  >> " if (i + 1) == ln else "     ") + str(i + 1) + ": " + lines[i])
        sys.exit(3)

    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)

    try:
        py_compile.compile(TARGET, doraise=True)
    except py_compile.PyCompileError as e:
        print("[FATAL] py_compile : " + str(e))
        shutil.copy2(backup, TARGET)
        print("[ROLLBACK]")
        sys.exit(4)

    print("[OK] " + MARKER_V2 + " applique.")
    for c in changes:
        print("  - " + c)
    print()
    print("Maintenant : 0.0 -> 0.0 (pas 1.0). Les 8 forced_exit auront scaled=0.")


if __name__ == "__main__":
    main()
