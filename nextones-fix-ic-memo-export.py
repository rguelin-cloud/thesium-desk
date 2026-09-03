# -*- coding: ascii -*-
# [MARKER] nextones-fix-ic-memo-export
#
# Patch quatre bugs export IC Memo (suite diag) :
#   B1  garde corps vide (raise + statut 'draft_empty')
#   B2  footer unique (supprime Paragraph footer du story, garde callback canvas)
#   B3  fonte symbole DejaVuSans pour /!\, (!), (OK), ->
#   B4  titre significatif : '#ID - tickers - regime - date'
#
# Usage :
#   py -3.13 .\nextones-fix-ic-memo-export.py            (apercu, dry-run)
#   py -3.13 .\nextones-fix-ic-memo-export.py --apply    (ecrit les fichiers)
#   py -3.13 .\nextones-fix-ic-memo-export.py --regen 49 (apres apply, regenere memo)
#
# Approche : modifie en place le fichier generateur IC Memo detecte
# par le diag. Backup .bak_YYYYMMDD_HHMMSS systematique.
# Lecture utf-8-sig, ecriture utf-8 sans BOM. Validation ast + py_compile.

import ast
import datetime
import glob
import os
import py_compile
import re
import shutil
import sqlite3
import sys
import traceback

DB_PATH    = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD_ROOT  = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
FONT_WIN   = r"C:\Windows\Fonts\DejaVuSans.ttf"
FONT_PROD  = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\fonts\DejaVuSans.ttf"

APPLY = "--apply" in sys.argv
REGEN = None
if "--regen" in sys.argv:
    i = sys.argv.index("--regen")
    if i + 1 < len(sys.argv):
        try:
            REGEN = int(sys.argv[i + 1])
        except ValueError:
            REGEN = None

TS = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

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
    return b.decode("utf-8")

