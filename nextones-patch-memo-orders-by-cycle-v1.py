# -*- coding: utf-8 -*-
# [PATCH_MEMO_ORDERS_BY_CYCLE_V1]
# Filtre le SELECT "Proposed Changes & Executions" du memo par cycle courant.
# Recupere le dernier cycle_id depuis regime_log et borne la requete dessus.
# Idempotent (marker en commentaire). ASCII pur, Windows-safe.

import io
import os
import re
import sys
import ast
import py_compile
import time
import shutil

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "memo_generator.py")
MARKER = "[PATCH_MEMO_ORDERS_BY_CYCLE_V1]"


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def write_text(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    if not os.path.exists(TARGET):
        print("MISSING:", TARGET); sys.exit(2)

    src = read_text(TARGET)
    if MARKER in src:
        print("[SKIP] marker already present")
        return

    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = TARGET + ".bak." + ts
    shutil.copy2(TARGET, bak)
    print("[BACKUP]", bak)

    # Cible L587 :
    old = (
        '    proposed_changes_rows = conn.execute(\n'
        '        """SELECT o.id, o.side, o.quantity, o.status, i.ticker\n'
        '           FROM orders o JOIN instruments i ON i.id = o.instrument_id\n'
        '           ORDER BY o.created_at DESC LIMIT 10"""\n'
        '    ).fetchall()\n'
    )

    new = (
        '    # [PATCH_MEMO_ORDERS_BY_CYCLE_V1] filtre proposed_changes par cycle courant\n'
        '    _cur_cycle_row = conn.execute(\n'
        '        "SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1"\n'
        '    ).fetchone()\n'
        '    _cur_cycle_id = _cur_cycle_row[0] if _cur_cycle_row else None\n'
        '    if _cur_cycle_id:\n'
        '        proposed_changes_rows = conn.execute(\n'
        '            """SELECT o.id, o.side, o.quantity, o.status, i.ticker\n'
        '               FROM orders o JOIN instruments i ON i.id = o.instrument_id\n'
        '               WHERE o.cycle_id = ?\n'
        '               ORDER BY o.created_at DESC LIMIT 50""",\n'
        '            (_cur_cycle_id,)\n'
        '        ).fetchall()\n'
        '    else:\n'
        '        proposed_changes_rows = conn.execute(\n'
        '            """SELECT o.id, o.side, o.quantity, o.status, i.ticker\n'
        '               FROM orders o JOIN instruments i ON i.id = o.instrument_id\n'
        '               ORDER BY o.created_at DESC LIMIT 10"""\n'
        '        ).fetchall()\n'
    )

    if old not in src:
        print("[FAIL] pattern proposed_changes_rows introuvable")
        # Dump pour debug
        idx = src.find("proposed_changes_rows = conn.execute")
        if idx >= 0:
            print("---- dump 800 chars ----")
            print(src[idx:idx + 800])
        sys.exit(3)

    src = src.replace(old, new, 1)
    print("[OK] proposed_changes filtre par cycle courant")

    # Validation
    try:
        ast.parse(src)
    except SyntaxError as e:
        print("[FAIL] AST parse :", e)
        sys.exit(4)
    print("[OK] AST parse")

    write_text(TARGET, src)
    py_compile.compile(TARGET, doraise=True)
    print("[OK] py_compile final")
    print("[DONE]", MARKER)


if __name__ == "__main__":
    main()
