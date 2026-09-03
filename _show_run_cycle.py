"""Affiche le bloc autour de pending_orders dans run_decision_cycle()
À placer dans C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\
Lance : py -3.13 _show_run_cycle.py
"""
import re

src = open("execution_engine.py", encoding="utf-8").read()
lines = src.splitlines()

# Cherche la fonction run_decision_cycle
fn_start = None
for i, l in enumerate(lines):
    if re.match(r"^def\s+run_decision_cycle\b", l):
        fn_start = i
        break

if fn_start is None:
    print("[X] Fonction run_decision_cycle introuvable")
else:
    # Cherche les passages clés
    print(f"=== run_decision_cycle commence ligne {fn_start + 1} ===\n")
    
    # Trouve les lignes contenant pending_orders, INSERT INTO orders, create_and_execute
    for i in range(fn_start, min(fn_start + 400, len(lines))):
        l = lines[i]
        if (
            "pending_orders" in l
            or "INSERT INTO orders" in l
            or "create_and_execute_order" in l
            or re.match(r"^def\s+\w+", l) and i > fn_start
        ):
            print(f"{i+1:>4} | {l}")
        # Stop si on rentre dans une autre fonction
        if i > fn_start and re.match(r"^def\s+\w+", l):
            print(f"\n[Fin de run_decision_cycle détectée ligne {i+1}]")
            break

print("\n=== Contexte autour de chaque pending_orders.append ===")
for i, l in enumerate(lines):
    if "pending_orders.append" in l:
        start = max(0, i - 2)
        end = min(len(lines), i + 5)
        print(f"\n--- ligne {i+1} ---")
        for j in range(start, end):
            marker = ">>>" if j == i else "   "
            print(f"{marker} {j+1:>4} | {lines[j]}")
