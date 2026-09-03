# -*- coding: utf-8 -*-
# Diag v12 - Dump precis de flush_md_table dans la fonction #1 (L1079-L1492)
# pour comprendre pourquoi les en-tetes de tables sont invisibles dans le PDF
# malgre l'application des 4 styles V6_R3.
#
# Hypotheses :
#   H1 : data[0] n'est PAS le header (header rendu via Paragraph separe au-dessus)
#   H2 : TEXTCOLOR header force a couleur = BACKGROUND header (texte invisible)
#   H3 : ligne 0 de data est vide / placeholder
#   H4 : V4_COVER a casse le rendu du header
#
# Sortie : sections clairement separees
#   [1] Bornes fonction #1
#   [2] Dump complet de flush_md_table (def jusqu'a la prochaine def ou dedent)
#   [3] Tous les TableStyle du PDF (header colors, fonts, padding)
#   [4] Tous les Paragraph qui apparaissent juste avant 'doc.build' ou 't = Table('
#   [5] Recherche 'data' / 'header' / 'col_widths' dans fonction #1
#   [6] Detection de Factor Scores (titre orphelin R5)
#
# Lecture utf-8-sig, ASCII pur.

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
OUT = os.path.join(ROOT, "diag-v12-output.txt")


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
    if not os.path.isfile(TARGET):
        print("[ERREUR] " + TARGET + " introuvable")
        return

    src = read_file(TARGET)
    lines = src.split("\n")
    out = []

    out.append("=" * 70)
    out.append("DIAG V12 - flush_md_table dans fonction #1 (api_server.py)")
    out.append("=" * 70)
    out.append("")

    # [1] Bornes
    f1_start, f1_end = find_func1_bounds(lines)
    if f1_start is None:
        out.append("[ERREUR] Aucune def get_memo_pdf trouvee")
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out))
        return

    out.append("[1] Bornes fonction #1")
    out.append("    start = L" + str(f1_start + 1))
    out.append("    end   = L" + str(f1_end + 1))
    out.append("    span  = " + str(f1_end - f1_start) + " lignes")
    out.append("")

    # [2] Dump de flush_md_table : cherche 'def flush_md_table' OU 'flush_md_table'
    # comme fonction interne. Si pas trouve comme def, dump la zone autour de 't = Table(data'
    out.append("[2] Dump flush_md_table")
    out.append("-" * 70)

    flush_def_idx = None
    for i in range(f1_start, f1_end):
        if re.match(r"^\s+def\s+flush_md_table\s*\(", lines[i]):
            flush_def_idx = i
            break

    if flush_def_idx is not None:
        # detecte fin : ligne au meme indent que def avec une nouvelle def OU
        # un nouveau bloc au niveau parent
        def_indent = len(lines[flush_def_idx]) - len(lines[flush_def_idx].lstrip(" "))
        flush_end_idx = f1_end
        for j in range(flush_def_idx + 1, f1_end):
            ln = lines[j]
            if not ln.strip():
                continue
            cur_indent = len(ln) - len(ln.lstrip(" "))
            # fin si dedent strictement <= def_indent et ce n'est pas une continuation
            if cur_indent <= def_indent and not ln.lstrip().startswith("#"):
                flush_end_idx = j
                break

        out.append("def flush_md_table trouvee : L" + str(flush_def_idx + 1) + ".." + str(flush_end_idx + 1))
        out.append("")
        for k in range(flush_def_idx, flush_end_idx):
            out.append("L" + str(k + 1).rjust(4) + " | " + lines[k])
    else:
        out.append("def flush_md_table introuvable - dump zone autour de 't = Table(data, colWidths=col_widths'")
        out.append("")
        for i in range(f1_start, f1_end):
            if "t = Table(data, colWidths=col_widths" in lines[i]:
                lo = max(f1_start, i - 60)
                hi = min(f1_end, i + 30)
                out.append("Contexte L" + str(lo + 1) + ".." + str(hi + 1))
                for k in range(lo, hi):
                    out.append("L" + str(k + 1).rjust(4) + " | " + lines[k])
                out.append("")
                break

    out.append("")
    out.append("-" * 70)

    # [3] Tous les TableStyle de fonction #1
    out.append("[3] Tous TableStyle de fonction #1")
    out.append("-" * 70)
    in_ts = False
    ts_buf = []
    ts_start = None
    for i in range(f1_start, f1_end):
        ln = lines[i]
        if "TableStyle(" in ln and not in_ts:
            in_ts = True
            ts_buf = [(i, ln)]
            ts_start = i
            # mono-ligne ?
            if ln.count("(") <= ln.count(")"):
                out.append("--- TableStyle L" + str(ts_start + 1) + " (mono-ligne) ---")
                out.append("L" + str(i + 1).rjust(4) + " | " + ln)
                in_ts = False
                ts_buf = []
            continue
        if in_ts:
            ts_buf.append((i, ln))
            if ln.rstrip().endswith("]))") or ln.rstrip().endswith("))"):
                out.append("--- TableStyle L" + str(ts_start + 1) + ".." + str(i + 1) + " ---")
                for (idx, content) in ts_buf:
                    out.append("L" + str(idx + 1).rjust(4) + " | " + content)
                out.append("")
                in_ts = False
                ts_buf = []
    out.append("")
    out.append("-" * 70)

    # [4] Recherche header markers : BACKGROUND header / TEXTCOLOR header / Paragraph header
    out.append("[4] Lignes contenant 'BACKGROUND', 'TEXTCOLOR', 'header', 'Paragraph' dans fonction #1")
    out.append("-" * 70)
    keywords = ["BACKGROUND", "TEXTCOLOR", "header", "Header", "data[0]", "data.insert", "data.append([", "Paragraph("]
    for i in range(f1_start, f1_end):
        ln = lines[i]
        for kw in keywords:
            if kw in ln:
                out.append("L" + str(i + 1).rjust(4) + " | [" + kw + "] " + ln.rstrip())
                break
    out.append("")
    out.append("-" * 70)

    # [5] Recherche col_widths et data definition
    out.append("[5] Recherche 'col_widths' et 'data =' / 'data.append' dans fonction #1")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        ln = lines[i]
        if re.search(r"\bcol_widths\b", ln) or re.search(r"\bdata\s*=\s*\[", ln) or re.search(r"\bdata\.append", ln):
            out.append("L" + str(i + 1).rjust(4) + " | " + ln.rstrip())
    out.append("")
    out.append("-" * 70)

    # [6] R5 - Factor Scores titre orphelin
    out.append("[6] R5 - recherche 'Factor Scores' dans fonction #1 et memo_generator")
    out.append("-" * 70)
    for i in range(f1_start, f1_end):
        if "Factor Scores" in lines[i]:
            lo = max(f1_start, i - 5)
            hi = min(f1_end, i + 10)
            out.append("Contexte L" + str(lo + 1) + ".." + str(hi + 1) + " (fonction #1)")
            for k in range(lo, hi):
                out.append("L" + str(k + 1).rjust(4) + " | " + lines[k])
            out.append("")

    # Cherche aussi dans memo_generator.py
    memo_gen = os.path.join(ROOT, "memo_generator.py")
    if os.path.isfile(memo_gen):
        gen_src = read_file(memo_gen)
        gen_lines = gen_src.split("\n")
        for i, ln in enumerate(gen_lines):
            if "Factor Scores" in ln:
                lo = max(0, i - 3)
                hi = min(len(gen_lines), i + 8)
                out.append("memo_generator.py L" + str(lo + 1) + ".." + str(hi + 1))
                for k in range(lo, hi):
                    out.append("L" + str(k + 1).rjust(4) + " | " + gen_lines[k])
                out.append("")
    out.append("")
    out.append("-" * 70)

    # [7] Markers V6 confirmation localisation
    out.append("[7] Markers V6 - localisation precise")
    out.append("-" * 70)
    for marker in ["[ICMEMO_V6_R2]", "[ICMEMO_V6_R3]", "[ICMEMO_V6_R4]"]:
        for i in range(f1_start, f1_end):
            if marker in lines[i]:
                out.append("L" + str(i + 1).rjust(4) + " | " + marker + " | " + lines[i].rstrip())
    out.append("")
    out.append("=" * 70)
    out.append("FIN DIAG V12")
    out.append("=" * 70)

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    print("Diag v12 ecrit : " + OUT)
    print("Total lignes : " + str(len(out)))


if __name__ == "__main__":
    main()
