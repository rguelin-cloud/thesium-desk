# -*- coding: utf-8 -*-
# Patch v7 - corrige R3-bis (header invisible) et R5 (Factor Scores orphelin)
# dans la fonction #1 de api_server.py (L1079-L1528).
#
# DECOUVERTE v12 :
#   La cause des en-tetes invisibles : sTH = ParagraphStyle(textColor=white, ...)
#   ReportLab applique textColor du ParagraphStyle, pas le TEXTCOLOR du TableStyle
#   sur les Paragraph. Donc texte blanc sur fond blanc = invisible.
#
# CORRECTIONS :
#
#   R3-BIS : L1328-1330 - change 'textColor=white' -> 'textColor=DEEP_TEAL'
#            dans la def sTH (style header de flush_md_table).
#            Cela corrige TOUTES les tables du PDF en meme temps.
#
#   R5     : Wrapper '### Factor Scores' + table suivante dans KeepTogether
#            pour eviter l'orphelin titre/table au page break.
#            Strategie : reperer la zone story.append(Paragraph(txt, sH1/sH2))
#            et detecter quand txt vaut 'Factor Scores' -> stocker pending_title,
#            puis lors du prochain Table(), wrapper [pending_title, table] dans
#            KeepTogether.
#            Approche minimale : juste avant 'return [KeepTogether([t])]' L1362
#            de flush_md_table, on a deja KeepTogether. Le probleme est en amont :
#            le sH2 'Factor Scores' est ajoute SEUL au story, puis flush_md_table
#            ajoute KeepTogether([t]). Resultat : sH2 en bas P1, table sur P2.
#            Solution : modifier flush_md_table pour qu'il accepte un titre
#            optionnel ET, plus simple : injecter un KeepTogether([dernier H2/H3
#            du story, t]) si le dernier element story est un Paragraph H2/H3.
#
# Garanties :
# - utf-8-sig lecture, utf-8 sans BOM ecriture
# - ast.parse + py_compile pre/post ecriture
# - backup horodate + rollback auto
# - markers V7 idempotents

import os
import re
import sys
import ast
import shutil
import datetime
import py_compile

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")

MARK_R3BIS = "[ICMEMO_V7_R3BIS]"
MARK_R5 = "[ICMEMO_V7_R5]"


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


def patch_r3bis(src):
    """Change textColor=white -> textColor=DEEP_TEAL dans sTH (header style)."""
    if MARK_R3BIS in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche la ligne contenant 'textColor=white, fontName=FONT_BOLD)'
    # dans sTH (proche de la def sTH = ParagraphStyle("TH"...)
    th_def_idx = None
    target_idx = None
    for i in range(f1_start, f1_end):
        if 'ParagraphStyle("TH"' in lines[i] or "ParagraphStyle('TH'" in lines[i]:
            th_def_idx = i
            break
    if th_def_idx is None:
        raise RuntimeError("Definition sTH = ParagraphStyle introuvable dans fonction #1")

    # La definition s'etend sur 1-2 lignes, on cherche 'textColor=white' dans les 3 lignes suivantes
    for j in range(th_def_idx, min(th_def_idx + 4, f1_end)):
        if "textColor=white" in lines[j]:
            target_idx = j
            break
    if target_idx is None:
        raise RuntimeError("'textColor=white' introuvable autour de sTH L" + str(th_def_idx + 1))

    # Remplacement : textColor=white -> textColor=DEEP_TEAL + marker
    old_line = lines[target_idx]
    new_line = old_line.replace("textColor=white", "textColor=DEEP_TEAL")
    # ajoute marker en commentaire en fin de ligne si pas deja present
    if MARK_R3BIS not in new_line:
        if new_line.rstrip().endswith(")"):
            new_line = new_line.rstrip() + "  # " + MARK_R3BIS + " header lisible (etait white)"
        else:
            new_line = new_line + "  # " + MARK_R3BIS

    lines[target_idx] = new_line
    return "\n".join(lines), "OK R3-bis textColor white->DEEP_TEAL L" + str(target_idx + 1)


