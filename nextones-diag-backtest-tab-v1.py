# -*- coding: utf-8 -*-
"""
DIAG : localiser l'onglet Backtest dans index.html
- Section/div parent qui contient le backtest
- Coordonnees exactes pour inserer une nouvelle card AU-DESSUS du backtest
- Ancre stable (id, class) pour patch idempotent
"""
import os
import re

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(BASE, "index.html")


def header(t):
    print("=" * 78)
    print(t)
    print("=" * 78)


with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()

print("Total lines :", len(lines))

# 1. Toutes les occurrences "backtest"
header("Occurrences 'backtest' (id, class, comment) dans index.html")
hits = []
for i, ln in enumerate(lines, start=1):
    if re.search(r"backtest", ln, re.IGNORECASE):
        hits.append((i, ln.rstrip("\n")))

print()
print("Total hits :", len(hits))
print()
for ln, txt in hits[:40]:
    print("  L{:5d} | {}".format(ln, txt.strip()[:160]))

# 2. Trouver la section parent (cherche section/div id contenant 'backtest')
header("Section parente avec id contenant 'backtest'")
parent_candidates = []
for i, ln in enumerate(lines, start=1):
    m = re.search(r'<(section|div)[^>]*\bid=[\"\']([^\"\']*backtest[^\"\']*)[\"\']', ln, re.IGNORECASE)
    if m:
        parent_candidates.append((i, m.group(1), m.group(2), ln.rstrip("\n")))

for ln, tag, eid, txt in parent_candidates:
    print("  L{:5d} | <{} id='{}'> | {}".format(ln, tag, eid, txt.strip()[:140]))

# 3. Tab navigation (header / nav)
header("Tab nav : data-tab / aria-controls / role='tab'")
nav_hits = []
for i, ln in enumerate(lines, start=1):
    if re.search(r"data-tab|role=[\"']tab[\"']|aria-controls", ln, re.IGNORECASE):
        nav_hits.append((i, ln.rstrip("\n")))
for ln, txt in nav_hits[:30]:
    print("  L{:5d} | {}".format(ln, txt.strip()[:160]))

# 4. Dump bloc autour du premier hit "backtest" (contexte 40 lignes)
header("Contexte premier hit backtest (30 lignes autour)")
if hits:
    first_ln = hits[0][0]
    s = max(1, first_ln - 5)
    e = min(len(lines), first_ln + 30)
    for i in range(s, e + 1):
        print("  L{:5d} | {}".format(i, lines[i - 1].rstrip("\n")))

# 5. Recherche "Backtest" Tab button
header("Backtest tab button (likely in nav)")
for i, ln in enumerate(lines, start=1):
    if re.search(r'>(\s*)Backtest(\s*)<', ln) or re.search(r'>[^<]*Backtest[^<]*<', ln):
        print("  L{:5d} | {}".format(i, ln.strip()[:160]))

print()
print("=" * 78)
print("DIAG DONE")
print("=" * 78)
