# -*- coding: utf-8 -*-
"""
nextones-patch-memo-convergence-v1
Ajoute la section 'Convergence Engine' au memo IC genere par memo_generator.py.

Insertion :
  1. Nouvelle fonction _build_convergence_section(conn) -> str
  2. Appel dans generate_ic_memo() entre theses et proposed_changes
  3. Marker idempotent : # [ICMEMO_CONVERGENCE_V1]

Validation : ast.parse + py_compile avant ecriture.
"""
import os, sys, io, re, ast, py_compile, shutil
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG_PATH = os.path.join(BASE, "memo_generator.py")
MARKER = "# [ICMEMO_CONVERGENCE_V1]"

# La fonction a ajouter
NEW_FUNCTION = '''
# [ICMEMO_CONVERGENCE_V1]
def _build_convergence_section(conn):
    """
    Section 'Convergence Engine' du memo IC.
    Lit convergence_snapshots pour le cycle le plus recent et produit un
    tableau markdown segmente : forced_exit / drift / strong / neutres.
    Lecture seule. Fail-safe : placeholder si table manquante ou cycle absent.
    """
    try:
        cur = conn.cursor()
        # cycle le plus recent
        cur.execute("SELECT cycle_id, created_at FROM convergence_snapshots ORDER BY rowid DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            return "## Convergence Engine\\n\\n*Aucun snapshot convergence disponible.*\\n\\n"
        cycle_id = row[0]
        created_at = row[1] if len(row) > 1 else ""

        cur.execute("""
            SELECT ticker, direction_consensus, n_aligned, n_present, convergence_pct,
                   sizing_multiplier, forced_exit, drift, is_crypto, buckets_json
            FROM convergence_snapshots
            WHERE cycle_id = ?
            ORDER BY ticker
        """, (cycle_id,))
        rows = [dict(zip(
            ["ticker","dir","n","ntotal","pct","sizing","fe","drift","crypto","buckets"], r
        )) for r in cur.fetchall()]

        if not rows:
            return f"## Convergence Engine\\n\\n*Aucun ticker dans le cycle {cycle_id}.*\\n\\n"

        # totaux
        n_total = len(rows)
        n_fe = sum(1 for r in rows if r["fe"])
        n_drift = sum(1 for r in rows if r["drift"] and not r["fe"])
        n_strong = sum(1 for r in rows
                       if not r["fe"] and not r["drift"]
                       and (r["sizing"] or 0) >= 1.0 and (r["n"] or 0) >= 3)
        n_neutral = n_total - n_fe - n_drift - n_strong

        def _bucket_driver(r, key):
            try:
                buckets = json.loads(r["buckets"] or "{}")
            except Exception:
                buckets = {}
            b = buckets.get(key) or {}
            return (b.get("direction"), b.get("driver"), b.get("source"))

        def _row_l5_driver(r):
            _, driver, _ = _bucket_driver(r, "L5")
            return driver or "-"

        def _row_dominant_drivers(r):
            try:
                buckets = json.loads(r["buckets"] or "{}")
            except Exception:
                buckets = {}
            parts = []
            for k in ["L1","L2","L3","L4","L5"]:
                b = buckets.get(k) or {}
                if b.get("direction"):
                    parts.append(f"{k}:{b.get('direction')}")
            return " · ".join(parts) if parts else "-"

        def _esc_md(s):
            if s is None:
                return "-"
            return str(s).replace("|", "\\\\|").replace("\\n", " ").strip()

        out = []
        out.append("## Convergence Engine")
        out.append("")
        out.append(f"**Cycle {cycle_id}** · {created_at} · {n_total} tickers · "
                   f"{n_fe} forced_exit · {n_drift} drift · {n_strong} strong · {n_neutral} neutres")
        out.append("")

        # Forced exit
        fe_rows = [r for r in rows if r["fe"]]
        if fe_rows:
            out.append("### Forced exit (sizing x0.0)")
            out.append("")
            out.append("| Ticker | Consensus | Aligné | Driver L5 (ExitAgent) |")
            out.append("|---|---|---|---|")
            for r in sorted(fe_rows, key=lambda x: (-(x["pct"] or 0), x["ticker"])):
                badge = " (crypto)" if r["crypto"] else ""
                out.append(f"| **{r['ticker']}**{badge} | {r['dir'] or '-'} | "
                           f"{r['n']}/{r['ntotal']} | {_esc_md(_row_l5_driver(r))[:120]} |")
            out.append("")

        # Drift
        dr_rows = [r for r in rows if r["drift"] and not r["fe"]]
        if dr_rows:
            out.append("### Drift (sizing x0.5)")
            out.append("")
            out.append("| Ticker | Consensus | Aligné | Driver L5 (ExitAgent) |")
            out.append("|---|---|---|---|")
            for r in sorted(dr_rows, key=lambda x: x["ticker"]):
                badge = " (crypto)" if r["crypto"] else ""
                out.append(f"| **{r['ticker']}**{badge} | {r['dir'] or '-'} | "
                           f"{r['n']}/{r['ntotal']} | {_esc_md(_row_l5_driver(r))[:120]} |")
            out.append("")

        # Strong
        st_rows = [r for r in rows
                   if not r["fe"] and not r["drift"]
                   and (r["sizing"] or 0) >= 1.0 and (r["n"] or 0) >= 3]
        if st_rows:
            out.append("### Strong consensus (sizing x1.0+, n_aligned ≥ 3)")
            out.append("")
            out.append("| Ticker | Consensus | Aligné | Buckets actifs |")
            out.append("|---|---|---|---|")
            for r in sorted(st_rows, key=lambda x: (-(x["pct"] or 0), x["ticker"])):
                badge = " (crypto)" if r["crypto"] else ""
                out.append(f"| **{r['ticker']}**{badge} | {r['dir'] or '-'} | "
                           f"{r['n']}/{r['ntotal']} | {_esc_md(_row_dominant_drivers(r))[:120]} |")
            out.append("")

        # Neutres (resume seulement)
        nu_rows = [r for r in rows
                   if not r["fe"] and not r["drift"]
                   and not ((r["sizing"] or 0) >= 1.0 and (r["n"] or 0) >= 3)]
        if nu_rows:
            tickers_str = ", ".join(sorted(r["ticker"] for r in nu_rows))
            out.append(f"### Neutres ({len(nu_rows)} tickers)")
            out.append("")
            out.append(f"{tickers_str}")
            out.append("")
            out.append(f"*Conviction faible (n_aligned < 3 ou sizing par defaut). "
                       f"Detail complet dans la carte Convergence Engine du dashboard Today.*")
            out.append("")

        return "\\n".join(out) + "\\n"

    except Exception as _e_cvg:
        return f"## Convergence Engine\\n\\n*Erreur lecture convergence_snapshots : {_e_cvg}*\\n\\n"

'''.lstrip()

