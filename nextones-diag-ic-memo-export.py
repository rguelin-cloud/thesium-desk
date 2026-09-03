# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-export
#
# Diagnostic complet de l'export IC Memo apres detection bugs :
#   B1  memos avec corps vide silencieusement exportes (cf IC-Memo-49)
#   B2  double footer "Generee par NEXTONES Desk" + "Page X" superposes
#   B3  glyphes warning/check (U+26A0, U+2713, ...) absents -> mojibake
#   B4  titre placeholder "Nextones IC Memo - YYYY-MM-DD"
#
# Usage :
#   py -3.13 .\nextones-diag-ic-memo-export.py
#
# Sortie : print structure + recommandations. AUCUNE ecriture.
# Lecture utf-8-sig partout.

import io
import os
import re
import sqlite3
import sys
import glob

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# -------- utils --------
def banner(t):
    print("")
    print("=" * 78)
    print("== " + t)
    print("=" * 78)

def read_utf8(path):
    with open(path, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    try:
        return b.decode("utf-8")
    except Exception:
        return b.decode("latin-1", errors="replace")

# -------- 1. DB : structure table memos + diag corps vide --------
def diag_db():
    banner("1. DB - structure table memos + memos vides")
    if not os.path.exists(DB_PATH):
        print("  [SKIP] DB introuvable : " + DB_PATH)
        return
    cn = sqlite3.connect(DB_PATH)
    cn.row_factory = sqlite3.Row
    try:
        # liste tables candidates
        tables = [r[0] for r in cn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND (name LIKE '%memo%' OR name LIKE '%ic_memo%')"
        ).fetchall()]
        print("  tables candidates : " + (", ".join(tables) if tables else "(aucune)"))
        for t in tables:
            print("")
            print("  -- table : " + t)
            cols = cn.execute("PRAGMA table_info(" + t + ")").fetchall()
            for c in cols:
                print("     col %-20s %-12s null=%s" % (c[1], c[2], c[3]))
            n = cn.execute("SELECT COUNT(*) FROM " + t).fetchone()[0]
            print("     total rows : %d" % n)

            # heuristique : detecter colonne corps
            body_cols = [c[1] for c in cols if c[1].lower() in
                ("body", "content", "markdown", "text", "memo", "html", "raw")]
            if not body_cols:
                print("     [WARN] aucune colonne corps detectee")
                continue
            for bc in body_cols:
                empty = cn.execute(
                    "SELECT COUNT(*) FROM " + t + " WHERE " + bc + " IS NULL OR TRIM(" + bc + ") = ''"
                ).fetchone()[0]
                print("     col '%s' : %d / %d vides" % (bc, empty, n))
                # lister les 10 premiers ids vides
                ids = [r[0] for r in cn.execute(
                    "SELECT id FROM " + t + " WHERE " + bc + " IS NULL OR TRIM(" + bc + ") = '' "
                    "ORDER BY id LIMIT 10").fetchall()]
                if ids:
                    print("     ids vides (max 10) : " + str(ids))

            # cherche memo 49 et 101 specifiquement
            for mid in (49, 101):
                row = cn.execute("SELECT * FROM " + t + " WHERE id = ?", (mid,)).fetchone()
                if row:
                    keys = row.keys()
                    print("")
                    print("     -- memo id=%d --" % mid)
                    for k in keys:
                        v = row[k]
                        if v is None:
                            sv = "NULL"
                        else:
                            sv = str(v)
                            if len(sv) > 80:
                                sv = sv[:77] + "..."
                        print("        %-15s : %s" % (k, sv))
    finally:
        cn.close()

