# -*- coding: utf-8 -*-
"""
Diag : trouve les contextes des résidus mojibake non couverts par le mapping.
Cherche : â¿, â—, Ã·, Â·, ainsi que tout char isolé suspect.
"""
import sys
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# Patterns résiduels à investiguer
RESIDUAL_PATTERNS = [
    ("\u00e2\u00bf", "â¿  (orphelin ₿ ou autre)"),
    ("\u00e2\u2014", "â—  (orphelin ● ou square emoji)"),
    ("\u00e2\u2013", "â–  (orphelin ■ ou similar)"),
    ("\u00c3\u00b7", "Ã·  (probable · middle dot)"),
    ("\u00c2\u00b7", "Â·  (double-enc · middle dot)"),
    ("\u00c3\u2030", "Ã‰  (devrait être déjà mappé É - vérif)"),
    ("\u00c3\u00a9", "Ã©  (devrait être déjà mappé é - vérif)"),
    ("\u00f0\u0178", "ðŸ  (préfixe emoji 4-byte)"),
    ("\u00e2\u20ac", "â€  (préfixe ponct typo)"),
]

TARGETS = [
    ROOT / "index.html",
    ROOT / "static" / "index.html",
    ROOT / "static" / "app.js",
    ROOT / "app.js",
]
# Ajouter tous les .html et .js récursifs
for ext in (".html", ".js"):
    for p in ROOT.rglob(f"*{ext}"):
        if "_backups_" in str(p) or ".bak" in p.name or "node_modules" in str(p):
            continue
        if p not in TARGETS:
            TARGETS.append(p)

print(f"=== Diag résidus mojibake sur {len(TARGETS)} fichiers ===\n")

found_total = {pat: 0 for pat, _ in RESIDUAL_PATTERNS}

for p in TARGETS:
    if not p.exists():
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f"  [SKIP] {p.relative_to(ROOT)} : {e}")
        continue
    found_local = {}
    for pat, desc in RESIDUAL_PATTERNS:
        cnt = text.count(pat)
        if cnt > 0:
            found_local[pat] = cnt
            found_total[pat] += cnt
    if found_local:
        rel = p.relative_to(ROOT)
        print(f"\n--- {rel} ---")
        for pat, cnt in found_local.items():
            desc = next(d for p2, d in RESIDUAL_PATTERNS if p2 == pat)
            print(f"  {desc}: {cnt} occurrences")
            # Montre 3 premières occurrences avec contexte (40 chars autour)
            shown = 0
            for m in re.finditer(re.escape(pat), text):
                if shown >= 3:
                    break
                start = max(0, m.start() - 40)
                end = min(len(text), m.end() + 40)
                ctx = text[start:end].replace("\n", "\\n").replace("\r", "")
                print(f"     ...{ctx}...")
                shown += 1

print("\n=== TOTAUX ===")
for pat, desc in RESIDUAL_PATTERNS:
    cnt = found_total[pat]
    if cnt > 0:
        print(f"  {desc}: {cnt} total")

# Recherche également de séquences raw bytes suspectes
print("\n=== Détection emoji squares colorés 🟥🟩🟧🟨🟦🟪🟫⬛⬜ (recherche directe) ===")
square_emojis = ["\U0001f7e5", "\U0001f7e9", "\U0001f7e7", "\U0001f7e8", "\U0001f7e6", "\U0001f7ea", "\U0001f7eb", "\u2b1b", "\u2b1c", "\u25cf", "\u26ab", "\u26aa"]
for p in TARGETS:
    if not p.exists():
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    for em in square_emojis:
        if em in text:
            rel = p.relative_to(ROOT)
            print(f"  {rel} contient {em} (U+{ord(em):04X})")
            break  # un seul match par fichier suffit
