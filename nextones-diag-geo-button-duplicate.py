# -*- coding: utf-8 -*-
"""
Diag: trouver TOUTES les occurrences de "Voir l'article complet" dans app.js
+ leurs contextes pour identifier le doublon (1er injection = texte brut, 2e = bouton stylise)
"""
from pathlib import Path

APP_JS = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js")
src = APP_JS.read_text(encoding="utf-8-sig")

print("=" * 90)
print(f"Recherche 'Voir l\\'article complet' dans app.js")
print(f"Taille app.js: {len(src)} chars")
print("=" * 90)

# Toutes les occurrences (texte brut)
needle = "Voir l'article complet"
occurrences = []
pos = 0
while True:
    idx = src.find(needle, pos)
    if idx == -1:
        break
    occurrences.append(idx)
    pos = idx + len(needle)

print(f"\nOccurrences trouvees: {len(occurrences)}")
print(f"Positions: {occurrences}")

# Pour chaque occurrence, afficher 200 chars avant et 100 apres
for n, pos in enumerate(occurrences, 1):
    print(f"\n{'=' * 90}")
    print(f"OCCURRENCE #{n} a position {pos}")
    print("=" * 90)
    start = max(0, pos - 250)
    end = min(len(src), pos + 150)
    context = src[start:end]
    # Numero ligne
    lineno = src[:pos].count("\n") + 1
    print(f"Ligne approximative: {lineno}")
    print(f"--- CONTEXTE ---")
    print(context)
    print(f"--- FIN ---")

print(f"\n{'=' * 90}")
print("MARQUEURS RECHERCHES")
print("=" * 90)
markers = [
    "[PPLX_GEO_BTN_PER_CARD_V1]",
    "[PPLX_GEO_DETAIL_V1]",
    "[PPLX_GEO_PANEL_MOVE_V1]",
    "pplx-risk-detail-btn",
    "openGeoRiskDetail",
    "MutationObserver",
]
for m in markers:
    cnt = src.count(m)
    print(f"  {m}: {cnt} occurrences")
