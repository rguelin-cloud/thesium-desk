# find_insert_orders.py
# Localise tous les INSERT INTO orders + le code de cast quantite dans le repo

import os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

# Cherche tous les .py qui contiennent "INTO orders" ou "INSERT" + "orders"
print("=" * 70)
print("FICHIERS .py contenant 'INTO orders' ou 'orders' + INSERT")
print("=" * 70)

hits = []
for root, dirs, files in os.walk(ROOT):
    # skip backups
    parts = set(p.lower() for p in root.split(os.sep))
    if "_backups" in parts or "_backups_reset" in parts or "__pycache__" in parts or ".venv" in parts or "venv" in parts:
        continue
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                content = f.read()
        except Exception:
            continue
        if re.search(r"INSERT\s+INTO\s+orders", content, re.IGNORECASE):
            hits.append(path)

for h in hits:
    print(f"  {h}")

print()
print("=" * 70)
print("EXTRAITS - contexte autour de chaque INSERT INTO orders")
print("=" * 70)

for path in hits:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().split("\n")
    for i, ln in enumerate(lines):
        if re.search(r"INSERT\s+INTO\s+orders", ln, re.IGNORECASE):
            start = max(0, i - 12)
            end = min(len(lines), i + 20)
            print(f"\n--- {os.path.basename(path)} : match L{i+1} ---")
            for k in range(start, end):
                marker = ">>>" if k == i else "   "
                print(f"  {marker} L{k+1:04d}| {lines[k]}")

print()
print("=" * 70)
print("CAST quantite : int(...) / floor(...) / round(...) avant INSERT")
print("=" * 70)
# Cherche les patterns qui cassent la qty fractionnaire dans execution_engine.py
target = os.path.join(ROOT, "execution_engine.py")
if os.path.exists(target):
    with open(target, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = f.read().split("\n")
    # On cherche dans la fonction qui construit l'order
    patterns = [
        (r"int\s*\(\s*[^)]*qty", "int(qty)"),
        (r"int\s*\(\s*[^)]*quantity", "int(quantity)"),
        (r"math\.floor\s*\(\s*qty", "floor(qty)"),
        (r"quantity\s*=\s*int\(", "quantity = int("),
        (r"\"quantity\"\s*:\s*int", '"quantity": int'),
    ]
    for i, ln in enumerate(lines):
        for pat, label in patterns:
            if re.search(pat, ln):
                start = max(0, i - 3)
                end = min(len(lines), i + 4)
                print(f"\n--- execution_engine.py : pattern '{label}' L{i+1} ---")
                for k in range(start, end):
                    marker = ">>>" if k == i else "   "
                    print(f"  {marker} L{k+1:04d}| {lines[k]}")
                break
