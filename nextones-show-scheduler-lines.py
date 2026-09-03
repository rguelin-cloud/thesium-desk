# [SHOW_SCHEDULER_LINES_V1]
# Affiche l'etat actuel des lignes scheduler.add_job dans api_server.py
# pour comprendre dans quel etat est tombe le fichier.

from pathlib import Path
import re

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
txt = TARGET.read_text(encoding="utf-8-sig", errors="replace")

print(f"Fichier : {TARGET}")
print(f"Taille  : {len(txt)} chars\n")

print("=" * 72)
print("Toutes les lignes contenant 'refresh_geo' (avec ou sans commentaire)")
print("=" * 72)
for i, line in enumerate(txt.split("\n"), 1):
    if "refresh_geo" in line:
        # tronque pour lisibilite
        print(f"  L{i:>4}: {line[:160]}")

print()
print("=" * 72)
print("Toutes les lignes contenant 'scheduler.add_job'")
print("=" * 72)
for i, line in enumerate(txt.split("\n"), 1):
    if "scheduler.add_job" in line:
        print(f"  L{i:>4}: {line[:160]}")

print()
print("=" * 72)
print("Markers GDELT_SCHEDULER_DISABLED_V1")
print("=" * 72)
for m in re.finditer(r"\[GDELT_SCHEDULER_DISABLED_V1\]", txt):
    line_no = txt[:m.start()].count("\n") + 1
    print(f"  L{line_no:>4} pos={m.start()}")
