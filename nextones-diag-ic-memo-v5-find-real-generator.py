# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v5-find-real-generator
#
# Le PDF effectivement produit par l'UI n'est PAS celui de /api/memos/{id}/pdf
# (qu'on a patche 3 fois en v2/v3/v4). Empreintes du PDF reel renvoye :
#   - Titre H1 "Nextones IC Memo - YYYY-MM-DD"  (tiret cadratin)
#   - Sous-titre "Perplexity Computer"
#   - Footer "Genere par NEXTONES Desk - Perplexity Computer"
#   - Page footer "Page 1/1"
#   - Aucun contenu structure : pas de Portfolio Snapshot, pas d'Audit Trail
#
# Ce diag SCANNE tout le projet pour identifier le VRAI generateur.

import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Empreintes UNIQUEMENT presentes dans le faux/autre generateur
SIGNATURES = [
    ("Perplexity Computer", "Sous-titre cover"),
    ("Genere par NEXTONES Desk", "Footer"),
    ("Page 1/1", "Pagination format Page X/Y"),
    ("Page %d/%d", "Pagination format Python f-string"),
    ('Nextones IC Memo', "Titre exact"),
    ("generate_pdf", "Module suspect (vu en session precedente)"),
    ("from reportlab", "Tout module reportlab importe"),
    ("from fpdf", "fpdf2 (concurrent reportlab)"),
    ("from weasyprint", "weasyprint"),
    ("xhtml2pdf", "xhtml2pdf"),
    ("pdfkit", "pdfkit (wkhtmltopdf)"),
    ("HTML(", "weasyprint HTML class"),
    ("FPDF", "fpdf2 class"),
]

# Routes possibles vers un PDF memo
ROUTE_PATTERNS = [
    r'@app\.(get|post)\(["\'][^"\']*memo[^"\']*["\']',
    r'@router\.(get|post)\(["\'][^"\']*memo[^"\']*["\']',
    r'@app\.(get|post)\(["\'][^"\']*pdf[^"\']*["\']',
    r'@router\.(get|post)\(["\'][^"\']*pdf[^"\']*["\']',
    r'@app\.(get|post)\(["\'][^"\']*export[^"\']*["\']',
    r'@router\.(get|post)\(["\'][^"\']*export[^"\']*["\']',
]


def banner(t):
    print("")
    print("=" * 78)
    print("== " + t)
    print("=" * 78)


def iter_py_files(root):
    skip_dirs = {".venv", "venv", "__pycache__", ".git", "node_modules",
                 "_backups", ".pytest_cache"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".py"):
                yield os.path.join(dirpath, fn)


def read_safe(p):
    try:
        with open(p, "rb") as f:
            b = f.read()
        if b.startswith(b"\xef\xbb\xbf"):
            b = b[3:]
        return b.decode("utf-8", errors="replace")
    except Exception as e:
        return ""


def main():
    banner("1] Scan signatures du faux generateur")
    hits_by_sig = {sig: [] for sig, _ in SIGNATURES}
    py_files = list(iter_py_files(ROOT))
    print("  fichiers .py scannes : %d" % len(py_files))

    for p in py_files:
        src = read_safe(p)
        if not src:
            continue
        for sig, label in SIGNATURES:
            if sig in src:
                # capture le numero de ligne de la 1re occurrence
                idx = src.find(sig)
                line_no = src[:idx].count("\n") + 1
                rel = os.path.relpath(p, ROOT)
                hits_by_sig[sig].append((rel, line_no))

    for sig, label in SIGNATURES:
        hits = hits_by_sig[sig]
        if hits:
            print("")
            print("  [HIT] " + sig + "  (" + label + ")")
            for rel, line_no in hits[:10]:
                print("        %s : L%d" % (rel, line_no))
            if len(hits) > 10:
                print("        ... +%d autres" % (len(hits) - 10))

    banner("2] Toutes les routes (get/post) qui parlent de memo/pdf/export")
    for p in py_files:
        src = read_safe(p)
        if not src:
            continue
        for pat in ROUTE_PATTERNS:
            for m in re.finditer(pat, src):
                line_no = src[:m.start()].count("\n") + 1
                # Capture la signature complete + la ligne suivante
                lines = src.splitlines()
                rel = os.path.relpath(p, ROOT)
                ctx_start = max(0, line_no - 1)
                ctx_end = min(len(lines), line_no + 4)
                print("")
                print("  %s : L%d" % (rel, line_no))
                for i in range(ctx_start, ctx_end):
                    print("    %4d | %s" % (i + 1, lines[i][:120]))

    banner("3] Liste des fichiers .py contenant 'pdf' dans leur nom")
    for p in py_files:
        bn = os.path.basename(p).lower()
        if "pdf" in bn:
            sz = os.path.getsize(p)
            rel = os.path.relpath(p, ROOT)
            print("  %s  (%d bytes)" % (rel, sz))

    banner("4] generate_pdf.py contenu exact")
    target = os.path.join(ROOT, "generate_pdf.py")
    if os.path.exists(target):
        src = read_safe(target)
        lines = src.splitlines()
        print("  Lignes : %d" % len(lines))
        print("  Tete (60 premieres) :")
        for i, ln in enumerate(lines[:60], 1):
            print("    %4d | %s" % (i, ln[:120]))
    else:
        print("  [ABSENT] generate_pdf.py n'est pas a la racine")

    banner("5] Recherche frontend : qui appelle l'endpoint dans les .html / .js")
    html_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if any(s in dirpath for s in [".venv", "node_modules", "__pycache__", ".git"]):
            continue
        for fn in filenames:
            if fn.endswith((".html", ".js")):
                html_files.append(os.path.join(dirpath, fn))
    print("  fichiers .html/.js : %d" % len(html_files))

    UI_PATTERNS = [
        r'memo[^"\']*\.pdf',
        r'/api/memos?/[^"\']*pdf',
        r'/api/[^"\']*export[^"\']*',
        r'href=["\'][^"\']*\.pdf["\']',
        r'fetch\(["\'][^"\']*pdf[^"\']*["\']',
        r'apiFetch\(["\'][^"\']*pdf[^"\']*["\']',
    ]
    for p in html_files:
        try:
            with open(p, "rb") as f:
                b = f.read()
            if b.startswith(b"\xef\xbb\xbf"):
                b = b[3:]
            src = b.decode("utf-8", errors="replace")
        except Exception:
            continue
        rel = os.path.relpath(p, ROOT)
        for pat in UI_PATTERNS:
            for m in re.finditer(pat, src, re.IGNORECASE):
                line_no = src[:m.start()].count("\n") + 1
                lines = src.splitlines()
                ctx = lines[line_no - 1] if line_no - 1 < len(lines) else ""
                print("  %s : L%d : %s" % (rel, line_no, ctx.strip()[:140]))

    banner("FIN DIAG v5")
    print("  -> Cherche dans la sortie le BON generateur (celui qui contient")
    print("     'Perplexity Computer' ou 'Genere par NEXTONES Desk').")
    print("     C'est lui qu'il faudra patcher, PAS api_server.py:get_memo_pdf.")


if __name__ == "__main__":
    main()
