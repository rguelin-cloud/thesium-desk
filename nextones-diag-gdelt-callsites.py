# [DIAG_GDELT_CALLSITES_V1]
# Localise tous les call-sites GDELT et USGS dans le projet ThesiumDesk
# pour preparer leur extinction propre.
#
# Cherche :
#   - imports gdelt
#   - URLs api.gdeltproject.org / earthquake.usgs.gov
#   - noms de fonctions/jobs scheduler
#
# Usage : py -3.13 nextones-diag-gdelt-callsites.py

from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

PATTERNS = {
    "URL_GDELT":   re.compile(r"api\.gdeltproject\.org|gdeltproject\.org", re.I),
    "URL_USGS":    re.compile(r"earthquake\.usgs\.gov|usgs\.gov", re.I),
    "IMPORT_GDELT": re.compile(r"^\s*(from|import)\s+\S*gdelt\S*", re.M | re.I),
    "FUNC_GDELT":  re.compile(r"def\s+(\w*gdelt\w*|\w*geo_risk\w*|\w*chokepoint\w*|\w*theatre\w*)", re.I),
    "SCHED_GDELT": re.compile(r"(scheduler|add_job|cron|interval).*?(gdelt|geo_risk|chokepoint|theatre)", re.I),
}

EXTENSIONS = (".py", ".js", ".ps1", ".html", ".json")
EXCLUDE_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "logs", "backups"}


def iter_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in EXTENSIONS:
            continue
        # ignore les fichiers backup
        if ".bak." in p.name:
            continue
        yield p


hits = {k: [] for k in PATTERNS}

for f in iter_files():
    try:
        txt = f.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    rel = f.relative_to(ROOT)
    for k, rx in PATTERNS.items():
        for m in rx.finditer(txt):
            line_no = txt[:m.start()].count("\n") + 1
            snippet = m.group(0).strip()[:120]
            hits[k].append((str(rel), line_no, snippet))

for k, rows in hits.items():
    print("=" * 72)
    print(f"[{k}] {len(rows)} occurrences")
    print("=" * 72)
    # dedup par fichier+ligne
    seen = set()
    for rel, ln, sn in rows:
        key = (rel, ln)
        if key in seen:
            continue
        seen.add(key)
        print(f"  {rel}:{ln}   {sn}")

# Bonus : recherche specifique du scheduler
print("\n" + "=" * 72)
print("[SCHEDULER] add_job / scheduled / interval references")
print("=" * 72)
for f in iter_files():
    if f.suffix.lower() != ".py":
        continue
    try:
        txt = f.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    rel = f.relative_to(ROOT)
    for m in re.finditer(r".*\b(add_job|scheduled_job|interval|CronTrigger|IntervalTrigger)\b.*", txt):
        line = m.group(0).strip()
        if "gdelt" in line.lower() or "geo" in line.lower() or "usgs" in line.lower() or "chokepoint" in line.lower() or "theatre" in line.lower():
            line_no = txt[:m.start()].count("\n") + 1
            print(f"  {rel}:{line_no}   {line[:160]}")
