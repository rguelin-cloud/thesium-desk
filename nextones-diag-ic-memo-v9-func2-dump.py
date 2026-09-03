# -*- coding: utf-8 -*-
# Diag v9 : dump cible de la 2eme fonction get_memo_pdf (L1494-L1839)
# + dump du body markdown des memos pour comprendre R4 (Active Thesis * 16) et R5 (Factor Scores)
#
# Sortie ASCII dans diag-v9-output.txt

import os
import io
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "api_server.py")
DB = os.path.join(ROOT, "thesium.db")
OUT = os.path.join(os.getcwd(), "diag-v9-output.txt")


def main():
    buf = io.StringIO()

    def w(line=""):
        buf.write(str(line) + "\n")

    w("=" * 78)
    w("DIAG V9 - DUMP FONCTION #2 get_memo_pdf + MARKDOWN MEMO 51")
    w("=" * 78)

    # ---- A) Dump api_server.py L1494-L1839 par tranches contextuelles ----
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    w("")
    w("-" * 78)
    w("[A] Signature et debut fonction #2 (L1494-L1530)")
    w("-" * 78)
    for i in range(1493, min(1530, len(lines))):
        w(str(i + 1).rjust(4) + " | " + lines[i].rstrip()[:160])

    w("")
    w("-" * 78)
    w("[B] Zone R2 doublon - bloc Thesis Summaries #2 (L1755-L1800)")
    w("-" * 78)
    for i in range(1754, min(1800, len(lines))):
        w(str(i + 1).rjust(4) + " | " + lines[i].rstrip()[:160])

    w("")
    w("-" * 78)
    w("[C] Zone R2 suite + Proposed Changes #2 (L1790-L1839)")
    w("-" * 78)
    for i in range(1789, min(1840, len(lines))):
        w(str(i + 1).rjust(4) + " | " + lines[i].rstrip()[:160])

    w("")
    w("-" * 78)
    w("[D] Zone flush_md_table fonction #2 (L1595-L1670) - R3 logique en-tete")
    w("-" * 78)
    for i in range(1594, min(1670, len(lines))):
        w(str(i + 1).rjust(4) + " | " + lines[i].rstrip()[:160])

    # ---- E) Dump markdown du memo 51 pour comprendre R4/R5 ----
    w("")
    w("-" * 78)
    w("[E] Markdown source memo 51 - sections Active Thesis / Factor Scores")
    w("-" * 78)
    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT id, body_md FROM ic_memos WHERE id = 51").fetchone()
        if not row:
            row = conn.execute("SELECT id, body_md FROM ic_memos ORDER BY id DESC LIMIT 1").fetchone()
        if row:
            md = row["body_md"] or ""
            w("Memo id : " + str(row["id"]))
            w("Body length : " + str(len(md)))
            # split en lignes
            md_lines = md.split("\n")
            w("Total lignes markdown : " + str(len(md_lines)))
            w("")
            # localiser sections
            for keyword in ("Active Thesis", "Factor Scores", "Factor Tilts", "Market Indicators", "Thesis Summaries", "Audit Trail", "Proposed Changes"):
                w(">>> section '" + keyword + "' :")
                for k, ln in enumerate(md_lines):
                    if keyword in ln:
                        w("  L" + str(k + 1) + " : " + ln.rstrip()[:140])
                w("")

            # extraire bloc "Active Thesis Summaries" complet
            w(">>> BLOC 'Active Thesis Summaries' complet (jusqu'a section suivante) :")
            start = None
            for k, ln in enumerate(md_lines):
                if "Active Thesis Summaries" in ln:
                    start = k
                    break
            if start is not None:
                # next H2 or H3 marker
                end = len(md_lines)
                for k in range(start + 1, len(md_lines)):
                    s = md_lines[k].lstrip()
                    if s.startswith("## ") or s.startswith("# "):
                        end = k
                        break
                w("Lignes " + str(start + 1) + " a " + str(end) + " (" + str(end - start) + " lignes)")
                w("---")
                for k in range(start, end):
                    w(md_lines[k].rstrip()[:160])
                w("---")
            w("")

            # extraire bloc "Factor Tilts" + "Factor Scores"
            w(">>> BLOC 'Factor Tilts' + 'Factor Scores' :")
            start = None
            for k, ln in enumerate(md_lines):
                if "Factor Tilts" in ln:
                    start = k
                    break
            if start is not None:
                end = len(md_lines)
                for k in range(start + 1, len(md_lines)):
                    s = md_lines[k].lstrip()
                    if s.startswith("## "):
                        end = k
                        break
                w("Lignes " + str(start + 1) + " a " + str(end))
                w("---")
                for k in range(start, end):
                    w(md_lines[k].rstrip()[:160])
                w("---")
            w("")

            # extraire bloc "Market Indicators" pour comprendre R3
            w(">>> BLOC 'Market Indicators' (R3) :")
            start = None
            for k, ln in enumerate(md_lines):
                if "Market Indicators" in ln:
                    start = k
                    break
            if start is not None:
                end = min(len(md_lines), start + 15)
                w("---")
                for k in range(start, end):
                    w(md_lines[k].rstrip()[:160])
                w("---")
        else:
            w("[ERREUR] aucun memo trouve")
        conn.close()
    except Exception as e:
        w("[ERREUR DB] " + str(e))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("Diag v9 ecrit dans : " + OUT)


if __name__ == "__main__":
    main()