def patch_r5_keeptogether(src):
    """
    Wrap H2/H3 precedant un Table dans KeepTogether pour eviter Factor Scores orphelin.

    Strategie minimale et robuste : modifier flush_md_table L1313 pour qu'il consulte
    le 'story' parent et, si le dernier element est un Paragraph (titre), le retire
    de story et le wrappe avec t dans KeepTogether.

    Mais flush_md_table est une fonction interne qui ne voit pas 'story'. On modifie
    son comportement de retour : au lieu de retourner [KeepTogether([t])], on
    retourne un marker special qui est intercepte plus loin... trop complexe.

    Approche alternative plus simple : modifier le 'return [KeepTogether([t])]'
    L1362 pour retourner [KeepTogether([t])] inchange, MAIS modifier les sites
    qui appellent flush_md_table pour absorber le titre H2/H3 precedent.

    Approche LA PLUS SIMPLE : injecter, juste apres 'def flush_md_table(...):',
    un parametre optionnel via closure - non, on ne peut pas.

    SOLUTION FINALE : ajouter une fonction utilitaire _wrap_title_with_table(story, t)
    qui retire le dernier element si c'est un Paragraph H2/H3 et le wrappe avec t.
    Puis remplacer 'return [KeepTogether([t])]' par cette logique.

    Pour cela on a besoin de l'acces a 'story' - or flush_md_table est definie
    AVANT que story soit construit. Mais 'story' est une variable de la fonction
    englobante get_memo_pdf, donc flush_md_table y a acces via closure.

    Implementation : remplacer L1362 'return [KeepTogether([t])]' par :
        # [ICMEMO_V7_R5] - absorbe le titre H2/H3 precedent dans KeepTogether
        if story and hasattr(story[-1], 'style') and getattr(story[-1].style, 'name', '') in ('H1', 'H2', 'H3'):
            _last = story.pop()
            return [KeepTogether([_last, t])]
        return [KeepTogether([t])]
    """
    if MARK_R5 in src:
        return src, "SKIP (deja patche)"

    lines = src.split("\n")
    f1_start, f1_end, _ = find_func1_bounds(src)

    # Cherche return [KeepTogether([t])] dans flush_md_table
    target_idx = None
    for i in range(f1_start, f1_end):
        if "return [KeepTogether([t])]" in lines[i]:
            target_idx = i
            break
    if target_idx is None:
        raise RuntimeError("'return [KeepTogether([t])]' introuvable dans fonction #1")

    # Indentation
    indent_match = re.match(r"^(\s*)", lines[target_idx])
    indent = indent_match.group(1) if indent_match else "        "

    # Remplacement multi-ligne
    new_block = [
        indent + "# " + MARK_R5 + " - absorbe titre H1/H2/H3 precedent dans KeepTogether",
        indent + "try:",
        indent + "    _last = story[-1] if story else None",
        indent + "    _style_name = getattr(getattr(_last, 'style', None), 'name', '') if _last is not None else ''",
        indent + "    if _style_name in ('H1', 'H2', 'H3'):",
        indent + "        story.pop()",
        indent + "        return [KeepTogether([_last, t])]",
        indent + "except Exception:",
        indent + "    pass",
        indent + "return [KeepTogether([t])]",
    ]

    # Supprime la ligne originale et insere le bloc
    new_lines = lines[:target_idx] + new_block + lines[target_idx + 1:]
    return "\n".join(new_lines), "OK R5 KeepTogether titre+table L" + str(target_idx + 1)


def main():
    print("=" * 70)
    print("PATCH V7 - R3-bis (header invisible) + R5 (Factor Scores orphelin)")
    print("=" * 70)

    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        sys.exit(1)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak_v7_" + ts
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
        src, r3bis_msg = patch_r3bis(src)
        print("R3-bis : " + r3bis_msg)

        src, r5_msg = patch_r5_keeptogether(src)
        print("R5     : " + r5_msg)
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
    print("Markers v7 :")
    print("  " + MARK_R3BIS + " : " + ("OK (" + str(final.count(MARK_R3BIS)) + ")" if MARK_R3BIS in final else "ABSENT"))
    print("  " + MARK_R5 + "      : " + ("OK (" + str(final.count(MARK_R5)) + ")" if MARK_R5 in final else "ABSENT"))

    print("")
    print("PATCH V7 termine.")
    print("")
    print("Actions :")
    print("  1. Ctrl+C uvicorn dans sa fenetre")
    print("  2. py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  3. py -3.13 .\\nextones-test-memo-pdf-direct.py")
    print("  4. M'envoyer memo-51-v5-direct.pdf (le script ecrase le precedent)")


if __name__ == "__main__":
    main()
