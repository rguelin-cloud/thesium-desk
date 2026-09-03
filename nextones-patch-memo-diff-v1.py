# -*- coding: utf-8 -*-
# nextones-patch-memo-diff-v1.py
# ETAPE 2.3 : injecte la section "Ce qui a change" dans le memo IC.
#
# Strategie :
#   1. Ajoute un helper _build_diff_section(conn) en haut de memo_generator.py
#      (juste avant generate_ic_memo) qui :
#        - lit le dernier cycle_id (regime_log)
#        - appelle diff_engine.compute_cycle_diff() x 2 (J-1, J-7)
#        - retourne render_diff_markdown() ou un placeholder
#   2. Patch la liste 'sections' dans generate_ic_memo (L309-318) :
#      insere _build_diff_section(conn) en position 2 (apres _build_header)
#
# Marker : [ICMEMO_DIFF_V1]
# Idempotent : skippe si marker present.
# Securite : ast.parse + py_compile + backup + rollback auto.

import ast
import py_compile
import shutil
import datetime as dt

MEMO = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"
MARKER = "[ICMEMO_DIFF_V1]"

HELPER = '''
# ============================================================
# [ICMEMO_DIFF_V1] Section "Ce qui a change" (J-1 / J-7)
# ============================================================
def _build_diff_section(conn) -> str:
    """Construit la section markdown 'Ce qui a change' pour le memo IC.
    Lecture seule. Fail-safe : retourne un placeholder si diff_engine indispo
    ou si pas assez de cycles historiques.
    """
    try:
        from diff_engine import compute_cycle_diff, render_diff_markdown
    except ImportError as _e_icmd:
        return f"## Ce qui a change\\n\\n*Module diff_engine indisponible ({_e_icmd}).*\\n\\n"
    try:
        _row_icmd = conn.execute(
            "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not _row_icmd:
            return "## Ce qui a change\\n\\n*Aucun cycle disponible dans regime_log.*\\n\\n"
        _cid_icmd = _row_icmd[0] if not hasattr(_row_icmd, "keys") else _row_icmd["cycle_id"]
        _d1_icmd = compute_cycle_diff(conn, _cid_icmd, ref="J-1")
        _d7_icmd = compute_cycle_diff(conn, _cid_icmd, ref="J-7")
        return render_diff_markdown(_d1_icmd, _d7_icmd) + "\\n"
    except Exception as _e_icmd:
        return f"## Ce qui a change\\n\\n*Erreur calcul diff : {_e_icmd}*\\n\\n"
# ============================================================
'''

OLD_SECTIONS = '''    sections = [
        _build_header(date_str, ps),
        _build_macro_section(macro_result),'''

NEW_SECTIONS = '''    sections = [
        _build_header(date_str, ps),
        _build_diff_section(conn),  # [ICMEMO_DIFF_V1]
        _build_macro_section(macro_result),'''


def main():
    print(f"[patch] Reading {MEMO}")
    with open(MEMO, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[patch] Marker already present -> SKIP")
        return True

    # 1) Insere le helper juste avant 'def generate_ic_memo'
    needle = "def generate_ic_memo(conn:"
    pos = src.find(needle)
    if pos < 0:
        print(f"[patch] ERROR: cannot find '{needle}'")
        return False
    # Remonte au debut de la ligne
    line_start = src.rfind("\n", 0, pos) + 1
    new_src = src[:line_start] + HELPER.lstrip("\n") + "\n\n" + src[line_start:]
    print(f"[patch] Helper inserted before generate_ic_memo (line {src[:pos].count(chr(10))+1})")

    # 2) Insere _build_diff_section dans la liste 'sections'
    if OLD_SECTIONS not in new_src:
        print("[patch] ERROR: OLD_SECTIONS pattern not found")
        # Debug: show context
        for i, line in enumerate(new_src.split("\n")):
            if "sections = [" in line:
                print(f"  L{i+1}: {line}")
        return False
    new_src = new_src.replace(OLD_SECTIONS, NEW_SECTIONS, 1)
    print("[patch] sections list patched")

    # Validation
    try:
        ast.parse(new_src)
        print("[patch] ast.parse OK")
    except SyntaxError as e:
        print(f"[patch] ERROR ast.parse: {e}")
        # Snippet autour de l'erreur
        if e.lineno:
            ln = e.lineno
            for i, l in enumerate(new_src.split("\n")[max(0, ln-3):ln+3], start=max(1, ln-2)):
                print(f"  L{i:4d}  {l}")
        return False

    # Backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{MEMO}.bak_diff_{ts}"
    shutil.copy2(MEMO, bak)
    print(f"[patch] Backup -> {bak}")

    with open(MEMO, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print(f"[patch] Wrote {MEMO}")

    try:
        py_compile.compile(MEMO, doraise=True)
        print("[patch] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[patch] ERROR py_compile: {e}")
        shutil.copy2(bak, MEMO)
        print("[patch] Rolled back from backup")
        return False

    print("[patch] SUCCESS")
    return True


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("ETAPE 2.3 : patch memo_generator.py for diff section")
    print("=" * 60)
    ok = main()
    print()
    print("=" * 60)
    print("RESULT:", "SUCCESS" if ok else "FAILED")
    print("=" * 60)
    sys.exit(0 if ok else 1)
