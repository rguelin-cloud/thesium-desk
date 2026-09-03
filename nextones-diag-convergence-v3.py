# -*- coding: utf-8 -*-
"""
[DIAG_CONVERGENCE_V3]
1. State du marker dans les DEUX fichiers PCA
2. Body complet de l'endpoint /api/construction/run dans api_server_with_static.py
3. Comment cycle_id est resolu (param body? fallback?)
4. Source du cycle_id le plus recent (decision_log? portfolio_targets_history? convergence_snapshots?)
"""
import sys
import io
import os
import sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")

PCA_ORIG = os.path.join(ROOT, "portfolio_construction_agent.py")
PCA_JAL2 = os.path.join(ROOT, "portfolio_construction_agent_jalon2.py")
API = os.path.join(ROOT, "api_server_with_static.py")

MARKER = "# [CONVERGENCE_SIZING_V1]"

# --- 1. State des deux fichiers PCA
print("=" * 70)
print("1. STATE des deux fichiers PCA")
print("=" * 70)
for path in (PCA_ORIG, PCA_JAL2):
    name = os.path.basename(path)
    if not os.path.exists(path):
        print(f"  [MISS] {name}")
        continue
    with open(path, "r", encoding="utf-8-sig") as f:
        c = f.read()
    has = MARKER in c
    nlines = c.count("\n")
    print(f"  [{('OK' if has else '--')}] {name:<45} {nlines:>5} lignes  patche={has}")

# --- 2. Endpoint /api/construction/run dans api_server_with_static.py
print("\n" + "=" * 70)
print("2. ENDPOINT /api/construction/run (api_server_with_static.py)")
print("=" * 70)
with open(API, "r", encoding="utf-8-sig") as f:
    api_lines = f.readlines()

# Trouve la route et dump 40 lignes
for i, ln in enumerate(api_lines):
    if "@app.post" in ln and "/api/construction/run" in ln:
        lo = i
        hi = min(len(api_lines), i + 45)
        print(f"\n--- Body L{i+1} a L{hi} ---")
        for j in range(lo, hi):
            print(f"  {j+1:4d} | {api_lines[j].rstrip()}")
        break

# --- 3. Sources potentielles pour cycle_id
print("\n" + "=" * 70)
print("3. TABLES contenant cycle_id (pour fallback resolution)")
print("=" * 70)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Liste les tables avec colonne cycle_id
cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
all_tables = [r["name"] for r in cur.fetchall()]
for tname in all_tables:
    try:
        cur = conn.execute(f"PRAGMA table_info({tname})")
        cols = [r["name"] for r in cur.fetchall()]
        if "cycle_id" in cols:
            # Compte + le plus recent
            cur = conn.execute(f"SELECT COUNT(*) AS n, MAX(cycle_id) AS last_cid FROM {tname}")
            r = cur.fetchone()
            # MAX peut etre alphanum pertinent vu format 'YYYYMMDD-HHMMSS'
            cur = conn.execute(
                f"SELECT cycle_id FROM {tname} WHERE cycle_id IS NOT NULL "
                f"ORDER BY rowid DESC LIMIT 1"
            )
            last_rowid = cur.fetchone()
            print(f"  {tname:<35} n={r['n']:>5}  max={r['last_cid']!r}  last_rowid={last_rowid['cycle_id'] if last_rowid else None!r}")
    except Exception as e:
        print(f"  {tname}: ERR {e}")

# --- 4. Helper convergence_snapshots : colonnes lisibles
print("\n" + "=" * 70)
print("4. SELECT realiste sur convergence_snapshots (cycle le plus recent)")
print("=" * 70)
cur = conn.execute("""
    SELECT ticker, sizing_multiplier, direction_consensus, forced_exit, drift, n_aligned, n_present
    FROM convergence_snapshots
    WHERE cycle_id = (SELECT cycle_id FROM convergence_snapshots ORDER BY rowid DESC LIMIT 1)
    ORDER BY sizing_multiplier ASC, ticker ASC
""")
print(f"\n{'TICKER':<8} {'MULT':>6} {'CONSENSUS':<14} {'FE':>3} {'DR':>3} {'N_AL':>5} {'N_PR':>5}")
print("-" * 60)
for r in cur.fetchall():
    print(f"  {r['ticker']:<6} {r['sizing_multiplier']:>6.3f}  {r['direction_consensus']:<14} {r['forced_exit']:>3} {r['drift']:>3} {r['n_aligned']:>5} {r['n_present']:>5}")

conn.close()
print("\n[OK] Diag termine.")
