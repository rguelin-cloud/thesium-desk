# -*- coding: utf-8 -*-
# Diag : signature complete de run_construction_agent + apply_convergence_sizing
# (les 2 fonctions principales a appeler en wrapper 8B.2)
import os, re

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
path = os.path.join(PROD_DIR, "portfolio_construction_agent.py")
with open(path, "r", encoding="utf-8-sig") as f:
    src = f.read()
lines = src.split("\n")

# Affiche L873 + 60 lignes pour voir la signature complete + premiere logique
print("=" * 78)
print("run_construction_agent (L873+)")
print("=" * 78)
for i in range(872, min(940, len(lines))):
    print(f"  L{i+1:4d}: {lines[i]}")

print("\n" + "=" * 78)
print("apply_convergence_sizing (L618+)")
print("=" * 78)
for i in range(617, min(685, len(lines))):
    print(f"  L{i+1:4d}: {lines[i]}")

# Cherche le return de run_construction_agent (ou la fin via prochaine def)
print("\n" + "=" * 78)
print("Fin de run_construction_agent : return statements + prochaine def")
print("=" * 78)
m = re.search(r"^def\s+run_construction_agent\s*\(", src, re.MULTILINE)
if m:
    start = m.start()
    # Cherche la prochaine def top-level (ligne commencant par 'def ')
    next_def = re.search(r"^def\s+", src[m.end():], re.MULTILINE)
    if next_def:
        end = m.end() + next_def.start()
    else:
        end = len(src)
    body = src[start:end]
    # Tous les return
    for rm in re.finditer(r"^(\s*)return\b(.*)$", body, re.MULTILINE):
        rel_line = body[:rm.start()].count("\n")
        abs_line = src[:start].count("\n") + 1 + rel_line
        print(f"  L{abs_line:4d}: return {rm.group(2).strip()[:120]}")

# Cherche save_convergence_snapshot (L619)
print("\n" + "=" * 78)
print("save_convergence_snapshot (L619+)")
print("=" * 78)
path_ce = os.path.join(PROD_DIR, "convergence_engine.py")
with open(path_ce, "r", encoding="utf-8-sig") as f:
    src_ce = f.read()
lines_ce = src_ce.split("\n")
for i in range(618, min(660, len(lines_ce))):
    print(f"  L{i+1:4d}: {lines_ce[i]}")
