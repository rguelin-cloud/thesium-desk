# [DIAG_OLD_GEO_PANEL_V1]
# Identifie l'ancien panel "RISQUE GEOPOLITIQUE" (GDELT + USGS) dans index.html
# pour preparer son masquage propre.
#
# Cherche :
#   - Titre "RISQUE GEOPOLITIQUE"
#   - Sous-titres "RISQUE CHOKEPOINTS", "NIVEAU DE MENACE", "ALERTES GEOPOLITIQUES", "HISTORIQUE 12 MOIS"
#   - Mention "GDELT Project, USGS"
#   - Conteneur parent (section, card, div id=...)

from pathlib import Path
import re

HTML = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\index.html")
raw = HTML.read_text(encoding="utf-8-sig", errors="replace")
print(f"Taille : {len(raw)} chars\n")

# 1) Cherche les ancres textuelles uniques
markers = [
    "RISQUE GEOPOLITIQUE",
    "RISQUE GÉOPOLITIQUE",
    "RISQUE CHOKEPOINTS",
    "NIVEAU DE MENACE",
    "ALERTES GEOPOLITIQUES",
    "ALERTES GÉOPOLITIQUES",
    "HISTORIQUE 12 MOIS",
    "GDELT Project",
    "USGS Earthquake",
    "geoScoreHistoryChart",
]
print("=" * 72)
print("[1] Ancres textuelles trouvees")
print("=" * 72)
positions = {}
for m in markers:
    n = raw.count(m)
    if n > 0:
        pos = raw.find(m)
        positions[m] = pos
        print(f"  [OK]   pos={pos:>6} count={n} | {m}")
    else:
        print(f"  [MISS] {m}")

# 2) Cherche le conteneur parent (carte) qui englobe tout cela
print("\n" + "=" * 72)
print("[2] Conteneur parent (section/card) le plus probable")
print("=" * 72)

# On prend la position la plus en amont parmi celles trouvees
if not positions:
    print("  Aucun marker trouve, abort")
else:
    pos_min = min(positions.values())
    pos_max = max(positions.values())
    print(f"  Range textuel : [{pos_min}, {pos_max}]")

    # Cherche le dernier <section ...> ou <div class="card..."> avant pos_min
    before = raw[:pos_min]
    # Patterns possibles : <section, <div class="card", <div id="..." class
    # On cherche les balises ouvrantes
    candidates = []
    for m in re.finditer(r'<(section|div)\b[^>]*>', before):
        candidates.append((m.start(), m.group(0)))
    # On garde les 5 dernieres ouvertures
    print("\n  5 dernieres balises ouvrantes avant la zone :")
    for pos, tag in candidates[-5:]:
        print(f"    pos={pos:>6}  {tag[:140]}")

    # 3) Cherche le marker [PPLX_GEO_PANEL_HTML_V1] BEGIN qui doit etre apres ce panel
    m = re.search(r"\[PPLX_GEO_PANEL_HTML_V1\] BEGIN", raw)
    if m:
        print(f"\n  [PPLX_GEO_PANEL_HTML_V1] BEGIN est a pos={m.start()}")
        # L'ancien panel finit avant ce marker
        # Cherche la </section> la plus proche AVANT ce marker
        before_pplx = raw[:m.start()]
        last_section_close = before_pplx.rfind("</section>")
        print(f"  Derniere </section> avant pplx : pos={last_section_close}")
        # Et la <section> qui ouvre cette section
        # on cherche en arriere depuis last_section_close
        # En remontant, on trouve l'ouverture qui matche
        print("\n  Apercu 500 chars autour du debut du panel (pos_min) :")
        print("  " + raw[max(0, pos_min - 300):pos_min + 200].replace("\n", "\n  "))

# 4) Liste tous les data-tab dans le HTML pour situer dans l'onglet
print("\n" + "=" * 72)
print("[3] Tabs (data-tab) detectes")
print("=" * 72)
for m in re.finditer(r'(id="tab-[^"]+")', raw):
    print(f"  pos={m.start():>6}  {m.group(0)}")
