# -*- coding: utf-8 -*-
"""[SHOW_RESIDUAL_WHERE_TICKER] montre les 3 requetes residuelles ticker = ? autour des lignes 495-530."""
from pathlib import Path
AGENT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")
txt = AGENT.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()
print("Lignes 490..540 :")
print("=" * 72)
for i in range(490, min(540, len(lines))):
    flag = " >>>" if 'WHERE ticker = ?' in lines[i-1] else "    "
    print(f"{flag} L{i:4d}: {lines[i-1]}")
print("=" * 72)
