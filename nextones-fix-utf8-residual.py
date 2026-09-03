# -*- coding: utf-8 -*-
"""
Fix residuel mojibake cible : 2 sequences seulement.
- a— (E2 + EM-DASH visualise comme square) -> ● (U+25CF, bullet plein)
- A· (double-encoded middle dot)            -> · (U+00B7, middle dot)

ASCII-safe : aucun accent dans le code source pour eviter les soucis d encodage.
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# Mapping via codepoints uniquement (zero accent dans le source)
RESIDUAL_MAP = {
    "\u00e2\u2014": "\u25cf",   # a + em-dash -> bullet plein
    "\u00c2\u00b7": "\u00b7",   # A-circumflex + middle-dot -> middle-dot
}

TARGETS = [
    ROOT / "index.html",
    ROOT / "app.js",
    ROOT / "static" / "index.html",
    ROOT / "static" / "app.js",
]

print(f"=== Fix residuel mojibake - TS={TS} ===\n")

total_fixed = 0
for p in TARGETS:
    if not p.exists():
        continue
    raw = p.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    if has_bom:
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        print(f"  [SKIP] {p.name}: decode error {e}")
        continue

    before = {k: text.count(k) for k in RESIDUAL_MAP}
    if sum(before.values()) == 0:
        print(f"  [CLEAN] {p.relative_to(ROOT)}")
        continue

    # Backup
    bak = p.with_name(p.name + f".bak_resid_{TS}")
    bak.write_bytes((b"\xef\xbb\xbf" if has_bom else b"") + raw)

    # Sort by length desc to avoid short eating long
    for src in sorted(RESIDUAL_MAP.keys(), key=len, reverse=True):
        text = text.replace(src, RESIDUAL_MAP[src])

    after = {k: text.count(k) for k in RESIDUAL_MAP}
    p.write_text(text, encoding="utf-8", newline="\n")
    total_fixed += 1
    rel = p.relative_to(ROOT)
    print(f"  [FIX] {rel}")
    for k, v in before.items():
        if v > 0:
            print(f"     {repr(k)} : {v} -> {after[k]}")

print(f"\n=== {total_fixed} fichier(s) corrige(s) ===")

# Validation finale
print("\n=== Validation finale ===")
ALL_CHECKS = list(RESIDUAL_MAP.keys()) + [
    "\u00c3\u00a9",         # Ã©
    "\u00c3\u2030",         # Ã‰
    "\u00e2\u00bf",         # â¿
    "\u00f0\u0178",         # prefix emoji
    "\u00e2\u20ac",         # prefix punct typo
]
for p in TARGETS:
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    parts = []
    for k in ALL_CHECKS:
        c = text.count(k)
        if c:
            parts.append(f"{repr(k)}={c}")
    rel = p.relative_to(ROOT)
    if parts:
        print(f"  {rel}: RESIDU {' '.join(parts)}")
    else:
        print(f"  {rel}: 0 residu")

print("\n=== Termine. Rafraichis le navigateur (Ctrl+Shift+R). ===")
