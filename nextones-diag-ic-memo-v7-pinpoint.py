# -*- coding: ascii -*-
# [MARKER] nextones-diag-ic-memo-v7-pinpoint
#
# Diag v6 a revele :
#   - app.js:L2919 -> bouton onclick="exportMemoPDF(memo_id)"
#   - app.js:L3109 -> async function exportMemoPDF(memoId) { ... }
#   - api_server.py:L1500-1750 = 2e bloc PDF generateur complet INDEPENDANT de
#     get_memo_pdf de L1078 (qu'on a patche 3x dans le vide)
#
# Ce diag v7 isole :
#   1) L'URL exacte appelee par exportMemoPDF (lecture L3109 -> L3250 de app.js)
#   2) La signature @app.get au-dessus de L1500 dans api_server.py
#   3) La fin de cette 2e fonction PDF (pour borner le patch)
#
# Sortie ASCII ecrite dans diag-v7-output.txt.

import os
import re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
OUT  = os.path.join(ROOT, "diag-v7-output.txt")


def read_safe(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b.decode("utf-8", errors="replace")


def write_ascii(out_path, lines):
    with open(out_path, "wb") as f:
        for ln in lines:
            safe = ln.encode("ascii", errors="replace").decode("ascii")
            f.write((safe + "\n").encode("ascii"))


def main():
    out = []
    W = out.append

    def banner(t):
        W("")
        W("=" * 80)
        W("== " + t)
        W("=" * 80)

    # ----- 1) app.js : function exportMemoPDF -----
    banner("[1] app.js  L3080 -> L3260  (function exportMemoPDF + URL fetch)")
    js = None
    for dirpath, dirs, files in os.walk(ROOT):
        if any(s in dirpath for s in [".venv", "node_modules", "_backups", "__pycache__"]):
            continue
        for fn in files:
            if fn == "app.js":
                js = os.path.join(dirpath, fn)
                break
        if js:
            break
    if not js:
        W("  [FATAL] app.js introuvable")
    else:
        W("  Fichier : " + os.path.relpath(js, ROOT))
        src = read_safe(js)
        lines = src.splitlines()
        for i in range(3079, min(3260, len(lines))):
            W("%5d | %s" % (i + 1, lines[i][:220]))

    # ----- 2) api_server.py : zone L1430-1510 (route au-dessus de L1500) -----
    banner("[2] api_server.py  L1430 -> L1510  (route + def juste avant)")
    api = os.path.join(ROOT, "api_server.py")
    src = read_safe(api)
    lines = src.splitlines()
    for i in range(1429, min(1510, len(lines))):
        W("%5d | %s" % (i + 1, lines[i][:220]))

    # ----- 3) api_server.py : detecter la fin du bloc L1500-XXX -----
    banner("[3] api_server.py  recherche FIN du bloc (apres L1500)")
    # On cherche la prochaine ligne au top-level: @app., @router., def , class
    # apres L1500.
    end_line = None
    for i in range(1500, len(lines)):
        ln = lines[i]
        if ln.startswith("@app.") or ln.startswith("@router.") or \
           (ln.startswith("def ") and not ln.startswith("def header_footer") and "    " not in ln[:4]) or \
           ln.startswith("class "):
            end_line = i + 1
            W("  Frontiere fin probable : L%d :  %s" % (end_line, ln[:150]))
            break
    if end_line:
        # Dump 10 lignes avant et 5 apres pour contexte
        a = max(0, end_line - 12)
        b = min(len(lines), end_line + 5)
        W("")
        W("  Contexte autour de la frontiere :")
        for i in range(a, b):
            marker = " >> " if (i + 1) == end_line else "    "
            W("%s%5d | %s" % (marker, i + 1, lines[i][:200]))

    # ----- 4) Lister TOUTES les routes get/post de api_server.py -----
    banner("[4] Toutes les routes de api_server.py (pour map global)")
    for i, ln in enumerate(lines, 1):
        if re.match(r'^@app\.(get|post|put|delete)\(', ln):
            # ligne suivante = signature def
            nxt = lines[i] if i < len(lines) else ""
            W("  L%-5d  %s   ::   %s" % (i, ln[:80], nxt[:80]))

    # ----- 5) Empreinte "Perplexity Computer" et "Genere par NEXTONES" autour de L1500 -----
    banner("[5] Empreintes du faux generateur dans api_server.py")
    for i, ln in enumerate(lines, 1):
        if "Perplexity Computer" in ln or "Genere par NEXTONES" in ln or "Genere par Nextones" in ln:
            W("  L%-5d : %s" % (i, ln[:200]))

    write_ascii(OUT, out)
    print("OK -> sortie ASCII ecrite dans : " + OUT)
    print("Ouvrir avec : notepad " + OUT)


if __name__ == "__main__":
    main()
