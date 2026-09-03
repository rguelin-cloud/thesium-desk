# diag_realized_score.py
# Verifier ou run_construction_agent est appele et si compute_realized_score est branche

import sqlite3
import re
from pathlib import Path

# 1. Verifier snapshot actuel
db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

print("=" * 70)
print("Snapshots dans portfolio_targets_history")
print("=" * 70)
cur.execute("""
    SELECT snapshot_id, COUNT(*) as n_rows, MIN(created_at) as ts
    FROM portfolio_targets_history
    GROUP BY snapshot_id
    ORDER BY ts DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[0]:40s}  n={row[1]:4d}  ts={row[2]}")

print()
print("=" * 70)
print("Snapshot le plus recent - sample R_norm")
print("=" * 70)
cur.execute("""
    SELECT snapshot_id FROM portfolio_targets_history
    ORDER BY created_at DESC LIMIT 1
""")
last_snap = cur.fetchone()[0]
print(f"  snapshot_id = {last_snap}")

cur.execute(f"PRAGMA table_info(portfolio_targets_history)")
cols = [c[1] for c in cur.fetchall()]
print(f"  cols = {cols}")

# Chercher colonne R_norm ou similar
r_cols = [c for c in cols if "r" in c.lower() or "real" in c.lower() or "norm" in c.lower()]
print(f"  R-related cols : {r_cols}")

cur.execute(f"""
    SELECT * FROM portfolio_targets_history
    WHERE snapshot_id = ?
    LIMIT 5
""", (last_snap,))
for row in cur.fetchall():
    print(f"  {dict(zip(cols, row))}")

con.close()

# 2. Chercher dans portfolio_construction_agent_jalon2.py
print()
print("=" * 70)
print("PCA jalon2 - chercher compute_realized_score / enable_realized")
print("=" * 70)
pca = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py")
if pca.exists():
    content = pca.read_text(encoding="utf-8-sig")
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if any(k in line for k in ["compute_realized", "enable_realized", "score_R", "R_norm", "w_realized", "[score_R]"]):
            if not line.strip().startswith("#"):
                print(f"  L{i+1:5d}: {line.rstrip()[:120]}")
else:
    print("  PCA file introuvable")

# 3. Chercher la fonction run_construction_agent
print()
print("=" * 70)
print("Fonctions definies dans PCA")
print("=" * 70)
if pca.exists():
    for i, line in enumerate(lines):
        if re.match(r"^\s*(def|async def)\s+", line):
            print(f"  L{i+1:5d}: {line.rstrip()[:120]}")
