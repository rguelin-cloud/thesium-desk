# -*- coding: utf-8 -*-
"""
Fix UTF-8 double-encoding via remplacement direct (mapping).
Évite encode/decode global qui plante sur les chars hors latin-1.
"""
import sys
from pathlib import Path
from datetime import datetime
import ast

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# Mapping mojibake -> caractère correct
# Construit avec : "é".encode("utf-8").decode("latin-1") => "Ã©"
# Donc on inverse : "Ã©" -> "é"
MAPPING = {
    # Lettres minuscules accentuées
    "\u00c3\u00a9": "\u00e9",  # Ã© -> é
    "\u00c3\u00a8": "\u00e8",  # Ã¨ -> è
    "\u00c3\u00aa": "\u00ea",  # Ãª -> ê
    "\u00c3\u00ab": "\u00eb",  # Ã« -> ë
    "\u00c3\u00a0": "\u00e0",  # Ã  -> à
    "\u00c3\u00a2": "\u00e2",  # Ã¢ -> â
    "\u00c3\u00a4": "\u00e4",  # Ã¤ -> ä
    "\u00c3\u00ae": "\u00ee",  # Ã® -> î
    "\u00c3\u00af": "\u00ef",  # Ã¯ -> ï
    "\u00c3\u00b4": "\u00f4",  # Ã´ -> ô
    "\u00c3\u00b6": "\u00f6",  # Ã¶ -> ö
    "\u00c3\u00b9": "\u00f9",  # Ã¹ -> ù
    "\u00c3\u00bb": "\u00fb",  # Ã» -> û
    "\u00c3\u00bc": "\u00fc",  # Ã¼ -> ü
    "\u00c3\u00a7": "\u00e7",  # Ã§ -> ç
    "\u00c3\u00b1": "\u00f1",  # Ã± -> ñ
    # Lettres majuscules accentuées
    "\u00c3\u2030": "\u00c9",  # Ã‰ -> É
    "\u00c3\u02c6": "\u00c8",  # Ãˆ -> È
    "\u00c3\u0160": "\u00ca",  # ÃŠ -> Ê
    "\u00c3\u20ac": "\u00c0",  # Ã€ -> À
    "\u00c3\u201a": "\u00c2",  # Ã‚ -> Â
    "\u00c3\u017d": "\u00ce",  # ÃŽ -> Î
    "\u00c3\u201d": "\u00d4",  # Ã" -> Ô
    "\u00c3\u2122": "\u00d9",  # Ã™ -> Ù
    "\u00c3\u00a6": "\u00e6",  # Ã¦ -> æ
    # Ponctuation typographique
    "\u00e2\u20ac\u2122": "\u2019",  # â€™ -> ' (apostrophe typo)
    "\u00e2\u20ac\u02dc": "\u2018",  # â€˜ -> ' ouvrante
    "\u00e2\u20ac\u0153": "\u201c",  # â€œ -> " ouvrante
    "\u00e2\u20ac\u009d": "\u201d",  # â€  -> " fermante
    "\u00e2\u20ac\u201d": "\u2014",  # â€" -> — em dash
    "\u00e2\u20ac\u201c": "\u2013",  # â€" -> – en dash
    "\u00e2\u20ac\u00a6": "\u2026",  # â€¦ -> … ellipse
    "\u00e2\u20ac\u00a2": "\u2022",  # â€¢ -> • bullet
    "\u00e2\u201e\u00a2": "\u2122",  # â„¢ -> ™
    "\u00c2\u00a0": "\u00a0",        # Â  -> nbsp
    "\u00c2\u00ab": "\u00ab",        # Â« -> «
    "\u00c2\u00bb": "\u00bb",        # Â» -> »
    "\u00c2\u00b0": "\u00b0",        # Â° -> °
    # Emojis 4 bytes (séquences typiques)
    "\u00f0\u0178\u201c\u0160": "\U0001f4ca",  # ðŸ"Š -> 📊
    "\u00f0\u0178\u201c\u02dc": "\U0001f4c8",  # ðŸ"˜ -> 📈
    "\u00f0\u0178\u00aa\u2122": "\U0001fa99",  # 🪙
    "\u00e2\u00bf\u00b1": "\u20bf",  # â¿± -> ₿ bitcoin sign approx
}

