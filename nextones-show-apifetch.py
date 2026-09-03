# -*- coding: utf-8 -*-
"""[SHOW_APIFETCH_V1] montre le corps de apiFetch + bloc UI univers pour patch."""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
APPJS = ROOT / "app.js"
HTML  = ROOT / "index.html"

def find_block(txt, start_idx, max_len=2500):
    depth = 0
    started = False
    i = start_idx
    while i < len(txt) and i - start_idx < max_len * 3:
        c = txt[i]
        if c == '{':
            depth += 1; started = True
        elif c == '}':
            depth -= 1
            if started and depth == 0:
                return txt[start_idx:i+1]
        i += 1
    return txt[start_idx:start_idx+max_len]

js = APPJS.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r'function\s+apiFetch\s*\(', js)
if m:
    blk = find_block(js, m.start(), 2500)
    print("=" * 72)
    print("apiFetch() complete :")
    print("=" * 72)
    print(blk)
    print()

# Aussi : montre comment apiFetch est appele par les autres cartes
print("=" * 72)
print("Premiers 15 appels apiFetch(...) dans app.js :")
print("=" * 72)
for i, m in enumerate(re.finditer(r'apiFetch\s*\([^)]{0,200}\)', js)):
    if i >= 15: break
    line = js[js.rfind(chr(10), 0, m.start())+1:js.find(chr(10), m.end())].strip()
    print(f"  L{js[:m.start()].count(chr(10))+1}: {line[:160]}")

# Affiche le bloc UI universe dans index.html (marker)
print()
print("=" * 72)
print("Bloc UI_UNIVERSE_V2 dans index.html :")
print("=" * 72)
html = HTML.read_text(encoding="utf-8-sig", errors="replace")
m = re.search(r'\[UI_UNIVERSE_V2_BEGIN\].*?\[UI_UNIVERSE_V2_END\]', html, re.DOTALL)
if m:
    print(f"Bloc trouve : {len(m.group(0))} chars, debut ligne {html[:m.start()].count(chr(10))+1}")
    print(m.group(0)[:3000])
    print("...")
    print(m.group(0)[-500:])
else:
    print("INTROUVABLE")
