# -*- coding: utf-8 -*-
"""
Fix MicrostructureAgent RSI None v2 (agents.py L469)
====================================================

CONTEXTE :
La ligne L469 fait partie d'une concatenation implicite de f-strings dans
une parenthese ouverte L462 et fermee L473. Impossible d'inserer du Python
au milieu. On remplace UNIQUEMENT la ligne L469 par une f-string equivalente
qui formate rsi14 via une expression conditionnelle inline.

Ligne actuelle :
    f"RSI(14) at {rsi14:.1f} shows {'overbought conditions' if rsi14 and rsi14 > 65 else 'oversold conditions' if rsi14 and rsi14 < 35 else 'neutral momentum'}. "

Ligne corrigee (utilise format(...) qui peut etre conditionnel) :
    f"RSI(14) at {(f'{rsi14:.1f}' if rsi14 is not None else 'N/A')} shows {('overbought conditions' if rsi14 is not None and rsi14 > 65 else 'oversold conditions' if rsi14 is not None and rsi14 < 35 else 'neutral momentum' if rsi14 is not None else 'insufficient data')}. "

Marker [MICRO_RSI_NONE_FIX_V2].
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
AGENTS = PROD / "agents.py"

MARKER = "MICRO_RSI_NONE_FIX_V2"

OLD = (
    'f"RSI(14) at {rsi14:.1f} shows '
    "{'overbought conditions' if rsi14 and rsi14 > 65 "
    "else 'oversold conditions' if rsi14 and rsi14 < 35 "
    "else 'neutral momentum'}. \""
)

NEW = (
    'f"RSI(14) at '
    "{(f'{rsi14:.1f}' if rsi14 is not None else 'N/A')}"
    ' shows '
    "{('overbought conditions' if rsi14 is not None and rsi14 > 65 "
    "else 'oversold conditions' if rsi14 is not None and rsi14 < 35 "
    "else 'neutral momentum' if rsi14 is not None "
    "else 'insufficient data')}"
    '. "'
    f"  # [{MARKER}]"
)


def main() -> int:
    if not AGENTS.exists():
        print(f"[ERR] {AGENTS} introuvable")
        return 2

    src = AGENTS.read_text(encoding="utf-8-sig", errors="strict")

    if MARKER in src:
        print(f"[SKIP] marker {MARKER} deja present")
        return 0

    lines = src.splitlines(keepends=False)

    # Trouver la ligne cible (L469 attendu)
    target_idx = None
    for i, ln in enumerate(lines):
        if "RSI(14) at {rsi14:.1f}" in ln:
            target_idx = i
            break

    if target_idx is None:
        print("[ERR] ligne 'RSI(14) at {rsi14:.1f}' introuvable")
        return 3

    raw = lines[target_idx]
    indent = raw[: len(raw) - len(raw.lstrip())]
    stripped = raw.strip()
    print(f"[INFO] cible L{target_idx + 1}")
    print(f"       avant : {stripped[:140]}")

    # On reconstruit la nouvelle ligne avec le bon indent
    new_content = (
        'f"RSI(14) at '
        "{(f'{rsi14:.1f}' if rsi14 is not None else 'N/A')}"
        ' shows '
        "{('overbought conditions' if rsi14 is not None and rsi14 > 65 "
        "else 'oversold conditions' if rsi14 is not None and rsi14 < 35 "
        "else 'neutral momentum' if rsi14 is not None "
        "else 'insufficient data')}"
        '. "'
        f"  # [{MARKER}]"
    )
    new_line = indent + new_content

    print(f"       apres : {new_content[:140]}")

    new_lines = lines[:target_idx] + [new_line] + lines[target_idx + 1 :]
    new_src = "\n".join(new_lines) + ("\n" if src.endswith("\n") else "")

    # Backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = AGENTS.with_suffix(f".py.bak_micro_rsi_v2_{ts}")
    shutil.copy2(AGENTS, bak)
    print(f"[BACKUP] {bak.name}")

    # Ecriture
    AGENTS.write_text(new_src, encoding="utf-8", newline="\n")

    # Validation
    try:
        py_compile.compile(str(AGENTS), doraise=True)
        ast.parse(AGENTS.read_text(encoding="utf-8-sig"))
        print("[OK] agents.py compile et parse")
    except Exception as ex:
        print(f"[ERR] post-patch broken : {ex}")
        print(f"[ROLLBACK] restauration {bak.name}")
        shutil.copy2(bak, AGENTS)
        return 5

    print(f"\n[OK] marker [{MARKER}] insere ligne {target_idx + 1}")
    print("Redemarre uvicorn et re-clique Run Decision Cycle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
