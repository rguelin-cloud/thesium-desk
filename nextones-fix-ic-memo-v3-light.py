# -*- coding: ascii -*-
# [MARKER] nextones-fix-ic-memo-v3-light
#
# Patch v3 : ALLEGE le rendu visuel du PDF IC Memo (apres v2 deja applique).
#   - SUPPRIME l'aplat sombre du header (bandeau navy plein) -> ligne fine claire
#   - SUPPRIME les fonds de header de tables (DEEP_TEAL plein, texte blanc)
#     -> header en teal LEGER, texte sombre, ou simple ligne basse
#   - SUPPRIME les ROWBACKGROUNDS zebres -> lignes horizontales fines uniquement
#   - PALETTE CLAIRE : teal pastel + beige tres clair, fini les contrastes durs
#
# Idempotent : marker [ICMEMO_PDF_V3_LIGHT]. Backup horodate. Rollback si py_compile fail.
#
# Usage :
#   py -3.13 .\nextones-fix-ic-memo-v3-light.py

import os
import py_compile
import re
import shutil
import sys
import time

API_FILE   = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER_V2  = "[ICMEMO_PDF_V2]"
MARKER_V3  = "[ICMEMO_PDF_V3_LIGHT]"


def read_utf8(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b.decode("utf-8")


def write_utf8(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))


def banner(t):
    print("")
    print("=" * 72)
    print("== " + t)
    print("=" * 72)


# ---- Substitutions ciblees sur le bloc v2 ----
# On modifie UNIQUEMENT les portions visuelles (couleurs + styles tables + header
# canvas). On NE touche PAS au parsing markdown, ni au calcul du titre, ni aux
# garde-fous B1.

# Couleurs : remplacer les anciennes valeurs (sombres) par des claires
# DEEP_TEAL #115058 -> #6FA8AE (teal pastel)
# MUTED_TEAL #20808D -> #8FC2C8 (teal tres clair)
# DARK_NAVY (utilise dans header rect) -> ne sera plus utilise pour aplat
# WARM_BEIGE garde mais ROWBACKGROUNDS retire

REPLACEMENTS = [
    # 1) Palette : assouplir les teals
    (
        'DARK_NAVY   = HexColor("#091717")',
        'DARK_NAVY   = HexColor("#091717")  # conserve mais plus utilise en aplat'
    ),
    (
        'DEEP_TEAL   = HexColor("#115058")',
        'DEEP_TEAL   = HexColor("#6FA8AE")  # [V3_LIGHT] teal pastel'
    ),
    (
        'MUTED_TEAL  = HexColor("#20808D")',
        'MUTED_TEAL  = HexColor("#8FC2C8")  # [V3_LIGHT] teal tres clair'
    ),
    # 2) Header canvas : supprimer le rectangle navy plein
    (
        '''    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(DARK_NAVY)
        canvas.rect(0, H - 18*mm, W, 18*mm, fill=1, stroke=0)
        canvas.setFillColor(MUTED_TEAL)
        canvas.setFont(FONT_BOLD, 11)
        canvas.drawString(15*mm, H - 12*mm, "NEXTONES.FINANCE")
        canvas.setFillColor(white)
        canvas.setFont(FONT_REG, 8)
        canvas.drawRightString(W - 15*mm, H - 12*mm,
                               f"IC Memo -- {raw_date}  |  Paper Trading")
        canvas.setStrokeColor(MUTED_TEAL)
        canvas.setLineWidth(1.2)
        canvas.line(15*mm, H - 18*mm, W - 15*mm, H - 18*mm)''',
        '''    def header_footer(canvas, doc):  # [V3_LIGHT] header epure, sans aplat
        canvas.saveState()
        # Pas de rectangle plein : juste typographie + filet teal pastel
        canvas.setFillColor(DEEP_TEAL)
        canvas.setFont(FONT_BOLD, 11)
        canvas.drawString(15*mm, H - 12*mm, "NEXTONES.FINANCE")
        canvas.setFillColor(HexColor("#5a7a7e"))
        canvas.setFont(FONT_REG, 8)
        canvas.drawRightString(W - 15*mm, H - 12*mm,
                               f"IC Memo -- {raw_date}  |  Paper Trading")
        canvas.setStrokeColor(MUTED_TEAL)
        canvas.setLineWidth(0.6)
        canvas.line(15*mm, H - 16*mm, W - 15*mm, H - 16*mm)'''
    ),
    # 3) Footer : couleur plus claire
    (
        '''        # Footer bas
        canvas.setFillColor(OFFBLACK)
        canvas.setFont(FONT_REG, 7)
        canvas.drawString(15*mm, 10*mm, "Nextones Desk -- AI-native fund operating system")''',
        '''        # Footer bas
        canvas.setFillColor(HexColor("#7a9094"))
        canvas.setFont(FONT_REG, 7)
        canvas.drawString(15*mm, 10*mm, "Nextones Desk -- AI-native fund operating system")'''
    ),
    # 4) Table style helper flush_md_table : header sans fond plein + pas de zebra
    (
        '''        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
            ("LEADING",    (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))''',
        '''        t.setStyle(TableStyle([
            # [V3_LIGHT] header transparent, juste filet bas teal pastel
            ("TEXTCOLOR",  (0, 0), (-1, 0), DEEP_TEAL),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 7.5),
            ("LEADING",    (0, 0), (-1, -1), 9.5),
            ("LINEBELOW",  (0, 0), (-1, 0), 0.8, MUTED_TEAL),
            ("LINEBELOW",  (0, 1), (-1, -1), 0.25, HexColor("#E5E3D4")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",  (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))'''
    ),
    # 5) Table Thesis Summaries : meme allegement
    (
        '''        t = Table(table_data, colWidths=[55, 85, 55, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))''',
        '''        t = Table(table_data, colWidths=[55, 85, 55, None])
        t.setStyle(TableStyle([  # [V3_LIGHT] header transparent, filet bas teal
            ("TEXTCOLOR",  (0, 0), (-1, 0), DEEP_TEAL),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("LINEBELOW",  (0, 0), (-1, 0), 0.8, MUTED_TEAL),
            ("LINEBELOW",  (0, 1), (-1, -1), 0.25, HexColor("#E5E3D4")),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))'''
    ),
    # 6) Table Proposed Changes : meme allegement
    (
        '''        t = Table(table_data, colWidths=[70, 60, 60, None])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DEEP_TEAL),
            ("TEXTCOLOR",  (0, 0), (-1, 0), white),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PAPER_WHITE, OFF_WHITE]),
            ("GRID",       (0, 0), (-1, -1), 0.4, WARM_BEIGE),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))''',
        '''        t = Table(table_data, colWidths=[70, 60, 60, None])
        t.setStyle(TableStyle([  # [V3_LIGHT] header transparent, filet bas teal
            ("TEXTCOLOR",  (0, 0), (-1, 0), DEEP_TEAL),
            ("FONTNAME",   (0, 0), (-1, 0), FONT_BOLD),
            ("FONTSIZE",   (0, 0), (-1, -1), 8.5),
            ("LEADING",    (0, 0), (-1, -1), 11),
            ("LINEBELOW",  (0, 0), (-1, 0), 0.8, MUTED_TEAL),
            ("LINEBELOW",  (0, 1), (-1, -1), 0.25, HexColor("#E5E3D4")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))'''
    ),
    # 7) Styles H1/H2 : titres en teal plus doux
    (
        '    sH1 = ParagraphStyle("MemoH1", parent=styles["Heading1"],\n        fontSize=16, leading=20, textColor=OFFBLACK,\n        spaceAfter=6, spaceBefore=12, fontName=FONT_BOLD)',
        '    sH1 = ParagraphStyle("MemoH1", parent=styles["Heading1"],  # [V3_LIGHT]\n        fontSize=16, leading=20, textColor=DEEP_TEAL,\n        spaceAfter=6, spaceBefore=12, fontName=FONT_BOLD)'
    ),
    (
        '    sH2 = ParagraphStyle("MemoH2", parent=styles["Heading2"],\n        fontSize=12, leading=15, textColor=DEEP_TEAL,\n        spaceAfter=4, spaceBefore=10, fontName=FONT_BOLD)',
        '    sH2 = ParagraphStyle("MemoH2", parent=styles["Heading2"],  # [V3_LIGHT]\n        fontSize=12, leading=15, textColor=MUTED_TEAL,\n        spaceAfter=4, spaceBefore=10, fontName=FONT_BOLD)'
    ),
    # 8) Marker pour idempotence
    (
        '@app.get("/api/memos/{memo_id}/pdf")  # [ICMEMO_PDF_V2]',
        '@app.get("/api/memos/{memo_id}/pdf")  # [ICMEMO_PDF_V2] [ICMEMO_PDF_V3_LIGHT]'
    ),
]


