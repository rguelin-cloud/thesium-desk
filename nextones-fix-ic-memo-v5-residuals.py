# -*- coding: utf-8 -*-
# Patch v5 - corrige les 4 residuels du PDF IC Memo (route serveur fonction #2)
#
# Cibles dans api_server.py (fonction #2 a L1494) :
#   R2 - doublon "Thesis Summaries" (L1761-L1788) et "Proposed Changes" (L1791-L1820)
#        --> entourer le bloc d'un "if False:" idempotent (marker [ICMEMO_V5_R2])
#
#   R3+R5 - header tables invisible (Market Indicators, Factor Scores, Proposed Changes)
#        --> renforcer le style header : fontSize 8.5, leading 11, padding 5/5 + bordure
#        --> dans flush_md_table L1637-L1649 (marker [ICMEMO_V5_R3])
#
#   R4 - 20 blocs Active Thesis trop longs
#        --> pre-filtre du markdown avant rendering : garde top-5 blocs Thesis ID,
#            ajoute ligne "+ N autres theses (voir audit trail pour le detail)"
#        --> insere un helper _truncate_active_thesis et applique avant le parsing
#            ligne par ligne (marker [ICMEMO_V5_R4])
#
# Garanties :
# - lecture utf-8-sig, ecriture utf-8 sans BOM
# - ast.parse + py_compile avant ecriture
# - backup horodate api_server.py.bak_v5_YYYYMMDD_HHMMSS
# - markers idempotents : si presents -> SKIP
# - rollback automatique si validation echoue

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_R2 = "[ICMEMO_V5_R2]"
MARK_R3 = "[ICMEMO_V5_R3]"
MARK_R4 = "[ICMEMO_V5_R4]"


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def validate_python(path):
    src = read_file(path)
    ast.parse(src)
    py_compile.compile(path, doraise=True)


def find_func2_bounds(src):
    """Localise les bornes de la 2eme def get_memo_pdf."""
    lines = src.split("\n")
    occurrences = []
    for i, ln in enumerate(lines):
        if re.match(r"^def\s+get_memo_pdf\s*\(", ln):
            occurrences.append(i)
    if len(occurrences) < 2:
        raise RuntimeError("Moins de 2 definitions get_memo_pdf trouvees : " + str(len(occurrences)))
    start_idx = occurrences[1]  # 2eme = celle qui est appelee
    # fin = prochain decorator @app.* ou @router.*
    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        s = lines[j].lstrip()
        if s.startswith("@app.") or s.startswith("@router."):
            end_idx = j
            break
    return start_idx, end_idx, lines


