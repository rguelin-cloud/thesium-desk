# =====================================================================
# show_target_gap.py
# Affiche le corps complet de _build_target_gap_proposals (L1352)
# et la requete target_gap (L1303)
# =====================================================================
from pathlib import Path

ee = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py")
src = ee.read_text(encoding="utf-8", errors="ignore")
lines = src.splitlines()

# Affiche L1352 -> L1534 (fonction _build_target_gap_proposals)
print("=" * 80)
print("  _build_target_gap_proposals  (L1352 -> L1534)")
print("=" * 80)
for i in range(1350, 1535):
    if i > len(lines): break
    print(f"  L{i:>4}  {lines[i-1]}")

print()
print("=" * 80)
print("  FIN")
print("=" * 80)
