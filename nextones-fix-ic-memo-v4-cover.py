# -*- coding: ascii -*-
# [MARKER] nextones-fix-ic-memo-v4-cover
#
# Patch v4 : applique APRES v2 + v3-light.
#   - Ajoute un BANDEAU DE COUVERTURE en page 1 (aplat bleu pale + titre noir
#     gras + sous-titre date), style cover-page pro
#   - R1/R6 : reduit le H1 (16->14pt, leading 18) pour eviter cassure mot
#   - R2    : SUPPRIME les 2 tables doublon en fin de PDF
#             ("Thesis Summaries" + "Proposed Changes") deja rendues dans le
#             body markdown
#   - R5    : elargit la colonne Status dans "Proposed Changes & Executions"
#             pour eviter "pending_validat / ion" coupe en 2 mots
#
# Idempotent : marker [ICMEMO_PDF_V4_COVER]. Backup horodate. Rollback py_compile.
#
# Usage :
#   py -3.13 .\nextones-fix-ic-memo-v4-cover.py

import os
import py_compile
import re
import shutil
import sys
import time

API_FILE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER_V2 = "[ICMEMO_PDF_V2]"
MARKER_V3 = "[ICMEMO_PDF_V3_LIGHT]"
MARKER_V4 = "[ICMEMO_PDF_V4_COVER]"


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


# ============================================================================
# Liste des substitutions ciblees a appliquer sur api_server.py
# ============================================================================

REPLACEMENTS = []

# ---- 1) Reduire le H1 (R1, R6) -----------------------------------------------
REPLACEMENTS.append((
    '    sH1 = ParagraphStyle("MemoH1", parent=styles["Heading1"],  # [V3_LIGHT]\n'
    '        fontSize=16, leading=20, textColor=DEEP_TEAL,\n'
    '        spaceAfter=6, spaceBefore=12, fontName=FONT_BOLD)',
    '    sH1 = ParagraphStyle("MemoH1", parent=styles["Heading1"],  # [V4_COVER]\n'
    '        fontSize=14, leading=18, textColor=DEEP_TEAL,\n'
    '        spaceAfter=6, spaceBefore=12, fontName=FONT_BOLD,\n'
    '        wordWrap="LTR")',
))

# ---- 2) Ajouter constantes pour le bandeau cover ----------------------------
# On insere juste apres la definition des couleurs v3 (DEEP_TEAL pastel).
REPLACEMENTS.append((
    'DEEP_TEAL   = HexColor("#6FA8AE")  # [V3_LIGHT] teal pastel',
    'DEEP_TEAL   = HexColor("#6FA8AE")  # [V3_LIGHT] teal pastel\n'
    '    # [V4_COVER] couleurs bandeau de couverture\n'
    '    COVER_BG    = HexColor("#E6EEF7")  # bleu pale\n'
    '    COVER_TXT   = HexColor("#0E1B2C")  # noir tres fonce pour titre\n'
    '    COVER_SUB   = HexColor("#5A6A7C")  # gris bleute pour sous-titres',
))

# ---- 3) Inserer le bandeau cover en debut de story --------------------------
# Le bandeau est un Table 1x1 avec backgroud COVER_BG, hauteur ~28mm, contenant:
#   "NEXTONES -- IC Memo"  (gros titre noir gras)
#   "Comite d'Investissement"
#   date_str
#
# On l'insere juste apres "story = []" et AVANT le 1er Paragraph (le titre v2).

