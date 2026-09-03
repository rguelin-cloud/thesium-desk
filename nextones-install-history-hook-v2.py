# -*- coding: utf-8 -*-
# nextones-install-history-hook-v2.py
# ETAPE 2.1bis (fix) : pose UNIQUEMENT le hook [HISTORY_SNAPSHOT_V1]
# (les 3 tables _history sont deja creees par v1).
#
# Fix v2 :
#   - Detection robuste de def execute_cycle (parentheses imbriquees,
#     ex: Depends(require_manager))
#   - Validation ast + py_compile
#   - Backup + rollback auto
#   - Idempotent (skip si marker present)

import os
import sys
import ast
import py_compile
import shutil
import datetime as dt
import re

API_SERVER = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[HISTORY_SNAPSHOT_V1]"

HOOK_CODE = '''
        # ===== [HISTORY_SNAPSHOT_V1] snapshot cycle vers tables _history =====
        try:
            import json as _json_hsv1
            import sqlite3 as _sql_hsv1
            _conn_hsv1 = _sql_hsv1.connect(DB_PATH)
            _conn_hsv1.execute("PRAGMA journal_mode=WAL")
            _cur_hsv1 = _conn_hsv1.cursor()
            _cid_hsv1 = locals().get("cycle_id") or locals().get("cid") or locals().get("new_cycle_id")
            _snap_date_hsv1 = None
            if _cid_hsv1 and isinstance(_cid_hsv1, str) and len(_cid_hsv1) >= 8:
                _snap_date_hsv1 = f"{_cid_hsv1[0:4]}-{_cid_hsv1[4:6]}-{_cid_hsv1[6:8]}"
            for _src_hsv1, _dst_hsv1 in (
                ("factor_quality_context", "factor_quality_history"),
                ("pplx_geo_context",       "pplx_geo_history"),
                ("crypto_context",         "crypto_context_history"),
            ):
                try:
                    _cur_hsv1.execute(f"SELECT * FROM {_src_hsv1} LIMIT 1")
                    _cols_hsv1 = [d[0] for d in _cur_hsv1.description]
                    _row_hsv1 = _cur_hsv1.fetchone()
                    if _row_hsv1 is None:
                        continue
                    _payload_hsv1 = {_cols_hsv1[i]: _row_hsv1[i] for i in range(len(_cols_hsv1))}
                    _cur_hsv1.execute(
                        f"INSERT INTO {_dst_hsv1} (cycle_id, snapshot_date, payload_json) VALUES (?, ?, ?)",
                        (_cid_hsv1, _snap_date_hsv1, _json_hsv1.dumps(_payload_hsv1, default=str)),
                    )
                except Exception as _e_hsv1:
                    print(f"[HISTORY_SNAPSHOT_V1] skip {_src_hsv1}: {_e_hsv1}")
                try:
                    _cur_hsv1.execute(
                        f"DELETE FROM {_dst_hsv1} WHERE created_at < datetime('now','-90 days')"
                    )
                except Exception:
                    pass
            _conn_hsv1.commit()
            _conn_hsv1.close()
            print(f"[HISTORY_SNAPSHOT_V1] snapshot done for cycle_id={_cid_hsv1}")
        except Exception as _e_outer_hsv1:
            print(f"[HISTORY_SNAPSHOT_V1] outer error: {_e_outer_hsv1}")
        # ===== /[HISTORY_SNAPSHOT_V1] =====
'''


def find_func_body_balanced(src, fname):
    """
    Localise la def fname dans src en gerant les parentheses imbriquees.
    Retourne (start_def_line_offset, end_signature_offset, indent_str).
    """
    # Cherche '(async )?def fname(' avec n'importe quoi entre ()
    pattern = re.compile(
        r"^(?P<indent>\s*)(async\s+)?def\s+" + re.escape(fname) + r"\s*\(",
        re.MULTILINE,
    )
    m = pattern.search(src)
    if not m:
        return None

    start_def = m.start()
    open_paren = m.end() - 1  # position du '('
    # On scanne pour trouver le ')' equilibre
    depth = 0
    i = open_paren
    while i < len(src):
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                # Apres ')' on cherche le ':' qui termine la signature
                j = i + 1
                while j < len(src) and src[j] != ":":
                    j += 1
                if j >= len(src):
                    return None
                return (start_def, j + 1, m.group("indent"))
        i += 1
    return None


