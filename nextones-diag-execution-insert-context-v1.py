"""
Diag: contexte precis autour de execution_engine.py L1350
(INSERT INTO orders + code juste apres).
Objectif : trouver l'ancre stable pour le hook justification.
"""
import os

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    lines = fh.read().splitlines()

print(f"[INFO] total lines: {len(lines)}")
print(f"[INFO] size: {os.path.getsize(F)} bytes")
print()

# Cherche l'INSERT INTO orders
target = None
for i, ln in enumerate(lines, 1):
    if "INSERT INTO orders" in ln:
        target = i
        break

if not target:
    print("[ERR] INSERT INTO orders not found")
    raise SystemExit(1)

print(f"[HIT] INSERT INTO orders at L{target}")
print()

# Contexte : 20 avant, 60 apres
start = max(1, target - 15)
end = min(len(lines), target + 80)

for i in range(start - 1, end):
    ln = lines[i]
    s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
    marker = " <-- INSERT" if i + 1 == target else ""
    print(f"L{i+1}: {s}{marker}")

print()
print("=" * 80)
print("Recherche 'conn.commit' et 'lastrowid' apres L", target)
print("=" * 80)
for i in range(target, min(len(lines), target + 100)):
    ln = lines[i]
    if any(k in ln for k in ("lastrowid", "conn.commit", "return", "cursor.execute", ".execute(")):
        s = ln.strip()[:200]
        print(f"L{i+1}: {s}")

print()
print("=" * 80)
print("Marker deja present ?")
print("=" * 80)
markers = ["[JUSTIFICATION_HOOK_V1]", "justification_builder", "build_justification"]
for m in markers:
    hits = [i+1 for i, ln in enumerate(lines) if m in ln]
    print(f"  {m}: hits={hits}")
