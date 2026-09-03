# Diag : recupere DDL exact replay_runs + replay_cycles + signature ReplayOrchestrator
import os, sqlite3, sys, inspect

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD_DIR, "thesium.db")
sys.path.insert(0, PROD_DIR)

print("=" * 70)
print("DIAG schema replay actuel + signature orchestrator")
print("=" * 70)

conn = sqlite3.connect(DB, timeout=10.0)
cur = conn.cursor()

for tbl in ["replay_runs", "replay_cycles"]:
    print(f"\n--- {tbl} ---")
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (tbl,)
    ).fetchone()
    if row:
        print(row[0])
    else:
        print("  NOT FOUND")
    print("  columns :")
    for r in cur.execute(f"PRAGMA table_info({tbl})").fetchall():
        print(f"    {r[1]:<25s} {r[2]}")

conn.close()

print("\n--- ReplayOrchestrator.__init__ signature ---")
from replay_orchestrator import ReplayOrchestrator
sig = inspect.signature(ReplayOrchestrator.__init__)
print(f"  {sig}")
print(f"  params:")
for name, p in sig.parameters.items():
    print(f"    {name:<25s} default={p.default}")

print("\n--- ReplayOrchestrator.run_replay signature ---")
sig2 = inspect.signature(ReplayOrchestrator.run_replay)
print(f"  {sig2}")
for name, p in sig2.parameters.items():
    print(f"    {name:<25s} default={p.default}")
