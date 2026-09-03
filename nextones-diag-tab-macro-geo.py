# -*- coding: utf-8 -*-
"""Repère la structure tab-macro + geoSection pour préparer insertion panel PPLX"""
import re
from pathlib import Path

# Trouve index.html
candidates = [
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\static\index.html",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app\index.html",
    r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\frontend\index.html",
]
target = None
for c in candidates:
    p = Path(c)
    if p.exists():
        target = p
        break

if not target:
    print("[KO] index.html introuvable, scan workspace...")
    for p in Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk").rglob("index.html"):
        print(f"  candidate: {p}")
    raise SystemExit(1)

print(f"[OK] index.html -> {target}")
src = target.read_text(encoding="utf-8-sig", errors="replace")
print(f"    {len(src):,} chars, {src.count(chr(10))} lignes")

# Section tab-macro
m = re.search(r'<section\b[^>]*\bid=["\']tab-macro["\'][^>]*>', src)
if m:
    start = m.start()
    line = src[:start].count('\n') + 1
    print(f"\n=== <section id='tab-macro'> trouve L{line} (offset {start}) ===")
    # Cherche la fermeture
    # Naivement on cherche le prochain </section> de meme niveau (approximation : 1er </section> apres)
    end = src.find('</section>', start)
    if end > 0:
        end_line = src[:end].count('\n') + 1
        print(f"    </section> L{end_line} (offset {end})")
else:
    print("[!] tab-macro introuvable")

# geoSection
for m in re.finditer(r'<div\b[^>]*\bid=["\']geoSection["\'][^>]*>', src):
    line = src[:m.start()].count('\n') + 1
    print(f"\n=== <div id='geoSection'> L{line} (offset {m.start()}) ===")
    # Cherche le </div> qui ferme (avec count)
    depth = 1
    pos = m.end()
    while depth > 0 and pos < len(src):
        next_open = src.find('<div', pos)
        next_close = src.find('</div>', pos)
        if next_close == -1:
            break
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            pos = next_close + 6
    end_line = src[:pos].count('\n') + 1
    print(f"    closing </div> L{end_line} (offset {pos})")
    # Montre les 200 premiers chars du contenu
    inner = src[m.end():pos-6][:300].strip()
    print(f"    inner preview: {inner[:200].replace(chr(10), ' | ')}")

# Cherche app.js
print("\n=== app.js ===")
for c in [target.parent / "app.js", target.parent / "static" / "app.js"]:
    if c.exists():
        s = c.read_text(encoding="utf-8-sig", errors="replace")
        print(f"  {c} : {len(s):,} chars, {s.count(chr(10))} lignes")
        # Cherche fonctions geo existantes
        for m in re.finditer(r'function\s+(\w*[Gg]eo\w*)\s*\(', s):
            print(f"    fct: {m.group(1)}")
        # Cherche fetch /api/geopolitical ou /api/pplx
        for m in re.finditer(r'fetch\(\s*["\']([^"\']*(?:geo|pplx)[^"\']*)["\']', s):
            print(f"    fetch: {m.group(1)}")
        break
