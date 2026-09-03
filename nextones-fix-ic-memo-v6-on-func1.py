# -*- coding: utf-8 -*-
# Patch v6 - applique R2 R3 R4 sur la VRAIE fonction (fonction #1, L1079).
#
# Decouverte v11 : la fonction #2 L1494 est du code mort. Le decorateur
# @app.get("/api/memos/{memo_id}/pdf") L1078 expose la fonction #1 L1079.
# Python sequence : def L1079 -> decorateur capture la ref -> def L1494 ecrase la
# variable mais FastAPI garde la ref originale.
#
# Cibles dans api_server.py fonction #1 (L1079-L1492) :
#   R2 - doublon Thesis Summaries L1431 : wrapper if False idempotent
#        (et aussi le bloc Proposed Changes qui suit)
#
#   R3 - flush_md_table (fonction #1) : styles header renforces
#        Doit trouver la 1ere occurrence de "t = Table(data, colWidths=col_widths, repeatRows=1)"
#        avant L1492 (fin fonction #1)
#
#   R4 - helper _truncate_active_thesis_v6 + appliquer sur 'lines = md.split(\"\\n\")'
#        de la fonction #1
#
# Strategie : nouveaux markers V6 distincts (V5 deja consommes sur fonction #2 morte)
#
# Garanties :
# - utf-8-sig lecture, utf-8 sans BOM ecriture
# - ast.parse + py_compile pre/post ecriture
# - backup horodate
# - markers V6 idempotents

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_R2 = "[ICMEMO_V6_R2]"
MARK_R3 = "[ICMEMO_V6_R3]"
MARK_R4 = "[ICMEMO_V6_R4]"


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def find_func1_bounds(src):
    """Localise les bornes de la 1ere def get_memo_pdf (la vraie)."""
    lines = src.split("\n")
    occurrences = []
    for i, ln in enumerate(lines):
        if re.match(r"^def\s+get_memo_pdf\s*\(", ln):
            occurrences.append(i)
    if not occurrences:
        raise RuntimeError("Aucune def get_memo_pdf trouvee")
    f1_start = occurrences[0]
    # fin = ligne contenant "# === END [ICMEMO_PDF_V2] ===" ou prochaine def get_memo_pdf
    f1_end = len(lines)
    for j in range(f1_start + 1, len(lines)):
        if "# === END [ICMEMO_PDF_V2] ===" in lines[j]:
            f1_end = j
            break
        if re.match(r"^def\s+get_memo_pdf\s*\(", lines[j]):
            f1_end = j
            break
    return f1_start, f1_end, lines


