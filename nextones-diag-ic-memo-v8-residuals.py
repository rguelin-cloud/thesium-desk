# -*- coding: utf-8 -*-
# Diag v8 : localiser dans api_server.py les zones a patcher en v5
# Cibles :
#   R2 = 2eme bloc "Thesis Summaries" apres "Audit Trail" (doublon a supprimer)
#   R3 = tables "Market Indicators" et "Proposed Changes" sans en-tete
#   R4 = boucle "Active Thesis Summaries" a limiter a top-5
#   R5 = "Factor Scores" titre sans en-tete colonne
#
# Sortie ASCII dans diag-v8-output.txt
# Lecture utf-8-sig, ecriture utf-8 sans BOM

import os
import re
import sys
import io

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
OUT = os.path.join(os.getcwd(), "diag-v8-output.txt")


def main():
    buf = io.StringIO()

    def w(line=""):
        buf.write(str(line) + "\n")

    w("=" * 78)
    w("DIAG V8 - LOCALISATION ZONES PATCH V5 (R2 R3 R4 R5)")
    w("=" * 78)
    w("Target : " + TARGET)
    w("")

    if not os.path.isfile(TARGET):
        w("[ERREUR] fichier introuvable")
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(buf.getvalue())
        return

    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    total = len(lines)
    w("Total lignes : " + str(total))
    w("")

    # ---- Etape 1 : delimiter la route /api/memos/{id}/pdf (de L1078 a fin fonction) ----
    w("-" * 78)
    w("[1] Bornes route /api/memos/{id}/pdf")
    w("-" * 78)
    start_idx = None
    for i in range(max(0, 1070), min(total, 1090)):
        if "/api/memos" in lines[i] and "pdf" in lines[i]:
            start_idx = i
            break
    if start_idx is None:
        # fallback : grep complet
        for i in range(total):
            if "/api/memos/{" in lines[i] and "pdf" in lines[i]:
                start_idx = i
                break
    w("Decorator route a ligne : " + str((start_idx + 1) if start_idx is not None else "?"))

    # Trouver fin de fonction = prochain decorator @app au meme niveau d'indentation
    end_idx = total
    if start_idx is not None:
        for j in range(start_idx + 2, total):
            stripped = lines[j].lstrip()
            if stripped.startswith("@app.") or stripped.startswith("@router."):
                end_idx = j
                break
    w("Fin de fonction (next decorator) ligne : " + str(end_idx))
    w("Span : " + str(end_idx - (start_idx or 0)) + " lignes")
    w("")

    # ---- Etape 2 : recherche occurrences "Thesis Summaries" (R2 doublon) ----
    w("-" * 78)
    w("[2] R2 - occurrences 'Thesis Summaries' dans la route")
    w("-" * 78)
    thesis_hits = []
    if start_idx is not None:
        for i in range(start_idx, end_idx):
            if "Thesis Summaries" in lines[i]:
                thesis_hits.append(i + 1)
                w("L" + str(i + 1) + " : " + lines[i].rstrip()[:120])
    w("Total occurrences : " + str(len(thesis_hits)))
    w("Note : 'Active Thesis Summaries' = legitime (R4), 'Thesis Summaries' seul = doublon (R2)")
    w("")

    # Distinguer "Active Thesis Summaries" et "Thesis Summaries" tout court
    active_hits = []
    plain_hits = []
    if start_idx is not None:
        for i in range(start_idx, end_idx):
            txt = lines[i]
            if "Active Thesis Summaries" in txt:
                active_hits.append(i + 1)
            elif "Thesis Summaries" in txt:
                plain_hits.append(i + 1)
    w("'Active Thesis Summaries' (R4 a borner) : " + str(active_hits))
    w("'Thesis Summaries' seul (R2 doublon) : " + str(plain_hits))
    w("")

    # ---- Etape 3 : recherche occurrences "Market Indicators", "Proposed Changes", "Factor Scores" (R3 R5) ----
    w("-" * 78)
    w("[3] R3 R5 - titres tables sans en-tete colonnes")
    w("-" * 78)
    for label in ("Market Indicators", "Proposed Changes", "Factor Scores", "Audit Trail"):
        w("Recherche : '" + label + "'")
        if start_idx is not None:
            for i in range(start_idx, end_idx):
                if label in lines[i]:
                    w("  L" + str(i + 1) + " : " + lines[i].rstrip()[:120])
        w("")

    # ---- Etape 4 : recherche Table([...]) qui pourraient manquer d'en-tete ----
    w("-" * 78)
    w("[4] Appels Table(...) dans la route (top 30 premiers)")
    w("-" * 78)
    tab_hits = []
    if start_idx is not None:
        for i in range(start_idx, end_idx):
            stripped = lines[i].lstrip()
            if stripped.startswith("Table(") or " Table(" in lines[i] or "=Table(" in lines[i].replace(" ", ""):
                tab_hits.append(i + 1)
                w("L" + str(i + 1) + " : " + lines[i].rstrip()[:120])
                if len(tab_hits) >= 30:
                    break
    w("Total : " + str(len(tab_hits)))
    w("")

    # ---- Etape 5 : recherche boucle for ... in ... pour Active Thesis (R4) ----
    w("-" * 78)
    w("[5] R4 - localiser la boucle Active Thesis (zone 200 lignes apres 'Active Thesis Summaries')")
    w("-" * 78)
    if active_hits:
        ahi = active_hits[0] - 1
        w("Zone autour de L" + str(ahi + 1) + " (active_hits[0]) :")
        for j in range(max(0, ahi - 2), min(total, ahi + 60)):
            tag = ">>" if j == ahi else "  "
            w(tag + " L" + str(j + 1) + " " + lines[j].rstrip()[:140])
    w("")

    # ---- Etape 6 : recherche zone "if False:" du v4 (R2 patch deja tente) ----
    w("-" * 78)
    w("[6] Verifier 'if False:' v4 deja en place (R2 patch echoue car mauvaise localisation)")
    w("-" * 78)
    if start_idx is not None:
        for i in range(start_idx, end_idx):
            if "if False:" in lines[i] or "[ICMEMO_PDF_V4_COVER]" in lines[i] or "[ICMEMO_PDF_V2]" in lines[i] or "[ICMEMO_PDF_V3_LIGHT]" in lines[i]:
                ctx_lo = max(0, i - 1)
                ctx_hi = min(total, i + 4)
                w("L" + str(i + 1) + " :")
                for k in range(ctx_lo, ctx_hi):
                    w("  " + str(k + 1) + " | " + lines[k].rstrip()[:140])
                w("")

    # ---- Etape 7 : recherche cle du markdown source (memo body) pour comprendre R3 ----
    w("-" * 78)
    w("[7] R3 - logique table markdown -> ReportLab (detection en-tete)")
    w("-" * 78)
    for needle in ("split('|')", '"|"', "markdown_table", "build_table", "is_table_row", "header_row", "separator"):
        w("Recherche : " + needle)
        if start_idx is not None:
            for i in range(start_idx, end_idx):
                if needle in lines[i]:
                    w("  L" + str(i + 1) + " : " + lines[i].rstrip()[:140])
        w("")

    # Ecrit le fichier
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("Diag v8 ecrit dans : " + OUT)


if __name__ == "__main__":
    main()
