# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v2
#
# Diagnostic v2 cible apres decouvertes diag v1 :
#   - table ic_memos a 5 colonnes texte (pas une seule 'body')
#   - generateur PDF non trouve sous *memo*.py
#   - rendu probablement HTML->PDF (weasyprint / xhtml2pdf / pdfkit)
#
# Objectifs v2 :
#   1. Dump #49 + dernier id + ids vides sur full_markdown
#   2. Scan LARGE du repo Prod (tous .py) pour signatures generateur
#   3. Scan templates .html / .j2 / .jinja2 (double footer cote template)
#   4. Inspecter pplx_memo_context.payload_json
#
# Usage :
#   py -3.13 .\nextones-diag-ic-memo-v2.py
#
# Sortie : print structure. AUCUNE ecriture.
# Lecture utf-8-sig.

import glob
import json
import os
import re
import sqlite3
import sys

DB_PATH   = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
SELF      = os.path.basename(__file__) if "__file__" in dir() else ""

def banner(t):
    print("")
    print("=" * 78)
    print("== " + t)
    print("=" * 78)

def read_utf8(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    try:
        return b.decode("utf-8")
    except Exception:
        return b.decode("latin-1", errors="replace")

def short(s, n=120):
    if s is None:
        return "NULL"
    s = str(s).replace("\r", " ").replace("\n", " ").replace("\t", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > n:
        return s[:n] + "..."
    return s

# -------- 1. DB : dump #49 + dernier + memos vides --------
def diag_db():
    banner("1. DB - dump memos #49, dernier id, memos vides sur full_markdown")
    if not os.path.exists(DB_PATH):
        print("  [SKIP] DB introuvable : " + DB_PATH)
        return None
    cn = sqlite3.connect(DB_PATH)
    cn.row_factory = sqlite3.Row
    try:
        # ic_memos
        cols = [c[1] for c in cn.execute("PRAGMA table_info(ic_memos)").fetchall()]
        print("  ic_memos cols : " + ", ".join(cols))
        n = cn.execute("SELECT COUNT(*) FROM ic_memos").fetchone()[0]
        print("  total : %d" % n)

        # candidats colonnes texte (vraies cibles 'corps')
        text_cols = [c for c in cols if c in
            ("title", "macro_summary", "factor_tilts", "thesis_summaries",
             "proposed_changes", "full_markdown")]

        # comptage vides par colonne
        print("")
        print("  -- vides par colonne (NULL ou trim vide) --")
        for c in text_cols:
            empty = cn.execute(
                "SELECT COUNT(*) FROM ic_memos "
                "WHERE " + c + " IS NULL OR TRIM(" + c + ") = ''"
            ).fetchone()[0]
            very_short = cn.execute(
                "SELECT COUNT(*) FROM ic_memos "
                "WHERE LENGTH(TRIM(" + c + ")) < 50 AND " + c + " IS NOT NULL"
            ).fetchone()[0]
            print("    %-20s : vides=%-3d   tres-courts(<50c)=%d" % (c, empty, very_short))

        # ids de memos suspects (full_markdown vide ou court)
        print("")
        print("  -- ids ou full_markdown vide ou tres court --")
        rows = cn.execute(
            "SELECT id, date, title, LENGTH(full_markdown) AS lmd, "
            "       LENGTH(macro_summary) AS lms, LENGTH(factor_tilts) AS lft, "
            "       LENGTH(thesis_summaries) AS lts, LENGTH(proposed_changes) AS lpc "
            "FROM ic_memos "
            "WHERE full_markdown IS NULL OR LENGTH(TRIM(full_markdown)) < 100 "
            "ORDER BY id"
        ).fetchall()
        print("    %d memos suspects" % len(rows))
        for r in rows:
            print("    id=%-4d date=%-12s lmd=%-5s lms=%-5s lft=%-5s lts=%-5s lpc=%-5s title=%s" %
                (r["id"], short(r["date"], 12), str(r["lmd"]), str(r["lms"]),
                 str(r["lft"]), str(r["lts"]), str(r["lpc"]), short(r["title"], 50)))

        # dump complet : id=49, dernier id, premier id avec full_markdown vide
        ids_to_dump = set()
        ids_to_dump.add(49)
        last_id = cn.execute("SELECT MAX(id) FROM ic_memos").fetchone()[0]
        if last_id:
            ids_to_dump.add(last_id)
        # premier vide
        first_empty = cn.execute(
            "SELECT id FROM ic_memos WHERE full_markdown IS NULL OR TRIM(full_markdown)='' "
            "ORDER BY id LIMIT 1"
        ).fetchone()
        if first_empty:
            ids_to_dump.add(first_empty[0])
        # premier non-vide pour reference
        first_full = cn.execute(
            "SELECT id FROM ic_memos WHERE LENGTH(TRIM(full_markdown)) > 200 "
            "ORDER BY id LIMIT 1"
        ).fetchone()
        if first_full:
            ids_to_dump.add(first_full[0])

        for mid in sorted(ids_to_dump):
            print("")
            print("  -- dump complet memo id=%d --" % mid)
            row = cn.execute("SELECT * FROM ic_memos WHERE id=?", (mid,)).fetchone()
            if not row:
                print("    [INEXISTANT]")
                continue
            for k in row.keys():
                v = row[k]
                if v is None:
                    print("    %-20s : NULL" % k)
                elif isinstance(v, (int, float)):
                    print("    %-20s : %s" % (k, v))
                else:
                    sv = str(v)
                    print("    %-20s : len=%-5d  %s" % (k, len(sv), short(sv, 200)))

        # exemple memo 101 reference : il a 2 pages, donc full_markdown != vide
        # mais le PDF original etait IC-Memo-101.pdf : numero != id en DB ?
        # On verifie : combien de memos contiennent 'Analyse Macro' ?
        print("")
        print("  -- recherche memo equivalent au PDF IC-Memo-101 --")
        rows = cn.execute(
            "SELECT id, date, title FROM ic_memos "
            "WHERE title LIKE '%Analyse Macro%' OR full_markdown LIKE '%Analyse Macro%' "
            "OR macro_summary LIKE '%GlobalScore 5.8%' "
            "ORDER BY id"
        ).fetchall()
        if rows:
            for r in rows:
                print("    id=%-4d date=%-12s title=%s" % (r["id"], short(r["date"], 12), short(r["title"], 60)))
        else:
            print("    [AUCUN match] -> les fichiers IC-Memo-XX.pdf utilisent peut-etre")
            print("    une numerotation autonome (sequence fichiers) plutot que ic_memos.id")

        # pplx_memo_context
        print("")
        print("  -- pplx_memo_context (sample) --")
        rows = cn.execute(
            "SELECT symbol, LENGTH(payload_json) AS lpj, LENGTH(citations_json) AS lcj, "
            "       generated_at, model, elapsed_s "
            "FROM pplx_memo_context ORDER BY generated_ts DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            print("    sym=%-10s lpj=%-6d lcj=%-5d gen=%s model=%s elapsed=%.1fs" %
                (r["symbol"], r["lpj"] or 0, r["lcj"] or 0,
                 short(r["generated_at"], 19), short(r["model"], 18), r["elapsed_s"] or 0))

        # echantillon payload_json du premier
        row = cn.execute(
            "SELECT symbol, payload_json FROM pplx_memo_context "
            "WHERE payload_json IS NOT NULL ORDER BY generated_ts DESC LIMIT 1"
        ).fetchone()
        if row and row["payload_json"]:
            try:
                pj = json.loads(row["payload_json"])
                keys = list(pj.keys()) if isinstance(pj, dict) else []
                print("    payload_json keys (%s) : %s" % (row["symbol"], ", ".join(keys)))
            except Exception:
                print("    payload_json non-JSON pour %s" % row["symbol"])

    finally:
        cn.close()

# -------- 2. CODE : scan LARGE du repo Prod --------
def diag_code():
    banner("2. CODE - scan large pour generateur PDF reel")
    if not os.path.isdir(PROD_ROOT):
        print("  [SKIP] PROD_ROOT introuvable : " + PROD_ROOT)
        return

    # tous .py sauf venv et nos scripts diag/fix
    files = []
    for f in glob.glob(os.path.join(PROD_ROOT, "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, PROD_ROOT).lower()
        if any(skip in rel for skip in
            ("venv", "site-packages", ".git", "__pycache__",
             "nextones-diag-ic-memo", "nextones-fix-ic-memo")):
            continue
        files.append(f)
    print("  fichiers .py scannes : %d" % len(files))

    # signatures
    sig_ic_memo  = re.compile(r"IC[-_\s]?Memo|ic_memos|full_markdown", re.IGNORECASE)
    sig_rl       = re.compile(r"\b(reportlab|SimpleDocTemplate|canvas\.Canvas)\b")
    sig_wp       = re.compile(r"\b(weasyprint|HTML\(|write_pdf)\b")
    sig_xhtml    = re.compile(r"\b(xhtml2pdf|pisa\.|pisaDocument)\b")
    sig_pdfkit   = re.compile(r"\b(pdfkit|from_string|from_file)\b")
    sig_endpoint = re.compile(r"@(?:app|router)\.(?:get|post).*?(?:memo|ic_memo|export)", re.IGNORECASE)
    sig_render   = re.compile(r"render_template|jinja|Template\(", re.IGNORECASE)
    sig_footer   = re.compile(r"Gener[\\u00e9e]+e?\s+par\s+NEXTONES|Page\s+1/")

    hits = []
    for f in files:
        try:
            src = read_utf8(f)
        except Exception:
            continue
        notes = []
        score = 0
        if sig_ic_memo.search(src): score += 1; notes.append("ic_memo-string")
        if sig_rl.search(src):      score += 3; notes.append("reportlab")
        if sig_wp.search(src):      score += 3; notes.append("weasyprint")
        if sig_xhtml.search(src):   score += 3; notes.append("xhtml2pdf")
        if sig_pdfkit.search(src):  score += 3; notes.append("pdfkit")
        if sig_endpoint.search(src):score += 2; notes.append("endpoint-memo")
        if sig_render.search(src):  score += 1; notes.append("jinja")
        if sig_footer.search(src):  score += 2; notes.append("footer-string")
        if score >= 3:
            hits.append((score, f, notes, src))
    hits.sort(key=lambda x: -x[0])

    print("  candidats score >=3 : %d" % len(hits))
    for sc, f, notes, src in hits[:10]:
        rel = os.path.relpath(f, PROD_ROOT)
        print("")
        print("  >> [%d] %s" % (sc, rel))
        print("     notes : " + ", ".join(notes))
        # extrait lignes-cles
        keys = ("IC[-_ ]?Memo|full_markdown|reportlab|weasyprint|xhtml2pdf|pdfkit|"
                "Gener[\\u00e9e]+e?\\s+par|SimpleDocTemplate|canvas\\.Canvas|"
                "write_pdf|pisa\\.|@(?:app|router)\\.(?:get|post)|render_template|"
                "ic_memos|build_memo|export_memo|render_memo|generate_memo|Page\\s+1/")
        kre = re.compile(keys, re.IGNORECASE)
        shown = 0
        for i, line in enumerate(src.splitlines(), 1):
            if kre.search(line):
                t = line.strip()
                if len(t) > 130:
                    t = t[:127] + "..."
                print("     L%-5d %s" % (i, t))
                shown += 1
                if shown >= 12:
                    print("     ... (tronque)")
                    break

# -------- 3. Templates HTML/Jinja --------
def diag_templates():
    banner("3. TEMPLATES - .html / .j2 / .jinja(2)")
    if not os.path.isdir(PROD_ROOT):
        return
    files = []
    for ext in ("*.html", "*.j2", "*.jinja", "*.jinja2", "*.htm"):
        for f in glob.glob(os.path.join(PROD_ROOT, "**", ext), recursive=True):
            rel = os.path.relpath(f, PROD_ROOT).lower()
            if any(skip in rel for skip in ("venv", "site-packages", ".git", "node_modules")):
                continue
            files.append(f)
    print("  templates scannes : %d" % len(files))

    sig = re.compile(r"IC[-_ ]?Memo|full_markdown|Gener[\\u00e9e]+e?\s+par\s+NEXTONES|Page\s+1/", re.IGNORECASE)
    hits = []
    for f in files:
        try:
            src = read_utf8(f)
        except Exception:
            continue
        if sig.search(src):
            hits.append((f, src))

    print("  templates pertinents : %d" % len(hits))
    for f, src in hits[:6]:
        rel = os.path.relpath(f, PROD_ROOT)
        print("")
        print("  >> " + rel + " (len=%d)" % len(src))
        # extrait
        kre = re.compile(r"IC[-_ ]?Memo|full_markdown|Gener[\\u00e9e]+e?\s+par|Page\s+1/", re.IGNORECASE)
        shown = 0
        for i, line in enumerate(src.splitlines(), 1):
            if kre.search(line):
                t = line.strip()
                if len(t) > 130:
                    t = t[:127] + "..."
                print("     L%-5d %s" % (i, t))
                shown += 1
                if shown >= 10:
                    print("     ... (tronque)")
                    break

# -------- 4. requirements / pyproject : quelle lib PDF est installee --------
def diag_libs():
    banner("4. LIBS - quelle lib PDF est utilisee")
    cands = ["requirements.txt", "requirements-dev.txt", "pyproject.toml", "Pipfile"]
    found = False
    for c in cands:
        p = os.path.join(PROD_ROOT, c)
        if os.path.exists(p):
            found = True
            print("")
            print("  -- " + c + " --")
            try:
                src = read_utf8(p)
            except Exception:
                continue
            for line in src.splitlines():
                low = line.lower()
                if any(k in low for k in ("reportlab", "weasyprint", "xhtml2pdf",
                                          "pdfkit", "wkhtmltopdf", "fpdf",
                                          "pypdf", "pdf-lib", "jinja")):
                    print("    " + line.strip())
    if not found:
        print("  [INFO] aucun fichier requirements/pyproject trouve a la racine.")
        # pip freeze probable
        print("  Conseil : py -3.13 -m pip freeze | findstr /I \"reportlab weasy xhtml pdfkit fpdf\"")

# -------- main --------
if __name__ == "__main__":
    print("nextones-diag-ic-memo-v2  -  31/05/2026")
    print("PROD_ROOT : " + PROD_ROOT)
    print("DB        : " + DB_PATH)
    diag_db()
    diag_code()
    diag_templates()
    diag_libs()
    print("")
    print("[DONE] Diagnostic v2 termine. Aucun fichier modifie.")
