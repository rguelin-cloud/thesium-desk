# -*- coding: utf-8 -*-
# Patch v8 - corrige R5 definitivement (KeepTogether titre H+Spacer+table)
#
# DECOUVERTE v13 :
#   - sH1 a name='MemoH1', sH2 a name='MemoH2', sH3 n'existe pas (### = sH2 ou sBody bold ?)
#   - Le V7_R5 check ('H1','H2','H3') ne match jamais (names sont 'MemoH1','MemoH2')
#   - Un Spacer L1392 est insere entre lignes blanches markdown
#     donc story[-1] avant flush_md_table = souvent Spacer, pas le Paragraph titre
#
# CORRECTION v8 :
#   Reecrire le bloc V7_R5 pour :
#   - Detecter les names 'MemoH1', 'MemoH2', 'MemoH3' (et 'Memo*' generique pour robustesse)
#   - Inspecter jusqu'a 3 elements en arriere : si Spacer trouve, on remonte plus loin
#   - Collecter tous les elements absorbes (titre + spacer optionnel) dans KeepTogether
#
# Strategie technique :
#   marker [ICMEMO_V8_R5] sur le NOUVEAU bloc, et idempotence : si V8_R5 deja present,
#   skip. Si V7_R5 present mais pas V8_R5, on remplace V7_R5 par V8_R5.

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_V8 = "[ICMEMO_V8_R5]"
MARK_V7 = "[ICMEMO_V7_R5]"


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def find_func1_bounds(src):
    lines = src.split("\n")
    occurrences = []
    for i, ln in enumerate(lines):
        if re.match(r"^def\s+get_memo_pdf\s*\(", ln):
            occurrences.append(i)
    if not occurrences:
        raise RuntimeError("Aucune def get_memo_pdf trouvee")
    f1_start = occurrences[0]
    f1_end = len(lines)
    for j in range(f1_start + 1, len(lines)):
        if "# === END [ICMEMO_PDF_V2] ===" in lines[j]:
            f1_end = j
            break
        if re.match(r"^def\s+get_memo_pdf\s*\(", lines[j]):
            f1_end = j
            break
    return f1_start, f1_end, lines


def patch_v8_replace_v7(src):
    """Remplace le bloc V7_R5 par un bloc V8_R5 plus robuste (names 'Memo*' + Spacer)."""
    if MARK_V8 in src:
        return src, "SKIP (deja patche V8)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Trouve le bloc V7_R5 - commence par "# [ICMEMO_V7_R5]" et finit par "return [KeepTogether([t])]"
    v7_start = None
    for i in range(f1_start, f1_end):
        if MARK_V7 in lines[i] and lines[i].lstrip().startswith("#"):
            v7_start = i
            break
    if v7_start is None:
        raise RuntimeError("Marker V7_R5 introuvable dans fonction #1")

    # Fin du bloc V7 : ligne "return [KeepTogether([t])]" apres v7_start
    v7_end = None
    for j in range(v7_start + 1, f1_end):
        if "return [KeepTogether([t])]" in lines[j] and not lines[j].lstrip().startswith("#"):
            v7_end = j
            break
    if v7_end is None:
        raise RuntimeError("Fin bloc V7_R5 (return [KeepTogether([t])]) introuvable")

    # Indentation
    indent_match = re.match(r"^(\s*)", lines[v7_start])
    indent = indent_match.group(1) if indent_match else "        "

    # Nouveau bloc V8_R5
    new_block = [
        indent + "# " + MARK_V8 + " - absorbe titre H1/H2/H3 (Memo*) + Spacer eventuel dans KeepTogether",
        indent + "try:",
        indent + "    _absorbed = []",
        indent + "    # remonte jusqu'a 3 elements (Spacer + Paragraph titre)",
        indent + "    for _ in range(3):",
        indent + "        if not story:",
        indent + "            break",
        indent + "        _last = story[-1]",
        indent + "        _cls_name = type(_last).__name__",
        indent + "        _style_name = getattr(getattr(_last, 'style', None), 'name', '') or ''",
        indent + "        # cas 1 : Spacer -> on l'absorbe et on continue",
        indent + "        if _cls_name == 'Spacer':",
        indent + "            _absorbed.insert(0, story.pop())",
        indent + "            continue",
        indent + "        # cas 2 : Paragraph dont le style est un H1/H2/H3 ou MemoH*",
        indent + "        if _cls_name == 'Paragraph' and (",
        indent + "            _style_name in ('H1', 'H2', 'H3', 'Heading1', 'Heading2', 'Heading3')",
        indent + "            or _style_name.startswith('MemoH')",
        indent + "        ):",
        indent + "            _absorbed.insert(0, story.pop())",
        indent + "            # apres avoir absorbe le titre, on s'arrete",
        indent + "            break",
        indent + "        # autre type d'element : on s'arrete sans l'absorber",
        indent + "        break",
        indent + "    if _absorbed:",
        indent + "        return [KeepTogether(_absorbed + [t])]",
        indent + "except Exception:",
        indent + "    pass",
        indent + "return [KeepTogether([t])]",
    ]

    new_lines = lines[:v7_start] + new_block + lines[v7_end + 1:]
    return "\n".join(new_lines), "OK V8_R5 remplace V7_R5 L" + str(v7_start + 1) + ".." + str(v7_end + 1)


def main():
    print("=" * 70)
    print("PATCH V8 - R5 robuste (MemoH1/H2 + Spacer absorption)")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v8_" + ts
    shutil.copy2(TARGET, backup)
    print("Backup : " + backup)

    src = read_file(TARGET)
    print("Source : " + str(len(src)) + " chars")

    try:
        ast.parse(src)
        print("AST initial : OK")
    except SyntaxError as e:
        print("[ERREUR] AST initial casse : " + str(e))
        sys.exit(1)

    try:
        src, msg = patch_v8_replace_v7(src)
        print("V8_R5 : " + msg)
    except Exception as e:
        print("[ERREUR PATCH] " + str(e))
        sys.exit(1)

    try:
        ast.parse(src)
        print("AST apres patch : OK")
    except SyntaxError as e:
        print("[ERREUR AST] " + str(e))
        sys.exit(1)

    write_file(TARGET, src)
    print("Ecrit : " + TARGET + " (" + str(len(src)) + " chars)")

    try:
        py_compile.compile(TARGET, doraise=True)
        print("py_compile : OK")
    except py_compile.PyCompileError as e:
        print("[ERREUR py_compile] " + str(e))
        shutil.copy2(backup, TARGET)
        print("Rollback depuis " + backup)
        sys.exit(1)

    final = read_file(TARGET)
    print("")
    print("Markers :")
    print("  " + MARK_V8 + " : " + ("OK (" + str(final.count(MARK_V8)) + ")" if MARK_V8 in final else "ABSENT"))
    print("  " + MARK_V7 + " : " + ("PRESENT (" + str(final.count(MARK_V7)) + ", aucun probleme)" if MARK_V7 in final else "supprime"))

    print("")
    print("PATCH V8 termine.")
    print("")
    print("Actions :")
    print("  1. Ctrl+C uvicorn")
    print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. py -3.13 .\\nextones-test-memo-pdf-direct.py")
    print("  4. M'envoyer memo-51-v5-direct.pdf")


if __name__ == "__main__":
    main()
