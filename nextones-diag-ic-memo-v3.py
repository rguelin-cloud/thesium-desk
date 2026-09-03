# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v3
#
# Diag v3 : localiser la fonction d'export PDF IC Memo dans api_server.py
#
# Hypothese (post diag v2) :
#   - Generateur PDF est in-process dans api_server.py (reportlab + endpoint memo)
#   - DB contient bien le contenu (full_markdown=8949 chars pour #49)
#   - Donc le bug B1 est dans le RENDERER (pas la donnee)
#   - Title en DB est deja mojibake : "Nextones IC Memo u 2026-05-25"
#     => double bug B4 : placeholder ET mojibake
#
# Sortie : extraits cibles de la fonction d'export, sans modification.

import os
import re
import sys

PROD_ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API_FILE  = os.path.join(PROD_ROOT, "api_server.py")

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

def main():
    print("nextones-diag-ic-memo-v3  -  31/05/2026")
    print("FILE : " + API_FILE)
    if not os.path.exists(API_FILE):
        print("[FATAL] api_server.py introuvable")
        sys.exit(1)

    src = read_utf8(API_FILE)
    lines = src.splitlines()
    print("  total lignes : %d" % len(lines))
    print("  bytes        : %d" % len(src.encode("utf-8")))

    # ---- 1. Routes memo/export/pdf ----
    banner("1. Routes memo/export/pdf dans api_server.py")
    route_re = re.compile(
        r"@(?:app|router)\.(?:get|post|put|delete)\(['\"]([^'\"]*)['\"]"
    )
    interesting = re.compile(r"(memo|export|pdf|markdown)", re.IGNORECASE)
    matches = []
    for i, line in enumerate(lines, 1):
        m = route_re.search(line)
        if m and interesting.search(m.group(1)):
            matches.append((i, m.group(1)))
    print("  routes pertinentes : %d" % len(matches))
    for i, path in matches:
        print("    L%-5d %s" % (i, path))

    # ---- 2. Pour chaque route memo, extraire la fonction (jusqu'a 80 lignes) ----
    banner("2. Extraits des fonctions de chaque route memo/export/pdf")
    for route_line, path in matches:
        print("")
        print("  >>> ROUTE L%d  %s" % (route_line, path))
        # extraire la def en dessous + ~80 lignes
        end = min(len(lines), route_line + 100)
        # cherche la prochaine route apres celle-ci pour borner
        for j in range(route_line, end):
            nxt = route_re.search(lines[j])
            if nxt and j > route_line + 2:
                end = j
                break
        for k in range(route_line - 1, end):
            t = lines[k]
            if len(t) > 200:
                t = t[:197] + "..."
            print("    L%-5d %s" % (k + 1, t))

    # ---- 3. Tous les usages de ic_memos dans api_server.py ----
    banner("3. Tous les usages 'ic_memos' / 'full_markdown' / 'macro_summary'")
    keys = re.compile(r"ic_memos|full_markdown|macro_summary|factor_tilts|"
                      r"thesis_summaries|proposed_changes", re.IGNORECASE)
    n = 0
    for i, line in enumerate(lines, 1):
        if keys.search(line):
            t = line.strip()
            if len(t) > 170:
                t = t[:167] + "..."
            print("    L%-5d %s" % (i, t))
            n += 1
    print("  total : %d lignes" % n)

    # ---- 4. Reportlab : SimpleDocTemplate + onPage + Paragraph footer ----
    banner("4. Reportlab : SimpleDocTemplate, onPage, footer Paragraph")
    rl = re.compile(
        r"SimpleDocTemplate|BaseDocTemplate|PageTemplate|onPage|onFirstPage|"
        r"onLaterPages|drawString|drawCentredString|drawRightString|"
        r"\bFooter\b|footer|Page\s+\d+|Generated\s+by|Genere\s+par",
        re.IGNORECASE
    )
    n = 0
    for i, line in enumerate(lines, 1):
        if rl.search(line):
            t = line.strip()
            if len(t) > 170:
                t = t[:167] + "..."
            print("    L%-5d %s" % (i, t))
            n += 1
            if n > 80:
                print("    ... (tronque a 80)")
                break

    # ---- 5. Glyphes warning / check / lightning ----
    banner("5. Glyphes warning/check/lightning (B3)")
    glyphes = [
        ("/!\\",    r"/!\\"),
        ("(!)",     r"\(!\)"),
        ("(OK)",    r"\(OK\)"),
        ("U+26A0 warning sign",  r"\\u26a0"),
        ("U+2713 check mark",    r"\\u2713"),
        ("U+26A1 high voltage",  r"\\u26a1"),
        ("warning text",         r"\bwarning\b"),
        ("alert text",           r"\balert\b"),
    ]
    for label, pat in glyphes:
        rx = re.compile(pat, re.IGNORECASE)
        hits = [(i+1, lines[i]) for i in range(len(lines)) if rx.search(lines[i])]
        print("  %-30s : %d occurrences" % (label, len(hits)))
        for ln, t in hits[:5]:
            tt = t.strip()
            if len(tt) > 150:
                tt = tt[:147] + "..."
            print("    L%-5d %s" % (ln, tt))
        if len(hits) > 5:
            print("    ... (+%d autres)" % (len(hits) - 5))

    # ---- 6. Origine du title 'Nextones IC Memo XXX' ----
    banner("6. Origine du title placeholder 'Nextones IC Memo'")
    rx = re.compile(r"Nextones\s+IC\s+Memo|IC\s+Memo\s*[\u2013\u2014\-]|memo.*title|title.*memo",
                    re.IGNORECASE)
    n = 0
    for i, line in enumerate(lines, 1):
        if rx.search(line):
            t = line.strip()
            if len(t) > 170:
                t = t[:167] + "..."
            print("    L%-5d %s" % (i, t))
            n += 1
    print("  total : %d lignes" % n)

    # ---- 7. Fonts utilisees (DejaVu / Inter / etc.) ----
    banner("7. Polices declarees (TTFont, registerFont)")
    rx = re.compile(r"TTFont|registerFont|Inter|DejaVu|DM[\s-]?Sans|Helvetica|"
                    r"\.ttf|\.otf|setFont", re.IGNORECASE)
    n = 0
    for i, line in enumerate(lines, 1):
        if rx.search(line):
            t = line.strip()
            if len(t) > 170:
                t = t[:167] + "..."
            print("    L%-5d %s" % (i, t))
            n += 1
            if n > 30:
                print("    ... (tronque a 30)")
                break

    print("")
    print("[DONE] Diagnostic v3 termine.")

if __name__ == "__main__":
    main()
