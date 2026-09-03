# diag_realized_v2.py - utf8 safe
import sqlite3
import json
import re
import sys
import io
from pathlib import Path

# Force utf-8 stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
cur = con.cursor()

print("=" * 70)
print("Sample components_json du dernier snapshot")
print("=" * 70)
cur.execute("""
    SELECT snapshot_id FROM portfolio_targets_history
    ORDER BY created_at DESC LIMIT 1
""")
last_snap = cur.fetchone()[0]
print(f"snapshot = {last_snap}")
print()

cur.execute("""
    SELECT ticker, score, target_weight_pct, prev_target_weight_pct,
           regime, included, cap_floor_applied, components_json
    FROM portfolio_targets_history
    WHERE snapshot_id = ?
    ORDER BY ticker
""", (last_snap,))

for row in cur.fetchall():
    ticker, score, tw, ptw, regime, inc, cap, comp = row
    print(f"--- {ticker} ---")
    print(f"  score={score} tw={tw} ptw={ptw} regime={regime} included={inc} cap={cap}")
    if comp:
        try:
            d = json.loads(comp)
            for k, v in d.items():
                # remplacer fleche par ->
                sv = str(v).replace("\u2192", "->").replace("\u2265", ">=").replace("\u2264", "<=")
                print(f"  {k} = {sv}")
        except Exception as e:
            print(f"  components_json parse error: {e}")
            safe = comp.replace("\u2192", "->")[:200]
            print(f"  raw: {safe}")
    print()

con.close()

# Chercher dans PCA jalon2
print("=" * 70)
print("PCA jalon2 - lignes cles")
print("=" * 70)
pca = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\portfolio_construction_agent_jalon2.py")
if pca.exists():
    content = pca.read_text(encoding="utf-8-sig")
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if any(k in line for k in ["compute_realized", "enable_realized", "score_R", "R_norm",
                                   "w_realized", "[score_R]", "[pca_jalon2]", "snapshot_id"]):
            if not line.strip().startswith("#"):
                safe = line.rstrip()[:140].replace("\u2192", "->")
                print(f"  L{i+1:5d}: {safe}")
    print()
    print("=" * 70)
    print("Fonctions definies dans PCA jalon2")
    print("=" * 70)
    for i, line in enumerate(lines):
        if re.match(r"^\s*(def|async def)\s+", line):
            safe = line.rstrip()[:120].replace("\u2192", "->")
            print(f"  L{i+1:5d}: {safe}")

# Chercher si run_construction_agent est appele depuis execution_engine
print()
print("=" * 70)
print("Appels a run_construction_agent / PCA depuis execution_engine.py")
print("=" * 70)
ee = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py")
if ee.exists():
    content = ee.read_text(encoding="utf-8-sig")
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if any(k in line for k in ["run_construction_agent", "construction_agent",
                                   "portfolio_construction", "snapshot_id", "PortfolioConstructionAgent"]):
            if not line.strip().startswith("#"):
                safe = line.rstrip()[:140].replace("\u2192", "->")
                print(f"  L{i+1:5d}: {safe}")
