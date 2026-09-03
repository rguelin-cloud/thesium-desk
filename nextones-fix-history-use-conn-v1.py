# -*- coding: utf-8 -*-
# nextones-fix-history-use-conn-v1.py
# Remplace l'ouverture de _conn_hsv1 = sqlite3.connect(DB_PATH) par la
# reutilisation de la connexion 'conn' deja ouverte dans execute_cycle.
# Plus propre (pas de 2eme connexion WAL) et corrige le bug DB_PATH undefined.

import ast
import py_compile
import shutil
import datetime as dt

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

OLD = '''            import json as _json_hsv1
            import sqlite3 as _sql_hsv1
            _conn_hsv1 = _sql_hsv1.connect(DB_PATH)
            _conn_hsv1.execute("PRAGMA journal_mode=WAL")
            _cur_hsv1 = _conn_hsv1.cursor()'''

NEW = '''            import json as _json_hsv1
            # Reuse the 'conn' opened at the top of execute_cycle (line 718)
            _conn_hsv1 = conn
            _cur_hsv1 = _conn_hsv1.cursor()'''

# Et on retire le commit + close en double a la fin (conn sera commit/close par execute_cycle)
OLD2 = '''            _conn_hsv1.commit()
            _conn_hsv1.close()
            print(f"[HISTORY_SNAPSHOT_V1] snapshot done for cycle_id={_cid_hsv1}")'''

NEW2 = '''            _conn_hsv1.commit()
            print(f"[HISTORY_SNAPSHOT_V1] snapshot done for cycle_id={_cid_hsv1}")'''


def main():
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if "_conn_hsv1 = conn" in src:
        print("[fix] Already applied -> SKIP")
        return True

    if OLD not in src:
        print("[fix] ERROR: OLD block not found (hook may have been edited)")
        return False
    if OLD2 not in src:
        print("[fix] ERROR: OLD2 block not found")
        return False

    new_src = src.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1)

    try:
        ast.parse(new_src)
        print("[fix] ast.parse OK")
    except SyntaxError as e:
        print(f"[fix] ERROR ast.parse: {e}")
        return False

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{API}.bak_hsv1_conn_{ts}"
    shutil.copy2(API, bak)
    print(f"[fix] Backup -> {bak}")

    with open(API, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)

    try:
        py_compile.compile(API, doraise=True)
        print("[fix] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"[fix] ERROR py_compile: {e}")
        shutil.copy2(bak, API)
        print("[fix] Rolled back")
        return False

    print("[fix] SUCCESS")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
