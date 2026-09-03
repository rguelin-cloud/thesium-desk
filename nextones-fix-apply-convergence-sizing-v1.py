# -*- coding: utf-8 -*-
# nextones-fix-apply-convergence-sizing-v1.py
# Patch [APPLY_CONVERGENCE_SIZING_FIX_V1] dans portfolio_construction_agent.py
#
# Bug : apply_convergence_sizing fait SELECT ... regime ... mais convergence_snapshots
#       n'a pas cette colonne. Le SELECT leve OperationalError, exception silencieuse,
#       fallback "return dict(allocations), {}" -> multipliers JAMAIS appliques.
#
# Fix : retirer "regime" du SELECT et du unpacking.
#       Stocker regime="" dans meta_map (compatibilite signature aval).
#
# Impact : sizing_multiplier=0 sera enfin applique aux 8 forced_exit du dernier cycle :
#          AAPL, AMZN, BTC, ETH, GOOGL, LINK, SOL, ZEC -> target_weight = 0
#
# Idempotent, 100% ASCII, AST + py_compile

import ast
import os
import sys
import time
import shutil
import py_compile

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent.py"
MARKER = "[APPLY_CONVERGENCE_SIZING_FIX_V1]"

# Anciens fragments a remplacer (textes exacts du fichier)
OLD_SELECT = '"SELECT ticker, sizing_multiplier, regime, forced_exit, drift "'
NEW_SELECT = '"SELECT ticker, sizing_multiplier, forced_exit, drift "'

OLD_ROW_REGIME = 'row["regime"] or "",'
NEW_ROW_REGIME = '"",  # [APPLY_CONVERGENCE_SIZING_FIX_V1] regime col absent du schema'

OLD_TUPLE_UNPACK = "t, mult, regime, forced, drift = row[0], row[1], row[2], row[3], row[4]"
NEW_TUPLE_UNPACK = "t, mult, forced, drift = row[0], row[1], row[2], row[3]"

OLD_META_TUPLE_FALLBACK = 'meta_map[t] = (float(mult or 1.0), regime or "", int(forced or 0), int(drift or 0))'
NEW_META_TUPLE_FALLBACK = 'meta_map[t] = (float(mult or 1.0), "", int(forced or 0), int(drift or 0))'


def is_ascii_pure(s):
    return all(ord(ch) < 128 for ch in s)


def main():
    if not all(is_ascii_pure(s) for s in [NEW_SELECT, NEW_ROW_REGIME, NEW_TUPLE_UNPACK, NEW_META_TUPLE_FALLBACK]):
        print("[FATAL] NEW fragments non-ASCII")
        sys.exit(2)

    if not os.path.exists(TARGET):
        print("[FATAL] Fichier introuvable: " + TARGET)
        sys.exit(2)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[SKIP] " + MARKER + " deja present.")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[BACKUP] " + backup)

    new_src = src
    changes = []

    # 1. Remplacer le SELECT
    if OLD_SELECT in new_src:
        new_src = new_src.replace(OLD_SELECT, NEW_SELECT, 1)
        changes.append("SELECT sans regime")
    else:
        print("[FATAL] OLD_SELECT introuvable : " + OLD_SELECT)
        sys.exit(2)

    # 2. Remplacer row["regime"] or "",
    if OLD_ROW_REGIME in new_src:
        new_src = new_src.replace(OLD_ROW_REGIME, NEW_ROW_REGIME, 1)
        changes.append('row["regime"] -> ""')
    else:
        print("[FATAL] OLD_ROW_REGIME introuvable : " + OLD_ROW_REGIME)
        sys.exit(2)

    # 3. Remplacer tuple unpack
    if OLD_TUPLE_UNPACK in new_src:
        new_src = new_src.replace(OLD_TUPLE_UNPACK, NEW_TUPLE_UNPACK, 1)
        changes.append("tuple unpack sans regime")
    else:
        print("[FATAL] OLD_TUPLE_UNPACK introuvable")
        sys.exit(2)

    # 4. Remplacer meta_tuple_fallback
    if OLD_META_TUPLE_FALLBACK in new_src:
        new_src = new_src.replace(OLD_META_TUPLE_FALLBACK, NEW_META_TUPLE_FALLBACK, 1)
        changes.append("meta_map tuple fallback")
    else:
        print("[FATAL] OLD_META_TUPLE_FALLBACK introuvable")
        sys.exit(2)

    # Inserer marker en commentaire dans la docstring de la fonction
    func_anchor = "def apply_convergence_sizing(conn, cycle_id, allocations):"
    if func_anchor in new_src:
        # Inserer le marker en commentaire juste apres la ligne def
        idx = new_src.find(func_anchor)
        line_end = new_src.find("\n", idx)
        comment = "\n    # " + MARKER
        new_src = new_src[:line_end] + comment + new_src[line_end:]
        changes.append("marker insere")

    # Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("[FATAL] AST parse: " + str(e))
        lines = new_src.split("\n")
        ln = e.lineno or 0
        for i in range(max(0, ln - 5), min(len(lines), ln + 5)):
            print(("  >> " if (i + 1) == ln else "     ") + str(i + 1) + ": " + lines[i])
        sys.exit(3)

    # Write
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)

    # py_compile
    try:
        py_compile.compile(TARGET, doraise=True)
    except py_compile.PyCompileError as e:
        print("[FATAL] py_compile: " + str(e))
        shutil.copy2(backup, TARGET)
        print("[ROLLBACK] restaure depuis " + backup)
        sys.exit(4)

    print("[OK] " + MARKER + " applique.")
    for c in changes:
        print("  - " + c)
    print()
    print("Impact attendu prochain cycle :")
    print("  8 forced_exit tickers (AAPL, AMZN, BTC, ETH, GOOGL, LINK, SOL, ZEC)")
    print("  -> target_weight_pct = 0 (au lieu de garder leur ancienne valeur)")


if __name__ == "__main__":
    main()