# -------- 2. Code : double footer + fontes manquantes --------
def diag_code():
    banner("2. CODE - inspection generateur PDF IC Memo")
    if not os.path.isdir(PROD_ROOT):
        print("  [SKIP] PROD_ROOT introuvable : " + PROD_ROOT)
        return

    # candidats : *memo*generator*, *export*memo*, pplx_memo*
    patterns = ["*memo*.py", "*ic_memo*.py", "*export*.py"]
    files = set()
    for p in patterns:
        files.update(glob.glob(os.path.join(PROD_ROOT, "**", p), recursive=True))
    files = sorted(files)
    print("  fichiers candidats : %d" % len(files))

    foot_re = re.compile(r"(Generee?|Genere)\s+par\s+NEXTONES", re.IGNORECASE)
    page_re = re.compile(r"Page\s*[%{]\s*(d|i)|drawRightString.*Page", re.IGNORECASE)
    onlat_re = re.compile(r"onLaterPages|onFirstPage", re.IGNORECASE)
    drawstr_re = re.compile(r"drawString|drawRightString|drawCentredString", re.IGNORECASE)
    glyph_re = re.compile(r"[\u26A0\u2713\u2717\u2192\u25CF\u25CB]")

    hits = []
    for f in files:
        try:
            src = read_utf8(f)
        except Exception:
            continue
        score = 0
        notes = []
        if foot_re.search(src):
            score += 1
            notes.append("footer-string")
        if onlat_re.search(src):
            score += 1
            notes.append("onPages-callback")
        if drawstr_re.search(src) and foot_re.search(src):
            score += 1
            notes.append("canvas-draw-footer")
        # footer dans STORY (Paragraph "Generee par...") ?
        if re.search(r"Paragraph\([^)]*Generee?\s+par\s+NEXTONES", src):
            score += 2
            notes.append("STORY-footer-flowable")
        if glyph_re.search(src):
            notes.append("glyph-unicode-present")
        if score >= 1:
            hits.append((f, score, notes))
    hits.sort(key=lambda x: -x[1])

    for f, sc, notes in hits[:8]:
        rel = os.path.relpath(f, PROD_ROOT)
        print("")
        print("  >> %s   [score %d]" % (rel, sc))
        print("     notes : " + ", ".join(notes))
        # extrait : lignes contenant "Generee par" ou "Page" ou "onLaterPages"
        for i, line in enumerate(src.splitlines(), 1):
            if (foot_re.search(line) or onlat_re.search(line)
                or re.search(r"Page\s*[/{]", line)
                or re.search(r"registerFont|TTFont", line)):
                txt = line.strip()
                if len(txt) > 110:
                    txt = txt[:107] + "..."
                print("     L%-5d %s" % (i, txt))

    # diag fontes : la presence d'un registerFont DejaVuSans suffit
    banner("3. FONTES - registerFont DejaVuSans (fallback symboles)")
    found_dejavu = False
    for f in files:
        try:
            src = read_utf8(f)
        except Exception:
            continue
        if "DejaVuSans" in src or "NotoSansSymbols" in src:
            found_dejavu = True
            print("  [OK] fonte symbole trouvee dans %s" % os.path.relpath(f, PROD_ROOT))
    if not found_dejavu:
        print("  [GAP] aucune fonte fallback symbole enregistree dans le generateur IC Memo")
        print("        -> glyphes /!\\, (!), (OK) sont des fallback ASCII")
        print("        -> patch v2 doit registerFont('Sym', '.../DejaVuSans.ttf')")

# -------- 4. Synthese --------
def synthese():
    banner("4. SYNTHESE & ACTIONS PATCH (a executer ensuite)")
    print("""
  B1 corps vide :
    - cause probable : champ body NULL non garde -> PDF genere quand meme.
    - patch : raise EmptyMemoError si TRIM(body) == '' ; status='draft_empty' en DB.

  B2 double footer :
    - cause probable : 1 Paragraph 'Generee par...' DANS le story + 1 callback canvas.
    - patch : conserver le callback uniquement ; supprimer le Paragraph footer du story.

  B3 mojibake symboles :
    - cause : Inter/DMSans n'ont pas U+26A0 / U+2713 -> fallback texte ASCII.
    - patch : registerFont('Sym', '/.../DejaVuSans.ttf') + remplacer /!\\ -> <font name='Sym'>chr(0x26A0)</font>.
    - Sous Windows : C:\\Windows\\Fonts\\DejaVuSans.ttf si installee, sinon embarquer.

  B4 titre placeholder :
    - cause : fallback 'Nextones IC Memo - <date>' quand title absent.
    - patch : prefixer par cycle_id + ticker(s) principaux + regime ;
              ex 'IC Memo #49 - BTC SELL - MAINTAIN - 2026-05-31'.
""")

if __name__ == "__main__":
    print("nextones-diag-ic-memo-export  -  31/05/2026")
    diag_db()
    diag_code()
    synthese()
    print("")
    print("[DONE] Diagnostic termine. Aucun fichier modifie.")