REPLACEMENTS.append((
    '    story = []\n'
    '    # === Titre principal ===',
    '    story = []\n'
    '    # === [V4_COVER] Bandeau de couverture page 1 ===\n'
    '    cover_title = Paragraph(\n'
    '        \'<font color="#0E1B2C"><b>NEXTONES &#8212; IC Memo</b></font>\',\n'
    '        ParagraphStyle("CoverTitle", parent=styles["Normal"],\n'
    '            fontSize=22, leading=26, fontName=FONT_BOLD,\n'
    '            textColor=COVER_TXT, spaceAfter=2)\n'
    '    )\n'
    '    cover_sub1 = Paragraph(\n'
    '        \'Comite d\\\'Investissement\',\n'
    '        ParagraphStyle("CoverSub1", parent=styles["Normal"],\n'
    '            fontSize=10, leading=14, fontName=FONT_REG,\n'
    '            textColor=COVER_SUB)\n'
    '    )\n'
    '    cover_sub2 = Paragraph(\n'
    '        raw_date,\n'
    '        ParagraphStyle("CoverSub2", parent=styles["Normal"],\n'
    '            fontSize=10, leading=14, fontName=FONT_REG,\n'
    '            textColor=COVER_SUB)\n'
    '    )\n'
    '    cover_inner = Table(\n'
    '        [[cover_title], [cover_sub1], [cover_sub2]],\n'
    '        colWidths=[doc.width],\n'
    '    )\n'
    '    cover_inner.setStyle(TableStyle([\n'
    '        ("LEFTPADDING",  (0, 0), (-1, -1), 14),\n'
    '        ("RIGHTPADDING", (0, 0), (-1, -1), 14),\n'
    '        ("TOPPADDING",   (0, 0), (0, 0), 12),\n'
    '        ("TOPPADDING",   (0, 1), (-1, -1), 0),\n'
    '        ("BOTTOMPADDING",(0, 0), (-1, -2), 0),\n'
    '        ("BOTTOMPADDING",(0, -1), (-1, -1), 12),\n'
    '    ]))\n'
    '    cover_band = Table([[cover_inner]], colWidths=[doc.width])\n'
    '    cover_band.setStyle(TableStyle([\n'
    '        ("BACKGROUND", (0, 0), (-1, -1), COVER_BG),\n'
    '        ("LEFTPADDING",  (0, 0), (-1, -1), 0),\n'
    '        ("RIGHTPADDING", (0, 0), (-1, -1), 0),\n'
    '        ("TOPPADDING",   (0, 0), (-1, -1), 0),\n'
    '        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),\n'
    '    ]))\n'
    '    story.append(cover_band)\n'
    '    story.append(Spacer(1, 8*mm))\n'
    '    # === Titre principal ===',
))

# ---- 4) R5 : elargir la colonne Status (Proposed Changes & Executions) ------
# La table d'origine (v2) a colWidths = [40, 50, 40, 35, 70, 50, 50, 60]
# On passe Status de 70 -> 90 et on retire 10 a Risk Notes et 10 a Slippage.
# On detecte par le commentaire "# [V2] Proposed Changes & Executions table"
# ajoute par v2. Si non trouve, on tente regex sur le pattern colWidths.

REPLACEMENTS.append((
    'colWidths=[40, 50, 40, 35, 70, 50, 50, 60],  # [V2] proposed changes',
    'colWidths=[40, 50, 40, 35, 90, 45, 45, 50],  # [V4_COVER] status elargi',
))

# Si le marker [V2] proposed changes n'est pas present (parfois ajoute via
# autre commit), on tente un fallback plus generique.
FALLBACK_R5_OLD = 'colWidths=[40, 50, 40, 35, 70, 50, 50, 60]'
FALLBACK_R5_NEW = 'colWidths=[40, 50, 40, 35, 90, 45, 45, 50]  # [V4_COVER]'

# ---- 5) R2 : supprimer les tables doublon en fin de doc ---------------------
# On entoure les 2 blocs "Thesis Summaries" + "Proposed Changes" d'une garde
# `if False:` pour les neutraliser sans casser le compile, et on marque [V4_COVER].
#
# Strategie generique : on cherche les 2 sections par leur titre Paragraph et
# on les commente jusqu'au prochain Spacer ou story.append() de section
# differente.

# Marker au-dessus de la section "Thesis Summaries" finale.
# On detecte le pattern utilise dans v2 : story.append(Paragraph("Thesis Summaries", sH2))
# Suivi de la construction d'une Table. On encapsule cette portion.

# Plus simple et plus sur : on enleve les 2 lignes "story.append(Paragraph(...))" pour
# Thesis Summaries et Proposed Changes (les tables associees suivent et n'apparaitront
# plus si on retire le declenchement). Mais en pratique les tables suivent quoi qu'il
# arrive ; il faut donc retirer toute la portion.
#
# On utilise une approche par bornes : entre les marqueurs commentaires v2.

