# -*- coding: utf-8 -*-
# Diag v11 : trace pourquoi le patch v5 n'a aucun effet visible
#
# Strategie :
#  1. Verifie l'environnement des 3 markers dans le fichier (context lignes)
#  2. Cherche toutes les definitions/duplications de get_memo_pdf
#  3. Cherche toutes occurrences "Thesis Summaries" et "thesis_summaries"
#  4. Dump complet de la zone entre markers pour voir si les wraps sont bien la
#  5. Cherche s'il y a un 3eme generateur de PDF (memo_generator.py?)
#  6. Verifie quelle est la VRAIE fonction exposee a la route via @app.get
#
# Sortie diag-v11-output.txt

import os
import re
import io

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
OUT = os.path.join(os.getcwd(), "diag-v11-output.txt")

MARKS = ["[ICMEMO_V5_R2]", "[ICMEMO_V5_R3]", "[ICMEMO_V5_R4]",
         "[ICMEMO_PDF_V2]", "[ICMEMO_PDF_V3_LIGHT]", "[ICMEMO_PDF_V4_COVER]"]


def main():
    buf = io.StringIO()

    def w(line=""):
        buf.write(str(line) + "\n")

    w("=" * 78)
    w("DIAG V11 - Trace effets reels du patch v5")
    w("=" * 78)

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()
    lines = src.split("\n")
    total = len(lines)
    w("Total lignes : " + str(total))
    w("")

    # 1) Localiser TOUTES les definitions de get_memo_pdf
    w("-" * 78)
    w("[1] Toutes definitions 'def get_memo_pdf'")
    w("-" * 78)
    defs = []
    for i, ln in enumerate(lines):
        if re.match(r"^def\s+get_memo_pdf\s*\(", ln):
            defs.append(i + 1)
    w("Lignes : " + str(defs))
    w("Total : " + str(len(defs)))
    w("")

    # 2) Quelle definition est decoree par @app.get("/api/memos/{...}/pdf") ?
    w("-" * 78)
    w("[2] Decorator @app.get/router.get pour memo pdf - quelle fonction est exposee ?")
    w("-" * 78)
    for i, ln in enumerate(lines):
        if "@app.get" in ln or "@router.get" in ln:
            if "/api/memos" in ln and "pdf" in ln:
                # cherche la fonction qui suit
                for j in range(i + 1, min(i + 5, total)):
                    if re.match(r"^def\s+", lines[j]):
                        w("L" + str(i + 1) + " : " + ln.rstrip()[:100])
                        w("  -> def en L" + str(j + 1) + " : " + lines[j].rstrip()[:100])
                        break
    w("")

    # 3) Toutes occurrences "Thesis Summaries" (avec contexte 1 ligne)
    w("-" * 78)
    w("[3] Toutes occurrences 'Thesis Summaries' et 'thesis_summaries'")
    w("-" * 78)
    for i, ln in enumerate(lines):
        if "Thesis Summaries" in ln or "thesis_summaries" in ln:
            w("L" + str(i + 1) + " : " + ln.rstrip()[:140])
    w("")

    # 4) Markers v5 + contexte (3 lignes avant, 3 apres)
    w("-" * 78)
    w("[4] Markers v5 + contexte")
    w("-" * 78)
    for mark in MARKS:
        w("--- " + mark + " ---")
        for i, ln in enumerate(lines):
            if mark in ln:
                lo = max(0, i - 2)
                hi = min(total, i + 4)
                for j in range(lo, hi):
                    tag = ">> " if j == i else "   "
                    w(tag + "L" + str(j + 1) + " | " + lines[j].rstrip()[:160])
                w("")

    # 5) Localiser la VRAIE fonction active (la 2eme) et verifier ses bornes apres patch v5
    w("-" * 78)
    w("[5] Fonction #2 get_memo_pdf - bornes apres patch")
    w("-" * 78)
    if len(defs) >= 2:
        f2_start = defs[1] - 1
        # fin = prochain @app.* ou @router.*
        f2_end = total
        for j in range(f2_start + 1, total):
            s = lines[j].lstrip()
            if s.startswith("@app.") or s.startswith("@router."):
                f2_end = j
                break
        w("Fonction #2 : L" + str(f2_start + 1) + " a L" + str(f2_end))
        w("Span : " + str(f2_end - f2_start) + " lignes")

        # Comptage markers DANS fonction #2
        w("")
        w("Markers presents dans fonction #2 :")
        for mark in MARKS:
            count_in_f2 = 0
            for j in range(f2_start, f2_end):
                if mark in lines[j]:
                    count_in_f2 += 1
            w("  " + mark + " : " + str(count_in_f2))
    w("")

    # 6) Cherche "if False:" autour du patch R2
    w("-" * 78)
    w("[6] Verif R2 : 'if False:' avec marker ICMEMO_V5_R2")
    w("-" * 78)
    for i, ln in enumerate(lines):
        if "ICMEMO_V5_R2" in ln and "if False" in ln:
            w("L" + str(i + 1) + " : " + ln.rstrip()[:160])
            # afficher 80 lignes apres pour voir l'etendue
            for j in range(i + 1, min(i + 80, total)):
                tag = "   "
                if "story.append" in lines[j] or "Paragraph(" in lines[j] or "Table(" in lines[j]:
                    tag = "** "
                w(tag + "L" + str(j + 1) + " | " + lines[j].rstrip()[:160])
                # stoppe si on tombe sur une ligne au niveau 4 espaces qui semble hors du wrap
                # critere : ligne non-vide et indentation == 4 espaces exactement
                s = lines[j]
                if s and not s.startswith("        ") and not s.startswith("    ") and s.strip():
                    break
                if s.startswith("    doc.build("):
                    w("   -> rencontre doc.build() -> fin de zone wrap")
                    break
            break  # un seul bloc
    w("")

    # 7) helper _truncate_active_thesis_v5 - verifier sa presence et son contexte
    w("-" * 78)
    w("[7] Helper R4 _truncate_active_thesis_v5")
    w("-" * 78)
    for i, ln in enumerate(lines):
        if "_truncate_active_thesis_v5" in ln:
            w("L" + str(i + 1) + " : " + ln.rstrip()[:160])
    w("")

    # 8) cherche 'lines = ' apres le helper R4 (pour voir s'il y a un reassignement qui ecrase)
    w("-" * 78)
    w("[8] Toutes assignations 'lines = ' dans la fonction #2 (apres helper R4)")
    w("-" * 78)
    if len(defs) >= 2:
        f2_start = defs[1] - 1
        for j in range(f2_start, f2_end):
            if re.match(r"^\s*lines\s*=\s*", lines[j]):
                w("L" + str(j + 1) + " : " + lines[j].rstrip()[:160])
    w("")

    # 9) PDF render lib utilises (verif si la fonction utilise bien reportlab et non autre chose)
    w("-" * 78)
    w("[9] Imports / outils PDF dans la fonction #2")
    w("-" * 78)
    if len(defs) >= 2:
        f2_start = defs[1] - 1
        for j in range(f2_start, min(f2_end, f2_start + 80)):
            ln = lines[j]
            if "import" in ln or "Paragraph" in ln or "from reportlab" in ln:
                w("L" + str(j + 1) + " : " + ln.rstrip()[:160])
    w("")

    # 10) Look for memo_generator.py reference
    w("-" * 78)
    w("[10] memo_generator references")
    w("-" * 78)
    for i, ln in enumerate(lines):
        if "memo_generator" in ln or "generate_memo" in ln:
            w("L" + str(i + 1) + " : " + ln.rstrip()[:160])
    w("")
    # presence du fichier
    mg = os.path.join(ROOT, "memo_generator.py")
    w("memo_generator.py existe : " + str(os.path.isfile(mg)))
    if os.path.isfile(mg):
        w("Taille : " + str(os.path.getsize(mg)) + " bytes, mtime : " + str(os.path.getmtime(mg)))
        # cherche 'def' qui contient 'pdf' dans memo_generator
        with open(mg, "r", encoding="utf-8-sig") as f2:
            mg_src = f2.read()
        mg_lines = mg_src.split("\n")
        w("Total lignes memo_generator : " + str(len(mg_lines)))
        for k, ln in enumerate(mg_lines):
            if re.match(r"^def\s+", ln) and ("pdf" in ln.lower() or "memo" in ln.lower() or "build" in ln.lower() or "render" in ln.lower()):
                w("  def L" + str(k + 1) + " : " + ln.rstrip()[:140])

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("Diag v11 ecrit dans : " + OUT)


if __name__ == "__main__":
    main()
