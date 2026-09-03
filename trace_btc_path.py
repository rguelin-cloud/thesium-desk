# trace_btc_path.py
# Affiche le chemin complet d'un proposal jusqu'a l'INSERT INTO orders
# Cible : la zone autour de L1850 (quantity = int(...) et la boucle qui call create_order)

import re

ENGINE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
with open(ENGINE, "r", encoding="utf-8-sig") as f:
    lines = f.read().split("\n")

# Zone 1 : autour de L1830-1900 (la boucle finale qui cree les ordres)
print("=" * 70)
print("ZONE 1 : L1820-1920 (boucle de creation des ordres)")
print("=" * 70)
for i in range(1819, min(1920, len(lines))):
    print(f"  L{i+1:04d}| {lines[i]}")

# Cherche pending_orders.append et create_and_execute_order
print()
print("=" * 70)
print("OCCURRENCES pending_orders.append / create_and_execute_order")
print("=" * 70)
patterns = [
    r"pending_orders\.append",
    r"create_and_execute_order\s*\(",
    r"def\s+create_and_execute_order",
    r"def\s+run_decision_cycle",
    r"def\s+_reconcile",
]
for pat in patterns:
    for i, ln in enumerate(lines):
        if re.search(pat, ln):
            print(f"  L{i+1:04d} [{pat}] {ln[:120]}")
