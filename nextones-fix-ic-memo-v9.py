# -*- coding: utf-8 -*-
# Patch v9 - cree sH3 (MemoH3) et l'utilise pour le rendu des '### ' markdown.
#
# DECOUVERTE post-v8 :
#   V8_R5 capture les titres Memo* + Spacer dans KeepTogether, MAIS Factor Scores
#   reste orphelin parce qu'il est en '### ' (H3 markdown). Or il n'existe PAS
#   de sH3 dans la fonction #1 : le code rend probablement '### ' comme
#   '<b>...</b>' en sBody, dont le name est 'MemoBody' -> non capture par V8_R5.
#
# CORRECTION v9 :
#   1) Definir sH3 = ParagraphStyle('MemoH3', parent=styles['Heading3'], ...)
#      juste apres sH2 (L1245-1247). Style legerement plus petit que sH2,
#      meme teal pastel pour coherence visuelle.
#   2) Remplacer la branche '### ' (rendu actuel via sBody bold) par
#      'story.append(Paragraph(txt, sH3))' identique a la branche '## ' sH2.
#      Comme sH3 a name 'MemoH3', V8_R5 le captura ('MemoH*' startswith)
#      et resoudra Factor Scores P1.
#
# Strategie :
#   - Recherche dans fonction #1 la zone '### ' L1407..L1413 (autour) :
#     'if stripped.startswith("### "):' suivi du rendu actuel.
#     Le rendu actuel est probablement story.append(Paragraph(f"<b>{txt}</b>", sBody))
#     L1401 d'apres diag v12 [4]. Ou L1411 sBullet ? Faux : L1411 = sBullet.
#   - On va trouver le 'if stripped.startswith("### "):' et reecrire les 3 lignes
#     suivantes pour utiliser sH3.
#
# Garanties :
#   - Backup horodate
#   - AST + py_compile
#   - Marker idempotent
#   - Rollback auto si py_compile echoue

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_DEF = "[ICMEMO_V9_SH3_DEF]"
MARK_USE = "[ICMEMO_V9_SH3_USE]"


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


def patch_add_sh3_def(src):
    """Insere la definition de sH3 juste apres sH2."""
    if MARK_DEF in src:
        return src, "SKIP (sH3 def deja patchee)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Trouve la def de sH2 : 'sH2 = ParagraphStyle("MemoH2"...)'. La def s'etend sur 1-3 lignes.
    sh2_start = None
    for i in range(f1_start, f1_end):
        if re.search(r"\bsH2\s*=\s*ParagraphStyle\(", lines[i]):
            sh2_start = i
            break
    if sh2_start is None:
        raise RuntimeError("Definition sH2 introuvable")

    # Trouver fin de la def sH2 : ligne qui se termine par ')'
    sh2_end = sh2_start
    for j in range(sh2_start, min(sh2_start + 5, f1_end)):
        if lines[j].rstrip().endswith(")"):
            sh2_end = j
            break

    # Indentation parente
    indent_match = re.match(r"^(\s*)", lines[sh2_start])
    indent = indent_match.group(1) if indent_match else "    "

    # Bloc sH3 : taille intermediaire entre sH2 (12) et sBody (9.5), couleur MUTED_TEAL
    sh3_block = [
        indent + "sH3 = ParagraphStyle(\"MemoH3\", parent=styles[\"Heading3\"],  # " + MARK_DEF,
        indent + "    fontSize=10.5, leading=13, textColor=MUTED_TEAL,",
        indent + "    spaceAfter=3, spaceBefore=8, fontName=FONT_BOLD)",
    ]

    new_lines = lines[:sh2_end + 1] + sh3_block + lines[sh2_end + 1:]
    return "\n".join(new_lines), "OK sH3 inseree apres L" + str(sh2_end + 1)


