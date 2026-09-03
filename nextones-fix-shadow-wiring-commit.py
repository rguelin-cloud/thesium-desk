# -*- coding: utf-8 -*-
# [NEXTONES-FIX-SHADOW-WIRING-COMMIT-V1]
# Probleme : execute_shadow ouvre sa propre connexion mais la connexion
# 'conn' de create_and_execute_order tient encore une transaction ouverte
# (INSERT orders + UPDATE quantity). Le lock writer bloque execute_shadow
# pendant 10s puis fail "database is locked".
#
# Solution : injecter conn.commit() juste avant l'appel execute_shadow
# dans le bloc [NEXTONES-SHADOW-EXEC-V1].
#
# Idempotent : detecte la presence du commit via marker V2.

import argparse
import ast
import os
import py_compile
import shutil
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD_DIR, "execution_engine.py")
MARKER_V1 = "[NEXTONES-SHADOW-EXEC-V1]"
MARKER_V2 = "[NEXTONES-SHADOW-EXEC-COMMIT-V2]"


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def fail(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def ok(msg):
    print(f"[OK] {msg}")


def rollback():
    banner("[ROLLBACK]")
    candidates = sorted(
        [f for f in os.listdir(PROD_DIR)
         if f.startswith("execution_engine.py.bak.")],
        reverse=True,
    )
    if not candidates:
        fail("aucun backup execution_engine.py.bak.*")
    latest = os.path.join(PROD_DIR, candidates[0])
    shutil.copyfile(latest, EE)
    ok(f"restaure depuis {candidates[0]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    if args.rollback:
        rollback()
        return

    banner("[1] Lecture execution_engine.py")
    with open(EE, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER_V1 not in src:
        fail("marker V1 absent : le wiring n'a pas ete installe")
    if MARKER_V2 in src:
        print("[INFO] marker V2 deja present : patch deja applique")
        return
    ok("wiring V1 present, V2 absent -> on patche")

    # ----------------------------- 2 -----------------------------
    banner("[2] Localise le bloc V1 et injecte conn.commit()")
    # On cherche le bloc qui commence par la ligne marker V1
    # Pattern attendu :
    #   # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele ...
    #   try:
    #       import bridge_config as _bc_sh
    #       if getattr(_bc_sh, "BROKER_SHADOW_ENABLED", False):
    #           ...
    #
    # On veut transformer en :
    #   # [NEXTONES-SHADOW-EXEC-COMMIT-V2] - commit conn avant shadow pour liberer le lock writer
    #   # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele ...
    #   try:
    #       try:
    #           conn.commit()
    #       except Exception:
    #           pass
    #       import bridge_config as _bc_sh
    #       ...

    # Trouve la ligne de marker V1
    pos = src.find(MARKER_V1)
    if pos < 0:
        fail("MARKER_V1 introuvable (apres check ?!)")

    # Remonter au debut de la ligne du marker
    line_start = src.rfind("\n", 0, pos) + 1
    # Indentation = caracteres jusqu'au # du marker
    indent = ""
    i = line_start
    while i < len(src) and src[i] in (" ", "\t"):
        indent += src[i]
        i += 1

    # Trouver le 'try:' qui suit le marker (sur les 3 lignes suivantes max)
    after_marker_line_end = src.find("\n", pos)
    rest = src[after_marker_line_end + 1:]
    # Le 'try:' doit etre la prochaine instruction non-vide a la meme indentation
    rest_lines = rest.split("\n")
    try_idx_in_rest = None
    for k, ln in enumerate(rest_lines):
        if ln.strip() == "":
            continue
        if ln.startswith(indent + "try:"):
            try_idx_in_rest = k
            break
        else:
            # Premiere ligne non-vide n'est pas le try -> structure inattendue
            print(f"[WARN] premiere ligne non-vide apres marker : {ln!r}")
            print(f"       attendu : {indent}try:")
            break

    if try_idx_in_rest is None:
        fail("'try:' non trouve juste apres le marker V1")

    # Detecte l'indentation interne du try (4 chars en plus)
    # Apres le 'try:' on doit voir les lignes plus indentees
    inner_indent = indent + "    "

    # On va modifier rest_lines :
    # - inserer juste apres 'try:' (donc en position try_idx_in_rest+1) 3 lignes :
    #     {inner_indent}try:
    #     {inner_indent}    conn.commit()
    #     {inner_indent}except Exception:
    #     {inner_indent}    pass
    # - ajouter le marker V2 en commentaire AVANT le marker V1 (au-dessus)
    inject = [
        inner_indent + "try:",
        inner_indent + "    conn.commit()  " + "# " + MARKER_V2,
        inner_indent + "except Exception:",
        inner_indent + "    pass",
    ]
    new_rest_lines = (
        rest_lines[: try_idx_in_rest + 1]
        + inject
        + rest_lines[try_idx_in_rest + 1 :]
    )
    new_rest = "\n".join(new_rest_lines)

    # Marker V2 en commentaire en haut, juste avant la ligne marker V1
    pre = src[:line_start]
    marker_v2_line = indent + "# " + MARKER_V2 + " - commit conn avant shadow pour liberer le lock writer\n"
    new_src = pre + marker_v2_line + src[line_start:after_marker_line_end + 1] + new_rest

    # ----------------------------- 3 -----------------------------
    banner("[3] Validation ast.parse + py_compile")
    tmp = EE + ".tmp.fix"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    try:
        ast.parse(new_src)
        py_compile.compile(tmp, doraise=True)
        ok("ast.parse + py_compile OK")
    except Exception as e:
        os.remove(tmp)
        fail(f"validation echouee : {e}")

    # ----------------------------- 4 -----------------------------
    banner("[4] Backup + apply")
    bak = f"{EE}.bak.{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copyfile(EE, bak)
    shutil.move(tmp, EE)
    ok(f"patch applique (backup : {os.path.basename(bak)})")

    # ----------------------------- 5 -----------------------------
    banner("[5] Smoke import en subprocess")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, r'{PROD_DIR}'); "
         "import execution_engine; print('import OK')"],
        capture_output=True, text=True, timeout=30,
    )
    print(f"  stdout : {r.stdout.strip()}")
    if r.returncode != 0:
        print(f"  stderr : {r.stderr.strip()}")
        # rollback auto
        shutil.copyfile(bak, EE)
        fail("smoke import echoue -> rollback automatique")
    ok("smoke import OK")

    banner("[VERDICT]")
    print("  patch V2 (conn.commit() avant execute_shadow) applique")
    print("  re-lancer le validator :")
    print("    py -3.13 nextones-validate-shadow-wired.py")


if __name__ == "__main__":
    main()
