"""
nextones-install-shadow-hook-v1.py - Phase 9.4
Patch chirurgical api_server.py : insere appel shadow_hook.run_shadow_cycle()
juste avant le return final de execute_cycle (L897).

Idempotent (skip si marker [SHADOW_HOOK_V1] present).
Backup .py.bak.<timestamp>.
Validation ast.parse + py_compile post-patch.
"""
import os
import sys
import time
import ast
import py_compile
import shutil

FPATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
MARKER = "[SHADOW_HOOK_V1] BEGIN"

# Anchor : derniere ligne du bloc HISTORY_SNAPSHOT_V1 (fin du commentaire)
ANCHOR = "        # ===== /[HISTORY_SNAPSHOT_V1] =====\n        return {\"success\": True, \"cycle_result\": result}"

# Bloc a inserer ENTRE les 2 lignes du anchor (indentation 8 espaces)
HOOK_BLOCK = '''        # ===== [SHADOW_HOOK_V1] BEGIN =====
        # Phase 9.4 - Jalon 9 Shadow Overlap : engine + fills + diff_log post-cycle
        # Safe-fail : toute exception loggee, ne casse JAMAIS le return.
        try:
            import shadow_hook as _sh_v1
            _sh_res_v1 = _sh_v1.run_shadow_cycle(
                db_path=r"DB_PATH_PLACEHOLDER",
                cycle_id=_cid_hsv1,
                prev_cycle_id=None,
            )
            print(f"[SHADOW_HOOK_V1] result={_sh_res_v1}")
        except Exception as _e_sh_v1:
            print(f"[SHADOW_HOOK_V1] outer error: {_e_sh_v1}")
        # ===== [SHADOW_HOOK_V1] END =====
'''

HOOK_BLOCK = HOOK_BLOCK.replace("DB_PATH_PLACEHOLDER", DB_PATH)


def main():
    if not os.path.exists(FPATH):
        print(f"[ERR] fichier introuvable : {FPATH}")
        sys.exit(1)

    # Cleanup orphan .tmp si run precedent foire
    tmp_orphan = FPATH + ".tmp"
    if os.path.exists(tmp_orphan):
        os.remove(tmp_orphan)
        print(f"[cleanup] {tmp_orphan} (orphan)")

    with open(FPATH, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8-sig", errors="replace")

    # Idempotence
    if MARKER in src:
        print(f"[SKIP] marker {MARKER} deja present dans {FPATH}")
        sys.exit(0)

    # Verif anchor present
    if ANCHOR not in src:
        print(f"[ERR] anchor introuvable. Verifier L893-L897 manuellement.")
        sys.exit(2)

    # Backup
    ts = int(time.time())
    bak = f"{FPATH}.bak.{ts}"
    shutil.copy2(FPATH, bak)
    print(f"[backup] {bak}")

    # Patch : replace ANCHOR (= 2 lignes) par : ligne1 ANCHOR + HOOK_BLOCK + ligne2 ANCHOR
    # ANCHOR = HISTORY_SNAPSHOT_V1 closing comment + return
    # On insere HOOK_BLOCK entre les 2 lignes du ANCHOR.
    replacement = (
        "        # ===== /[HISTORY_SNAPSHOT_V1] =====\n"
        + HOOK_BLOCK
        + "        return {\"success\": True, \"cycle_result\": result}"
    )
    if src.count(ANCHOR) != 1:
        print(f"[ERR] ANCHOR count = {src.count(ANCHOR)} (attendu 1)")
        sys.exit(7)
    new_src = src.replace(ANCHOR, replacement)
    anchor_return = "        return {\"success\": True, \"cycle_result\": result}"

    # Verif marker bien injecte
    if MARKER not in new_src:
        print(f"[ERR] marker non injecte post-patch.")
        sys.exit(3)

    # Verif compte d'occurrences anchor_return : doit etre identique +/- 0
    if new_src.count(anchor_return) != src.count(anchor_return):
        print(f"[ERR] count return divergent : src={src.count(anchor_return)} new={new_src.count(anchor_return)}")
        sys.exit(4)

    # Write
    tmp = FPATH + ".tmp"
    with open(tmp, "wb") as f:
        f.write(new_src.encode("utf-8"))

    # Validation stricte
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"[ERR] ast.parse FAIL : {e}")
        os.remove(tmp)
        sys.exit(5)

    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"[ERR] py_compile FAIL : {e}")
        os.remove(tmp)
        sys.exit(6)

    # Atomic replace
    shutil.move(tmp, FPATH)

    # Stats
    n_lines_added = HOOK_BLOCK.count("\n")
    print(f"[OK] patch applique. +{n_lines_added} lignes injectees.")
    print(f"[OK] marker {MARKER} present.")
    print(f"[OK] ast.parse + py_compile OK.")
    print(f"\nNext step : redemarrer uvicorn pour activer le hook.")


if __name__ == "__main__":
    main()
