# -*- coding: utf-8 -*-
# Diag v10 : trouver le nom de colonne markdown + dumper le contenu du memo 51
# Sortie ASCII dans diag-v10-output.txt

import os
import io
import sqlite3
import json

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
OUT = os.path.join(os.getcwd(), "diag-v10-output.txt")


def main():
    buf = io.StringIO()

    def w(line=""):
        buf.write(str(line) + "\n")

    w("=" * 78)
    w("DIAG V10 - MARKDOWN SOURCE MEMO 51")
    w("=" * 78)

    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row

        # 1. schema ic_memos
        w("")
        w("-" * 78)
        w("[1] Schema ic_memos")
        w("-" * 78)
        cols = conn.execute("PRAGMA table_info(ic_memos)").fetchall()
        for c in cols:
            w("col " + str(c["cid"]).rjust(2) + " | " + (c["name"] or "").ljust(28) + " | " + (c["type"] or ""))
        col_names = [c["name"] for c in cols]
        w("")
        w("Colonnes : " + ", ".join(col_names))

        # 2. memo 51 full row
        w("")
        w("-" * 78)
        w("[2] Memo 51 - dump tous champs")
        w("-" * 78)
        row = conn.execute("SELECT * FROM ic_memos WHERE id = 51").fetchone()
        if not row:
            row = conn.execute("SELECT * FROM ic_memos ORDER BY id DESC LIMIT 1").fetchone()
        if not row:
            w("[ERREUR] aucun memo")
            conn.close()
            with open(OUT, "w", encoding="utf-8") as f:
                f.write(buf.getvalue())
            return
        d = {k: row[k] for k in row.keys()}
        w("Memo id : " + str(d.get("id")))
        for k, v in d.items():
            s = str(v) if v is not None else "NULL"
            w("  field=" + k + " | len=" + str(len(s)) + " | preview=" + s.replace("\n", "\\n")[:120])

        # 3. identifier la colonne markdown
        w("")
        w("-" * 78)
        w("[3] Identifier colonne markdown (champ avec '## ' ou '|' ou 'Active Thesis')")
        w("-" * 78)
        md_col = None
        for k, v in d.items():
            if v is None:
                continue
            s = str(v)
            if ("## " in s or "Active Thesis" in s or "Market Indicators" in s) and len(s) > 200:
                md_col = k
                w("==> Colonne markdown trouvee : " + k + " (len=" + str(len(s)) + ")")
                break
        if md_col is None:
            w("[KO] aucune colonne markdown detectee. Examiner les plus longues :")
            sorted_cols = sorted(d.items(), key=lambda x: -len(str(x[1] or "")))
            for k, v in sorted_cols[:5]:
                w("  " + k + " len=" + str(len(str(v or ""))))
            conn.close()
            with open(OUT, "w", encoding="utf-8") as f:
                f.write(buf.getvalue())
            return

        md = str(d[md_col])
        md_lines = md.split("\n")
        w("")
        w("Total lignes markdown : " + str(len(md_lines)))

        # 4. extraction sections cles
        w("")
        w("-" * 78)
        w("[4] Sections du markdown (par '## ' headers)")
        w("-" * 78)
        for k, ln in enumerate(md_lines):
            s = ln.lstrip()
            if s.startswith("## ") or s.startswith("# "):
                w("L" + str(k + 1) + " : " + ln.rstrip()[:140])

        # 5. dump bloc Market Indicators
        w("")
        w("-" * 78)
        w("[5] BLOC 'Market Indicators' brut")
        w("-" * 78)
        start = None
        for k, ln in enumerate(md_lines):
            if "Market Indicators" in ln:
                start = k
                break
        if start is not None:
            end = min(len(md_lines), start + 20)
            for k in range(start, end):
                w("L" + str(k + 1) + " : " + repr(md_lines[k])[:160])

        # 6. dump bloc Factor Tilts + Factor Scores
        w("")
        w("-" * 78)
        w("[6] BLOC 'Factor Tilts' / 'Factor Scores' brut")
        w("-" * 78)
        start = None
        for k, ln in enumerate(md_lines):
            if "Factor Tilts" in ln:
                start = k
                break
        if start is not None:
            end = min(len(md_lines), start + 35)
            for k in range(start, end):
                w("L" + str(k + 1) + " : " + repr(md_lines[k])[:160])

        # 7. dump bloc Active Thesis Summaries en entier
        w("")
        w("-" * 78)
        w("[7] BLOC 'Active Thesis Summaries' brut (jusqu'a prochain '## ')")
        w("-" * 78)
        start = None
        for k, ln in enumerate(md_lines):
            if "Active Thesis Summaries" in ln:
                start = k
                break
        if start is not None:
            end = len(md_lines)
            for k in range(start + 1, len(md_lines)):
                s = md_lines[k].lstrip()
                if s.startswith("## "):
                    end = k
                    break
            w("Plage L" + str(start + 1) + " a L" + str(end) + " (" + str(end - start) + " lignes)")
            # comptage Thesis ID #xxxx
            count_blocks = 0
            for k in range(start, end):
                if "Thesis ID" in md_lines[k]:
                    count_blocks += 1
            w("Nombre de blocs 'Thesis ID' : " + str(count_blocks))
            w("---")
            for k in range(start, end):
                w("L" + str(k + 1) + " : " + md_lines[k].rstrip()[:160])
            w("---")

        # 8. dump bloc Proposed Changes
        w("")
        w("-" * 78)
        w("[8] BLOC 'Proposed Changes' brut")
        w("-" * 78)
        start = None
        for k, ln in enumerate(md_lines):
            if "Proposed Changes" in ln:
                start = k
                break
        if start is not None:
            end = min(len(md_lines), start + 30)
            for k in range(start, end):
                w("L" + str(k + 1) + " : " + repr(md_lines[k])[:180])

        conn.close()
    except Exception as e:
        w("[ERREUR] " + str(e))

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(buf.getvalue())
    print("Diag v10 ecrit dans : " + OUT)


if __name__ == "__main__":
    main()