def patch_r2_doublon(src):
    """Wrap les 2 blocs doublons dans 'if False:' idempotent."""
    if MARK_R2 in src:
        return src, "SKIP (deja patche)"
    lines = src.split("\n")
    start_idx, end_idx, _ = find_func2_bounds(src)

    # cherche les 2 blocs : '    # Thesis summary table' puis '    # Proposed changes table'
    # ils sont au niveau d'indentation 4 espaces (commentaire) + 4 espaces (if)
    block1_start = None
    block2_start = None
    for i in range(start_idx, end_idx):
        s = lines[i]
        if s.strip() == "# Thesis summary table" and block1_start is None:
            block1_start = i
        elif s.strip() == "# Proposed changes table" and block2_start is None:
            block2_start = i

    if block1_start is None or block2_start is None:
        raise RuntimeError("Blocs doublons introuvables : thesis=" + str(block1_start) + " proposed=" + str(block2_start))

    # bloc1 va de block1_start (commentaire) a juste avant block2_start
    # bloc2 va de block2_start a juste avant la prochaine ligne "    doc.build(...)" ou
    # un endroit a indentation 4 qui revient au flot principal

    # trouve fin du bloc2 : avant 'doc.build(' au niveau 4 espaces
    block2_end = None
    for j in range(block2_start + 1, end_idx):
        if lines[j].startswith("    doc.build("):
            block2_end = j
            break
    if block2_end is None:
        # fallback : prochain commentaire ou prochaine instruction au niveau 4 qui n'est pas dans le bloc
        for j in range(block2_start + 1, end_idx):
            s = lines[j]
            if s.startswith("    ") and not s.startswith("        ") and not s.startswith("    #") and s.strip() and "doc" in s:
                block2_end = j
                break
    if block2_end is None:
        raise RuntimeError("Fin du bloc2 (Proposed Changes) introuvable avant doc.build()")

    # Strategy : indenter d'un cran (4 espaces) tout entre block1_start et block2_end exclu,
    # et inserer 2 if False: avec marker
    new_lines = list(lines)

    # Insertion en marche arriere pour ne pas decaler les indices
    # 1. transformer le bloc2 : indenter de 4 espaces tout bloc2_start..block2_end-1
    # On enveloppe les deux blocs dans un seul if False: pour simplicite

    # Plus simple : commenter chaque ligne entre block1_start (inclus) et block2_end (exclu)
    # avec un prefixe "# [ICMEMO_V5_R2] " pour neutralisation totale
    # Mais ca casse trop. On prefere wrap en if False:

    # Approche : a la ligne block1_start, inserer "    if False:  # [ICMEMO_V5_R2] doublon supprime"
    # puis indenter de +4 espaces toutes lignes block1_start..block2_end-1 INCLUSIVE.

    # Sauve les lignes a indenter
    to_indent_start = block1_start
    to_indent_end = block2_end  # exclusif
    indented = []
    for j in range(to_indent_start, to_indent_end):
        ln = new_lines[j]
        if ln.strip() == "":
            indented.append(ln)  # ligne vide reste vide
        else:
            indented.append("    " + ln)  # +4 espaces

    # Construit le nouveau buffer
    result_lines = (
        new_lines[:to_indent_start]
        + ["    if False:  # " + MARK_R2 + " doublons Thesis Summaries / Proposed Changes neutralises"]
        + indented
        + new_lines[to_indent_end:]
    )
    return "\n".join(result_lines), "OK R2 wrap if False: entre L" + str(to_indent_start + 1) + " et L" + str(to_indent_end) + " (incl)"


def patch_r3_header(src):
    """Renforce le style header dans flush_md_table.

    Cible la zone L1637-L1649 (TableStyle de flush_md_table).
    Ajoute : ('FONTSIZE', (0,0), (-1,0), 8.5), ('BOTTOMPADDING', (0,0), (-1,0), 6), 
             ('TOPPADDING', (0,0), (-1,0), 6), ('LINEBELOW', (0,0), (-1,0), 1.2, white)
    """
    if MARK_R3 in src:
        return src, "SKIP (deja patche)"

    # On cherche la 2eme occurrence de TableStyle dans flush_md_table (fonction #2)
    # Repere : juste apres "t = Table(data, colWidths=col_widths, repeatRows=1)" et avant 
    # "elements.append(KeepTogether([t]))"
    lines = src.split("\n")
    start_idx, end_idx, _ = find_func2_bounds(src)

    target_line = None
    for i in range(start_idx, end_idx):
        if "t = Table(data, colWidths=col_widths, repeatRows=1)" in lines[i]:
            target_line = i
            break
    if target_line is None:
        raise RuntimeError("Cible flush_md_table (t = Table(data,...)) introuvable")

    # Cherche la fin du TableStyle (']))' au meme niveau)
    ts_end = None
    for j in range(target_line + 1, min(target_line + 30, end_idx)):
        if lines[j].rstrip().endswith("]))"):
            ts_end = j
            break
    if ts_end is None:
        raise RuntimeError("Fin TableStyle flush_md_table introuvable")

    # On insere 4 lignes juste avant ts_end :
    new_styles = [
        "            ('FONTSIZE', (0, 0), (-1, 0), 8.5),  # " + MARK_R3 + " header plus lisible",
        "            ('TOPPADDING', (0, 0), (-1, 0), 6),  # " + MARK_R3,
        "            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # " + MARK_R3,
        "            ('LINEBELOW', (0, 0), (-1, 0), 1.2, white),  # " + MARK_R3,
    ]

    new_lines = lines[:ts_end] + new_styles + lines[ts_end:]
    return "\n".join(new_lines), "OK R3 4 styles header ajoutes avant L" + str(ts_end + 1)


