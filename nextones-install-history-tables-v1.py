# -*- coding: utf-8 -*-
# nextones-install-history-tables-v1.py
# ETAPE 2.1bis : tables _history pour diff J-1 / J-7
#
# Cree :
#   - factor_quality_history  : snapshot factor_quality_context par cycle
#   - pplx_geo_history        : snapshot pplx_geo_context par cycle
#   - crypto_context_history  : snapshot crypto_context par cycle (bonus, meme cout)
#
# Pose un hook [HISTORY_SNAPSHOT_V1] dans api_server.py execute_cycle
# qui :
#   1. Lit les tables snapshot (factor_quality_context, pplx_geo_context, crypto_context)
#   2. INSERT dans la table _history correspondante avec cycle_id + payload JSON
#   3. DELETE WHERE created_at < date('now','-90 days')  -> purge auto
#
# Idempotent : detecte marker [HISTORY_SNAPSHOT_V1] et skippe.
# Validation : ast.parse + py_compile avant ecriture.

import os
import sys
import sqlite3
import ast
import py_compile
import shutil
import datetime as dt
import re

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
API_SERVER = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
MARKER = "[HISTORY_SNAPSHOT_V1]"

# ---------------------------------------------------------------------------
# 1) MIGRATION SQL
# ---------------------------------------------------------------------------

MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS factor_quality_history (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id      TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_fqh_cycle ON factor_quality_history(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_fqh_date  ON factor_quality_history(snapshot_date)",

    """
    CREATE TABLE IF NOT EXISTS pplx_geo_history (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id      TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pgh_cycle ON pplx_geo_history(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_pgh_date  ON pplx_geo_history(snapshot_date)",

    """
    CREATE TABLE IF NOT EXISTS crypto_context_history (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle_id      TEXT NOT NULL,
        snapshot_date TEXT NOT NULL,
        payload_json  TEXT NOT NULL,
        created_at    TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_cch_cycle ON crypto_context_history(cycle_id)",
    "CREATE INDEX IF NOT EXISTS idx_cch_date  ON crypto_context_history(snapshot_date)",
]


def run_migrations():
    print("[migration] Connecting to", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    for stmt in MIGRATIONS:
        cur.execute(stmt)
    conn.commit()

    # Verif
    for tbl in ("factor_quality_history", "pplx_geo_history", "crypto_context_history"):
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,),
        )
        row = cur.fetchone()
        print(f"[migration] {tbl} : {'OK' if row else 'MISSING'}")
    conn.close()


# ---------------------------------------------------------------------------
# 2) HOOK execute_cycle
# ---------------------------------------------------------------------------

HOOK_CODE = '''
        # ===== [HISTORY_SNAPSHOT_V1] snapshot cycle vers tables _history =====
        try:
            import json as _json_hsv1
            import sqlite3 as _sql_hsv1
            _conn_hsv1 = _sql_hsv1.connect(DB_PATH)
            _conn_hsv1.execute("PRAGMA journal_mode=WAL")
            _cur_hsv1 = _conn_hsv1.cursor()
            _snap_date_hsv1 = cycle_id[:8] if cycle_id and len(cycle_id) >= 8 else None
            if _snap_date_hsv1:
                _snap_date_hsv1 = f"{_snap_date_hsv1[:4]}-{_snap_date_hsv1[4:6]}-{_snap_date_hsv1[6:8]}"
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
                        (cycle_id, _snap_date_hsv1, _json_hsv1.dumps(_payload_hsv1, default=str)),
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
            print(f"[HISTORY_SNAPSHOT_V1] snapshot done for cycle_id={cycle_id}")
        except Exception as _e_outer_hsv1:
            print(f"[HISTORY_SNAPSHOT_V1] outer error: {_e_outer_hsv1}")
        # ===== /[HISTORY_SNAPSHOT_V1] =====
'''


def patch_api_server():
    print("[patch] Reading", API_SERVER)
    with open(API_SERVER, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if MARKER in src:
        print("[patch] Marker already present -> skip")
        return True

    # Cible : juste avant le return final de execute_cycle, on insere le hook.
    # On cherche le marker [EXECUTE_CYCLE_TRACE_V1] (deja pose) qui est dans le except.
    # Le hook doit etre dans le TRY, apres tout le travail du cycle, idealement juste avant
    # le return de la fonction execute_cycle.
    #
    # Strategie : on cherche la def execute_cycle, puis le premier "return" au niveau du try
    # principal qui suit. Plus simple : on cherche le pattern de fin de execute_cycle
    # avant le bloc except qui contient [EXECUTE_CYCLE_TRACE_V1].

    # On va chercher "return {" suivi d'un dict contenant typiquement "cycle_id" dans
    # execute_cycle. Approche robuste : on localise la fonction par sa signature.

    func_match = re.search(
        r"(async\s+def\s+execute_cycle\s*\([^)]*\)\s*:|def\s+execute_cycle\s*\([^)]*\)\s*:)",
        src,
    )
    if not func_match:
        print("[patch] ERROR: execute_cycle function not found")
        return False

    func_start = func_match.end()
    # On scanne jusqu'au prochain "except" au niveau matching de la fonction.
    # Pour rester simple : on cherche dans la fenetre [func_start, func_start+50000]
    # le premier "return" qui est suivi d'un dict mentionnant "cycle_id" ou "status".

    window = src[func_start: func_start + 80000]

    # Cherche tous les "return ..." dans la fonction. On veut le premier qui est
    # apres le travail du cycle (donc PAS un return precoce de garde).
    # Heuristique : on prend le DERNIER return avant le bloc "except" qui contient
    # [EXECUTE_CYCLE_TRACE_V1].

    trace_marker_pos = window.find("[EXECUTE_CYCLE_TRACE_V1]")
    if trace_marker_pos < 0:
        print("[patch] WARN: [EXECUTE_CYCLE_TRACE_V1] not found, fallback to first return")
        scan_end = len(window)
    else:
        scan_end = trace_marker_pos

    # Trouve le dernier "return" avant scan_end
    last_return = None
    for m in re.finditer(r"^(\s+)return\s", window[:scan_end], flags=re.MULTILINE):
        last_return = m

    if not last_return:
        print("[patch] ERROR: no return found inside execute_cycle before except")
        return False

    indent = last_return.group(1)
    abs_return_pos = func_start + last_return.start()

    # On adapte l'indentation du HOOK_CODE pour matcher
    # Le HOOK_CODE est ecrit avec 8 espaces (corps d'un try). On va le re-indenter.
    hook_indented = "\n".join(
        (indent + line[8:] if line.startswith("        ") else (indent + line if line.strip() else line))
        for line in HOOK_CODE.strip("\n").split("\n")
    )

    new_src = src[:abs_return_pos] + hook_indented + "\n" + src[abs_return_pos:]

    # Validation
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"[patch] ERROR ast.parse: {e}")
        # Dump pour debug
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

    # Write UTF-8 sans BOM
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

    return True


# ---------------------------------------------------------------------------
# 3) MAIN
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("ETAPE 2.1bis : install history tables + hook")
    print("=" * 60)
    run_migrations()
    print()
    ok = patch_api_server()
    print()
    print("=" * 60)
    print("RESULT:", "SUCCESS" if ok else "FAILED")
    print("=" * 60)
    sys.exit(0 if ok else 1)