def patch():
    print(f"[patch] Reading {API_SERVER}")
    with open(API_SERVER, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[patch] Marker already present -> SKIP (idempotent)")
        return True

    info = find_func_body_balanced(src, "execute_cycle")
    if info is None:
        print("[patch] ERROR: execute_cycle not found via balanced scanner")
        return False
    func_start, sig_end, func_indent = info
    line_no = src[:func_start].count("\n") + 1
    print(f"[patch] Found def execute_cycle at line {line_no}, indent='{func_indent}'")

    # On cherche le dernier 'return' AVANT le marker [EXECUTE_CYCLE_TRACE_V1]
    # (qui est dans le except, donc apres le bloc try principal).
    trace_pos = src.find("[EXECUTE_CYCLE_TRACE_V1]", sig_end)
    if trace_pos < 0:
        print("[patch] WARN: trace marker not found, using end of file as scan limit")
        scan_end = len(src)
    else:
        scan_end = trace_pos
        print(f"[patch] Trace marker found at line {src[:trace_pos].count(chr(10))+1}")

    # Dernier return entre sig_end et scan_end
    last_return = None
    for m in re.finditer(r"^(\s+)return\b", src[sig_end:scan_end], flags=re.MULTILINE):
        last_return = m

    if not last_return:
        print("[patch] ERROR: no return found between def signature and trace marker")
        return False

    indent = last_return.group(1)
    abs_return_pos = sig_end + last_return.start()
    ret_line = src[:abs_return_pos].count("\n") + 1
    print(f"[patch] Last return found at line {ret_line}, indent={len(indent)} spaces")

    # Re-indente HOOK_CODE : le hook est ecrit avec 8 espaces de base, on remplace par 'indent'
    hook_lines = HOOK_CODE.strip("\n").split("\n")
    reindented = []
    for line in hook_lines:
        if line.startswith("        "):
            reindented.append(indent + line[8:])
        elif line.strip() == "":
            reindented.append("")
        else:
            reindented.append(indent + line.lstrip())
    hook_indented = "\n".join(reindented)

    new_src = src[:abs_return_pos] + hook_indented + "\n" + src[abs_return_pos:]

    # Validation
    try:
        ast.parse(new_src)
        print("[patch] ast.parse OK")
    except SyntaxError as e:
        print(f"[patch] ERROR ast.parse: {e}")
        snippet_start = max(0, abs_return_pos - 200)
        snippet_end = min(len(new_src), abs_return_pos + len(hook_indented) + 200)
        print("---- snippet around insertion ----")
        print(new_src[snippet_start:snippet_end])
        print("----------------------------------")
        return False

    # Backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{API_SERVER}.bak_history_{ts}"
    shutil.copy2(API_SERVER, bak)
    print(f"[patch] Backup -> {bak}")

    # Ecriture UTF-8 sans BOM
    with open(API_SERVER, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print(f"[patch] Wrote {API_SERVER}")

    # py_compile final
    try:
        py_compile.compile(API_SERVER, doraise=True)
        print("[patch] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[patch] ERROR py_compile: {e}")
        shutil.copy2(bak, API_SERVER)
        print("[patch] Rolled back from backup")
        return False

    print(f"[patch] Hook inserted at line {ret_line}")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("ETAPE 2.1bis fix v2 : install hook HISTORY_SNAPSHOT_V1")
    print("=" * 60)
    ok = patch()
    print()
    print("=" * 60)
    print("RESULT:", "SUCCESS" if ok else "FAILED")
    print("=" * 60)
    sys.exit(0 if ok else 1)
