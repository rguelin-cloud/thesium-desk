# -*- coding: utf-8 -*-
"""Trouve la variable utilisée pour sqlite3.connect dans api_server.py"""
import re
from pathlib import Path

target = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py")
src = target.read_text(encoding="utf-8-sig")

print("=== sqlite3.connect(...) occurrences ===")
for m in re.finditer(r'sqlite3\.connect\s*\(\s*([^)]+)\s*\)', src):
    print(f"  line {src[:m.start()].count(chr(10))+1}: connect({m.group(1)})")

print("\n=== Définitions DB_* ===")
for m in re.finditer(r'(?m)^(DB_\w+|DATABASE_\w+|DB\w*PATH)\s*=\s*(.+)$', src):
    print(f"  line {src[:m.start()].count(chr(10))+1}: {m.group(0)}")

print("\n=== Imports depuis modules locaux (pour voir où est la DB) ===")
for m in re.finditer(r'(?m)^from\s+(\w+)\s+import\s+(.+)$', src):
    mod, what = m.group(1), m.group(2)
    if "db" in mod.lower() or "DB" in what or "PATH" in what:
        print(f"  line {src[:m.start()].count(chr(10))+1}: from {mod} import {what}")

print("\n=== thesium.db references ===")
for m in re.finditer(r'thesium\.db|\.db["\']\s*\)', src):
    line_no = src[:m.start()].count(chr(10))+1
    # contexte ±50 chars
    lo = max(0, m.start()-60)
    hi = min(len(src), m.end()+30)
    print(f"  line {line_no}: ...{src[lo:hi].strip()}...")

print("\n=== Helpers PPLX existants (5 premières connect lignes près de pplx) ===")
# Cherche fonctions liées à pplx
for m in re.finditer(r'def\s+(_?pplx\w+|api_pplx\w+)\s*\(', src):
    fname = m.group(1)
    fstart = m.start()
    # Look at next 800 chars for sqlite3
    chunk = src[fstart:fstart+1500]
    conn = re.search(r'sqlite3\.connect\s*\(\s*([^)]+)\s*\)', chunk)
    if conn:
        print(f"  {fname}: connect({conn.group(1)})")