# Signatures pour détecter résiduel
SIGNATURES = list(MAPPING.keys()) + [
    "\u00c3\u00a9",
    "\u00e2\u20ac",
    "\u00f0\u0178",
]

def count_mojibake(text):
    return sum(text.count(sig) for sig in SIGNATURES)

def fix_mojibake_map(text):
    """Remplacement char-par-char via le mapping."""
    # Trier par longueur décroissante pour éviter qu'une séquence courte
    # mange une séquence longue qui la contient
    for src in sorted(MAPPING.keys(), key=len, reverse=True):
        text = text.replace(src, MAPPING[src])
    return text

HTML_JS_CSS_EXT = {".html", ".js", ".css"}
ALLOWED_PY_FILES = {
    "api_server.py",
    "api_server_with_static.py",
    "execution_engine.py",
    "execution_engine_v6_5.py",
}

def should_skip(p: Path) -> bool:
    name = p.name
    parts = set(p.parts)
    if any(part.startswith("_backups_") for part in p.parts):
        return True
    if ".bak_" in name or name.endswith(".bak"):
        return True
    if "diag_utf8" in name or "diag-utf8" in name:
        return True
    if "fix_utf8" in name or "fix-utf8" in name:
        return True
    if "nextones-diag-utf8" in name:
        return True
    if "node_modules" in parts or ".venv" in parts or "__pycache__" in parts:
        return True
    return False

candidates = []
for ext in HTML_JS_CSS_EXT:
    for p in ROOT.rglob(f"*{ext}"):
        if not should_skip(p):
            candidates.append(p)

for fname in ALLOWED_PY_FILES:
    p = ROOT / fname
    if p.exists() and not should_skip(p):
        candidates.append(p)

print(f"=== {len(candidates)} fichiers à examiner ===\n")

total = 0
fixed_count = 0
skipped = 0
errors = []

for p in sorted(candidates, key=lambda x: str(x)):
    total += 1
    try:
        raw_bytes = p.read_bytes()
    except Exception as e:
        errors.append((p, f"read_bytes: {e}"))
        continue
    has_bom = raw_bytes.startswith(b'\xef\xbb\xbf')
    if has_bom:
        raw_bytes = raw_bytes[3:]
    try:
        text = raw_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        errors.append((p, f"decode utf-8: {e}"))
        continue
    before_hits = count_mojibake(text)
    if before_hits == 0:
        skipped += 1
        continue
    # Backup
    backup_path = p.with_name(p.name + f".bak_utf8_{TS}")
    backup_path.write_bytes((b'\xef\xbb\xbf' if has_bom else b'') + raw_bytes)
    # Fix par mapping
    fixed_text = fix_mojibake_map(text)
    after_hits = count_mojibake(fixed_text)
    # Écrit sans BOM
    p.write_text(fixed_text, encoding="utf-8", newline="\n")
    fixed_count += 1
    rel = p.relative_to(ROOT)
    status = "OK" if after_hits == 0 else f"residual {after_hits}"
    print(f"  {rel} : {before_hits} -> {after_hits} mojibake ({status})")

print(f"\n=== RESUME ===")
print(f"  Examinés : {total}")
print(f"  Corrigés : {fixed_count}")
print(f"  Propres : {skipped}")
if errors:
    print(f"  Erreurs : {len(errors)}")
    for p, e in errors:
        print(f"    {p.relative_to(ROOT)}: {e}")

# Validation syntaxe Python
print("\n=== Validation syntaxe Python ===")
for fname in ALLOWED_PY_FILES:
    p = ROOT / fname
    if p.exists():
        try:
            ast.parse(p.read_text(encoding="utf-8"))
            print(f"  [OK] {fname}")
        except SyntaxError as e:
            print(f"  [KO] {fname} : {e}")
            # Auto-restore
            bak = list(ROOT.glob(f"{fname}.bak_utf8_{TS}"))
            if bak:
                p.write_bytes(bak[0].read_bytes())
                print(f"    Restauré depuis {bak[0].name}")
