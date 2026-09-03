# -*- coding: utf-8 -*-
# Diag v13 - styles sH1/sH2/sH3 + insertions Spacer dans la fonction #1
# Objectif : comprendre pourquoi KeepTogether V7_R5 ne capture pas le titre
# H3 'Factor Scores' avant la table.
#
# Hypotheses :
#   H1 - les ParagraphStyle 'H1'/'H2'/'H3' ont un name different (ex: 'Heading3')
#   H2 - un Spacer est insere entre Paragraph(titre) et l'accumulation de table
#        -> story[-1] est le Spacer, pas le Paragraph
#   H3 - le titre Factor Scores est rendu via un autre code path

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
OUT = os.path.join(ROOT, "diag-v13-output.txt")


def read_file(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def find_func1_bounds(lines):
    occurrences = []
    for i, ln in enumerate(lines):
        if re.match(r"^def\s+get_memo_pdf\s*\(", ln):
            occurrences.append(i)
    if not occurrences:
        return None, None
    f1_start = occurrences[0]
    f1_end = len(lines)
    for j in range(f1_start + 1, len(lines)):
        if "# === END [ICMEMO_PDF_V2] ===" in lines[j]:
            f1_end = j
            break
        if re.match(r"^def\s+get_memo_pdf\s*\(", lines[j]):
            f1_end = j
            break
    return f1_start, f1_end


def main():
    src = read_file(TARGET)
    lines = src.split("\n")
    out = []
    out.append("=" * 70)
    out.append("DIAG V13 - styles sH1/sH2/sH3 + Spacer insertions")
    out.append("=" * 70)
    out.append("")

    f1_start, f1_end = find_func1_bounds(lines)
    out.append("Bornes fonction #1 : L" + str(f1_start + 1) + ".." + str(f1_end + 1))
    out.append("")

    # [1] Definitions sH1, sH2, sH3, sBody, sBullet, sSmall
    out.append("[1] Definitions des styles ParagraphStyle dans fonction #1")
    out.append("-" * 70)
    style_patterns = [
        r"\bsH1\s*=",
        r"\bsH2\s*=",
        r"\bsH3\s*=",
        r"\bsBody\s*=",
        r"\bsBullet\s*=",
        r"\bsSmall\s*=",
        r"\bsTitle\s*=",
    ]
    for i in range(f1_start, f1_end):
        for p in style_patterns:
            if re.search(p, lines[i]):
                # dump cette ligne + jusqu'a 3 lignes si la def s'etend
                out.append("L" + str(i + 1).rjust(4) + " | " + lines[i].rstrip())
                # continuation : si la ligne ne se termine pas par ) on ajoute jusqu'a fermeture
                if not lines[i].rstrip().endswith(")"):
                    for k in range(i + 1, min(i + 5, f1_end)):
                        out.append("L" + str(k + 1).rjust(4) + " | " + lines[k].rstrip())
                        if lines[k].rstrip().endswith(")"):
                            break
                break
    out.append("")

    # [2] Toutes les recherches ParagraphStyle( dans fonction #1
    out.append("[2] Tous les ParagraphStyle(...) dans fonction #1")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        if "ParagraphStyle(" in lines[i]:
            out.append("L" + str(i + 1).rjust(4) + " | " + lines[i].rstrip())
    out.append("")

    # [3] Toutes les insertions Spacer dans fonction #1
    out.append("[3] Toutes les insertions Spacer dans fonction #1")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        if "Spacer(" in lines[i] or "story.append(Spacer" in lines[i]:
            out.append("L" + str(i + 1).rjust(4) + " | " + lines[i].rstrip())
    out.append("")

    # [4] Zone story.append(Paragraph(txt, sH1/sH2/sH3 + 5 lignes autour
    out.append("[4] Contexte story.append(Paragraph(txt, sH1/sH2/sH3)")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        m = re.search(r"story\.append\(Paragraph\(.+,\s*(sH1|sH2|sH3|sTitle)", lines[i])
        if m:
            lo = max(f1_start, i - 2)
            hi = min(f1_end, i + 5)
            out.append("--- Match L" + str(i + 1) + " style=" + m.group(1) + " ---")
            for k in range(lo, hi):
                out.append("L" + str(k + 1).rjust(4) + " | " + lines[k].rstrip())
            out.append("")

    # [5] Zone autour du marker V7_R5 (return KeepTogether)
    out.append("[5] Zone V7_R5 (return KeepTogether)")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        if "[ICMEMO_V7_R5]" in lines[i]:
            lo = max(f1_start, i - 2)
            hi = min(f1_end, i + 14)
            for k in range(lo, hi):
                out.append("L" + str(k + 1).rjust(4) + " | " + lines[k].rstrip())
            out.append("")
            break

    # [6] Boucle parsing markdown : detection de comment table_rows est detectee
    # et comment flush_md_table est appelee (pour voir l'ordre des operations)
    out.append("[6] Appels flush_md_table dans fonction #1 (contexte 4 lignes)")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        if re.search(r"\bflush_md_table\s*\(", lines[i]) and "def flush_md_table" not in lines[i]:
            lo = max(f1_start, i - 3)
            hi = min(f1_end, i + 5)
            out.append("--- Appel L" + str(i + 1) + " ---")
            for k in range(lo, hi):
                out.append("L" + str(k + 1).rjust(4) + " | " + lines[k].rstrip())
            out.append("")

    out.append("=" * 70)
    out.append("FIN DIAG V13")
    out.append("=" * 70)

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("Diag v13 ecrit : " + OUT)
    print("Total lignes : " + str(len(out)))


if __name__ == "__main__":
    main()
