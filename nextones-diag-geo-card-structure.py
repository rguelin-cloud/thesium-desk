# -*- coding: utf-8 -*-
"""
Diag : trouve la structure HTML des cartes de risque geo dans app.js
(la fonction qui rend les risques)
"""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
APP_JS = ROOT / "app.js"

text = APP_JS.read_text(encoding="utf-8")

print("=== Recherche fonctions de rendu geo ===\n")

# Patterns possibles
patterns = [
    r"function\s+(\w*[Gg]eo\w*[Rr]isk\w*)",
    r"function\s+(\w*[Rr]ender\w*[Gg]eo\w*)",
    r"function\s+(pplx\w*[Gg]eo\w*)",
    r"(\w*GeoRisk\w*)\s*[=:]\s*function",
    r"(\w+GeoCard\w*)\s*[=:]",
]
for pat in patterns:
    matches = re.findall(pat, text)
    if matches:
        print(f"  Pattern {pat[:40]} : {matches}")

# Cherche le bloc qui contient 'risk_id' ou 'severity' pour identifier le rendu
print("\n=== Blocs contenant risk_id et le HTML innerHTML ===")
# Cherche les blocs entre `innerHTML` et la prochaine fermeture
for m in re.finditer(r"innerHTML\s*=\s*[`'\"]", text):
    start = m.start()
    # Recule de 200 chars pour avoir le contexte
    ctx_start = max(0, start - 200)
    ctx = text[ctx_start:start]
    # Verifie si on est dans une fonction qui parle de risk/geo
    if "risk" in ctx.lower() or "geo" in ctx.lower() or "severity" in ctx.lower():
        # Affiche le contexte + 600 chars apres
        print(f"\n--- Position {start} ---")
        print(text[ctx_start:start + 600])
        print("---")

# Recherche directe par contenu 'severity' avec template literal
print("\n=== Templates literals avec severity ===")
for m in re.finditer(r"`[^`]{50,800}`", text):
    snippet = m.group(0)
    if "severity" in snippet and ("class=" in snippet or "data-" in snippet):
        # Affiche contexte avant
        ctx_start = max(0, m.start() - 100)
        print(f"\n--- Position {m.start()} ---")
        print(text[ctx_start:m.end()][:800])
        print("---")

# Identifie le selecteur de carte risque
print("\n=== Recherche createElement / div risk ===")
for line_num, line in enumerate(text.split("\n"), 1):
    if "risk" in line.lower() and ("class=" in line or "className" in line) and "card" in line.lower():
        print(f"  L{line_num}: {line.strip()[:200]}")