# Le call a inserer dans generate_ic_memo (entre theses et proposed_changes)
CALL_LINE = "    sections.append(_build_convergence_section(conn))  # [ICMEMO_CONVERGENCE_V1]"

def patch():
    with open(MG_PATH, "r", encoding="utf-8-sig") as f:
        src = f.read()
    print(f"[READ] {MG_PATH} ({len(src)} chars)")

    if MARKER in src:
        print("[SKIP] marker present, idempotent")
        return False

    # 1. Inserer la fonction AVANT 'def generate_ic_memo'
    pat_gen = re.compile(r'^def\s+generate_ic_memo\b', re.MULTILINE)
    m = pat_gen.search(src)
    if not m:
        print("[ERREUR] generate_ic_memo introuvable")
        return False
    insertion_func = m.start()
    print(f"[INSERT FUNC] avant generate_ic_memo @ ligne ~{src[:insertion_func].count(chr(10))+1}")

    new_src = src[:insertion_func] + NEW_FUNCTION + "\n" + src[insertion_func:]

    # 2. Inserer l'appel dans generate_ic_memo
    # Strategie : trouver le call au _build_thesis_section et inserer juste APRES
    # Si non trouve, fallback : trouver _build_proposed_changes_section et inserer AVANT.
    pat_thesis_call = re.compile(r'^(\s*)(sections\.append\(_build_thesis_section[^\n]*\))', re.MULTILINE)
    m2 = pat_thesis_call.search(new_src)
    if m2:
        # Insertion apres la ligne du _build_thesis_section
        end = m2.end()
        indent = m2.group(1)
        new_src = new_src[:end] + "\n" + indent + CALL_LINE.lstrip() + new_src[end:]
        print(f"[INSERT CALL] apres _build_thesis_section")
    else:
        pat_proposed = re.compile(r'^(\s*)(sections\.append\(_build_proposed_changes_section[^\n]*\))', re.MULTILINE)
        m3 = pat_proposed.search(new_src)
        if m3:
            start = m3.start()
            indent = m3.group(1)
            new_src = new_src[:start] + indent + CALL_LINE.lstrip() + "\n" + new_src[start:]
            print(f"[INSERT CALL] avant _build_proposed_changes_section (fallback)")
        else:
            print("[WARN] aucun call thesis/proposed trouve, on cherche append en fin")
            # Fallback ultime : avant le retour de generate_ic_memo
            pat_join = re.compile(r'^(\s*)(full_markdown\s*=\s*["\']\\?\\?n["\']\.join\(sections\))', re.MULTILINE)
            mj = pat_join.search(new_src)
            if mj:
                indent = mj.group(1)
                new_src = new_src[:mj.start()] + indent + CALL_LINE.lstrip() + "\n" + new_src[mj.start():]
                print(f"[INSERT CALL] avant '.join(sections)' (fallback ultime)")
            else:
                print("[ERREUR] impossible d'inserer le call - abort")
                return False

    # 3. Validation AST
    try:
        ast.parse(new_src)
        print("[AST] OK")
    except SyntaxError as e:
        print(f"[AST] FAIL : {e}")
        # Sauvegarde du fichier qui pose probleme pour debug
        debug_path = MG_PATH + ".debug-failed"
        with open(debug_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_src)
        print(f"      ecrit pour debug : {debug_path}")
        return False

    # 4. Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = MG_PATH + f".bak-icmemo-conv-{ts}"
    shutil.copy2(MG_PATH, bak)
    print(f"[BACKUP] {bak}")

    # 5. Write
    with open(MG_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_src)
    print(f"[WRITE] {len(new_src) - len(src)} chars ajoutes")

    # 6. py_compile final
    try:
        py_compile.compile(MG_PATH, doraise=True)
        print("[PY_COMPILE] OK")
    except py_compile.PyCompileError as e:
        print(f"[PY_COMPILE] FAIL : {e}")
        # restore
        shutil.copy2(bak, MG_PATH)
        print(f"[RESTORE] depuis {bak}")
        return False

    return True

if __name__ == "__main__":
    print("=" * 60)
    print("PATCH MEMO CONVERGENCE V1")
    print("=" * 60)
    r = patch()
    print()
    print(f"[RESULT] {'PATCHED' if r else 'SKIPPED/FAILED'}")
    if r:
        print("[NEXT] Regenerer un memo IC :")
        print("  curl -X POST http://localhost:8000/api/memos/generate")
        print("  ou via UI bouton 'Generate Memo'")
        print("  puis GET /api/memos pour voir le nouveau, et /api/memos/{id}/markdown pour valider")