def write_utf8(p, s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    with open(p, "wb") as f:
        f.write(s)

def validate_py(p):
    src = read_utf8(p)
    ast.parse(src, filename=p)
    py_compile.compile(p, doraise=True)
    print("    [OK] ast.parse + py_compile : " + os.path.basename(p))

# -------- 1. Localiser le generateur IC Memo --------
def find_generator():
    banner("1. Localisation generateur IC Memo")
    candidates = []
    patterns = ["*memo*.py", "*ic_memo*.py", "*pplx_memo*.py"]
    if not os.path.isdir(PROD_ROOT):
        print("  [FAIL] PROD_ROOT introuvable : " + PROD_ROOT)
        return None
    seen = set()
    for p in patterns:
        for f in glob.glob(os.path.join(PROD_ROOT, "**", p), recursive=True):
            if f in seen:
                continue
            seen.add(f)
            try:
                s = read_utf8(f)
            except Exception:
                continue
            score = 0
            if "SimpleDocTemplate" in s or "canvas.Canvas" in s:
                score += 3
            if re.search(r"Generee?\s+par\s+NEXTONES", s):
                score += 2
            if "IC Memo" in s or "IC-Memo" in s:
                score += 2
            if "Page %d" in s or "Page {0}" in s or "Page 1/" in s:
                score += 1
            if score >= 4:
                candidates.append((score, f))
    candidates.sort(reverse=True)
    if not candidates:
        print("  [FAIL] aucun generateur PDF IC Memo detecte. Lance d'abord le diag.")
        return None
    print("  Top candidats :")
    for sc, f in candidates[:5]:
        print("    [%d] %s" % (sc, os.path.relpath(f, PROD_ROOT)))
    return candidates[0][1]

# -------- 2. Patch source generateur --------
PATCH_HEADER_TAG = "# [PATCH-IC-MEMO-V2] nextones-fix-ic-memo-export"

PATCH_FONT_BLOCK = '''
# [PATCH-IC-MEMO-V2] fonte symbole (B3)
try:
    from reportlab.pdfbase import pdfmetrics as _pdfm_v2
    from reportlab.pdfbase.ttfonts import TTFont as _TTF_v2
    import os as _os_v2
    _sym_candidates = [
        r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\fonts\\DejaVuSans.ttf",
        r"C:\\Windows\\Fonts\\DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for _sp in _sym_candidates:
        if _os_v2.path.exists(_sp):
            try:
                _pdfm_v2.registerFont(_TTF_v2("Sym", _sp))
                break
            except Exception:
                pass
except Exception:
    pass
'''

PATCH_GUARD_BLOCK = '''
# [PATCH-IC-MEMO-V2] garde corps vide (B1)
class EmptyMemoError(ValueError):
    pass

def _ic_assert_body_not_empty(body, memo_id=None):
    if body is None or (isinstance(body, str) and not body.strip()):
        raise EmptyMemoError(
            "IC Memo %s : corps vide. Refus d'exporter. "
            "Verifier scheduler PPLX + table memos." % str(memo_id))
'''

def patch_source(path):
    banner("2. Patch generateur : " + os.path.relpath(path, PROD_ROOT))
    src = read_utf8(path)
    original = src
    changes = []

    # 2.0 idempotence
    if PATCH_HEADER_TAG in src:
        print("  [SKIP] patch deja applique (tag present).")
        return False, []

    # 2.1 B1 + B3 : inserer blocs en tete (apres derniers imports)
    lines = src.split("\n")
    last_import = 0
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(import|from)\s+", ln):
            last_import = i
    insert_at = last_import + 1
    block = "\n" + PATCH_HEADER_TAG + " - " + TS + "\n" + PATCH_FONT_BLOCK + PATCH_GUARD_BLOCK + "\n"
    lines.insert(insert_at, block)
    src = "\n".join(lines)
    changes.append("B1+B3 : blocs garde + fonte inseres ligne %d" % insert_at)

    # 2.2 B2 : supprimer Paragraph footer du STORY (pas le callback)
    # 'Gener\xe9e?' / 'Generee?' couvre Generee et Gener\u00e9e (mojibake et propre)
    pat_footer_para = re.compile(
        r"^[ \t]*[A-Za-z_][A-Za-z0-9_]*\.append\(\s*Paragraph\([^)]*Gener" +
        u"[\u00e9e]e?".encode("unicode_escape").decode("ascii") +
        r"\s+par\s+NEXTONES[^)]*\)\s*\)\s*$",
        re.MULTILINE)
    n_removed = 0
    def _kill(m):
        return "    # [PATCH-IC-MEMO-V2] B2 footer flowable retire (callback canvas conserve)"
    src, n_removed = pat_footer_para.subn(_kill, src)
    if n_removed:
        changes.append("B2 : %d Paragraph footer retire(s) du story" % n_removed)
    else:
        # fallback : commenter toute ligne contenant 'Generee par NEXTONES' DANS un story.append
        pat2 = re.compile(
            r"^([ \t]*)(.*Gener" +
            u"[\u00e9e]e?".encode("unicode_escape").decode("ascii") +
            r"\s+par\s+NEXTONES.*)$", re.MULTILINE)
        def _comment(m):
            indent, body = m.group(1), m.group(2)
            # ne commenter QUE si dans un append (heuristique : pas dans callback canvas)
            if "drawString" in body or "drawRightString" in body or "drawCentredString" in body:
                return m.group(0)  # callback canvas : on garde
            if "append" in body or "story" in body.lower() or "elements" in body.lower():
                return indent + "# [PATCH-IC-MEMO-V2] B2 # " + body
            return m.group(0)
        src, n2 = pat2.subn(_comment, src)
        if n2:
            changes.append("B2 (fallback) : %d ligne(s) commentee(s)" % n2)

    # 2.3 B4 : titre - si on trouve le placeholder, l'enrichir
    pat_title = re.compile(r"Nextones\s+IC\s+Memo\s*[-\u2013]\s*\{[^}]*date[^}]*\}", re.IGNORECASE)
    if pat_title.search(src):
        src = pat_title.sub("IC Memo #{memo_id} - {tickers} - {regime} - {date}", src)
        changes.append("B4 : titre enrichi (placeholders memo_id/tickers/regime)")
    else:
        # marqueur a verifier manuellement
        changes.append("B4 : placeholder titre non trouve - a verifier manuellement")

    # 2.4 B1 : injecter appel _ic_assert_body_not_empty si signature evidente
    # cherche def *generate*memo*(... body=... ) ou def export*pdf*
    pat_def = re.compile(
        r"(def\s+(?:generate_memo_pdf|export_memo_pdf|render_memo|build_memo_pdf|generate_ic_memo)\s*\([^)]*\)\s*:)",
        re.IGNORECASE)
    m = pat_def.search(src)
    if m:
        insert = (m.group(1) +
            "\n    # [PATCH-IC-MEMO-V2] B1 garde corps vide"
            "\n    try:"
            "\n        _ic_assert_body_not_empty(locals().get('body') or locals().get('content') or locals().get('markdown'), locals().get('memo_id'))"
            "\n    except EmptyMemoError as _e_v2:"
            "\n        import logging as _lg_v2; _lg_v2.getLogger(__name__).error(str(_e_v2))"
            "\n        raise"
        )
        src = src.replace(m.group(1), insert, 1)
        changes.append("B1 : assertion corps inseree dans " + m.group(1).split("(")[0].strip())

    if src == original:
        print("  [NOOP] aucun changement applique.")
        return False, []

    # 2.5 backup + write si --apply
    bak = path + ".bak_" + TS
    if APPLY:
        shutil.copy2(path, bak)
        write_utf8(path, src)
        try:
            validate_py(path)
        except Exception as e:
            # rollback
            shutil.copy2(bak, path)
            print("  [ROLLBACK] validation echouee, fichier restaure : " + str(e))
            traceback.print_exc()
            return False, []
        print("  [APPLY] patch applique. backup : " + os.path.basename(bak))
    else:
        # ecrire dans un .preview
        preview = path + ".preview_" + TS
        write_utf8(preview, src)
        print("  [DRY-RUN] preview ecrit : " + preview)
        print("  Pour appliquer : py -3.13 .\\nextones-fix-ic-memo-export.py --apply")
    for c in changes:
        print("    - " + c)
    return APPLY, changes

# -------- 3. Statut DB pour les memos vides --------
def mark_empty_memos():
    banner("3. DB - marquer memos vides en 'draft_empty'")
    if not os.path.exists(DB_PATH):
        print("  [SKIP] DB introuvable : " + DB_PATH)
        return
    cn = sqlite3.connect(DB_PATH, timeout=30.0)
    cn.execute("PRAGMA busy_timeout = 30000")
    try:
        tables = [r[0] for r in cn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%memo%'").fetchall()]
        for t in tables:
            cols = [c[1].lower() for c in cn.execute("PRAGMA table_info(" + t + ")").fetchall()]
            body_col = None
            for cand in ("body", "content", "markdown", "text", "memo"):
                if cand in cols:
                    body_col = cand
                    break
            if not body_col:
                continue
            has_status = "status" in cols
            if not has_status:
                print("  table %s : pas de col 'status' - skip" % t)
                continue
            empty_ids = [r[0] for r in cn.execute(
                "SELECT id FROM " + t + " WHERE " + body_col + " IS NULL OR TRIM(" + body_col + ") = ''"
            ).fetchall()]
            print("  table %s : %d memos vides" % (t, len(empty_ids)))
            if APPLY and empty_ids:
                cn.execute(
                    "UPDATE " + t + " SET status = 'draft_empty' "
                    "WHERE (" + body_col + " IS NULL OR TRIM(" + body_col + ") = '') "
                    "AND (status IS NULL OR status NOT IN ('draft_empty','archived'))")
                cn.commit()
                print("    [APPLY] %d ligne(s) marquee(s) draft_empty" % len(empty_ids))
    finally:
        cn.close()

# -------- 4. Regen memo temoin --------
def regen_memo(mid):
    banner("4. Regeneration memo #%d" % mid)
    print("  Note : non-implementee ici - dependante de l'API generateur.")
    print("  Apres apply, faire :")
    print("    py -3.13 -c \"from pplx_memo_agent import export_memo_pdf as e; "
          "e(memo_id=%d, force_refresh=True)\"" % mid)

# -------- main --------
if __name__ == "__main__":
    print("nextones-fix-ic-memo-export  -  " + TS)
    print("mode : " + ("APPLY" if APPLY else "DRY-RUN"))
    gen = find_generator()
    if gen:
        patch_source(gen)
    mark_empty_memos()
    if REGEN is not None:
        regen_memo(REGEN)
    print("")
    print("[DONE]")
