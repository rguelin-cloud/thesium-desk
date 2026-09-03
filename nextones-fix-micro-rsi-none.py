# -*- coding: utf-8 -*-
"""
Fix MicrostructureAgent RSI None (agents.py L469)
================================================

BUG :
    f"RSI(14) at {rsi14:.1f} shows {'overbought' if rsi14 and rsi14 > 65 else 'oversold' if rsi14 and rsi14 < 35 else 'neutral momentum'}. "

Quand rsi14 is None, {rsi14:.1f} plante avant que les `if rsi14` ne s'evaluent.

FIX :
    Construire le string par etapes avec _rsi_str et _rsi_kind avant la f-string.

Marker idempotent [MICRO_RSI_NONE_FIX_V1].
Backup .bak_micro_rsi_YYYYMMDD_HHMMSS.

Lancement :
    py -3.13 .\nextones-fix-micro-rsi-none.py
"""
from __future__ import annotations

import sys
import ast
import shutil
import datetime as dt
import py_compile
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROD = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
AGENTS = PROD / "agents.py"

MARKER = "[MICRO_RSI_NONE_FIX_V1]"


def main() -> int:
    if not AGENTS.exists():
        print(f"[ERR] {AGENTS} introuvable")
        return 2

    src = AGENTS.read_text(encoding="utf-8-sig", errors="strict")

    if MARKER in src:
        print(f"[SKIP] marker {MARKER} deja present")
        return 0

    lines = src.splitlines(keepends=False)

    # Cherche la ligne 469 (1-indexed) qui contient "RSI(14) at {rsi14:.1f}"
    target_idx = None
    for i, ln in enumerate(lines):
        if "RSI(14) at {rsi14:.1f}" in ln:
            target_idx = i
            print(f"[INFO] cible trouvee L{i+1}")
            print(f"       contenu : {ln.strip()[:140]}")
            break

    if target_idx is None:
        print("[ERR] ligne 'RSI(14) at {rsi14:.1f}' introuvable")
        return 3

    raw = lines[target_idx]
    indent = raw[: len(raw) - len(raw.lstrip())]

    # Detection contexte : on cherche le bloc complet qui contient cette f-string
    # En general la ligne ressemble a :
    #   "RSI(14) at {rsi14:.1f} shows {... if rsi14 ...}. "
    # On va remplacer DEUX morceaux :
    #   {rsi14:.1f}  ->  {_rsi_str}
    # et ajouter avant ce return/append, un guard sur _rsi_str

    # Remplacement local sur la ligne
    new_line = raw.replace("{rsi14:.1f}", "{_rsi_str}")
    # On remplace aussi le contenu conditionnel "shows {'overbought' if rsi14 ...}"
    # par une variable pre-calculee {_rsi_kind} pour eviter tout autre piege.
    # Pattern souple :
    cond_pat = re.compile(
        r"shows \{'overbought conditions' if rsi14 and rsi14 > 65 else 'oversold conditions' if rsi14 and rsi14 < 35 else 'neutral momentum'\}"
    )
    if cond_pat.search(new_line):
        new_line = cond_pat.sub("shows {_rsi_kind}", new_line)
    else:
        # Pattern de secours plus tolerant
        cond_pat2 = re.compile(
            r"shows \{[^{}]*?overbought[^{}]*?oversold[^{}]*?neutral[^{}]*?\}"
        )
        if cond_pat2.search(new_line):
            new_line = cond_pat2.sub("shows {_rsi_kind}", new_line)
            print("[INFO] pattern conditionnel matche via fallback regex")
        else:
            print("[WARN] pattern conditionnel non matche, on garde le conditionnel original")

    # Bloc guard a inserer juste avant la ligne cible
    guard_block = [
        f"{indent}# === {MARKER} BEGIN ===",
        f'{indent}if rsi14 is None:',
        f'{indent}    _rsi_str = "N/A"',
        f'{indent}    _rsi_kind = "insufficient data"',
        f"{indent}else:",
        f'{indent}    _rsi_str = f"{{rsi14:.1f}}"',
        f"{indent}    if rsi14 > 65:",
        f'{indent}        _rsi_kind = "overbought conditions"',
        f"{indent}    elif rsi14 < 35:",
        f'{indent}        _rsi_kind = "oversold conditions"',
        f"{indent}    else:",
        f'{indent}        _rsi_kind = "neutral momentum"',
        f"{indent}# === {MARKER} END ===",
    ]

    new_lines = lines[:target_idx] + guard_block + [new_line] + lines[target_idx + 1 :]
    new_src = "\n".join(new_lines) + ("\n" if src.endswith("\n") else "")

    # Backup
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = AGENTS.with_suffix(f".py.bak_micro_rsi_{ts}")
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

    print(f"\n[OK] marker {MARKER} insere.")
    print("Redemarre uvicorn puis re-clique Run Decision Cycle.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
