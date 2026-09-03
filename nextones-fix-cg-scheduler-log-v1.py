"""
Fix : bug logging CG scheduler dans api_server.py L151+L153
{{e}} en f-string = accolade litterale echappee -> affiche '{e}' au lieu de la valeur.
Correction : {{e}} -> {e} et {{len(...)}} -> {len(...)}
"""
import os
import shutil
import sys
import time

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARK = "# [FIX_CG_SCHEDULER_LOG_V1]"
TS = time.strftime("%Y%m%d_%H%M%S")

# Les 2 lignes buggees exactes (extraites du diag)
OLD_1 = 'print(f"[scheduler] CG crypto refreshed: updated={{len(res.get(\'updated\', []))}}")'
NEW_1 = 'print(f"[scheduler] CG crypto refreshed: updated={len(res.get(\'updated\', []))}")  ' + MARK

OLD_2 = 'print(f"[scheduler] CG crypto refresh error: {{e}}")'
NEW_2 = 'print(f"[scheduler] CG crypto refresh error: {e}")  ' + MARK


def main():
    if not os.path.exists(F):
        print("[ERR] file not found:", F)
        return 2

    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    if MARK in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    # Verifie que les 2 lignes existent verbatim
    if OLD_1 not in src:
        print("[ERR] OLD_1 not found verbatim")
        print("      cherche:", repr(OLD_1))
        return 3
    if OLD_2 not in src:
        print("[ERR] OLD_2 not found verbatim")
        print("      cherche:", repr(OLD_2))
        return 4

    print("[OK] both lines found")

    new_src = src.replace(OLD_1, NEW_1, 1)
    new_src = new_src.replace(OLD_2, NEW_2, 1)

    if new_src == src:
        print("[ERR] no change produced")
        return 5

    # Validation syntaxique
    try:
        compile(new_src, F, "exec")
        print("[OK] compile() passes on patched source")
    except SyntaxError as e:
        print(f"[ERR] SyntaxError post-patch: {e}")
        return 6

    # Backup + write
    bak = F + ".bak." + TS
    shutil.copy2(F, bak)
    print("[BAK]", bak)

    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_src)
    print("[OK] written:", F)

    # Sanity check : les 2 nouvelles lignes doivent etre presentes
    with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
        check = fh.read()

    checks = [
        ("updated={len(res.get('updated', []))}", "L151 fix (updated=)"),
        ("CG crypto refresh error: {e}", "L153 fix (error=)"),
        (MARK, "marker present"),
    ]
    print()
    print("[POST-WRITE CHECKS]")
    for needle, label in checks:
        n = check.count(needle)
        tag = "OK" if n > 0 else "MISSING"
        print(f"  [{tag}] {label}: {n} occurrences")

    # Anti-regression : les vieilles chaines {{e}} et {{len ne doivent plus apparaitre
    # (au moins pas dans les 2 lignes en question)
    remaining_bad = check.count("CG crypto refresh error: {{e}}")
    remaining_bad2 = check.count("CG crypto refreshed: updated={{len")
    print(f"  [{'OK' if remaining_bad == 0 else 'STILL BUGGY'}] no '{{{{e}}}}' left in error line: {remaining_bad}")
    print(f"  [{'OK' if remaining_bad2 == 0 else 'STILL BUGGY'}] no '{{{{len(' left in updated line: {remaining_bad2}")

    print()
    print("[NEXT] Restart uvicorn")
    print("[NEXT] Au prochain refresh CG (toutes 2h), le vrai message d'erreur s'affichera")
    return 0


if __name__ == "__main__":
    sys.exit(main())
