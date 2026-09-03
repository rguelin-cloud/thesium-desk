# Localise :
#   1. Le code reconciler qui dropp avec raison "Portfolio deja a la cible"
#   2. Le seuil exact utilise (chercher >, < dans cette fonction)
#   3. Le selecteur de budget_build vs budget_maintain vs budget_rebalance
#   4. Tout fichier qui contient "Portfolio d" pour matcher l'accent

import glob
from pathlib import Path
import re

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
files = sorted(glob.glob(str(ROOT / "*.py")))

print("=" * 80)
print("[1] Fichiers contenant 'Portfolio d' (accent variable)")
print("=" * 80)
for f in files:
    fname = Path(f).name
    if "diag" in fname.lower() or "_backup" in fname.lower():
        continue
    try:
        txt = Path(f).read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    # Cherche "Portfolio d" suivi d'un caractere accentue ou non
    for i, line in enumerate(txt.splitlines(), 1):
        if re.search(r"Portfolio d.j.{1,3} a la cible", line) or "Portfolio dej" in line:
            print(f"\n  -- {fname} L{i} --")
            lines = txt.splitlines()
            for j in range(max(0, i-25), min(len(lines), i+5)):
                marker = " >>" if j == i-1 else "   "
                print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
            break

print()
print("=" * 80)
print("[2] Cherche 'DROPPED' + 'cible' dans reconciler")
print("=" * 80)
for f in files:
    fname = Path(f).name
    if "diag" in fname.lower() or "_backup" in fname.lower():
        continue
    try:
        txt = Path(f).read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    if "DROPPED" in txt and "cible" in txt.lower():
        print(f"\n  -- {fname} --")
        lines = txt.splitlines()
        # Cherche fonction reconcile
        for i, line in enumerate(lines, 1):
            if "DROPPED" in line and i < len(lines):
                # Contexte 20 lignes avant
                for j in range(max(0, i-20), min(len(lines), i+5)):
                    marker = " >>" if j == i-1 else "   "
                    print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
                print()

print()
print("=" * 80)
print("[3] Selecteur budget_build vs budget_maintain")
print("=" * 80)
for f in files:
    fname = Path(f).name
    if "_backup" in fname.lower() or "diag" in fname.lower():
        continue
    try:
        txt = Path(f).read_text(encoding="utf-8-sig", errors="replace")
    except Exception:
        continue
    if "budget_build" in txt or "budget_maintain" in txt:
        print(f"\n  -- {fname} --")
        lines = txt.splitlines()
        for i, line in enumerate(lines, 1):
            if any(k in line for k in ["budget_build", "budget_maintain", "budget_rebalance"]):
                if not line.strip().startswith("#") and "json" not in line.lower():
                    print(f"    L{i:>4}: {line.rstrip()[:200]}")

print()
print("[DONE]")
