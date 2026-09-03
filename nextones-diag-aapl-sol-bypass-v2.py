"""
Diag v2 : pourquoi AAPL et SOL ont target != 0 malgre sizing_multiplier=0 ?

v1 a confirme : snapshot OK pour tous (mult=0, forced_exit=1).
=> Le bug est dans apply_convergence_sizing OU une etape posterieure.

Cette v2 :
  1. Inspecte schema portfolio_targets
  2. Dump complet AAPL/SOL/AMZN/BTC depuis portfolio_targets
  3. Cherche tous les UPDATE portfolio_targets dans le code
  4. Tracer les write paths

ASCII pur.
"""
import os
import re
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 1. Schema portfolio_targets
print("=== Schema portfolio_targets ===")
rows = cur.execute("PRAGMA table_info(portfolio_targets)").fetchall()
cols = [r["name"] for r in rows]
print("Colonnes :", cols)

# 2. Dump complet AAPL/SOL/AMZN/BTC/HYPE/ZEC
print("\n=== portfolio_targets complet (AAPL, SOL, AMZN, BTC, HYPE, ZEC, ETH) ===")
rows = cur.execute(
    "SELECT * FROM portfolio_targets WHERE ticker IN "
    "('AAPL','SOL','AMZN','BTC','HYPE','ZEC','ETH','GOOGL','LINK') "
    "ORDER BY ticker"
).fetchall()
for r in rows:
    print("\n--- " + r["ticker"] + " ---")
    for c in cols:
        v = r[c]
        if v is not None and isinstance(v, str) and len(v) > 80:
            v = v[:80] + "..."
        print("  {} = {}".format(c, v))

# 3. Chercher tous les UPDATE/INSERT portfolio_targets dans le code prod
print("\n\n=== UPDATE/INSERT portfolio_targets dans le code prod ===")
patterns = [
    re.compile(r"UPDATE\s+portfolio_targets", re.IGNORECASE),
    re.compile(r"INSERT\s+INTO\s+portfolio_targets", re.IGNORECASE),
    re.compile(r"REPLACE\s+INTO\s+portfolio_targets", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM\s+portfolio_targets", re.IGNORECASE),
]
for root, dirs, files in os.walk(PROD):
    # Skip backups
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules")]
    for fn in files:
        if not fn.endswith(".py"):
            continue
        if ".bak." in fn:
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, "r", encoding="utf-8-sig", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            for pat in patterns:
                if pat.search(line):
                    rel = os.path.relpath(fp, PROD)
                    print("  {} L{}: {}".format(rel, i, line.strip()[:120]))
                    break

# 4. Comparer AAPL/SOL vs ETH/BTC dans target_construction_config
print("\n\n=== target_construction_config ===")
try:
    rows = cur.execute("SELECT * FROM target_construction_config").fetchall()
    for r in rows:
        d = dict(r)
        print(d)
except Exception as e:
    print("Erreur :", e)

# 5. Tous les forced_exit du dernier cycle + valeurs targets actuelles
print("\n=== Cross-check : forced_exit du dernier cycle vs target ===")
last_cid_row = cur.execute(
    "SELECT cycle_id FROM convergence_snapshots ORDER BY rowid DESC LIMIT 1"
).fetchone()
if last_cid_row:
    cid = last_cid_row["cycle_id"]
    print("Cycle :", cid)
    snaps = cur.execute(
        "SELECT ticker, sizing_multiplier, forced_exit, direction_consensus "
        "FROM convergence_snapshots WHERE cycle_id = ? AND forced_exit = 1",
        (cid,)
    ).fetchall()
    for s in snaps:
        tk = s["ticker"]
        t = cur.execute(
            "SELECT target_weight_pct, updated_at FROM portfolio_targets WHERE ticker = ?",
            (tk,)
        ).fetchone()
        if t:
            ok = "[OK]" if t["target_weight_pct"] == 0 else "[FAIL]"
            print("  {} snap_mult={} target={} {} updated={}".format(
                tk, s["sizing_multiplier"], t["target_weight_pct"], ok, t["updated_at"]))
        else:
            print("  {} snap_mult={} target=ABSENT".format(tk, s["sizing_multiplier"]))

con.close()
print("\n[DONE]")
