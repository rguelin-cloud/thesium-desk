# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v4-dump
#
# Diag v4 : dump brut L1178 -> L1410 de api_server.py
# (le coeur du parser markdown + assemblage story du PDF IC Memo)
#
# Objectif :
#   - localiser le bug B1 (corps vide) : parser markdown qui drop tout
#   - confirmer presence/absence de Paragraph footer en doublon (B2)
#   - lister tous les glyphes ASCII (B3) : /!\, (!), (OK), [WARN]
#   - reperer ou se forme le titre (B4)
#
# Sortie : print L1178 a L1410 brut + scan glyphes sur tout le fichier.

import os
import re
import sys

API_FILE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

def read_utf8_or_latin1(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    # try strict utf-8 first
    try:
        return b.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return b.decode("latin-1"), "latin-1-fallback"

def main():
    if not os.path.exists(API_FILE):
        print("[FATAL] api_server.py introuvable")
        sys.exit(1)

    src, enc = read_utf8_or_latin1(API_FILE)
    print("nextones-diag-ic-memo-v4-dump  -  31/05/2026")
    print("FILE : " + API_FILE)
    print("ENCODING DETECTE : " + enc)
    lines = src.splitlines()
    print("Total lignes : %d" % len(lines))

    # ---- 1. Detection mojibake double-encodage dans le source ----
    print("")
    print("=" * 78)
    print("== 1. Detection mojibake dans api_server.py")
    print("=" * 78)
    mojibake_patterns = [
        ("u-grave standalone (faux em-dash)",  r" \xc3\xb9 | \xf9 "),
        ("u-circumflex standalone",            r" \xc3\xbb | \xfb "),
        ("a-circumflex euro (-> em-dash)",     r"\xc3\xa2\xe2\x82\xac"),
        ("BOM markers",                        r"\xef\xbb\xbf"),
    ]
    # On scan en bytes pour eviter les pieges
    with open(API_FILE, "rb") as f:
        raw = f.read()
    for label, pat in mojibake_patterns:
        try:
            rx = re.compile(pat.encode("latin-1"))
        except Exception:
            continue
        hits = list(rx.finditer(raw))
        print("  %-45s : %d occurrences" % (label, len(hits)))

    # ---- 2. Dump brut L1178 -> L1410 (coeur du PDF builder) ----
    print("")
    print("=" * 78)
    print("== 2. Dump brut L1178 -> L1410 (parser markdown + story)")
    print("=" * 78)
    start = 1178
    end   = min(len(lines), 1410)
    for i in range(start - 1, end):
        # supprimer non-ASCII pour l'affichage console PowerShell
        line = lines[i]
        # affichage byte-safe : remplace tout non-ASCII par '?'
        safe = "".join(c if 32 <= ord(c) < 127 else ("\\x%02x" % ord(c)) for c in line)
        if len(safe) > 240:
            safe = safe[:237] + "..."
        print("L%-5d %s" % (i + 1, safe))

    # ---- 3. Scan glyphes ASCII speciaux dans tout le fichier ----
    print("")
    print("=" * 78)
    print("== 3. Glyphes ASCII speciaux (B3)")
    print("=" * 78)
    glyph_pats = [
        ("/!\\",        r"/!\\"),
        ("(!)",         r"\(!\)"),
        ("(OK)",        r"\(OK\)"),
        ("[WARN]",      r"\[WARN\]"),
        ("[OK]",        r"\[OK\]"),
        ("[CHECK]",     r"\[CHECK\]"),
        ("[X]",         r"\[X\]"),
        ("=>",          r"=>"),
        ("->",          r"->"),
    ]
    for label, pat in glyph_pats:
        rx = re.compile(pat)
        hits = [(i+1, lines[i]) for i in range(len(lines)) if rx.search(lines[i])]
        # filtre les lignes contenant ic_memo, memo, pdf, header_footer pour rester focus
        keep = []
        for ln, t in hits:
            low = t.lower()
            if any(k in low for k in ("memo", "pdf", "markdown", "header_footer", "report", "footer")):
                keep.append((ln, t))
        if keep:
            print("  %-15s : %d occurrences pertinentes" % (label, len(keep)))
            for ln, t in keep[:5]:
                tt = t.strip()
                if len(tt) > 150:
                    tt = tt[:147] + "..."
                # safe display
                safe = "".join(c if 32 <= ord(c) < 127 else "?" for c in tt)
                print("    L%-5d %s" % (ln, safe))

    print("")
    print("[DONE] Diag v4 dump termine.")

if __name__ == "__main__":
    main()
