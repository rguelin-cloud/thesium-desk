# -*- coding: utf-8 -*-
# [NEXTONES-FIX-RECONCILER-ORDER]
# Corrige l'ordre des appels dans main() :
#   AVANT (l462) : fetch_mappings(con, thesium_tickers=list(thesium_positions.keys()))
#   PROBLEME    : thesium_positions n'est pas encore defini
#
# STRATEGIE : on cherche dans le source l'appel
#   "fetch_mappings(con, thesium_tickers=list(thesium_positions.keys()))"
# et on s'assure qu'il vient APRES :
#   "thesium_positions = fetch_thesium_positions(con)"
#
# Si ce n'est pas le cas :
#   1) on extrait la ligne fetch_mappings et son contexte (variables)
#   2) on la deplace juste apres l'appel fetch_thesium_positions
#
# Validation stricte avant ecriture.

import argparse
import ast
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "nextones-broker-reconciler.py")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    banner("[1] Lecture target")
    with open(TARGET, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    lines = src.splitlines(keepends=False)
    print(f"  taille : {len(src)} octets, {len(lines)} lignes")

    # Cherche les deux lignes cles
    idx_map = None
    idx_thesium = None
    for i, ln in enumerate(lines):
        if ("fetch_mappings(con, thesium_tickers=list(thesium_positions"
                in ln):
            idx_map = i
        if ("thesium_positions = fetch_thesium_positions(con)" in ln
                or "thesium_positions=fetch_thesium_positions(con)" in ln):
            idx_thesium = i

    print(f"  L{idx_map+1 if idx_map is not None else '?'}: fetch_mappings(con, thesium_tickers=...)")
    print(f"  L{idx_thesium+1 if idx_thesium is not None else '?'}: thesium_positions = fetch_thesium_positions(con)")

    if idx_map is None or idx_thesium is None:
        print("[FAIL] introuvable. Dump 30 premieres lignes de main() :")
        # cherche main()
        for i, ln in enumerate(lines):
            if ln.strip().startswith("def main("):
                for j in range(i, min(i + 60, len(lines))):
                    print(f"  L{j+1}: {lines[j]}")
                break
        sys.exit(1)

    if idx_thesium < idx_map:
        print("  [OK] ordre correct (thesium AVANT mapping)")
        # Mais alors pourquoi l'erreur ? On dump le contexte
        banner("[2] Contexte autour des deux lignes (ordre semble OK)")
        lo = max(0, min(idx_map, idx_thesium) - 5)
        hi = min(len(lines), max(idx_map, idx_thesium) + 5)
        for j in range(lo, hi):
            mark = ">>>" if j in (idx_map, idx_thesium) else "   "
            print(f"  {mark} L{j+1}: {lines[j]}")
        # rien a faire
        print("  rien a corriger ?")
        sys.exit(0)

    print(f"  [FIX NEEDED] mapping (L{idx_map+1}) est AVANT thesium (L{idx_thesium+1})")

    banner("[2] Extraction du bloc a deplacer")
    # On suppose que le bloc fetch_mappings tient sur 1 ligne ou plusieurs
    # avec continuation par ( ... ). On capture la ligne d'origine et,
    # si elle finit par '(' ou ',' sans ')', les suivantes jusqu'a la ')'.
    map_block = [lines[idx_map]]
    # cas typique : tout sur une ligne ; on verifie equilibre des paren
    open_p = lines[idx_map].count("(") - lines[idx_map].count(")")
    j = idx_map
    while open_p > 0 and j + 1 < len(lines):
        j += 1
        map_block.append(lines[j])
        open_p += lines[j].count("(") - lines[j].count(")")
    map_block_end = j  # inclus
    print(f"  bloc mapping : lignes {idx_map+1}..{map_block_end+1}")
    for ln in map_block:
        print(f"    {ln}")

    banner("[3] Suppression + reinsertion apres thesium_positions")
    new_lines = list(lines)
    # supprime de idx_map a map_block_end
    del new_lines[idx_map:map_block_end + 1]
    # idx_thesium n'est pas decale parce qu'il est avant... mais wait,
    # on est dans le cas ou idx_thesium > idx_map donc oui il est decale
    # mais on est dans le cas oppose (idx_thesium > idx_map ?). Non,
    # on a dit "FIX NEEDED" car idx_map < idx_thesium (mapping AVANT
    # thesium). Donc supprimer idx_map decale idx_thesium de
    # -(map_block_end - idx_map + 1).
    shift = (map_block_end - idx_map + 1)
    new_idx_thesium = idx_thesium - shift
    # insertion APRES la ligne thesium_positions
    insert_at = new_idx_thesium + 1
    for k, ln in enumerate(map_block):
        new_lines.insert(insert_at + k, ln)

    src2 = "\n".join(new_lines)
    if not src2.endswith("\n"):
        src2 += "\n"
    print(f"  nouveau total : {len(src2)} octets, {len(new_lines)} lignes")

    banner("[4] ast.parse + py_compile")
    ast.parse(src2)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(src2)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmpname)
        except Exception:
            pass

    banner("[5] Smoke --help")
    tmp_target = TARGET + ".tmpord"
    with open(tmp_target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src2)
    try:
        r = subprocess.run(
            ["py", "-3.13", tmp_target, "--help"],
            capture_output=True, text=True, timeout=30, cwd=PROD,
        )
        if r.returncode != 0:
            print(f"[FAIL] smoke rc={r.returncode}")
            print(r.stderr[-500:])
            sys.exit(1)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmp_target)
        except Exception:
            pass

    if args.dry_run:
        banner("[6] DRY-RUN : pas d'ecriture")
    else:
        banner("[6] Backup + ecriture")
        bak = TARGET + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(TARGET, bak)
        print(f"  backup : {bak}")
        with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src2)
        print(f"  ecrit  : {TARGET}")

    banner("[7] DONE")
    print("  py -3.13 nextones-broker-reconciler.py --no-broker --verbose")


if __name__ == "__main__":
    main()
