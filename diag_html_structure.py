"""Cartographie la structure du HTML pour comprendre où placer le panel pplx."""
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
html = (ROOT / "index.html").read_text(encoding="utf-8-sig", errors="replace")

print(f"Taille totale: {len(html)} chars")
print()

# 1) Trouve toutes les balises principales <section>, <main>, <div id="...">, data-route, data-page, etc.
print("=" * 70)
print("1) ATTRIBUTS DE NAVIGATION (data-route, data-page, data-tab, etc.)")
print("=" * 70)
for attr in ["data-route", "data-page", "data-tab", "data-view", "data-section", "data-panel"]:
    matches = list(re.finditer(rf'{attr}=["\']([^"\']+)["\']', html))
    if matches:
        print(f"\n  {attr} : {len(matches)} occurrences")
        for m in matches[:15]:
            print(f"     value='{m.group(1)}' @ offset {m.start()}")

# 2) Trouve les principaux <section id=...> et <div id=...>
print()
print("=" * 70)
print("2) TOUS LES <section> ET <main> AVEC ATTRIBUTS")
print("=" * 70)
for m in re.finditer(r'<(section|main|article)([^>]{0,200})>', html):
    tag = m.group(1)
    attrs = m.group(2).strip()
    if attrs:
        print(f"  @ {m.start():6} <{tag} {attrs[:150]}>")

# 3) Trouve la navigation latérale ("Today", "Theses", "Market Intel", ...)
print()
print("=" * 70)
print("3) ITEMS DE NAVIGATION (mots Today, Theses, Market Intel, etc.)")
print("=" * 70)
for word in ["Today", "Market Intel", "Theses", "Macro US", "IC Memos"]:
    for m in re.finditer(re.escape(word), html):
        s = max(0, m.start() - 100)
        e = min(len(html), m.end() + 100)
        ctx = html[s:e].replace("\n", " ")
        print(f"  '{word}' @ {m.start():6} ctx: ...{ctx[:180]}...")
        break  # juste le 1er

# 4) Trouve les conteneurs principaux qui changent quand on clique sur un item de nav
print()
print("=" * 70)
print("4) ID/CLASS DES CONTENEURS PRINCIPAUX (id contenant 'view', 'page', 'tab', 'content', 'today', 'market')")
print("=" * 70)
for m in re.finditer(r'<(div|section|main)\s+([^>]*?)(?:id|class)=["\']([^"\']*(?:view|page|tab|content|today|market)[^"\']*)["\']([^>]*)>', html, re.IGNORECASE):
    print(f"  @ {m.start():6} <{m.group(1)} ... '{m.group(3)}' ...>")

# 5) Position du bloc pplx-insights-panel par rapport aux balises principales
print()
print("=" * 70)
print("5) CONTEXTE DU BLOC PPLX (200 chars AVANT son injection)")
print("=" * 70)
idx = html.find("[PPLX_PANEL_V1_HTML]")
if idx > 0:
    print(html[max(0, idx-400):idx+50])

# 6) Position de la fin du body
print()
print("=" * 70)
print("6) FIN DU FICHIER — où s'arrête le HTML ?")
print("=" * 70)
print(f"  </body> @ offset {html.rfind('</body>')}")
print(f"  </html> @ offset {html.rfind('</html>')}")
print(f"  pplx-insights-panel @ offset {html.find('pplx-insights-panel')}")
print(f"  THESIS_PANEL_V2_HTML @ offset {html.find('[PPLX_THESIS_PANEL_V2_HTML]')}")
print()
print("  → si pplx > </body>, c'est HORS du body (problème)")
print("  → si pplx < </body>, c'est dans le body mais peut-être pas dans la bonne vue")
