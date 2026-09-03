# -*- coding: utf-8 -*-
# nextones-fix-memo-verdict-reason-v6.py
# Patch [MEMO_VERDICT_REASON_FIX_V6] dans memo_generator.py
# Ajoute mapping humanise pour stop_loss dans _humanize_block_reason :
# - "position_loss_exceeds_threshold" : raison extraite de details.stop_loss.reason
# - "stop_loss" : fallback si blocked_by=stop_loss sans reason
# Idempotent, 100% ASCII, AST + py_compile validation

import ast
import os
import sys
import time
import shutil
import py_compile

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"
MARKER = "[MEMO_VERDICT_REASON_FIX_V6]"

# Ancre : la derniere ligne du dict HUMAN (la cle block_forced_exit)
ANCHOR = '"block_forced_exit":'

# Nouvelles entrees ajoutees apres la ligne block_forced_exit
NEW_ENTRIES = '''        # [MEMO_VERDICT_REASON_FIX_V6] stop-loss mapping
        "position_loss_exceeds_threshold": ("Stop-loss declenche",
                                          "Position en perte >= 8% - blocage achat supplementaire"),
        "stop_loss":                     ("Stop-loss declenche",
                                          "Position en perte >= 8% - blocage achat supplementaire"),
        "block_stop_loss":               ("Stop-loss declenche",
                                          "Position en perte >= 8% - blocage achat supplementaire"),
'''


def is_ascii_pure(s):
    return all(ord(ch) < 128 for ch in s)


def main():
    if not is_ascii_pure(NEW_ENTRIES):
        print("[FATAL] NEW_ENTRIES non-ASCII")
        sys.exit(2)

    if not os.path.exists(TARGET):
        print("[FATAL] Fichier introuvable: " + TARGET)
        sys.exit(2)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    # Idempotence
    if MARKER in src:
        print("[SKIP] " + MARKER + " deja present.")
        return

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[BACKUP] " + backup)

    # Trouver la ligne "block_forced_exit":
    idx = src.find(ANCHOR)
    if idx < 0:
        print("[FATAL] Ancre '" + ANCHOR + "' introuvable")
        sys.exit(2)

    # Aller a la fin du tuple (la ligne suivant ce que ferme la parenthese du tuple)
    # block_forced_exit s'etale sur 2 lignes :
    # "block_forced_exit":             ("...",
    #                                   "..."),
    # On cherche la } qui ferme le dict HUMAN apres ANCHOR
    close_brace_idx = src.find("}", idx)
    if close_brace_idx < 0:
        print("[FATAL] '}' fermant le dict HUMAN introuvable")
        sys.exit(2)

    # Remonter au debut de la ligne du }
    line_start_brace = src.rfind("\n", 0, close_brace_idx) + 1

    # Inserer NEW_ENTRIES juste avant la ligne du }
    new_src = src[:line_start_brace] + NEW_ENTRIES + src[line_start_brace:]

    # Ajouter le marker en commentaire au debut de la fonction
    func_marker_anchor = "    # [MEMO_VERDICT_REASON_FIX_V5]"
    if func_marker_anchor in new_src:
        new_src = new_src.replace(
            func_marker_anchor,
            "    # " + MARKER + "\n" + func_marker_anchor,
            1,
        )
    else:
        # Fallback : inserer apres le docstring de la fonction
        anchor_def = 'def _humanize_block_reason(blocked_by, details_json):'
        i = new_src.find(anchor_def)
        if i >= 0:
            # Trouver la fin du docstring
            ds_end = new_src.find('"""', new_src.find('"""', i) + 3)
            if ds_end > 0:
                line_end = new_src.find("\n", ds_end)
                new_src = (
                    new_src[: line_end + 1]
                    + "    # " + MARKER + "\n"
                    + new_src[line_end + 1 :]
                )

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
        print("[ROLLBACK] " + TARGET)
        sys.exit(4)

    print("[OK] " + MARKER + " applique avec succes.")
    print("[OK] 3 cles ajoutees au dict HUMAN :")
    print("     - position_loss_exceeds_threshold")
    print("     - stop_loss")
    print("     - block_stop_loss")
    print("     Toutes mappees vers 'Stop-loss declenche / Position en perte >= 8%'")


if __name__ == "__main__":
    main()
