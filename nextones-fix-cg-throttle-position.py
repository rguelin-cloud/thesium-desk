# -*- coding: utf-8 -*-
"""
[FIX_CG_THROTTLE_POSITION_V1]
Le helper [CG_THROTTLE_V2] a ete insere AVANT 'from __future__ import annotations',
ce qui casse Python (futures doivent etre en tete de fichier).

Ce script :
  1) Localise le bloc helper '# [CG_THROTTLE_V2] === BEGIN ... === END'
  2) Le retire de sa position actuelle
  3) Le re-insere APRES la derniere ligne 'from __future__ import ...'
  4) Valide ast + py_compile
"""
import re
import shutil
import datetime
import ast
import py_compile
from pathlib import Path

AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
BEGIN_MARK = "# [CG_THROTTLE_V2] === BEGIN"
END_MARK = "# [CG_THROTTLE_V2] === END"


def main():
    if not AGENT.exists():
        print(f"[ERR] {AGENT} introuvable")
        return

    raw = AGENT.read_bytes()
    bom = b'\xef\xbb\xbf'
    has_bom = raw.startswith(bom)
    if has_bom:
        raw = raw[3:]
    txt = raw.decode("utf-8", errors="replace")

    # 1) Trouver les bornes du bloc helper
    i_begin = txt.find(BEGIN_MARK)
    i_end = txt.find(END_MARK)
    if i_begin < 0 or i_end < 0:
        print("[ERR] bornes du bloc helper introuvables")
        return

    # Fin = jusqu'au saut de ligne apres END_MARK
    after_end = txt.find("\n", i_end)
    if after_end < 0:
        after_end = len(txt)
    else:
        after_end += 1  # inclure le \n
    # On veut inclure la ligne qui contient END_MARK + son \n suivant

    helper_block = txt[i_begin:after_end]
    # On retire egalement l'eventuel saut de ligne immediatement AVANT BEGIN (cosmetique)
    pre_block_start = i_begin
    if pre_block_start > 0 and txt[pre_block_start - 1] == "\n":
        # garde un seul \n pour ne pas tout coller, mais en pratique helper_block commence par \n deja
        pass

    print(f"[OK] helper localise : chars {i_begin}..{after_end} ({after_end - i_begin} chars)")

    # 2) Retirer le bloc
    txt_without = txt[:i_begin] + txt[after_end:]

    # 3) Trouver la derniere ligne 'from __future__ import ...'
    future_pattern = re.compile(r'^\s*from\s+__future__\s+import\b[^\n]*\n', re.MULTILINE)
    matches = list(future_pattern.finditer(txt_without))
    if not matches:
        # Pas de from __future__ : on insere apres le docstring / shebang / encoding
        # Strategie : on insere apres la zone d'en-tete (commentaires + docstring)
        # Pour rester safe : on essaie d'inserer apres le 1er bloc qui n'est ni shebang/encoding/docstring.
        # Plus simple : si pas de future, on remet juste apres les premiers commentaires/docstring.
        print("[INFO] pas de 'from __future__' trouve, insertion apres le docstring")
        # On tente : trouver fin d'un docstring """...""" ou '''...''' en debut de fichier
        # ou simplement apres la 1ere ligne de code reelle.
        # Strategie minimale : on cherche la 1ere ligne 'import ' ou 'from ' et on insere AVANT.
        first_import = re.search(r'^(import\s+\w|from\s+\w)', txt_without, re.MULTILINE)
        if first_import:
            insert_pos = first_import.start()
        else:
            insert_pos = 0
    else:
        last_future = matches[-1]
        insert_pos = last_future.end()  # juste apres le \n final du dernier from __future__
        print(f"[OK] {len(matches)} 'from __future__' trouve(s), insertion apres le dernier")

    # 4) Reinjecter le bloc avec separations propres
    # S'assurer qu'on a un \n avant le bloc et un \n apres
    prefix = "" if insert_pos == 0 or txt_without[insert_pos - 1] == "\n" else "\n"
    suffix = "" if insert_pos < len(txt_without) and txt_without[insert_pos] == "\n" else "\n"
    block_clean = helper_block.lstrip("\n")
    if not block_clean.endswith("\n"):
        block_clean += "\n"

    new_txt = (
        txt_without[:insert_pos]
        + prefix
        + block_clean
        + suffix
        + txt_without[insert_pos:]
    )

    # 5) Validation
    try:
        ast.parse(new_txt)
        print("[OK] ast.parse OK")
    except SyntaxError as e:
        print(f"[ERR SYNTAX] {e}")
        bad = AGENT.with_suffix(".py.bad-fix-throttle-pos")
        bad.write_text(new_txt, encoding="utf-8")
        print(f"[ERR] dump dans {bad.name}")
        return

    # 6) Backup + ecriture
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = AGENT.with_suffix(f".py.bak-{ts}-pre-fix-throttle-pos")
    shutil.copy2(AGENT, bak)
    print(f"[BAK] {bak.name}")

    AGENT.write_bytes(new_txt.encode("utf-8"))

    try:
        py_compile.compile(str(AGENT), doraise=True)
        print("[OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[ERR py_compile] {e}")
        return

    # 7) Sanity check : afficher l'ordre des 30 premieres lignes pour confirmer
    print()
    print("=" * 60)
    print("30 premieres lignes du fichier final :")
    print("=" * 60)
    for i, line in enumerate(new_txt.split("\n")[:30], 1):
        print(f"  {i:3d}: {line}")
    print()
    print("Fait. Tu peux relancer :")
    print("  py -3.13 .\\nextones-trigger-crypto-scan.py")


if __name__ == "__main__":
    main()
