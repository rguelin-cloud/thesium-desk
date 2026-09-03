# [SHOW_IS_PAST_LOGIC_V2]
# Trouve la logique qui definit ev["_is_past"] dans data_macro.py
# et examine les 3 lignes sans guard : L774, L784, L794.

from pathlib import Path

TARGET = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_macro.py")
txt = TARGET.read_text(encoding="utf-8-sig", errors="replace")
lines = txt.split("\n")

print(f"Fichier : {TARGET}, {len(lines)} lignes\n")

# 1) Toutes les definitions / usages _is_past
print("=" * 72)
print("[1] Toutes les lignes mentionnant _is_past")
print("=" * 72)
for i, ln in enumerate(lines, 1):
    if "_is_past" in ln:
        # marqueur si c'est une assignation
        stripped = ln.strip()
        is_assign = stripped.startswith("ev[") and "= " in stripped and "_is_past" in stripped.split("=")[0]
        marker = ">>" if is_assign else "  "
        print(f"  {marker} L{i:>4}: {ln.rstrip()[:180]}")

# 2) Bloc des 3 lignes sans guard (L774, L784, L794)
print()
print("=" * 72)
print("[2] Lignes L770-L800 — context des assignations sans guard")
print("=" * 72)
for i in range(770, min(805, len(lines))):
    print(f"  L{i+1:>4}: {lines[i][:180]}")

# 3) Bloc complet du format dispatch (autour de L720-L815)
print()
print("=" * 72)
print("[3] Bloc format dispatch L720-L815")
print("=" * 72)
for i in range(719, min(816, len(lines))):
    flag = "*" if "_is_past" in lines[i] else " "
    print(f" {flag}L{i+1:>4}: {lines[i][:180]}")