def patch_use_sh3(src):
    """Remplace le rendu '### ' actuel par story.append(Paragraph(txt, sH3))."""
    if MARK_USE in src:
        return src, "SKIP (sH3 use deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche 'if stripped.startswith("### "):' dans fonction #1
    h3_idx = None
    for i in range(f1_start, f1_end):
        if re.search(r'if\s+stripped\.startswith\(\s*[\'"]###\s+[\'"]\s*\)\s*:', lines[i]):
            h3_idx = i
            break
    if h3_idx is None:
        raise RuntimeError("Branche 'if stripped.startswith(\"### \"):' introuvable dans fonction #1")

    # Indentation interne (1 niveau plus profond que le if)
    if_indent_match = re.match(r"^(\s*)", lines[h3_idx])
    if_indent = if_indent_match.group(1) if if_indent_match else "        "
    inner_indent = if_indent + "    "

    # On extrait la ligne 'txt = _xml_escape(stripped[4:].strip())' qui suit (typiquement +1)
    # Puis on cherche la fin du bloc actuel (jusqu'au 'continue' ou autre branche)
    # On veut REMPLACER le contenu du if par : txt = ..., story.append(Paragraph(txt, sH3)), body_paragraphs_count += 1, continue
    txt_idx = None
    for j in range(h3_idx + 1, min(h3_idx + 4, f1_end)):
        if "txt = _xml_escape(stripped[4:]" in lines[j]:
            txt_idx = j
            break
    if txt_idx is None:
        raise RuntimeError("Ligne 'txt = _xml_escape(stripped[4:]' introuvable apres branche ###")

    # Cherche la fin du bloc : prochaine ligne au meme niveau que h3_idx OU 'continue' explicite
    block_end = None
    for j in range(txt_idx + 1, min(txt_idx + 12, f1_end)):
        ln = lines[j]
        if not ln.strip():
            continue
        cur_indent = len(ln) - len(ln.lstrip(" "))
        if cur_indent <= len(if_indent):
            block_end = j  # exclusif
            break
        # Si on trouve un 'continue' on l'inclut
        if ln.lstrip().startswith("continue"):
            block_end = j + 1
            break
    if block_end is None:
        raise RuntimeError("Fin de bloc '### ' introuvable")

    # Nouveau contenu interne (3 lignes apres 'if stripped.startswith("### "):')
    new_inner = [
        inner_indent + "txt = _xml_escape(stripped[4:].strip())  # " + MARK_USE,
        inner_indent + "story.append(Paragraph(txt, sH3))",
        inner_indent + "body_paragraphs_count += 1",
        inner_indent + "continue",
    ]

    # On garde : lines[:h3_idx+1] (avec le 'if stripped.startswith("### "):')
    # puis new_inner, puis lines[block_end:]
    new_lines = lines[:h3_idx + 1] + new_inner + lines[block_end:]
    return "\n".join(new_lines), "OK rendu ### -> sH3 L" + str(h3_idx + 1) + ".." + str(block_end)


def main():
    print("=" * 70)
    print("PATCH V9 - sH3 (MemoH3) + rendu '### ' via sH3 pour KeepTogether")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v9_" + ts
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
        src, msg1 = patch_add_sh3_def(src)
        print("sH3 def : " + msg1)

        src, msg2 = patch_use_sh3(src)
        print("sH3 use : " + msg2)
    except Exception as e:
        print("[ERREUR PATCH] " + str(e))
        sys.exit(1)

    try:
        ast.parse(src)
        print("AST apres patches : OK")
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
    print("Markers v9 :")
    print("  " + MARK_DEF + " : " + ("OK (" + str(final.count(MARK_DEF)) + ")" if MARK_DEF in final else "ABSENT"))
    print("  " + MARK_USE + " : " + ("OK (" + str(final.count(MARK_USE)) + ")" if MARK_USE in final else "ABSENT"))

    print("")
    print("PATCH V9 termine.")
    print("")
    print("Actions :")
    print("  1. Ctrl+C uvicorn")
    print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. py -3.13 .\\nextones-test-memo-pdf-direct.py")
    print("  4. M'envoyer memo-51-v5-direct.pdf")


if __name__ == "__main__":
    main()
