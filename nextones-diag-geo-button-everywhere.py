# -*- coding: utf-8 -*-
"""
Cherche 'Voir l'article' (au sens large) dans TOUS les fichiers HTML/JS/CSS
du projet pour localiser la source du doublon visible dans le navigateur.
"""
import os
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
EXCLUDE_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules"}

# On ne scan PAS les backups (on ne veut que les sources actives)
EXCLUDE_PREFIXES = ("_backups_", ".bak", "bak-")

EXTS = (".html", ".htm", ".js", ".css", ".jinja", ".jinja2", ".tpl")
NEEDLES = [
    "Voir l'article",
    "article complet",
    "pplx-risk-detail-btn",
    "pplx-risk-card-actions",
    "openGeoRiskDetail",
    "MutationObserver",
]

print(f"Scan racine: {ROOT}")
print(f"Extensions: {EXTS}")
print("=" * 90)

files = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # Exclure venv et backups
    dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(EXCLUDE_PREFIXES)]
    for fn in filenames:
        if fn.endswith(EXTS):
            full = Path(dirpath) / fn
            files.append(full)

print(f"{len(files)} fichiers a scanner")
print()

hits_per_needle = {n: [] for n in NEEDLES}

for f in files:
    try:
        txt = f.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    rel = f.relative_to(ROOT)
    for needle in NEEDLES:
        cnt = txt.count(needle)
        if cnt:
            hits_per_needle[needle].append((str(rel), cnt))

for needle, hits in hits_per_needle.items():
    print(f"\n{'=' * 90}")
    print(f"Pattern: '{needle}'  ({len(hits)} fichiers)")
    print("=" * 90)
    for fpath, cnt in hits:
        print(f"  {fpath}: {cnt} occurrences")

# Pour les fichiers qui matchent 'Voir l'article', afficher contexte
print(f"\n{'=' * 90}")
print("CONTEXTES detailles pour 'Voir l'article'")
print("=" * 90)
for fpath, cnt in hits_per_needle["Voir l'article"]:
    full = ROOT / fpath
    txt = full.read_text(encoding="utf-8-sig", errors="ignore")
    pos = 0
    found = 0
    while True:
        idx = txt.find("Voir l'article", pos)
        if idx == -1:
            break
        found += 1
        lineno = txt[:idx].count("\n") + 1
        start = max(0, idx - 200)
        end = min(len(txt), idx + 100)
        print(f"\n--- {fpath} occurrence #{found} (ligne ~{lineno}) ---")
        print(txt[start:end])
        pos = idx + 1
