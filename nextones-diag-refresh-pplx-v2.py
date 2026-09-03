# -*- coding: utf-8 -*-
"""Cherche refresh_* sous toutes les formes (def, async def, import, lambda, =)"""
import re
from pathlib import Path

target = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
src = target.read_text(encoding="utf-8-sig")

for fname in ["refresh_pplx_crypto", "refresh_pplx_factor", "refresh_geo", "refresh_macro", "refresh_prices"]:
    print(f"\n=== {fname} ===")
    # Toutes occurrences (def, import, assign)
    for m in re.finditer(rf'\b{fname}\b', src):
        line_no = src[:m.start()].count('\n') + 1
        # contexte ligne complète
        line_start = src.rfind('\n', 0, m.start()) + 1
        line_end = src.find('\n', m.end())
        line = src[line_start:line_end]
        print(f"  L{line_no}: {line}")
