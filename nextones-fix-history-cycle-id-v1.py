# -*- coding: utf-8 -*-
# nextones-fix-history-cycle-id-v1.py
# Corrige la recuperation de cycle_id dans le hook [HISTORY_SNAPSHOT_V1] :
#   - 1er essai : result["cycle_id"] si dispo
#   - 2eme essai : SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1
# Plus robuste que locals().get() qui retournait None.

import ast
import py_compile
import shutil
import datetime as dt

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

OLD = '            _cid_hsv1 = locals().get("cycle_id") or locals().get("cid") or locals().get("new_cycle_id")'

NEW = '''            _cid_hsv1 = None
            try:
                if isinstance(result, dict):
                    _cid_hsv1 = result.get("cycle_id") or (result.get("cycle") or {}).get("cycle_id") if isinstance(result.get("cycle"), dict) else result.get("cycle_id")
            except Exception:
                _cid_hsv1 = None
            if not _cid_hsv1:
                try:
                    _r_hsv1 = _cur_hsv1.execute("SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
                    if _r_hsv1:
                        _cid_hsv1 = _r_hsv1[0]
                except Exception:
                    pass'''


def main():
    with open(API, "r", encoding="utf-8-sig") as f:
        src = f.read()

    if OLD not in src:
        print("[fix] OLD line not found, marker may have been edited or fix already applied")
        # Check if NEW already there
        if "if isinstance(result, dict):" in src and "regime_log ORDER BY id DESC" in src:
            print("[fix] Fix already applied -> SKIP")
            return True
        print("[fix] ERROR: cannot locate target line")
        return False

    new_src = src.replace(OLD, NEW, 1)

    try:
        ast.parse(new_src)
        print("[fix] ast.parse OK")
    except SyntaxError as e:
        print(f"[fix] ERROR ast.parse: {e}")
        return False

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{API}.bak_hsv1_cid_{ts}"
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
