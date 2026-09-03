"""Trouve où sont construits les 'proposal' et comment la boucle est structurée
À placer dans C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\
Lance : py -3.13 _show_proposals.py
"""
import re

src = open("execution_engine.py", encoding="utf-8").read()
lines = src.splitlines()

# Trouve run_decision_cycle
fn_start = None
for i, l in enumerate(lines):
    if re.match(r"^def\s+run_decision_cycle\b", l):
        fn_start = i
        break

if fn_start is None:
    print("[X] run_decision_cycle introuvable")
    exit()

# Trouve la fin de la fonction (prochaine def au niveau 0)
fn_end = len(lines)
for i in range(fn_start + 1, len(lines)):
    if re.match(r"^def\s+\w+", lines[i]) or re.match(r"^class\s+\w+", lines[i]):
        fn_end = i
        break

print(f"=== run_decision_cycle : lignes {fn_start+1} → {fn_end} ({fn_end - fn_start} lignes) ===\n")

# Toutes les lignes contenant 'proposal' ou 'proposals' ou 'for ... in'
print("=== Mentions de 'proposal' et boucles for ===")
for i in range(fn_start, fn_end):
    l = lines[i]
    if "proposal" in l.lower() or re.match(r"\s+for\s+\w+\s+in\s+", l):
        print(f"{i+1:>4} | {l}")

print("\n=== Bloc complet lignes 520 à 575 (autour du create_and_execute) ===")
for i in range(519, min(575, fn_end)):
    print(f"{i+1:>4} | {lines[i]}")