def patch_r4_active_thesis_truncate(src):
    """Pre-filtre du markdown pour limiter Active Thesis Summaries a top-5.

    Insere un helper apres la recuperation de `md` (full_markdown) et avant le parsing ligne.
    Cherche le point ou full_markdown est lu (memo.get('full_markdown', ''))
    et applique _truncate_active_thesis dessus.
    """
    if MARK_R4 in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    start_idx, end_idx, _ = find_func2_bounds(src)

    # Cherche la ligne ou full_markdown est lu (typiquement "md = memo.get('full_markdown'..."
    # ou un "lines = ... .split('\n')" pour parser
    md_var_line = None
    for i in range(start_idx, end_idx):
        s = lines[i]
        # patterns possibles
        if ("memo.get(" in s and "full_markdown" in s) or ("memo[\"full_markdown\"]" in s) or ("memo['full_markdown']" in s):
            md_var_line = i
            break
    if md_var_line is None:
        # fallback : la boucle 'for line in lines:' L1658 = on injecte juste avant
        for i in range(start_idx, end_idx):
            if re.match(r"^\s*for\s+line\s+in\s+lines\s*:", lines[i]):
                md_var_line = i - 1  # juste avant
                break
    if md_var_line is None:
        raise RuntimeError("Point d'insertion R4 introuvable")

    # On cherche aussi la variable du nom local : md, markdown, body, full_markdown ?
    # On detecte: si la ligne contient 'X = memo.get(' on extrait X.
    var_name = None
    if md_var_line is not None:
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*memo\.get\(", lines[md_var_line])
        if m:
            var_name = m.group(1)

    # Si on n'a pas trouve un binding clair, on cherche la variable 'lines' qui est utilisee
    # dans la boucle 'for line in lines:'. Cette variable est probablement le split du md.
    # Plan B : injecter le truncate juste avant la boucle, en modifiant 'lines' directement.

    # On trouve l'assignation 'lines = ' avant la boucle for line in lines
    for_loop_idx = None
    for i in range(start_idx, end_idx):
        if re.match(r"^\s*for\s+line\s+in\s+lines\s*:", lines[i]):
            for_loop_idx = i
            break
    if for_loop_idx is None:
        raise RuntimeError("Boucle 'for line in lines:' introuvable")

    # cherche en remontant l'assignation 'lines = '
    lines_assign_idx = None
    for j in range(for_loop_idx - 1, start_idx, -1):
        if re.match(r"^\s*lines\s*=\s*", lines[j]):
            lines_assign_idx = j
            break
    if lines_assign_idx is None:
        raise RuntimeError("Assignation 'lines = ...' avant boucle introuvable")

    # determine indentation
    indent_match = re.match(r"^(\s*)", lines[lines_assign_idx])
    indent = indent_match.group(1) if indent_match else "    "

    # Helper a inserer JUSTE APRES 'lines = ...'
    helper_block = [
        "",
        indent + "# " + MARK_R4 + " - tronque Active Thesis Summaries a top-5 blocs",
        indent + "def _truncate_active_thesis_v5(_lines, _keep=5):",
        indent + "    out = []",
        indent + "    in_section = False",
        indent + "    blocks_kept = 0",
        indent + "    blocks_total = 0",
        indent + "    skipping = False",
        indent + "    for _ln in _lines:",
        indent + "        _s = _ln.lstrip()",
        indent + "        if _s.startswith('## Active Thesis Summaries'):",
        indent + "            in_section = True",
        indent + "            out.append(_ln)",
        indent + "            continue",
        indent + "        if in_section and _s.startswith('## '):",
        indent + "            in_section = False",
        indent + "            if blocks_total > _keep:",
        indent + "                out.append('')",
        indent + "                out.append('*+ ' + str(blocks_total - _keep) + ' autres theses (voir Audit Trail pour le detail).*')",
        indent + "                out.append('')",
        indent + "            out.append(_ln)",
        indent + "            skipping = False",
        indent + "            continue",
        indent + "        if in_section and _s.startswith('### '):",
        indent + "            blocks_total += 1",
        indent + "            if blocks_total > _keep:",
        indent + "                skipping = True",
        indent + "            else:",
        indent + "                blocks_kept += 1",
        indent + "                skipping = False",
        indent + "        if in_section and skipping:",
        indent + "            continue",
        indent + "        out.append(_ln)",
        indent + "    return out",
        indent + "lines = _truncate_active_thesis_v5(lines, _keep=5)  # " + MARK_R4,
        "",
    ]

    new_lines = lines[:lines_assign_idx + 1] + helper_block + lines[lines_assign_idx + 1:]
    return "\n".join(new_lines), "OK R4 helper insere apres L" + str(lines_assign_idx + 1)


def main():
    print("=" * 70)
    print("PATCH V5 - IC Memo residuels R2 R3 R5 R4")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    # backup
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v5_" + ts
    shutil.copy2(TARGET, backup)
    print("Backup : " + backup)

    src = read_file(TARGET)
    print("Source : " + str(len(src)) + " chars")

    # Validation initiale
    try:
        ast.parse(src)
        print("AST initial : OK")
    except SyntaxError as e:
        print("[ERREUR] Source initial deja casse : " + str(e))
        sys.exit(1)

    # Pipeline de patches
    try:
        src, r2_msg = patch_r2_doublon(src)
        print("R2 : " + r2_msg)

        src, r3_msg = patch_r3_header(src)
        print("R3 : " + r3_msg)

        src, r4_msg = patch_r4_active_thesis_truncate(src)
        print("R4 : " + r4_msg)
    except Exception as e:
        print("[ERREUR PATCH] " + str(e))
        print("Rollback (aucune ecriture)")
        sys.exit(1)

    # Validation AST + py_compile sur le buffer en memoire
    try:
        ast.parse(src)
        print("AST apres patches : OK")
    except SyntaxError as e:
        print("[ERREUR AST apres patches] " + str(e))
        print("Rollback (aucune ecriture)")
        sys.exit(1)

    # Ecriture
    write_file(TARGET, src)
    print("Ecrit : " + TARGET + " (" + str(len(src)) + " chars)")

    # py_compile sur fichier
    try:
        py_compile.compile(TARGET, doraise=True)
        print("py_compile : OK")
    except py_compile.PyCompileError as e:
        print("[ERREUR py_compile] " + str(e))
        print("Rollback depuis " + backup)
        shutil.copy2(backup, TARGET)
        sys.exit(1)

    # Verifie presence markers
    final = read_file(TARGET)
    print("")
    print("Markers presents :")
    print("  " + MARK_R2 + " : " + ("OK" if MARK_R2 in final else "ABSENT"))
    print("  " + MARK_R3 + " : " + ("OK" if MARK_R3 in final else "ABSENT"))
    print("  " + MARK_R4 + " : " + ("OK" if MARK_R4 in final else "ABSENT"))

    print("")
    print("PATCH V5 termine.")
    print("")
    print("Actions :")
    print(" 1. Redemarrer uvicorn :")
    print("    py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print(" 2. Page IC Memos -> bouton 'Export PDF' sur un memo")
    print(" 3. M'envoyer le PDF telecharge pour validation finale")


if __name__ == "__main__":
    main()