REPLACEMENTS.append((
    '    # [V2] Footer Thesis Summaries duplicate',
    '    # [V4_COVER] block neutralise (doublon avec body markdown)\n'
    '    if False:  # [V4_COVER] disabled - was: [V2] Footer Thesis Summaries duplicate',
))
REPLACEMENTS.append((
    '    # [V2] Footer Proposed Changes duplicate',
    '    # [V4_COVER] block neutralise (doublon avec body markdown)\n'
    '    if False:  # [V4_COVER] disabled - was: [V2] Footer Proposed Changes duplicate',
))

# ---- 6) Marker idempotence sur la route -------------------------------------
REPLACEMENTS.append((
    '@app.get("/api/memos/{memo_id}/pdf")  # [ICMEMO_PDF_V2] [ICMEMO_PDF_V3_LIGHT]',
    '@app.get("/api/memos/{memo_id}/pdf")  # [ICMEMO_PDF_V2] [ICMEMO_PDF_V3_LIGHT] [ICMEMO_PDF_V4_COVER]',
))


# ============================================================================
# Application
# ============================================================================

def main():
    print("nextones-fix-ic-memo-v4-cover  -  01/06/2026")
    print("FILE : " + API_FILE)
    if not os.path.exists(API_FILE):
        print("[FATAL] api_server.py introuvable")
        sys.exit(1)

    src = read_utf8(API_FILE)

    if MARKER_V4 in src:
        print("[SKIP] Marker " + MARKER_V4 + " deja present. Patch deja applique.")
        return 0

    if MARKER_V2 not in src or MARKER_V3 not in src:
        print("[FATAL] Markers v2 + v3-light requis avant v4.")
        print("        v2 present : " + str(MARKER_V2 in src))
        print("        v3 present : " + str(MARKER_V3 in src))
        sys.exit(2)

    ts = time.strftime("%Y%m%d_%H%M%S")
    bk = API_FILE + ".bak_icmemo_v4cover_" + ts
    shutil.copy2(API_FILE, bk)
    print("  backup : " + bk)

    new_src = src
    applied = 0
    not_found = []
    for old, new in REPLACEMENTS:
        if old in new_src:
            new_src = new_src.replace(old, new, 1)
            applied += 1
        else:
            not_found.append(old.splitlines()[0][:80])

    # Fallback R5 si marker [V2] absent
    if FALLBACK_R5_OLD not in new_src and FALLBACK_R5_NEW not in new_src:
        # rien a faire, deja patche
        pass
    elif FALLBACK_R5_OLD in new_src and FALLBACK_R5_NEW not in new_src:
        new_src = new_src.replace(FALLBACK_R5_OLD, FALLBACK_R5_NEW, 1)
        applied += 1
        print("  [INFO] fallback R5 applique (colWidths sans marker [V2])")

    print("  substitutions appliquees : %d" % applied)
    if not_found:
        print("  [WARN] non trouvees (pattern absent du fichier) :")
        for f in not_found:
            print("    - " + f)

    # R2 : strategie alternative si les markers [V2] Footer ne sont pas presents
    # On loggue juste pour info ; le doublon restera tant que ce v4 n'a pas de pattern
    # exact. Le user pourra coller le code R2 specifique si besoin.

    if applied == 0:
        print("[FATAL] aucune substitution appliquee. Le fichier n'a pas le format attendu.")
        sys.exit(3)

    write_utf8(API_FILE, new_src)
    print("  ecrit  : %d bytes" % len(new_src.encode("utf-8")))

    try:
        py_compile.compile(API_FILE, doraise=True)
        print("  py_compile : OK")
    except py_compile.PyCompileError as pce:
        print("[FAIL] py_compile : " + str(pce))
        shutil.copy2(bk, API_FILE)
        print("  ROLLBACK depuis " + bk)
        sys.exit(4)

    banner("DONE")
    print("v4 applique. Prochaines etapes :")
    print("  1) Redemarrer l'API :")
    print("     py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000")
    print("  2) Retelecharger les 2 PDFs temoins :")
    print("     http://localhost:8000/api/memos/1/pdf")
    print("     http://localhost:8000/api/memos/49/pdf")
    print("  3) Verifier :")
    print("     - Bandeau de couverture bleu pale en haut de page 1")
    print("     - Titre H1 en plus petit, plus de cassure en milieu de mot")
    print("     - Colonne Status lisible (pending_validation sur une ligne)")
    print("     - Plus de doublon 'Thesis Summaries' / 'Proposed Changes' en fin")
    return 0


if __name__ == "__main__":
    sys.exit(main())
