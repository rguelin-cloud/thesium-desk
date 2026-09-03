# -*- coding: utf-8 -*-
"""
Patch chirurgical du handler execute_cycle (L716 api_server.py) :
- AVANT  : except Exception as e: raise HTTPException(500, detail=str(e))
- APRES  : log traceback complet dans console uvicorn + detail enrichi
           (type + message + dump premier frame du traceback dans la reponse)

Idempotent (marker [EXECUTE_CYCLE_TRACE_V1]).
Backup .bak_trace_YYYYMMDD_HHMMSS.

Lancement :
    py -3.13 .\nextones-patch-execute-cycle-trace.py
"""
from __future__ import annotations

import sys
import ast
import shutil
import datetime as dt
import py_compile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROD = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
API = PROD / "api_server.py"

MARKER = "[EXECUTE_CYCLE_TRACE_V1]"


def main() -> int:
    if not API.exists():
        print(f"[ERR] {API} introuvable")
        return 2

    src = API.read_text(encoding="utf-8-sig", errors="strict")
    lines = src.splitlines(keepends=False)

    if MARKER in src:
        print(f"[SKIP] marker {MARKER} deja present, rien a faire")
        return 0

    # Localiser def execute_cycle
    tree = ast.parse(src)
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "execute_cycle":
            target = node
            break
    if target is None:
        print("[ERR] execute_cycle introuvable")
        return 3

    s, e = target.lineno, target.end_lineno or target.lineno
    print(f"[INFO] execute_cycle @ L{s}-L{e}")

    # Cherche la ligne "raise HTTPException(status_code=500, detail=str(e))"
    target_line_idx = None
    for i in range(s - 1, e):
        if "raise HTTPException" in lines[i] and "500" in lines[i] and "str(e)" in lines[i]:
            target_line_idx = i
            break
    if target_line_idx is None:
        print("[ERR] ligne 'raise HTTPException(500, str(e))' introuvable dans execute_cycle")
        return 4

    # Detection indentation
    raw = lines[target_line_idx]
    indent = raw[: len(raw) - len(raw.lstrip())]
    print(f"[INFO] cible L{target_line_idx + 1} indent={len(indent)} : {raw.strip()[:100]}")

    # Remplacement
    new_block = [
        f"{indent}# === [EXECUTE_CYCLE_TRACE_V1] BEGIN ===",
        f"{indent}import traceback as _tb_ec",
        f'{indent}_tb_str = _tb_ec.format_exc()',
        f'{indent}print("[execute_cycle] EXCEPTION ===")',
        f'{indent}print(_tb_str)',
        f'{indent}print("=== /[execute_cycle] EXCEPTION")',
        f'{indent}_detail = {{',
        f'{indent}    "type": type(e).__name__,',
        f'{indent}    "msg": str(e),',
        f'{indent}    "traceback_tail": _tb_str.splitlines()[-12:],',
        f"{indent}}}",
        f"{indent}raise HTTPException(status_code=500, detail=_detail)",
        f"{indent}# === [EXECUTE_CYCLE_TRACE_V1] END ===",
    ]

    new_lines = lines[:target_line_idx] + new_block + lines[target_line_idx + 1 :]
    new_src = "\n".join(new_lines) + ("\n" if src.endswith("\n") else "")

    # Backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = API.with_suffix(f".py.bak_trace_{ts}")
    shutil.copy2(API, bak)
    print(f"[BACKUP] {bak.name}")

    # Ecriture
    API.write_text(new_src, encoding="utf-8", newline="\n")

    # Validation
    try:
        py_compile.compile(str(API), doraise=True)
        ast.parse(API.read_text(encoding="utf-8-sig"))
        print("[OK] api_server.py compile et parse")
    except Exception as ex:
        print(f"[ERR] post-patch broken : {ex}")
        print(f"[ROLLBACK] restauration {bak.name}")
        shutil.copy2(bak, API)
        return 5

    print(f"[OK] marker {MARKER} insere ligne {target_line_idx + 1}")
    print("\nProchaine etape : redemarrer uvicorn puis re-cliquer Run Decision Cycle.")
    print("La console uvicorn affichera la stack trace complete.")
    print("Le toast UI montrera type + msg + 12 dernieres lignes de traceback.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
