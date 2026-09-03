# -*- coding: utf-8 -*-
# nextones-test-diff-engine-v1.py
# Test standalone du module diff_engine.py :
#   - prend le dernier cycle de regime_log
#   - calcule diff J-1 et J-7
#   - dump JSON brut dans diff_test_dump.json
#   - dump markdown rendu dans diff_test_memo.md
#   - imprime aussi en console

import os
import sys
import json
import sqlite3

# Permettre import diff_engine pose dans le meme dossier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
OUT_JSON = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\diff_test_dump.json"
OUT_MD   = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\diff_test_memo.md"

try:
    from diff_engine import compute_cycle_diff, render_diff_markdown
except ImportError as e:
    print(f"[test] ERROR: cannot import diff_engine: {e}")
    print(f"[test] Make sure diff_engine.py is in the same folder as this script.")
    sys.exit(1)

print("=" * 70)
print("TEST diff_engine.py")
print("=" * 70)
print(f"DB : {DB}")

conn = sqlite3.connect(DB)
row = conn.execute("SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
if not row:
    print("[test] No cycles in regime_log")
    sys.exit(1)
cid = row[0]
print(f"Latest cycle : {cid}")
print()

# Compte les cycles disponibles
ncycles = conn.execute("SELECT COUNT(DISTINCT cycle_id) FROM regime_log").fetchone()[0]
print(f"Total cycles in regime_log : {ncycles}")

# Verif history tables
for tbl in ("factor_quality_history", "pplx_geo_history", "crypto_context_history"):
    n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    last = conn.execute(f"SELECT MAX(cycle_id) FROM {tbl}").fetchone()[0]
    print(f"  {tbl} : {n} rows, last={last}")
print()

# Calcul diff
print("Computing diff J-1 ...")
d1 = compute_cycle_diff(conn, cid, ref="J-1")
print("Computing diff J-7 ...")
d7 = compute_cycle_diff(conn, cid, ref="J-7")

# Dump JSON
dump = {"diff_j1": d1, "diff_j7": d7}
with open(OUT_JSON, "w", encoding="utf-8", newline="") as f:
    json.dump(dump, f, indent=2, ensure_ascii=False, default=str)
print(f"JSON dump -> {OUT_JSON}")

# Dump markdown
md = render_diff_markdown(d1, d7)
with open(OUT_MD, "w", encoding="utf-8", newline="") as f:
    f.write(md)
print(f"Markdown   -> {OUT_MD}")
print()
print("=" * 70)
print("MARKDOWN PREVIEW")
print("=" * 70)
print(md)
print()
print("=" * 70)
print("SUMMARY LINES")
print("=" * 70)
print(f"J-1 : {d1.get('summary_line', '?')}")
print(f"J-7 : {d7.get('summary_line', '?')}")

conn.close()
print()
print("DONE.")
