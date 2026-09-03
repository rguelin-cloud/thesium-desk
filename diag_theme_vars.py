"""
Identifie les variables CSS du thème (mode clair/sombre) dans index.html.
On cherche les :root { --xxx: ... } et les sélecteurs sombres (.dark, [data-theme=dark], etc.).
"""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
html = (ROOT / "index.html").read_text(encoding="utf-8-sig", errors="replace")

print("=" * 70)
print("1) DÉCLARATIONS DE VARIABLES CSS (--xxx: ...)")
print("=" * 70)
# Trouve tous les blocs où il y a des var CSS
var_defs = list(re.finditer(r'(--[a-zA-Z][a-zA-Z0-9_-]*)\s*:\s*([^;]+);', html))
seen = {}
for m in var_defs:
    name = m.group(1)
    val  = m.group(2).strip()
    if name not in seen:
        seen[name] = []
    seen[name].append(val)

print(f"  Total variables uniques: {len(seen)}")
for name, vals in sorted(seen.items()):
    uniq_vals = list(dict.fromkeys(vals))  # dedup en gardant ordre
    print(f"  {name:35} = {uniq_vals[:3]}")

print()
print("=" * 70)
print("2) SÉLECTEURS DE MODE SOMBRE (cherche .dark, [data-theme=...], body.dark)")
print("=" * 70)
for pattern in [
    r'\.dark[^{]*\{[^}]+\}',
    r'\[data-theme[^\]]*\][^{]*\{[^}]+\}',
    r'body\.dark[^{]*\{[^}]+\}',
    r'html\.dark[^{]*\{[^}]+\}',
    r'@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)',
]:
    matches = list(re.finditer(pattern, html, re.DOTALL))
    if matches:
        print(f"\n  Pattern '{pattern}' : {len(matches)} match(s)")
        for m in matches[:3]:
            snippet = m.group(0)[:300].replace('\n', ' ')
            print(f"     {snippet}")

print()
print("=" * 70)
print("3) ATTRIBUT data-theme sur <html> ou <body> (ou class='dark')")
print("=" * 70)
for m in re.finditer(r'<(html|body)\b[^>]*(?:data-theme|theme|class)[^>]*>', html):
    print(f"  {m.group(0)[:200]}")

print()
print("=" * 70)
print("4) CHERCHE DES MOTS-CLÉS POUR LE TOGGLE THÈME EN JS (app.js)")
print("=" * 70)
js = (ROOT / "app.js").read_text(encoding="utf-8-sig", errors="replace")
for pat in [
    r'data-theme',
    r"['\"]dark['\"]",
    r"\.classList\.(add|remove|toggle)\s*\(\s*['\"]dark['\"]",
    r"theme\s*[:=]\s*['\"](dark|light)",
    r"localStorage\.[gs]etItem\s*\(\s*['\"]theme",
]:
    matches = list(re.finditer(pat, js))
    if matches:
        print(f"\n  Pattern '{pat}' : {len(matches)} match(s)")
        for m in matches[:3]:
            s = max(0, m.start()-50); e = min(len(js), m.end()+80)
            print(f"     ...{js[s:e]}...")

print()
print("=" * 70)
print("5) RÈGLES CSS SUR .card OU .table-section EN MODE SOMBRE")
print("=" * 70)
# Trouve les déclarations de .card dans le HTML/CSS
for pat in [r'\.card\s*\{[^}]+\}', r'\.tab-content\s*\{[^}]+\}', r'\.table-section\s*\{[^}]+\}']:
    for m in re.finditer(pat, html, re.DOTALL):
        print(f"  {m.group(0)[:250].strip()}")
        print()
