#!/usr/bin/env python3
# nextones-validate-risk-v2-runtime.py
# Validation Risk Engine v2 runtime sur les 10 ordres pending du cycle 29/05
#
# Verifie :
#  1. Les 10 ordres sont bien lies a risk_checks (1:1 ou plus)
#  2. Chaque ordre a passe les 6 controles pre-trade
#  3. Les valeurs des controles sont coherentes (sizing, leverage, var, corr, drawdown, cluster)
#  4. Detail risk_checks par symbole avec status PASS/FAIL/WARN
#  5. Audit log des decisions (table risk_audit ou equivalent)

import sqlite3, json
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("RISK ENGINE V2 RUNTIME — Validation cycle 29/05/2026")
print("=" * 78)

# === 1. Discover tables related to risk ===
print("\n[1] Tables risk en base")
print("-" * 78)
cur.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND (name LIKE '%risk%' OR name LIKE '%check%' OR name LIKE '%audit%')
    ORDER BY name
""")
risk_tables = [r[0] for r in cur.fetchall()]
for t in risk_tables:
    cur.execute(f"SELECT COUNT(*) FROM {t}")
    n = cur.fetchone()[0]
    print(f"  {t:40s}  {n} rows")

# === 2. Schema de la table principale risk_checks ===
print("\n[2] Schema risk_checks (ou equivalent)")
print("-" * 78)
target_table = None
for cand in ("risk_checks", "risk_check", "pretrade_checks", "risk_audit"):
    if cand in risk_tables:
        target_table = cand
        break
if not target_table and risk_tables:
    target_table = risk_tables[0]

if target_table:
    print(f"  Table cible : {target_table}")
    cur.execute(f"PRAGMA table_info({target_table})")
    cols = cur.fetchall()
    for c in cols:
        print(f"    {c[1]:30s} {c[2]}")

# === 3. Les 10 ordres pending du cycle (IDs 4895, 4898, 4899, 4901-4907) ===
print("\n[3] 10 ordres pending du cycle 29/05")
print("-" * 78)
cur.execute("""
    SELECT id, symbol, side, qty, status, source_thesis_id, created_at
    FROM orders
    WHERE id IN (4895, 4898, 4899, 4901, 4902, 4903, 4904, 4905, 4906, 4907)
    ORDER BY id
""")
orders = cur.fetchall()
print(f"  {'ID':<6} {'SYM':<8} {'SIDE':<6} {'QTY':<10} {'STATUS':<12} {'THESIS':<8} {'CREATED'}")
for o in orders:
    print(f"  {o['id']:<6} {o['symbol']:<8} {o['side']:<6} {str(o['qty']):<10} {o['status']:<12} {str(o['source_thesis_id']):<8} {o['created_at']}")

if not orders:
    print("  AUCUN ordre trouve avec ces IDs — recheche par created_at")
    cur.execute("""
        SELECT id, symbol, side, qty, status, source_thesis_id, created_at
        FROM orders
        WHERE created_at >= '2026-05-29 10:50:00'
        ORDER BY id DESC LIMIT 15
    """)
    orders = cur.fetchall()
    for o in orders:
        print(f"  {o['id']:<6} {o['symbol']:<8} {o['side']:<6} {str(o['qty']):<10} {o['status']:<12} {str(o['source_thesis_id']):<8} {o['created_at']}")

# === 4. Risk checks attaches a chaque ordre ===
if target_table and orders:
    print(f"\n[4] Detail {target_table} par ordre")
    print("-" * 78)
    cur.execute(f"PRAGMA table_info({target_table})")
    col_names = [c[1] for c in cur.fetchall()]
    has_order_id = "order_id" in col_names
    has_symbol = "symbol" in col_names
    has_status = "status" in col_names or "result" in col_names or "decision" in col_names

    for o in orders:
        print(f"\n  --- Ordre #{o['id']} {o['symbol']} {o['side']} qty={o['qty']} ---")
        if has_order_id:
            cur.execute(f"SELECT * FROM {target_table} WHERE order_id = ?", (o['id'],))
        elif has_symbol:
            cur.execute(f"SELECT * FROM {target_table} WHERE symbol = ? AND created_at >= '2026-05-29 10:00:00' ORDER BY id DESC LIMIT 10", (o['symbol'],))
        else:
            cur.execute(f"SELECT * FROM {target_table} ORDER BY id DESC LIMIT 5")
        checks = cur.fetchall()
        if not checks:
            print(f"    AUCUN risk check trouve")
            continue
        for chk in checks:
            d = dict(chk)
            # affiche les champs cles
            cle = d.get("control") or d.get("check_name") or d.get("rule") or d.get("name", "?")
            status = d.get("status") or d.get("result") or d.get("decision") or "?"
            value = d.get("value") or d.get("metric_value") or ""
            threshold = d.get("threshold") or d.get("limit") or ""
            msg = d.get("message") or d.get("reason") or d.get("notes") or ""
            print(f"    {str(cle):<22} {str(status):<8} val={str(value):<10} lim={str(threshold):<10} {msg[:60]}")

# === 5. Stats globales : combien de PASS / FAIL / WARN ===
if target_table:
    print(f"\n[5] Stats globales {target_table} sur le cycle")
    print("-" * 78)
    cur.execute(f"PRAGMA table_info({target_table})")
    col_names = [c[1] for c in cur.fetchall()]
    status_col = next((c for c in ("status", "result", "decision") if c in col_names), None)
    if status_col:
        cur.execute(f"""
            SELECT {status_col} AS s, COUNT(*) AS n
            FROM {target_table}
            WHERE created_at >= '2026-05-29 10:00:00'
            GROUP BY {status_col}
        """)
        for r in cur.fetchall():
            print(f"  {r['s']:<12} {r['n']}")

# === 6. Verifier les 6 controles attendus ===
print(f"\n[6] Couverture des 6 controles pre-trade")
print("-" * 78)
expected_controls = [
    "sizing", "leverage", "var", "correlation", "drawdown", "cluster",
    "position_size", "leverage_limit", "var_limit", "corr_limit", "dd_limit", "cluster_limit"
]
if target_table:
    cur.execute(f"PRAGMA table_info({target_table})")
    col_names = [c[1] for c in cur.fetchall()]
    ctrl_col = next((c for c in ("control", "check_name", "rule", "name") if c in col_names), None)
    if ctrl_col:
        cur.execute(f"""
            SELECT DISTINCT {ctrl_col} AS c
            FROM {target_table}
            WHERE created_at >= '2026-05-29 10:00:00'
        """)
        found = [r['c'] for r in cur.fetchall()]
        print(f"  Controles trouves dans le cycle : {len(found)}")
        for c in found:
            print(f"    OK  {c}")
        missing = [e for e in expected_controls if e not in (found or [])]
        if missing:
            print(f"  Controles attendus non vus : {missing[:6]}")

conn.close()
print("\n" + "=" * 78)
print("FIN VALIDATION")
print("=" * 78)
