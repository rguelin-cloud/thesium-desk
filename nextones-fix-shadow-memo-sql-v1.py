# -*- coding: utf-8 -*-
"""
Fix bug SQL dans shadow_memo_generator.py :
  - shadow_variants n'a pas de col 'id', mais 'variant_id'.
  - JOIN doit etre v.variant_id = p.variant_id

Avant patch, dump PRAGMA shadow_variants pour confirmer.
"""
import os
import re
import shutil
import sqlite3
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
SRC = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\shadow_memo_generator.py"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK = "# [SHADOW_MEMO_SQL_FIX_V1]"

# 1. Confirm schema
print("=== PRAGMA table_info(shadow_variants) ===")
conn = sqlite3.connect(DB, timeout=10.0)
try:
    cur = conn.execute("PRAGMA table_info(shadow_variants)")
    cols = cur.fetchall()
    for c in cols:
        print("  ", c)
    col_names = [c[1] for c in cols]
    print("Cols :", col_names)
    pk_candidate = None
    for c in cols:
        if c[5] == 1:  # pk
            pk_candidate = c[1]
            break
    print("PK :", pk_candidate)
finally:
    conn.close()
print()

# 2. Patch source
with open(SRC, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

if MARK in src:
    print("[SKIP] marker fix deja present")
else:
    OLD = "LEFT JOIN shadow_variants v ON v.id = p.variant_id "
    NEW = "LEFT JOIN shadow_variants v ON v.variant_id = p.variant_id " + MARK + " "
    if OLD not in src:
        print("[ERR] bloc OLD introuvable")
        # Aide diagnostic
        for line in src.split("\n"):
            if "LEFT JOIN" in line or "shadow_variants v" in line:
                print("  found:", line.strip())
    else:
        bak = SRC + ".bak." + TS
        shutil.copy2(SRC, bak)
        print("[BAK]", bak)
        new = src.replace(OLD, NEW, 1)
        with open(SRC, "w", encoding="utf-8", newline="") as f:
            f.write(new)
        print("[OK] SQL patche, delta=", len(new) - len(src), "chars")

print()
print("Next : py -3.13 .\\shadow_memo_generator.py --force")
print("DONE")
