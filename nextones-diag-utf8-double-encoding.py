# -*- coding: utf-8 -*-
"""
Diagnostic : trouve les fichiers avec double-encoding UTF-8
Signature : présence de séquences typiques "Ã©", "Ã¨", "Ã ", "GÃ‰", "Ã®", "â", "ðŸ"
qui ne devraient JAMAIS apparaitre dans un texte UTF-8 propre.
"""
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

# Signatures fortes de double-encoding (mojibake)
PATTERNS = [
    r'Ã©',    # é
    r'Ã¨',    # è
    r'Ã ',    # à
    r'Ã®',    # î
    r'Ã´',    # ô
    r'Ã»',    # û
    r'Ã§',    # ç
    r'Ã‰',    # É
    r'Ãˆ',    # È
    r'Ã€',    # À
    r'â€™',   # ' (apostrophe typographique)
    r'â€"',   # — em-dash
    r'â€"',   # – en-dash
    r'â€¢',   # • puce
    r'ðŸ',    # début emoji 4-bytes (drapeau, etc.)
    r'â¿',    # crypto/emoji
]

# Fichiers à scanner
EXTENSIONS = {".html", ".js", ".css", ".py"}

print(f"=== Scan {ROOT} ===\n")
results = []
for ext in EXTENSIONS:
    for p in ROOT.rglob(f"*{ext}"):
        # Skip backups
        if ".bak_" in p.name:
            continue
        # Skip node_modules, venv, etc
        parts = set(p.parts)
        if "node_modules" in parts or ".venv" in parts or "__pycache__" in parts:
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, PermissionError):
            continue
        hits = []
        for pat in PATTERNS:
            cnt = len(re.findall(pat, content))
            if cnt:
                hits.append((pat, cnt))
        if hits:
            total = sum(c for _, c in hits)
            results.append((p, total, hits))

# Tri par nb d'occurrences décroissant
results.sort(key=lambda x: -x[1])

print(f"Fichiers atteints : {len(results)}\n")
for p, total, hits in results[:30]:
    rel = p.relative_to(ROOT)
    samples = ", ".join(f"{pat}×{cnt}" for pat, cnt in hits[:6])
    print(f"  [{total:5d}] {rel}")
    print(f"          {samples}")

# Vérifie présence BOM
print("\n=== BOM dans fichiers principaux ===")
for name in ["index.html", "app.js", "style.css", "api_server.py"]:
    p = ROOT / name
    if p.exists():
        head = p.read_bytes()[:3]
        has_bom = head == b'\xef\xbb\xbf'
        print(f"  {name}: BOM={'OUI' if has_bom else 'non'}")
