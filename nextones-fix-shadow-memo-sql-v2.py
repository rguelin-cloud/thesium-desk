# -*- coding: utf-8 -*-
"""
Fix bug v2 : le marker '# [SHADOW_MEMO_SQL_FIX_V1]' a ete injecte
DANS la chaine SQL, ce que SQLite refuse (# n'est pas un commentaire SQL).
Retire le marker de la chaine SQL et le laisse uniquement en commentaire Python.
"""
import os
import shutil
from datetime import datetime

SRC = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_memo_generator.py"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_V2 = "# [SHADOW_MEMO_SQL_FIX_V2]"

with open(SRC, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK_V2 in src:
    print("[SKIP] marker v2 deja present")
else:
    # Bloc actuel pollue
    OLD = '"LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id # [SHADOW_MEMO_SQL_FIX_V1] "'
    NEW = '"LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id "  ' + MARK_V2

    if OLD not in src:
        print("[ERR] bloc OLD introuvable - dump lignes LEFT JOIN :")
        for i, line in enumerate(src.split("\n"), 1):
            if "LEFT JOIN" in line:
                print("  L{} | {}".format(i, line.rstrip()))
    else:
        bak = SRC + ".bak." + TS
        shutil.copy2(SRC, bak)
        print("[BAK]", bak)
        new = src.replace(OLD, NEW, 1)
        with open(SRC, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] SQL nettoye, delta=", len(new) - len(src), "chars")

# Validation post-patch
import ast, py_compile
try:
    with open(SRC, "rb") as f:
        d = f.read()
    ast.parse(d.decode("utf-8"))
    py_compile.compile(SRC, doraise=True)
    print("[OK] py validation")
except Exception as e:
    print("[ERR] py validation:", e)

print()
print("Next : py -3.13 .\\shadow_memo_generator.py --force")
print("DONE")
