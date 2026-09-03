# -*- coding: utf-8 -*-
"""Montre la définition de refresh_pplx_crypto et refresh_pplx_factor"""
import re
from pathlib import Path

target = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
src = target.read_text(encoding="utf-8-sig")

for fname in ["refresh_pplx_crypto", "refresh_pplx_factor", "refresh_geo"]:
    print(f"\n=== def {fname} ===")
    m = re.search(rf'(?m)^def\s+{fname}\s*\([^)]*\)\s*:', src)
    if not m:
        print("  NOT FOUND")
        continue
    start = m.start()
    # Find next def at module level (line starting with 'def ' or 'class ' or '@')
    chunk = src[start:start+2000]
    next_def = re.search(r'\n(def\s+|class\s+|@app\.|@router\.|scheduler\.)', chunk[10:])
    end = (start + 10 + next_def.start()) if next_def else (start + 2000)
    block = src[start:end]
    line0 = src[:start].count('\n') + 1
    for i, line in enumerate(block.splitlines()):
        print(f"  L{line0+i:5d} | {line}")
