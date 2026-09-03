# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v6-memo-generator
#
# Le VRAI generateur est memo_generator.py (signature "Nextones IC Memo" L22).
# Une route relais dans api_server.py:L1562 (signature "Perplexity Computer")
# l'appelle. Le bouton UI est "Export PDF".
#
# Ce diag :
#   1) Dump memo_generator.py en entier (1193 lignes -> on prend tout)
#   2) Dump api_server.py L1500-1750 (zone de la route relais)
#   3) Cherche dans les .html / .js le bouton "Export PDF" -> endpoint exact
#
# Sortie redirigee fichier ASCII pour eviter UnicodeEncodeError PowerShell cp1252.

import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
OUT  = os.path.join(ROOT, "diag-v6-output.txt")


def read_safe(p):
    try:
        with open(p, "rb") as f:
            b = f.read()
        if b.startswith(b"\xef\xbb\xbf"):
            b = b[3:]
        return b.decode("utf-8", errors="replace")
    except Exception:
        return ""


def write_ascii(out_path, lines):
    with open(out_path, "wb") as f:
        for ln in lines:
            # Tout passer en ASCII (toute occurrence > 127 -> "?")
            safe = ln.encode("ascii", errors="replace").decode("ascii")
            f.write((safe + "\n").encode("ascii"))


def main():
    out_lines = []
    def W(s=""):
        out_lines.append(s)

    def banner(t):
        W("")
        W("=" * 80)
        W("== " + t)
        W("=" * 80)

    # -------------------------------------------------------------
    banner("[1] memo_generator.py - dump complet")
    # -------------------------------------------------------------
    mg = os.path.join(ROOT, "memo_generator.py")
    if not os.path.exists(mg):
        W("  [ABSENT] memo_generator.py n'existe pas a la racine")
    else:
        src = read_safe(mg)
        lines = src.splitlines()
        W("  Lignes : %d  |  Taille : %d bytes" % (len(lines), len(src.encode("utf-8"))))
        W("")
        for i, ln in enumerate(lines, 1):
            W("%5d | %s" % (i, ln[:200]))

    # -------------------------------------------------------------
    banner("[2] api_server.py L1500-1750 (zone route relais memo_generator)")
    # -------------------------------------------------------------
    api = os.path.join(ROOT, "api_server.py")
    if not os.path.exists(api):
        W("  [ABSENT] api_server.py n'existe pas")
    else:
        src = read_safe(api)
        lines = src.splitlines()
        start = 1500
        end = min(1750, len(lines))
        W("  Extraction L%d -> L%d (sur %d total)" % (start, end, len(lines)))
        W("")
        for i in range(start - 1, end):
            W("%5d | %s" % (i + 1, lines[i][:200]))

    # -------------------------------------------------------------
    banner("[3] Recherche bouton 'Export PDF' + endpoint associe (HTML/JS)")
    # -------------------------------------------------------------
    PATTERNS = [
        ("Texte bouton 'Export PDF'", r'Export\s+PDF'),
        ("Texte bouton 'Export pdf'", r'export[_\-\s]?pdf'),
        ("Texte 'Telecharger'",       r'[Tt]el[e\u00e9]?charger.*pdf'),
        ("Class export",              r'class=["\'][^"\']*export[^"\']*["\']'),
        ("data-action export",        r'data-action=["\'][^"\']*export[^"\']*["\']'),
        ("onclick exportPdf",         r'onclick=["\'][^"\']*[Ee]xport[Pp]df[^"\']*["\']'),
        ("Fonction exportPdf",        r'function\s+exportPdf'),
        ("Fonction export_pdf",       r'def\s+export_pdf'),
        ("Fetch /export",             r'(?:fetch|apiFetch)\(["\'][^"\']*export[^"\']*["\']'),
        ("Fetch /pdf",                r'(?:fetch|apiFetch)\(["\'][^"\']*\.pdf["\']'),
        ("Fetch /memos/.../pdf",      r'(?:fetch|apiFetch)\(["\'][^"\']*memos?/[^"\']*pdf[^"\']*["\']'),
    ]

    candidate_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if any(s in dirpath for s in [".venv", "node_modules", "__pycache__", ".git", "_backups"]):
            continue
        for fn in filenames:
            if fn.endswith((".html", ".js", ".jsx", ".ts", ".tsx", ".vue")):
                candidate_files.append(os.path.join(dirpath, fn))
    W("  Fichiers UI scannes : %d" % len(candidate_files))

    for label, pat in PATTERNS:
        W("")
        W("  -- Pattern : %s  ( %s )" % (label, pat))
        rx = re.compile(pat, re.IGNORECASE)
        hits = 0
        for p in candidate_files:
            src = read_safe(p)
            if not src:
                continue
            for m in rx.finditer(src):
                line_no = src[:m.start()].count("\n") + 1
                rel = os.path.relpath(p, ROOT)
                lines = src.splitlines()
                ctx_start = max(0, line_no - 2)
                ctx_end = min(len(lines), line_no + 3)
                W("    %s : L%d" % (rel, line_no))
                for i in range(ctx_start, ctx_end):
                    marker = " >> " if (i + 1) == line_no else "    "
                    W("%s    %5d | %s" % (marker, i + 1, lines[i][:180]))
                W("")
                hits += 1
                if hits >= 10:
                    W("    ... (cap a 10 hits par pattern)")
                    break
            if hits >= 10:
                break
        if hits == 0:
            W("    (aucun match)")

    # -------------------------------------------------------------
    banner("[4] Routes Python qui IMPORTENT memo_generator")
    # -------------------------------------------------------------
    PY_PATTERNS = [
        r'import\s+memo_generator',
        r'from\s+memo_generator',
        r'memo_generator\.',
    ]
    py_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if any(s in dirpath for s in [".venv", "node_modules", "__pycache__", ".git", "_backups"]):
            continue
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(os.path.join(dirpath, fn))
    W("  Fichiers .py scannes : %d" % len(py_files))

    for pat in PY_PATTERNS:
        W("")
        W("  -- " + pat)
        rx = re.compile(pat)
        for p in py_files:
            src = read_safe(p)
            if not src:
                continue
            for m in rx.finditer(src):
                line_no = src[:m.start()].count("\n") + 1
                rel = os.path.relpath(p, ROOT)
                lines = src.splitlines()
                W("    %s : L%d : %s" % (rel, line_no, lines[line_no - 1][:200]))

    # Ecriture finale
    write_ascii(OUT, out_lines)
    print("OK -> sortie ASCII ecrite dans : " + OUT)
    print("Ouvrir avec : notepad " + OUT)


if __name__ == "__main__":
    main()
