# -*- coding: utf-8 -*-
# nextones-fix-cycle-id-paren-v1.py
# Fix parenthese mal placee L1284 execution_engine.py
# AVANT : json.dumps(risk_result, cycle_id))
# APRES : json.dumps(risk_result), cycle_id)
# Idempotent : skip si pattern correct deja present.
import os
import sys
import shutil
import time
import ast
import py_compile

PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
MARKER = "# [FIX_CYCLE_ID_PAREN_V1]"

BAD = "json.dumps(risk_result, cycle_id))"
GOOD = "json.dumps(risk_result), cycle_id)"

def main():
    if not os.path.exists(PATH):
        print("FAIL: not found", PATH)
        sys.exit(1)

    with open(PATH, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")

    if MARKER in text:
        print("SKIP: marker already present (idempotent)")
        return

    # Compte occurrences BAD
    n_bad = text.count(BAD)
    print("Occurrences BAD pattern '%s' : %d" % (BAD, n_bad))
    if n_bad == 0:
        print("FAIL: bad pattern not found - check if already fixed manually")
        sys.exit(1)
    if n_bad > 1:
        print("WARNING: %d occurrences found, will replace ALL" % n_bad)

    # Verifier que GOOD n'est pas deja la
    n_good = text.count(GOOD)
    print("Occurrences GOOD pattern '%s' : %d" % (GOOD, n_good))

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = PATH + ".bak." + ts
    shutil.copy2(PATH, bak)
    print("Backup:", bak)

    # Replace + marker
    new_text = text.replace(BAD, GOOD + "  " + MARKER)

    # Validate AST + py_compile via tmp
    tmp = PATH + ".tmp." + ts
    with open(tmp, "wb") as f:
        f.write(new_text.encode("utf-8"))
    try:
        ast.parse(open(tmp, "rb").read().decode("utf-8"))
        print("ast.parse OK")
        py_compile.compile(tmp, doraise=True)
        print("py_compile OK")
    except Exception as e:
        print("FAIL validation:", e)
        os.remove(tmp)
        sys.exit(1)

    # Write final (no BOM)
    os.replace(tmp, PATH)
    print("WRITE OK")

    # Verif
    with open(PATH, "rb") as f:
        verify_text = f.read().decode("utf-8-sig")
    print()
    print("Verif :")
    print("  BAD restants  :", verify_text.count(BAD))
    print("  GOOD presents :", verify_text.count(GOOD))
    print("  Marker present:", MARKER in verify_text)
    print()
    print("OK fix applied")

if __name__ == "__main__":
    main()
