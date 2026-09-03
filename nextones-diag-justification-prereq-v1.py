"""
Diag prereq: Justification BUY/SELL dans Pending Approvals + Proposed Changes.

Objectifs:
1) Schema orders complet (colonnes dispo pour stocker la note)
2) Est-ce qu'il existe deja une colonne 'justification' / 'memo' / 'rationale' ?
3) Localiser create_and_execute_order (point d'insertion) et son body
4) Verifier que convergence_snapshots, market_regime_log, agents_output
   existent pour recuperer les inputs de la note
5) Endpoint API qui renvoie Pending Approvals + Proposed Changes (grep)
6) Dernier ordre execute (pour voir ce qu'on a comme donnees en pratique)
"""
import os
import sqlite3
import re

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server_with_static.py"
UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"

print("=" * 80)
print("1) SCHEMA TABLE orders")
print("=" * 80)
conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("PRAGMA table_info(orders)")
cols_orders = cur.fetchall()
for r in cols_orders:
    print(f"  {r['cid']:2d} {r['name']:35s} {r['type']:15s} pk={r['pk']} notnull={r['notnull']}")

col_names_orders = [r['name'] for r in cols_orders]
print()
print("  justification present:", "justification" in col_names_orders)
print("  memo present:", "memo" in col_names_orders)
print("  rationale present:", "rationale" in col_names_orders)
print("  risk_notes present:", "risk_notes" in col_names_orders)

print()
print("=" * 80)
print("2) TABLES PERTINENTES (existence + colonnes cle)")
print("=" * 80)
for tbl in ["convergence_snapshots", "market_regime_log", "agents_output",
            "shadow_variants", "targets", "positions", "portfolio_positions"]:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
    exists = cur.fetchone() is not None
    print(f"  {tbl}: exists={exists}")
    if exists:
        cur.execute(f"PRAGMA table_info({tbl})")
        cols = [r['name'] for r in cur.fetchall()]
        print(f"    cols: {cols}")

print()
print("=" * 80)
print("3) DERNIER ORDRE EXECUTE (contenu reel)")
print("=" * 80)
cur.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 3")
for row in cur.fetchall():
    d = dict(row)
    print()
    print(f"--- order id={d.get('id')} ---")
    for k, v in d.items():
        s = str(v)
        if len(s) > 200:
            s = s[:200] + "...[TRUNC]"
        print(f"  {k}: {s}")

print()
print("=" * 80)
print("4) DERNIER convergence_snapshot")
print("=" * 80)
try:
    cur.execute("SELECT * FROM convergence_snapshots ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        d = dict(row)
        for k, v in d.items():
            s = str(v)
            if len(s) > 300:
                s = s[:300] + "...[TRUNC]"
            print(f"  {k}: {s}")
    else:
        print("  (empty)")
except Exception as e:
    print("  ERR:", e)

print()
print("=" * 80)
print("5) DERNIER market_regime_log")
print("=" * 80)
try:
    cur.execute("SELECT * FROM market_regime_log ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    if row:
        d = dict(row)
        for k, v in d.items():
            s = str(v)
            if len(s) > 200:
                s = s[:200] + "...[TRUNC]"
            print(f"  {k}: {s}")
    else:
        print("  (empty)")
except Exception as e:
    print("  ERR:", e)

conn.close()

print()
print("=" * 80)
print("6) API - endpoints Pending Approvals + Proposed Changes")
print("=" * 80)
if os.path.exists(API):
    with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
        api_src = f.read()
    api_lines = api_src.splitlines()

    patterns = [
        (r"/api/orders/pending", "pending endpoint"),
        (r"/api/orders/approvals", "approvals endpoint"),
        (r"pending.approval", "pending approval string"),
        (r"proposed.changes", "proposed changes"),
        (r"def create_and_execute_order", "func def"),
        (r"def approve_order", "approve func"),
    ]
    for pat, label in patterns:
        matches = []
        for i, ln in enumerate(api_lines, 1):
            if re.search(pat, ln, re.IGNORECASE):
                matches.append((i, ln.strip()[:180]))
        print(f"\n  [{label}] pattern={pat!r} matches={len(matches)}")
        for i, ln in matches[:6]:
            print(f"    L{i}: {ln}")
else:
    print("  api file missing:", API)

print()
print("=" * 80)
print("7) UI - localisation Pending Approvals + Proposed Changes")
print("=" * 80)
if os.path.exists(UI):
    with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
        ui_src = f.read()
    ui_lines = ui_src.splitlines()
    patterns = [
        (r"Pending Approvals", "PA card title"),
        (r"Proposed Changes", "PC section title"),
        (r"pending-approvals", "PA id/class"),
        (r"RISK NOTES", "risk notes col"),
        (r"renderPendingApprovals", "PA render"),
        (r"renderProposed", "PC render"),
    ]
    for pat, label in patterns:
        matches = []
        for i, ln in enumerate(ui_lines, 1):
            if re.search(pat, ln, re.IGNORECASE):
                matches.append((i, ln.strip()[:180]))
        print(f"\n  [{label}] pattern={pat!r} matches={len(matches)}")
        for i, ln in matches[:6]:
            print(f"    L{i}: {ln}")
else:
    print("  ui file missing:", UI)

print()
print("[DONE]")
