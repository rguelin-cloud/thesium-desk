# -*- coding: ascii -*-
# [MARKER] nextones-fix-icmemo-jsclient-redirect
#
# Le bouton "Export PDF" appelle exportMemoPDF() (app.js L3108) qui genere
# un PDF cote NAVIGATEUR avec jsPDF (CDN). Cela court-circuite totalement
# la route serveur /api/memos/{id}/pdf qu'on a patchee en v2/v3/v4.
#
# Ce patch :
#   - Localise la fonction async function exportMemoPDF(memoId) { ... }
#   - Remplace son corps par 6 lignes qui appellent /api/memos/{id}/pdf
#     et declenchent un download du PDF serveur (notre version corrigee)
#   - Backup app.js horodate, idempotent via marker, rollback auto
#
# Idempotent : marker [ICMEMO_JS_REDIRECT_V1]
#
# Usage :
#   py -3.13 .\nextones-fix-icmemo-jsclient-redirect.py

import os
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MARKER = "[ICMEMO_JS_REDIRECT_V1]"


def read_utf8(p):
    with open(p, "rb") as f:
        b = f.read()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    return b.decode("utf-8")


def write_utf8(p, s):
    with open(p, "wb") as f:
        f.write(s.encode("utf-8"))


def find_app_js(root):
    for dirpath, dirs, files in os.walk(root):
        if any(s in dirpath for s in [".venv", "node_modules", "_backups", "__pycache__"]):
            continue
        for fn in files:
            if fn == "app.js":
                return os.path.join(dirpath, fn)
    return None


def find_function_bounds(src, fn_signature):
    """Find start and end (exclusive) line indices of the function block.
    fn_signature : exact line text that opens the function (without trailing { ).
    Returns (start_line_idx, end_line_idx) or None.
    Uses brace counting starting from the opening { on the same line or next.
    """
    lines = src.splitlines(keepends=True)
    start_idx = None
    for i, ln in enumerate(lines):
        if fn_signature in ln:
            start_idx = i
            break
    if start_idx is None:
        return None

    # Find opening brace
    text_from_start = "".join(lines[start_idx:])
    brace_pos = text_from_start.find("{")
    if brace_pos < 0:
        return None

    # Brace counting
    depth = 0
    cursor = 0
    end_offset = None
    for j, ch in enumerate(text_from_start[brace_pos:], start=brace_pos):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end_offset = j + 1
                break
    if end_offset is None:
        return None

    # Convert back to line indices
    end_char = sum(len(l) for l in lines[:start_idx]) + end_offset
    char_count = 0
    end_idx = None
    for k, ln in enumerate(lines):
        char_count += len(ln)
        if char_count >= end_char:
            end_idx = k + 1
            break
    if end_idx is None:
        end_idx = len(lines)
    return (start_idx, end_idx)


NEW_FN = (
    "// " + MARKER + " - Redirection vers route serveur (patches v2/v3/v4)\n"
    "async function exportMemoPDF(memoId) {\n"
    "  const btn = document.querySelector('.btn-export-pdf');\n"
    "  const origHTML = btn ? btn.innerHTML : null;\n"
    "  if (btn) {\n"
    "    btn.disabled = true;\n"
    "    btn.innerHTML = '<svg width=\"12\" height=\"12\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"2.5\" class=\"spin\"><path d=\"M21 12a9 9 0 1 1-6.219-8.56\"/></svg> Export...';\n"
    "  }\n"
    "  try {\n"
    "    // Recupere le token JWT (cf. apiFetch)\n"
    "    const token = (typeof getToken === 'function') ? getToken() : (localStorage.getItem('token') || '');\n"
    "    const resp = await fetch('/api/memos/' + encodeURIComponent(memoId) + '/pdf', {\n"
    "      method: 'GET',\n"
    "      headers: token ? { 'Authorization': 'Bearer ' + token } : {}\n"
    "    });\n"
    "    if (!resp.ok) {\n"
    "      throw new Error('HTTP ' + resp.status + ' ' + resp.statusText);\n"
    "    }\n"
    "    const blob = await resp.blob();\n"
    "    const cd = resp.headers.get('Content-Disposition') || '';\n"
    "    let filename = 'IC-Memo-' + memoId + '.pdf';\n"
    "    const m = /filename=\"?([^\";]+)\"?/i.exec(cd);\n"
    "    if (m) filename = m[1];\n"
    "    const url = URL.createObjectURL(blob);\n"
    "    const a = document.createElement('a');\n"
    "    a.href = url;\n"
    "    a.download = filename;\n"
    "    document.body.appendChild(a);\n"
    "    a.click();\n"
    "    document.body.removeChild(a);\n"
    "    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);\n"
    "    if (typeof showToast === 'function') showToast('Export PDF OK : ' + filename, 'success');\n"
    "  } catch (err) {\n"
    "    if (typeof showToast === 'function') showToast('Export PDF echoue: ' + err.message, 'error');\n"
    "    else alert('Export PDF echoue: ' + err.message);\n"
    "  } finally {\n"
    "    if (btn) {\n"
    "      btn.disabled = false;\n"
    "      if (origHTML !== null) btn.innerHTML = origHTML;\n"
    "    }\n"
    "  }\n"
    "}\n"
)


def main():
    print("nextones-fix-icmemo-jsclient-redirect  -  02/06/2026")
    js = find_app_js(ROOT)
    if not js:
        print("[FATAL] app.js introuvable sous " + ROOT)
        sys.exit(1)
    print("FILE : " + js)

    src = read_utf8(js)

    if MARKER in src:
        print("[SKIP] Marker " + MARKER + " deja present. Patch deja applique.")
        return 0

    bounds = find_function_bounds(src, "async function exportMemoPDF(memoId)")
    if not bounds:
        print("[FATAL] fonction exportMemoPDF introuvable.")
        sys.exit(2)
    s_idx, e_idx = bounds
    lines = src.splitlines(keepends=True)
    print("  Bornes detectees : L%d -> L%d (%d lignes a remplacer)" %
          (s_idx + 1, e_idx, e_idx - s_idx))

    ts = time.strftime("%Y%m%d_%H%M%S")
    bk = js + ".bak_jsredirect_" + ts
    shutil.copy2(js, bk)
    print("  backup : " + bk)

    # Reconstruit le fichier
    new_lines = lines[:s_idx] + [NEW_FN] + lines[e_idx:]
    new_src = "".join(new_lines)

    write_utf8(js, new_src)
    print("  ecrit  : %d bytes" % len(new_src.encode("utf-8")))

    # Validation syntaxique JS basique : compter braces
    opens = new_src.count("{")
    closes = new_src.count("}")
    if opens != closes:
        print("[FAIL] desequilibre accolades { %d vs } %d - ROLLBACK" % (opens, closes))
        shutil.copy2(bk, js)
        sys.exit(3)
    print("  braces : { %d } %d  (OK)" % (opens, closes))

    print("")
    print("=" * 60)
    print("DONE - exportMemoPDF redirige vers /api/memos/{id}/pdf")
    print("=" * 60)
    print("Prochaines etapes :")
    print("  1) Rafraichir le navigateur avec Ctrl+F5 (cache buster)")
    print("  2) Aller dans la liste des IC Memos")
    print("  3) Cliquer 'Export PDF' sur le memo #51 (ou un autre)")
    print("  4) Le PDF telecharge doit etre celui de la route serveur :")
    print("     - bandeau cover bleu pale (v4)")
    print("     - palette teal pastel (v3)")
    print("     - 4 bugs B1-B4 corriges (v2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
