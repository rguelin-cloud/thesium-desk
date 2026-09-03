# Localise precisement la ligne RELEASE_MAP/rid=53 (GDP) pour faire le patch ensuite.
from pathlib import Path
import re

DM = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
txt = DM.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.splitlines()

print("=" * 80)
print("[1] Toutes les lignes contenant 'GDP' ou 'A191' ou 'rid' ou 'release_id' ou '53'")
print("=" * 80)
for i, line in enumerate(lines, 1):
    s = line.strip()
    if any(k in line for k in ['"GDP"', "'GDP'", "GDP (Advance", "A191", "GDPC1"]):
        print(f"  L{i:>4}: {line.rstrip()[:200]}")

print()
print("=" * 80)
print("[2] Cherche la structure entre L500-L540 (RELEASE_MAP est cense etre la)")
print("=" * 80)
for i in range(495, min(545, len(lines))):
    print(f"  L{i+1:>4}: {lines[i].rstrip()[:200]}")

print()
print("=" * 80)
print("[3] Cherche '53:' ou '53 :' (rid GDP) en debut de ligne ou apres {/,")
print("=" * 80)
for i, line in enumerate(lines, 1):
    if re.search(r"(^|\{|\s|,)\s*53\s*:", line):
        # Affiche le contexte (5 lignes)
        for j in range(max(0, i-2), min(len(lines), i+3)):
            marker = " >>" if j == i-1 else "   "
            print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
        print()

print()
print("=" * 80)
print("[4] Cherche '175:' (rid Initial Jobless Claims)")
print("=" * 80)
for i, line in enumerate(lines, 1):
    if re.search(r"(^|\{|\s|,)\s*175\s*:", line):
        for j in range(max(0, i-2), min(len(lines), i+3)):
            marker = " >>" if j == i-1 else "   "
            print(f"  {marker} L{j+1:>4}: {lines[j].rstrip()[:200]}")
        print()

print("[DONE]")
