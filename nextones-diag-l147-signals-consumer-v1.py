"""
Diag : voir ce que fait data_crypto.py L147 (le call unique de fetch_crypto_signals)
+ le retour et son consommateur (endpoint API probable).
"""
import os
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\data_crypto.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    lines = fh.read().splitlines()

print("[DUMP] data_crypto.py L140-L200 (contexte call fetch_crypto_signals)")
print("-" * 78)
for i in range(139, min(200, len(lines))):
    print(f"L{i+1:5d}  {lines[i][:200]}")

print()

# Cherche endpoints API qui utilisent crypto_overview ou similaire
print("[STAGE 2] Endpoints API consommant les signals")
for candidate in ["api_server.py", "api_server_with_static.py"]:
    fp = os.path.join(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk", candidate)
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8-sig", errors="replace") as fh:
        src = fh.read()

    # cherche imports data_crypto.* et fetch_crypto_signals
    for m in re.finditer(r"(data_crypto\.\w+|fetch_crypto_signals|crypto_overview|/api/crypto)", src):
        ln = src[:m.start()].count("\n") + 1
        line_start = src.rfind("\n", 0, m.start()) + 1
        line_end = src.find("\n", m.end())
        print(f"  {candidate}:L{ln}: {src[line_start:line_end].strip()[:180]}")
