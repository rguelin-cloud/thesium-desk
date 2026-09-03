# -*- coding: utf-8 -*-
# Patch v10 - corrige regression R7 : les ** markdown apparaissent litteralement
# dans le rendu '### ' apres v9.
#
# DECOUVERTE post-v9 :
#   v9 a remplace le rendu '### ' par story.append(Paragraph(txt, sH3)) avec
#   txt = _xml_escape(stripped[4:].strip()). Mais _xml_escape ne convertit pas
#   **...** en <b>...</b>. Le rendu precedent (sBody bold) ou un autre code path
#   appliquait probablement la regex de substitution markdown.
#
#   Symptome : "**NVDA** -- MacroAgent ..." apparait litteralement avec les **.
#
# CORRECTION v10 :
#   Inject la regex _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', ...) autour de
#   _xml_escape(stripped[4:].strip()) dans la branche '### ' patchee par v9.
#
#   Patch cible la ligne contenant '[ICMEMO_V9_SH3_USE]' et la remplace.

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_V10 = "[ICMEMO_V10_R7]"
MARK_V9 = "[ICMEMO_V9_SH3_USE]"


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


def patch_v10_bold_substitution(src):
    """Wrap _xml_escape avec _re.sub pour convertir **...** en <b>...</b>."""
    if MARK_V10 in src:
        return src, "SKIP (deja patche V10)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Trouve la ligne avec marker V9_SH3_USE (txt = _xml_escape(...))
    target_idx = None
    for i in range(f1_start, f1_end):
        if MARK_V9 in lines[i] and "_xml_escape(stripped[4:]" in lines[i]:
            target_idx = i
            break
    if target_idx is None:
        raise RuntimeError("Ligne V9_SH3_USE 'txt = _xml_escape(stripped[4:]' introuvable")

    old_line = lines[target_idx]
    # Reconstruction : on remplace '_xml_escape(stripped[4:].strip())' par
    # '_re.sub(r"\\*\\*(.+?)\\*\\*", r"<b>\\1</b>", _xml_escape(stripped[4:].strip()))'
    pattern_to_replace = "_xml_escape(stripped[4:].strip())"
    replacement = "_re.sub(r'\\*\\*(.+?)\\*\\*', r'<b>\\1</b>', _xml_escape(stripped[4:].strip()))"
    if pattern_to_replace not in old_line:
        raise RuntimeError("Pattern '_xml_escape(stripped[4:].strip())' introuvable dans la ligne cible L" + str(target_idx + 1))

    new_line = old_line.replace(pattern_to_replace, replacement)
    # remplace marker V9 par V10 pour eviter de retomber sur cette ligne si on relance
    new_line = new_line.replace(MARK_V9, MARK_V10)

    lines[target_idx] = new_line
    return "\n".join(lines), "OK V10 bold substitution L" + str(target_idx + 1)


def main():
    print("=" * 70)
    print("PATCH V10 - R7 ** markdown bold dans rendu sH3")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v10_" + ts
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
        src, msg = patch_v10_bold_substitution(src)
        print("V10 : " + msg)
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
    print("  " + MARK_V10 + " : " + ("OK (" + str(final.count(MARK_V10)) + ")" if MARK_V10 in final else "ABSENT"))
    print("  " + MARK_V9 + "  : " + ("PRESENT (" + str(final.count(MARK_V9)) + ", normal)" if MARK_V9 in final else "remplace par V10"))

    print("")
    print("PATCH V10 termine.")
    print("")
    print("Actions :")
    print("  1. Ctrl+C uvicorn")
    print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. py -3.13 .\\nextones-test-memo-pdf-direct.py")
    print("  4. M'envoyer memo-51-v5-direct.pdf")


if __name__ == "__main__":
    main()
