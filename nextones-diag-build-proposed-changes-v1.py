"""
Diag _build_proposed_changes_section dans memo_generator.py.
Dump la fonction complete pour identifier :
- Le SELECT sur orders
- Le format de la table markdown (headers, row template)
- Ou inserer la colonne Justification
"""
import os
import re

F = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\memo_generator.py"

with open(F, "r", encoding="utf-8-sig", errors="replace") as fh:
    src = fh.read()

print("[INFO] size:", len(src))
print()

# Trouve la fonction
m = re.search(r"def\s+_build_proposed_changes_section\b", src)
if not m:
    print("[ERR] _build_proposed_changes_section not found")
    # cherche variantes
    for pat in ["proposed_changes", "Proposed Changes", "_build_proposed", "def _build_"]:
        print(f"\n[SEARCH] {pat!r} :")
        for mm in re.finditer(re.escape(pat), src):
            ln = src[:mm.start()].count("\n") + 1
            print(f"  L{ln}")
    raise SystemExit(1)

start = m.start()
start_line = src[:start].count("\n") + 1
print(f"[FOUND] _build_proposed_changes_section at line {start_line}")
print()

# Cherche la fin de la fonction (prochaine def ou class au meme niveau d'indentation)
# Estime la fin en scannant les lignes suivantes
lines = src.splitlines()
end_line = None
for i in range(start_line, min(len(lines), start_line + 200)):
    ln = lines[i]
    # nouvelle def au meme niveau (0 indent) = fin de la fonction
    if i > start_line and re.match(r"^(def|class)\s+", ln):
        end_line = i
        break

if end_line is None:
    end_line = min(len(lines), start_line + 150)

print(f"[DUMP] lignes {start_line} a {end_line} :")
print("-" * 80)
for i in range(start_line - 1, end_line):
    print(f"L{i+1:5d}: {lines[i][:220]}")

print()
print(f"[INFO] fonction s'etend de L{start_line} a ~L{end_line}")

# Cherche aussi le SELECT sur orders dans le fichier
print()
print("[SELECT sur orders dans memo_generator.py]")
for m in re.finditer(r"SELECT[^;]*?FROM\s+orders", src, re.IGNORECASE | re.DOTALL):
    ln = src[:m.start()].count("\n") + 1
    snippet = m.group(0)[:200].replace("\n", " ")
    print(f"  L{ln}: {snippet}")
