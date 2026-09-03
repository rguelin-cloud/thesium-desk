"""Diag : schema shadow_diff_log + repere d'integration dans scheduler prod."""
import sqlite3, os, re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

print("=== SCHEMA shadow_diff_log ===")
conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()
cur.execute("PRAGMA table_info(shadow_diff_log)")
for c in cur.fetchall():
    print(f"  {c[1]:30s} {c[2]:15s} nn={c[3]} pk={c[5]}")

cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='shadow_diff_log'")
print("\n=== INDEXES ===")
for r in cur.fetchall():
    print(f"  {r[0]}")

# Repere : ou est appele run_decision_cycle dans scheduler ?
print("\n=== SCHEDULER : appels run_decision_cycle / execute_cycle ===")
for fname in ["scheduler.py", "api_server_with_static.py"]:
    fpath = os.path.join(ROOT, fname)
    if not os.path.exists(fpath):
        continue
    print(f"\n--- {fname} ---")
    with open(fpath, "rb") as f:
        data = f.read().decode("utf-8-sig", errors="replace")
    lines = data.split("\n")
    for i, ln in enumerate(lines, 1):
        if re.search(r"(run_decision_cycle|execute_cycle|run_cycle)\s*\(", ln):
            print(f"  L{i}: {ln.strip()[:120]}")

# Last 2 cycles prod pour test Phase 9.4
print("\n=== 2 derniers cycles prod ===")
cur.execute("""
    SELECT cycle_id, COUNT(*) as n FROM convergence_snapshots
    GROUP BY cycle_id ORDER BY cycle_id DESC LIMIT 5
""")
for r in cur.fetchall():
    print(f"  {r[0]:25s} n={r[1]}")

conn.close()
