# -*- coding: utf-8 -*-
# Trouve la vraie variable/fonction qui donne le chemin de la DB dans api_server.py

import re

API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"

with open(API, "r", encoding="utf-8-sig") as f:
    src = f.read()

print("=== 1) DEF/VAR DB_PATH / DB_FILE / DATABASE ===")
for m in re.finditer(r"^(DB_PATH|DB_FILE|DATABASE|DB_URL|THESIUM_DB|DB)\s*=\s*(.+)$", src, re.MULTILINE):
    line = src[:m.start()].count("\n") + 1
    print(f"  L{line:5d}  {m.group(0)[:120]}")

print()
print("=== 2) DEF db() / get_db / connect ===")
for m in re.finditer(r"^(\s*)def\s+(db|get_db|get_conn|connect)\s*\(", src, re.MULTILINE):
    line = src[:m.start()].count("\n") + 1
    print(f"  L{line:5d}  {m.group(0).strip()}")
    # Affiche les 8 lignes suivantes
    after = src[m.end():].split("\n")[:8]
    for j, l in enumerate(after):
        print(f"  L{line+j+1:5d}    {l}")
    print()

print("=== 3) sqlite3.connect(...) callsites (top 10) ===")
n = 0
for m in re.finditer(r"sqlite3\.connect\([^)]+\)", src):
    line = src[:m.start()].count("\n") + 1
    print(f"  L{line:5d}  {m.group(0)[:120]}")
    n += 1
    if n >= 10:
        break
