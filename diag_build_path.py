# diag_build_path.py
# Trouver ou la logique BUILD est appliquee dans execution_engine.py
# et identifier la zone a patcher pour override qty=1 sur equities en BUILD

import re
from pathlib import Path

target = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py")
content = target.read_text(encoding="utf-8-sig")
lines = content.split("\n")

print("=" * 70)
print("Recherche : BUILD / phase / action_type / proposed_action")
print("=" * 70)
keywords = ["BUILD", "phase", "action_type", "proposed_action", "build_budget", "MIN_TRADE"]
for i, line in enumerate(lines):
    for kw in keywords:
        if kw in line and not line.strip().startswith("#"):
            print(f"  L{i+1:5d}: {line.rstrip()[:120]}")
            break

print()
print("=" * 70)
print("Contexte autour du patch [RDC_CRYPTO_V1] (L1858-1870 approx)")
print("=" * 70)
for i, line in enumerate(lines):
    if "[RDC_CRYPTO_V1]" in line:
        start = max(0, i - 10)
        end = min(len(lines), i + 20)
        for j in range(start, end):
            marker = " >>> " if j == i else "     "
            print(f"  L{j+1:5d}{marker}{lines[j].rstrip()[:120]}")
        print()
        break

print()
print("=" * 70)
print("Recherche function definitions autour de run_decision_cycle")
print("=" * 70)
for i, line in enumerate(lines):
    if re.match(r"^\s*(def|async def)\s+", line):
        if 1500 <= i <= 1950:
            print(f"  L{i+1:5d}: {line.rstrip()[:120]}")
