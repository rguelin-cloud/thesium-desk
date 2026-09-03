# -*- coding: utf-8 -*-
# Diag micro : dumper la signature exacte de run_pretrade_checks
# et la structure de risk_pretrade.py autour des points d'ouverture conn.

import os, re

P = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\risk_pretrade.py"

with open(P, "r", encoding="utf-8-sig") as f:
    src = f.read()

lines = src.splitlines()

def dump_around(label, pattern, before=2, after=15):
    print("=" * 72)
    print(label)
    print("-" * 72)
    rx = re.compile(pattern)
    hits = [i for i, ln in enumerate(lines) if rx.search(ln)]
    for i in hits:
        a = max(0, i - before)
        b = min(len(lines), i + after + 1)
        for j in range(a, b):
            marker = ">>" if j == i else "  "
            print(marker + " L" + str(j + 1).rjust(4) + " | " + lines[j][:200])
        print("---")

dump_around("[A] def run_pretrade_checks", r"^def\s+run_pretrade_checks", before=1, after=30)
dump_around("[B] def _conn", r"^def\s+_conn", before=1, after=20)
dump_around("[C] tous les def top-level", r"^def\s+\w+", before=0, after=0)

# Liste des fonctions qui appellent _conn
print("=" * 72)
print("[D] Appels a _conn(...)")
print("-" * 72)
for i, ln in enumerate(lines):
    if "_conn(" in ln and not ln.lstrip().startswith("def "):
        print("  L" + str(i+1) + " | " + ln[:200])

# Petites stats finales
print("=" * 72)
print("[E] Stats")
print("-" * 72)
print("Total lignes : " + str(len(lines)))
print("commit/close occurrences avec contexte ~5 lignes:")
for i, ln in enumerate(lines):
    if ".commit()" in ln or ".close()" in ln:
        # Montre 3 lignes avant
        a = max(0, i-3)
        for j in range(a, i+1):
            mk = ">>" if j == i else "  "
            print(mk + " L" + str(j+1).rjust(4) + " | " + lines[j][:160])
        print("---")
