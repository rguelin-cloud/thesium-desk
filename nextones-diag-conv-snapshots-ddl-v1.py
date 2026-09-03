# Verifie le DDL exact de replay_convergence_snapshots
# pour confirmer la convention de nom de colonne (cycle_id ou cycle_id_replay)
import os, sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=10.0)
cur = conn.cursor()

print("--- DDL replay_convergence_snapshots ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_convergence_snapshots'"
).fetchone()
print(row[0] if row else "(introuvable)")

print("\n--- DDL replay_targets ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_targets'"
).fetchone()
print(row[0] if row else "(introuvable)")

print("\n--- DDL replay_targets_history ---")
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='replay_targets_history'"
).fetchone()
print(row[0] if row else "(introuvable)")

conn.close()
