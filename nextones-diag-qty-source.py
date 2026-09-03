# -*- coding: utf-8 -*-
"""
Diag: trouver le code source qui cree les ordres avec quantity=1 hardcodee
Cible: tous les .py du projet ThesiumDesk (sauf .venv, __pycache__, backups)

Sortie:
  - Liste de tous les patterns suspects avec fichier + ligne + extrait
  - Patterns recherches:
      * "INSERT INTO orders" (toute insertion d'ordre)
      * "quantity\s*=\s*1\b" / "qty\s*=\s*1\b"
      * "approved_quantity\s*=\s*1"
      * "quantity\s*=\s*int\(" (cast suspect)
      * "round\(.*qty" / "int\(.*qty"
      * fonctions build_order / create_order / propose_order
"""

import os
import re
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "backups", "static"}
EXCLUDE_PREFIXES = ("bak-", "backup-", ".bak")

PATTERNS = [
    ("INSERT_ORDERS",      re.compile(r"INSERT\s+INTO\s+orders", re.IGNORECASE)),
    ("QTY_EQUALS_1",       re.compile(r"\b(quantity|qty|approved_quantity)\s*=\s*1\b")),
    ("QTY_HARDCODE_1",     re.compile(r"['\"]?(quantity|qty|approved_quantity)['\"]?\s*[:=]\s*1[^0-9.]")),
    ("INT_CAST_QTY",       re.compile(r"(quantity|qty)\s*=\s*int\(")),
    ("ROUND_QTY",          re.compile(r"(quantity|qty)\s*=\s*round\(")),
    ("BUILD_ORDER_DEF",    re.compile(r"def\s+(build_order|create_order|propose_order|insert_order|make_order|new_order)\s*\(")),
    ("PROPOSAL_QTY",       re.compile(r"proposal.*qty|proposal.*quantity", re.IGNORECASE)),
    ("TARGET_WEIGHT_USE",  re.compile(r"target_weight\s*\*")),
    ("PORTFOLIO_VALUE",    re.compile(r"portfolio_value\s*[*/]")),
]

def should_skip(p: Path) -> bool:
    parts = set(p.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if any(seg.startswith(EXCLUDE_PREFIXES) for seg in p.parts):
        return True
    return False

def scan():
    print(f"[diag-qty-source] Scan racine: {ROOT}")
    print(f"[diag-qty-source] Exclusions: {EXCLUDE_DIRS}")
    print("=" * 80)

    by_pattern = {name: [] for name, _ in PATTERNS}

    py_files = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in filenames:
            if fn.endswith(".py"):
                full = Path(dirpath) / fn
                if not should_skip(full):
                    py_files.append(full)

    print(f"[diag-qty-source] {len(py_files)} fichiers .py a analyser")
    print()

    for f in py_files:
        try:
            txt = f.read_text(encoding="utf-8-sig", errors="ignore")
        except Exception as e:
            print(f"  SKIP {f.name}: {e}")
            continue
        lines = txt.splitlines()
        rel = f.relative_to(ROOT)

        for i, line in enumerate(lines, 1):
            for name, rx in PATTERNS:
                if rx.search(line):
                    by_pattern[name].append((str(rel), i, line.strip()[:200]))

    # Rapport groupe par pattern
    for name, hits in by_pattern.items():
        print(f"\n{'=' * 80}")
        print(f"PATTERN: {name}  ({len(hits)} hits)")
        print("=" * 80)
        for fpath, lineno, snippet in hits:
            print(f"  {fpath}:{lineno}")
            print(f"    {snippet}")

    print("\n" + "=" * 80)
    print("[diag-qty-source] FIN")
    print("=" * 80)

if __name__ == "__main__":
    scan()
