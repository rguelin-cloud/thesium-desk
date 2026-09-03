"""
Diag: dump tous les markers SHADOW_UI dans app.js + contexte autour
des occurrences r.id / shadowRowsCache / recoBadge pour comprendre
la structure reelle.
"""
import os
import re

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

lines = src.splitlines()
print("[INFO] total lines:", len(lines))
print("[INFO] total bytes:", len(src))
print()

# 1) Toutes les lignes qui contiennent SHADOW_UI (case-insensitive)
print("=== Lignes contenant 'SHADOW_UI' (case-insensitive) ===")
for i, ln in enumerate(lines, 1):
    if re.search(r"SHADOW_UI", ln, re.IGNORECASE):
        # tronque a 200 chars
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 2) Toutes les lignes contenant shadowRowsCache
print("=== Lignes contenant 'shadowRowsCache' ===")
for i, ln in enumerate(lines, 1):
    if "shadowRowsCache" in ln:
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 3) Toutes les lignes contenant recoBadge
print("=== Lignes contenant 'recoBadge' ===")
for i, ln in enumerate(lines, 1):
    if "recoBadge" in ln:
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 4) Toutes occurrences de r.id (en JS, donc avec un point devant id)
print("=== Lignes contenant 'r.id' (regex \\br\\.id\\b) ===")
for i, ln in enumerate(lines, 1):
    if re.search(r"\br\.id\b", ln):
        s = ln if len(ln) <= 200 else ln[:200] + "...[TRUNC]"
        print(f"L{i}: {s}")
print()

# 5) Comptes globaux
print("=== Counts globaux ===")
print("shadowRowsCache[r.id]:", src.count("shadowRowsCache[r.id]"))
print("shadowRowsCache[r.variant_id]:", src.count("shadowRowsCache[r.variant_id]"))
print("r.id count (regex):", len(re.findall(r"\br\.id\b", src)))
print("r.variant_id count:", src.count("r.variant_id"))