def main():
    print("nextones-fix-ic-memo-v3-light  -  31/05/2026")
    print("FILE : " + API_FILE)
    if not os.path.exists(API_FILE):
        print("[FATAL] api_server.py introuvable")
        sys.exit(1)

    src = read_utf8(API_FILE)

    if MARKER_V3 in src:
        print("[SKIP] Marker " + MARKER_V3 + " deja present. Patch deja applique.")
        return 0

    if MARKER_V2 not in src:
        print("[FATAL] Marker " + MARKER_V2 + " introuvable.")
        print("       Le patch v2 (nextones-fix-ic-memo-v2.py) doit etre")
        print("       applique avant ce v3-light.")
        sys.exit(2)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bk = API_FILE + ".bak_icmemo_v3light_" + ts
    shutil.copy2(API_FILE, bk)
    print("  backup : " + bk)

    # Apply substitutions
    new_src = src
    applied = 0
    failed = []
    for old, new in REPLACEMENTS:
        if old in new_src:
            new_src = new_src.replace(old, new, 1)
            applied += 1
        else:
            # On capture l'echec pour reporting
            failed.append(old.splitlines()[0][:80])

    print("  substitutions appliquees : %d / %d" % (applied, len(REPLACEMENTS)))
    if failed:
        print("  [WARN] non trouvees (probable derive du v2) :")
        for f in failed:
            print("    - " + f)

    if applied == 0:
        print("[FATAL] aucune substitution n'a pu etre appliquee.")
        sys.exit(3)

    write_utf8(API_FILE, new_src)
    print("  ecrit  : %d bytes" % len(new_src.encode("utf-8")))

    # Validation py_compile
    try:
        py_compile.compile(API_FILE, doraise=True)
        print("  py_compile : OK")
    except py_compile.PyCompileError as pce:
        print("[FAIL] py_compile : " + str(pce))
        shutil.copy2(bk, API_FILE)
        print("  ROLLBACK depuis " + bk)
        sys.exit(4)

    banner("DONE")
    print("Allegement visuel applique. Prochaines etapes :")
    print("  1) Redemarrer l'API :")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) Retelecharger les 2 PDFs temoins :")
    print("     http://localhost:8000/api/memos/1/pdf")
    print("     http://localhost:8000/api/memos/49/pdf")
    print("  3) Verifier visuellement :")
    print("     - Header : plus de bandeau sombre, juste texte + fine ligne teal pastel")
    print("     - Tables : plus de fond plein sur header, plus de zebra, juste filets fins")
    print("     - Titres : teal doux au lieu de noir/teal fonce")
    return 0


if __name__ == "__main__":
    sys.exit(main())
