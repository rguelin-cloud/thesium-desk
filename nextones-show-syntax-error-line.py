# -*- coding: utf-8 -*-
"""[SHOW_SYNTAX_ERR_V1] affiche lignes 1135..1160 de index.html pour reperer le token '.' orphelin."""
from pathlib import Path
HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
txt = HTML.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()
print(f"Total lignes : {len(lines)}")
print(f"Affichage 1130..1170 (erreur signalee L1145) :")
print("=" * 72)
for i in range(1130, min(1180, len(lines)+1)):
    marker = " >>>" if i == 1145 else "    "
    print(f"{marker} L{i:4d}: {lines[i-1]}")
print("=" * 72)

# Cherche aussi les patterns suspects dans le bloc complet
import re
m = re.search(r'\[UI_UNIVERSE_V2_BEGIN\].*?\[UI_UNIVERSE_V2_END\]', txt, re.DOTALL)
if m:
    block = m.group(0)
    print()
    print("Patterns suspects dans le bloc UI_UNIVERSE :")
    # Patterns : .xxx orphelin, " . " standalone, "window.apiFetch.xxx" suspect
    for pat_name, pat in [
        ('window.apiFetch suivi de .', r'window\.apiFetch[^\(]'),
        ('Identifier vide ".(" ', r'\.\s*\('),
        ('Double dot', r'\.\.'),
        ('async sans function', r'async\s*[^\s(f]'),
    ]:
        for mm in re.finditer(pat, block):
            start = max(0, mm.start()-40)
            end = min(len(block), mm.end()+40)
            snippet = block[start:end].replace('\n', '\\n')
            print(f"  [{pat_name}] ...{snippet}...")
