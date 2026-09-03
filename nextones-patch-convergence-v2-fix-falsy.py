# -*- coding: utf-8 -*-
"""
[PATCH_CONV_V2_FIX_FALSY]

Bug critique : `0.0 or 1.0` retourne `1.0` en Python (0.0 falsy).
Donc les sizing_multiplier=0.0 (forced_exit) etaient lus comme 1.0 ->
aucune reduction d'allocation.

Fix : remplacer `float(row["xxx"] or 1.0)` par `float(row["xxx"] if row["xxx"] is not None else 1.0)`
Et pareil pour les ints `int(row["xxx"] or 0)`.

Cible : portfolio_construction_agent_jalon2.py
Marker : # [CONV_FALSY_FIX_V1]

Lance :
  py -3.13 nextones-patch-convergence-v2-fix-falsy.py
"""
import sys
import io
import os
import ast
import py_compile
import shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "portfolio_construction_agent_jalon2.py")
MARKER = "# [CONV_FALSY_FIX_V1]"

TS = datetime.now().strftime("%Y%m%d-%H%M%S")

# Anciennes valeurs (bug) -> nouvelles (fix)
REPLACEMENTS = [
    # Bloc row factory Row
    (
        '                    mult = float(row["sizing_multiplier"] or 1.0)\n'
        '                    cons = row["direction_consensus"] or ""\n'
        '                    fe = int(row["forced_exit"] or 0)\n'
        '                    dr = int(row["drift"] or 0)\n',
        '                    # [CONV_FALSY_FIX_V1] Eviter le piege 0.0 or 1.0 = 1.0\n'
        '                    _m = row["sizing_multiplier"]\n'
        '                    mult = float(_m) if _m is not None else 1.0\n'
        '                    cons = row["direction_consensus"] or ""\n'
        '                    _fe = row["forced_exit"]\n'
        '                    fe = int(_fe) if _fe is not None else 0\n'
        '                    _dr = row["drift"]\n'
        '                    dr = int(_dr) if _dr is not None else 0\n',
    ),
    # Bloc tuple fallback
    (
        '                    t, mult, cons, fe, dr = row[0], row[1], row[2], row[3], row[4]\n'
        '                    mult = float(mult or 1.0)\n'
        '                    fe = int(fe or 0)\n'
        '                    dr = int(dr or 0)\n',
        '                    t, mult, cons, fe, dr = row[0], row[1], row[2], row[3], row[4]\n'
        '                    # [CONV_FALSY_FIX_V1]\n'
        '                    mult = float(mult) if mult is not None else 1.0\n'
        '                    fe = int(fe) if fe is not None else 0\n'
        '                    dr = int(dr) if dr is not None else 0\n',
    ),
]


def main():
    if not os.path.exists(TARGET):
        print(f"[ERR] Fichier introuvable : {TARGET}")
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        c = f.read()

    if MARKER in c:
        print(f"[SKIP] {MARKER} deja present")
        sys.exit(0)

    # Backup
    bk = TARGET + f".bak-falsy-{TS}"
    shutil.copy2(TARGET, bk)
    print(f"[OK] Backup : {bk}")

    new_c = c
    applied = 0
    for old, new in REPLACEMENTS:
        if old in new_c:
            new_c = new_c.replace(old, new, 1)
            applied += 1
            print(f"[OK] Remplacement #{applied} applique")
        else:
            print(f"[WARN] Bloc #{applied + 1} introuvable, je passe")

    if applied == 0:
        print("[ERR] Aucun remplacement applique. Pas d'ecriture.")
        sys.exit(1)

    # Validation
    try:
        ast.parse(new_c)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError : {e}")
        sys.exit(1)

    tmp = TARGET + ".tmp-falsy"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_c)
    try:
        py_compile.compile(tmp, doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile : {e}")
        sys.exit(1)
    os.replace(tmp, TARGET)
    print(f"[OK] Ecrit : {os.path.basename(TARGET)}")
    print(f"[OK] {applied} remplacement(s) applique(s)")


if __name__ == "__main__":
    main()
