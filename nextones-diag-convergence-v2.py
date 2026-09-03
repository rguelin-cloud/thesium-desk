# -*- coding: utf-8 -*-
"""
[DIAG_CONVERGENCE_V2]
1. Schema exact de convergence_snapshots
2. Localiser endpoint /api/construction/run (cherche dans tous les .py)
3. Vérifier l'indentation du patch dans portfolio_construction_agent.py
"""
import sys
import io
import os
import sqlite3
import glob
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")
PCA = os.path.join(ROOT, "portfolio_construction_agent.py")

# --- 1. Schema convergence_snapshots
print("=" * 70)
print("1. SCHEMA convergence_snapshots")
print("=" * 70)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.execute("PRAGMA table_info(convergence_snapshots)")
print(f"{'NAME':<22} {'TYPE':<12} {'NN':>3} {'DFL':<10} {'PK':>3}")
print("-" * 60)
for r in cur.fetchall():
    print(f"  {r['name']:<20} {r['type']:<12} {r['notnull']:>3} {str(r['dflt_value']):<10} {r['pk']:>3}")

# Echantillon
print("\n--- Sample row ---")
cur = conn.execute("SELECT * FROM convergence_snapshots LIMIT 1")
row = cur.fetchone()
if row:
    for k in row.keys():
        print(f"  {k} = {row[k]!r}")
conn.close()

# --- 2. Endpoint /api/construction/run
print("\n" + "=" * 70)
print("2. RECHERCHE endpoint /api/construction/run")
print("=" * 70)
for path in glob.glob(os.path.join(ROOT, "*.py")):
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
    except Exception:
        continue
    if "/api/construction/run" in content:
        rel = os.path.basename(path)
        print(f"\n--- {rel} ---")
        for i, ln in enumerate(content.split("\n"), 1):
            if "/api/construction/run" in ln or "run_construction_agent" in ln:
                print(f"  L{i}: {ln.rstrip()}")
    if "run_construction_agent" in content and "/api/construction/run" not in content:
        rel = os.path.basename(path)
        print(f"\n--- {rel} (run_construction_agent only) ---")
        for i, ln in enumerate(content.split("\n"), 1):
            if "run_construction_agent" in ln:
                print(f"  L{i}: {ln.rstrip()}")

# --- 3. Indentation du patch
print("\n" + "=" * 70)
print("3. INDENTATION du patch dans portfolio_construction_agent.py")
print("=" * 70)
with open(PCA, "r", encoding="utf-8-sig") as f:
    pca_lines = f.readlines()

# Trouve le bloc autour du marker
for i, ln in enumerate(pca_lines):
    if "[CONVERGENCE_SIZING_V1]" in ln and "Application" in ln:
        # Dump L-3 a L+12 avec longueur indent visible
        lo = max(0, i - 3)
        hi = min(len(pca_lines), i + 12)
        print(f"\n--- Contexte autour de L{i+1} ---")
        for j in range(lo, hi):
            line = pca_lines[j].rstrip("\n")
            indent = len(line) - len(line.lstrip(" "))
            marker = ">>>" if j == i else "   "
            print(f"  {marker} {j+1:4d} [{indent:>2}sp] | {line}")
        break

# Trouve aussi softmax_allocate appel
for i, ln in enumerate(pca_lines):
    if "raw_alloc = softmax_allocate(" in ln:
        line = ln.rstrip("\n")
        indent = len(line) - len(line.lstrip(" "))
        print(f"\n  REF L{i+1} [{indent:>2}sp] | {line}")
        break

print("\n[OK] Diag termine.")