def patch_r2_doublon_func1(src):
    """Wrap les 2 blocs doublons (Thesis Summaries L1431 + Proposed Changes) dans 'if False:' dans fonction #1."""
    if MARK_R2 in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche le commentaire qui precede la 1ere occurrence de Paragraph("Thesis Summaries"
    # On veut wrapper depuis "    if thesis_summaries and isinstance(thesis_summaries, list)..."
    # jusqu'a la fin du bloc Proposed Changes (avant doc.build ou avant une ligne au niveau 4 espaces non liee)

    block1_start = None
    for i in range(f1_start, f1_end):
        # cherche pattern "    if thesis_summaries and isinstance(thesis_summaries, list)"
        if re.match(r"^\s{4}if\s+thesis_summaries\s+and\s+isinstance\(thesis_summaries,\s*list\)", lines[i]):
            block1_start = i
            break
    if block1_start is None:
        raise RuntimeError("Bloc thesis_summaries dans fonction #1 introuvable")

    # block2 = bloc proposed_changes qui suit
    block2_start = None
    for i in range(block1_start + 1, f1_end):
        if re.match(r"^\s{4}if\s+proposed_changes\s+and\s+isinstance\(proposed_changes,\s*list\)", lines[i]):
            block2_start = i
            break

    # bornes : on cherche la prochaine ligne au niveau 4 espaces qui n'est pas dans le bloc
    # apres block2_start. Probablement "    doc.build(" ou un commentaire au niveau 4
    block2_end = None
    search_from = block2_start if block2_start is not None else block1_start + 1
    for j in range(search_from + 1, f1_end):
        ln = lines[j]
        if not ln.strip():
            continue
        # ligne au niveau 4 espaces non commentaire et non continuation
        if ln.startswith("    ") and not ln.startswith("        "):
            # exclure si fait partie d'un block courant : verifie indentation strictement 4
            indent = len(ln) - len(ln.lstrip(" "))
            if indent == 4 and not ln.lstrip().startswith("#"):
                # detecte fin si on tombe sur "doc.build(" ou autre instruction de flow principal
                stripped = ln.lstrip()
                if stripped.startswith("doc.build(") or stripped.startswith("buf.seek(") or stripped.startswith("return ") or stripped.startswith("from starlette"):
                    block2_end = j
                    break
    if block2_end is None:
        raise RuntimeError("Fin du wrap R2 (doc.build/buf.seek/return) introuvable apres block2_start")

    # Strategie : on insere "    if False:  # marker" juste avant block1_start
    # puis on indente +4 espaces toutes les lignes entre block1_start et block2_end exclu
    to_indent_start = block1_start
    to_indent_end = block2_end  # exclusif
    indented = []
    for j in range(to_indent_start, to_indent_end):
        ln = lines[j]
        if ln.strip() == "":
            indented.append(ln)
        else:
            indented.append("    " + ln)

    result_lines = (
        lines[:to_indent_start]
        + ["    if False:  # " + MARK_R2 + " doublons Thesis Summaries / Proposed Changes neutralises (fonction #1)"]
        + indented
        + lines[to_indent_end:]
    )
    return "\n".join(result_lines), "OK R2 wrap L" + str(to_indent_start + 1) + ".." + str(to_indent_end) + " (incl)"


def patch_r3_header_func1(src):
    """Renforce style header dans flush_md_table de la fonction #1."""
    if MARK_R3 in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche flush_md_table dans fonction #1 : 1ere occurrence de "t = Table(data, colWidths=col_widths, repeatRows=1)"
    target_line = None
    for i in range(f1_start, f1_end):
        if "t = Table(data, colWidths=col_widths, repeatRows=1)" in lines[i]:
            target_line = i
            break
    if target_line is None:
        raise RuntimeError("'t = Table(data, colWidths=col_widths, repeatRows=1)' introuvable dans fonction #1")

    # Cherche la fin du TableStyle suivant (]))
    ts_end = None
    for j in range(target_line + 1, min(target_line + 35, f1_end)):
        if lines[j].rstrip().endswith("]))"):
            ts_end = j
            break
    if ts_end is None:
        raise RuntimeError("Fin TableStyle flush_md_table fonction #1 introuvable")

    new_styles = [
        "            ('FONTSIZE', (0, 0), (-1, 0), 8.5),  # " + MARK_R3 + " header plus lisible",
        "            ('TOPPADDING', (0, 0), (-1, 0), 6),  # " + MARK_R3,
        "            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # " + MARK_R3,
        "            ('LINEBELOW', (0, 0), (-1, 0), 1.2, white),  # " + MARK_R3,
    ]

    new_lines = lines[:ts_end] + new_styles + lines[ts_end:]
    return "\n".join(new_lines), "OK R3 4 styles avant L" + str(ts_end + 1)


def patch_r4_truncate_func1(src):
    """Insere helper truncate Active Thesis dans fonction #1, avant la boucle 'for line in lines:'."""
    if MARK_R4 in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche 'lines = ' (assignation) dans fonction #1
    lines_assign_idx = None
    for i in range(f1_start, f1_end):
        if re.match(r"^\s*lines\s*=\s*md\.split", lines[i]):
            lines_assign_idx = i
            break
    if lines_assign_idx is None:
        # fallback : assignation lines = quelque chose
        for i in range(f1_start, f1_end):
            if re.match(r"^\s*lines\s*=\s*", lines[i]):
                lines_assign_idx = i
                break
    if lines_assign_idx is None:
        raise RuntimeError("Assignation 'lines = ...' introuvable dans fonction #1")

    indent_match = re.match(r"^(\s*)", lines[lines_assign_idx])
    indent = indent_match.group(1) if indent_match else "    "

    helper_block = [
        "",
        indent + "# " + MARK_R4 + " - tronque Active Thesis Summaries a top-5 blocs (fonction #1)",
        indent + "def _truncate_active_thesis_v6(_lines, _keep=5):",
        indent + "    out = []",
        indent + "    in_section = False",
        indent + "    blocks_total = 0",
        indent + "    skipping = False",
        indent + "    for _ln in _lines:",
        indent + "        _s = _ln.lstrip()",
        indent + "        if _s.startswith('## Active Thesis Summaries'):",
        indent + "            in_section = True",
        indent + "            out.append(_ln)",
        indent + "            continue",
        indent + "        if in_section and _s.startswith('## '):",
        indent + "            if blocks_total > _keep:",
        indent + "                out.append('')",
        indent + "                out.append('*+ ' + str(blocks_total - _keep) + ' autres theses (voir Audit Trail pour le detail).*')",
        indent + "                out.append('')",
        indent + "            in_section = False",
        indent + "            skipping = False",
        indent + "            out.append(_ln)",
        indent + "            continue",
        indent + "        if in_section and _s.startswith('### '):",
        indent + "            blocks_total += 1",
        indent + "            skipping = blocks_total > _keep",
        indent + "        if in_section and skipping:",
        indent + "            continue",
        indent + "        out.append(_ln)",
        indent + "    return out",
        indent + "lines = _truncate_active_thesis_v6(lines, _keep=5)  # " + MARK_R4,
        "",
    ]

    new_lines = lines[:lines_assign_idx + 1] + helper_block + lines[lines_assign_idx + 1:]
    return "\n".join(new_lines), "OK R4 helper apres L" + str(lines_assign_idx + 1)


def main():
    print("=" * 70)
    print("PATCH V6 - IC Memo residuels sur la VRAIE fonction (fonction #1)")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v6_" + ts
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
        src, r2_msg = patch_r2_doublon_func1(src)
        print("R2 : " + r2_msg)

        src, r3_msg = patch_r3_header_func1(src)
        print("R3 : " + r3_msg)

        src, r4_msg = patch_r4_truncate_func1(src)
        print("R4 : " + r4_msg)
    except Exception as e:
        print("[ERREUR PATCH] " + str(e))
        print("Rollback (aucune ecriture)")
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
    print("Markers v6 :")
    print("  " + MARK_R2 + " : " + ("OK (" + str(final.count(MARK_R2)) + ")" if MARK_R2 in final else "ABSENT"))
    print("  " + MARK_R3 + " : " + ("OK (" + str(final.count(MARK_R3)) + ")" if MARK_R3 in final else "ABSENT"))
    print("  " + MARK_R4 + " : " + ("OK (" + str(final.count(MARK_R4)) + ")" if MARK_R4 in final else "ABSENT"))

    print("")
    print("PATCH V6 termine.")
    print("")
    print("Actions :")
    print("  1. Ctrl+C uvicorn dans sa fenetre")
    print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. py -3.13 .\\nextones-test-memo-pdf-direct.py")
    print("  4. M'envoyer memo-51-v5-direct.pdf (le script ecrase le precedent)")


if __name__ == "__main__":
    main()
