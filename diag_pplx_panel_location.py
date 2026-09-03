"""Trouve OÙ le panel Perplexity Insights est injecté dans index.html
et POURQUOI il ne se rend pas (vue parente, display:none, JS non appelé, etc.)
"""
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
html = (ROOT / "index.html").read_text(encoding="utf-8-sig", errors="replace")
js   = (ROOT / "app.js").read_text(encoding="utf-8-sig", errors="replace")

print("=" * 70)
print("1) BLOC HTML DU PANEL — contexte autour")
print("=" * 70)

# Trouve l'ID/classe principal du panel
for marker in ["pplx-insights", "perplexity-insights", "Perplexity Insights"]:
    for m in re.finditer(re.escape(marker), html):
        start = max(0, m.start() - 300)
        end   = min(len(html), m.end() + 200)
        print(f"\n--- match '{marker}' @ offset {m.start()} ---")
        print(html[start:end])
        print("--- fin ---")
        break  # juste le premier de chaque marqueur

print()
print("=" * 70)
print("2) DANS QUELLE VIEW <section data-view='X'> est-il imbriqué ?")
print("=" * 70)
# Trouve toutes les section data-view, et localise pplx-insights par offset
sections = []
for m in re.finditer(r'<section[^>]*data-view=["\']([^"\']+)["\'][^>]*>', html):
    sections.append((m.start(), m.group(1)))
# Si pplx-insights est entre deux <section ...> alors on connaît la vue
pidx = html.find("pplx-insights")
if pidx > 0:
    parent = None
    for off, name in sections:
        if off < pidx:
            parent = name
    print(f"  pplx-insights est dans <section data-view='{parent}'> (si None => en dehors de toute vue)")
else:
    print("  pas trouvé pplx-insights")

# Cherche aussi les markers V1/V2
print()
print("=" * 70)
print("3) POSITION DES MARKERS V1/V2 DANS HTML")
print("=" * 70)
for mk in ["[PPLX_PANEL_V1_HTML]", "[PPLX_THESIS_PANEL_V2_HTML]"]:
    idx = html.find(mk)
    if idx >= 0:
        # Trouve la vue parente
        parent = None
        for off, name in sections:
            if off < idx:
                parent = name
        print(f"  {mk:35} offset={idx:6}  parent_view={parent}")
    else:
        print(f"  {mk:35} ABSENT")

print()
print("=" * 70)
print("4) JS — la fonction loadPplxInsights est-elle APPELÉE ?")
print("=" * 70)
# Cherche les définitions et appels
for pattern, label in [
    (r"function\s+loadPplxInsights", "DEFINITION loadPplxInsights"),
    (r"loadPplxInsights\s*\(", "APPELS loadPplxInsights"),
    (r"renderThesisChallenges", "renderThesisChallenges (def+appels)"),
    (r"addEventListener\s*\(\s*['\"]DOMContentLoaded", "DOMContentLoaded listeners"),
    (r"setInterval\s*\(", "setInterval"),
]:
    matches = list(re.finditer(pattern, js))
    print(f"  {label:45} count={len(matches)}")
    for m in matches[:3]:
        # Affiche 80 char autour
        s = max(0, m.start() - 30)
        e = min(len(js), m.end() + 60)
        snippet = js[s:e].replace("\n", " ")[:140]
        print(f"     @ {m.start():6} : {snippet}")

print()
print("=" * 70)
print("5) Y A-T-IL DU CSS display:none QUI MASQUE LE PANEL ?")
print("=" * 70)
# Cherche du CSS qui ciblerait pplx-insights
for m in re.finditer(r'(#pplx-insights|\.pplx-insights)[^{]*\{[^}]*\}', html, re.DOTALL):
    print(f"  CSS rule: {m.group(0)[:200]}")

# Cherche aussi style="display:none" ou hidden sur le bloc
for m in re.finditer(r'(<[^>]*pplx-insights[^>]*>)', html):
    print(f"  TAG: {m.group(1)[:200]}")

print()
print("=" * 70)
print("6) STRUCTURE DES VIEWS (data-view) — laquelle est active par défaut ?")
print("=" * 70)
for off, name in sections:
    # Regarde si class="active" dans les 200 char autour
    snippet = html[off:off+250]
    active = "active" in snippet
    hidden = 'hidden' in snippet or 'style="display:none' in snippet
    print(f"  data-view='{name}'  active={active}  hidden={hidden}")
