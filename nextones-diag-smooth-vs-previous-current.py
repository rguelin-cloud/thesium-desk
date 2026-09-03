"""
Diag : montrer l etat actuel de smooth_vs_previous apres le patch v1
       (qui a casse new_alloc -> NameError).
ASCII pur.
"""
JALON2 = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py"

with open(JALON2, "r", encoding="utf-8-sig") as f:
    lines = f.readlines()

print("Total lignes :", len(lines))

# Trouver "def smooth_vs_previous"
start = None
for i, l in enumerate(lines, 1):
    if "def smooth_vs_previous" in l:
        start = i
        break

if start is None:
    print("[ERR] smooth_vs_previous not found")
else:
    print("\n=== smooth_vs_previous starts at L{} ===".format(start))
    # Lire 40 lignes a partir de la
    for i in range(start, min(start + 45, len(lines) + 1)):
        print("  L{}: {}".format(i, lines[i-1].rstrip()))

# Backups recents
import os, glob
backups = sorted(glob.glob(JALON2 + ".bak.*"), reverse=True)
print("\n=== Backups recents (3 plus recents) ===")
for b in backups[:3]:
    print(" ", os.path.basename(b))
