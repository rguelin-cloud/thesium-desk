# [SHOW_DATA_MACRO_CALENDAR_V1]
# Extrait :
#   - Le corps de _get_economic_calendar()
#   - L'event GDP (Advance Estimate) ligne 517
#   - L'event Initial Jobless Claims ligne 523
#   - Toutes les cles utilisees (actual, forecast, previous, time, date)
# Pour comprendre comment patcher : retirer 'actual' si l'event n'est pas encore tombe.

from pathlib import Path
import re

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
txt = TARGET.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.split("\n")

print(f"Fichier : {TARGET}")
print(f"Taille  : {len(txt)} chars, {len(lines)} lignes\n")

# 1) Bloc autour de la ligne 517 (GDP)
print("=" * 72)
print("[1] GDP (Advance Estimate) — bloc autour de L517")
print("=" * 72)
for i in range(max(1, 517 - 5), min(len(lines), 517 + 15)):
    flag = ">>" if i == 517 else "  "
    print(f"  {flag} L{i:>4}: {lines[i-1][:160]}")

print()
print("=" * 72)
print("[2] Initial Jobless Claims — bloc autour de L523")
print("=" * 72)
for i in range(max(1, 523 - 5), min(len(lines), 523 + 15)):
    flag = ">>" if i == 523 else "  "
    print(f"  {flag} L{i:>4}: {lines[i-1][:160]}")

# 2) Corps de _get_economic_calendar
print()
print("=" * 72)
print("[3] Corps de _get_economic_calendar()")
print("=" * 72)
m = re.search(r"^def\s+_get_economic_calendar\s*\(", txt, re.M)
if m:
    body_start = m.start()
    next_def = re.search(r"\n(?:def|class)\s+\w", txt[m.end():])
    body_end = m.end() + (next_def.start() if next_def else 3000)
    block = txt[body_start:body_end]
    for i, ln in enumerate(block.split("\n")[:80], 1):
        print(f"  {i:>3}: {ln[:160]}")
else:
    print("  Fonction non trouvee")

# 3) Identifier les cles 'actual' presentes dans le fichier
print()
print("=" * 72)
print("[4] Toutes les lignes contenant 'actual' dans data_macro.py")
print("=" * 72)
for i, ln in enumerate(lines, 1):
    if '"actual"' in ln or "'actual'" in ln or '"actual:' in ln:
        print(f"  L{i:>4}: {ln.strip()[:160]}")

# 4) Lignes avec 'forecast' pour comparaison
print()
print("=" * 72)
print("[5] Lignes contenant 'forecast'")
print("=" * 72)
n = 0
for i, ln in enumerate(lines, 1):
    if '"forecast"' in ln or "'forecast'" in ln:
        print(f"  L{i:>4}: {ln.strip()[:160]}")
        n += 1
        if n >= 10:
            print("  ... (tronque)")
            break

# 5) Liste les events du jour (28/05) si la date est codee
print()
print("=" * 72)
print("[6] Recherche date 28/05 ou '2026-05-28' dans le fichier")
print("=" * 72)
for needle in ["28/05", "2026-05-28", "May 28", "28 mai", "jeu. 28 mai"]:
    for m in re.finditer(re.escape(needle), txt):
        line_no = txt[:m.start()].count("\n") + 1
        line = lines[line_no - 1].strip()
        print(f"  L{line_no:>4} [{needle}]: {line[:160]}")
