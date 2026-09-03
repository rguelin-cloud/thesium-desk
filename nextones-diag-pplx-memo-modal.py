# -*- coding: utf-8 -*-
"""
Diag rapide : repérer comment le modal pplxMemoBackdrop s'ouvre et où placer la banniere.
- fonction pplxMemoOpen ou ouvrir() dans app.js
- ID du conteneur où injecter (titre ou debut body modal)
- comment le ticker est extrait (du DOM ou parametre fonction)
"""
import os, sys, re, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
APP_JS = os.path.join(BASE, "app.js")
INDEX = os.path.join(BASE, "index.html")

with open(APP_JS, "r", encoding="utf-8-sig") as f:
    js = f.read()
with open(INDEX, "r", encoding="utf-8-sig") as f:
    html = f.read()

print("=" * 60)
print("PPLX MEMO MODAL STRUCTURE")
print("=" * 60)

print("\n[HTML structure pplxMemoBackdrop]")
# Trouver bloc complet
m = re.search(r'<div\s+id="pplxMemoBackdrop"[^>]*>(.*?)</div>\s*</div>', html, re.DOTALL)
if m:
    block = m.group(0)
    print(block[:1500])
else:
    print("Pas trouvé en 1 regex, essai ligne par ligne")
    lines = html.split("\n")
    for i, line in enumerate(lines, 1):
        if "pplxMemoBackdrop" in line or "pplx-memo-modal" in line or "pplxMemoTitle" in line:
            print(f"  L{i}: {line.strip()[:200]}")

print("\n[Fonctions JS liees memo]")
patterns = [
    r'function\s+pplxMemoOpen',
    r'function\s+pplxMemo\w+',
    r'pplxMemoOpen\s*=',
    r'pplxMemoTitle',
    r'pplx-memo-modal',
]
for p in patterns:
    for m in re.finditer(p, js):
        line_num = js[:m.start()].count("\n") + 1
        line = js.split("\n")[line_num-1].strip()
        print(f"  L{line_num} ({p}): {line[:180]}")

print("\n[Fonction pplxMemoOpen body si trouvee]")
m = re.search(r'(async\s+)?function\s+pplxMemoOpen\s*\(([^)]*)\)\s*\{', js)
if m:
    start = m.start()
    # extraire jusqu'a accolade fermante (approximation simple)
    depth = 0
    i = m.end() - 1  # sur l'accolade ouvrante
    end = i
    for j in range(i, min(len(js), i + 5000)):
        if js[j] == "{":
            depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    print(js[start:end][:2000])
else:
    print("  pplxMemoOpen non trouve (peut-etre nom different)")

print("\n[Boutons Memo IA dans la table convergence — generes par renderConvergenceCard?]")
# le bouton 'Memo IA' est injecte par un autre observer (vu sur screenshots). On cherche origin
for kw in ["Memo IA", "pplx-memo-trigger", "memoTrigger", "openMemo"]:
    for m in re.finditer(re.escape(kw), js):
        line_num = js[:m.start()].count("\n") + 1
        line = js.split("\n")[line_num-1].strip()
        print(f"  L{line_num} ({kw}): {line[:180]}")
        break  # 1 par kw suffit

print("\n[DONE]")
