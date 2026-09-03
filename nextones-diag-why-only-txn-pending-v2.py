# -*- coding: utf-8 -*-
"""
Diag v2 : detecter dynamiquement la colonne symbole dans instruments.
"""
import sqlite3
import os
import re

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Detection auto de la colonne symbole
cols = [r["name"] for r in cur.execute("PRAGMA table_info(instruments)").fetchall()]
print(f"Colonnes instruments : {cols}")
SYM_COL = None
for cand in ("ticker", "symbol", "code", "name"):
    if cand in cols:
        SYM_COL = cand
        break
if not SYM_COL:
    print("ERREUR : aucune colonne symbole trouvee")
    con.close()
    raise SystemExit(1)
print(f"Colonne symbole utilisee : instruments.{SYM_COL}")
print()

ORDER_IDS = [336, 337, 338, 339, 342, 343, 344, 345, 346, 347]
ph = ",".join("?" * len(ORDER_IDS))

print("=" * 80)
print("1. ETAT ACTUEL DES 10 ORDERS RECENTS")
print("=" * 80)
rows = cur.execute(f"""
    SELECT o.id, i.{SYM_COL} AS ticker, o.side, o.quantity, o.status,
           o.cycle_id, o.created_at, o.validated_at, o.validated_by
    FROM orders o
    LEFT JOIN instruments i ON i.id = o.instrument_id
    WHERE o.id IN ({ph})
    ORDER BY o.id
""", ORDER_IDS).fetchall()
for r in rows:
    print(f"  #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} qty={r['quantity']:<4} "
          f"status={r['status']:<22} cycle={r['cycle_id']} "
          f"created={r['created_at']} validated_by={r['validated_by']}")

print()
print("=" * 80)
print("2. DISTRIBUTION PAR CYCLE_ID (10 ordres recents)")
print("=" * 80)
rows = cur.execute(f"""
    SELECT cycle_id, status, COUNT(*) AS n
    FROM orders
    WHERE id IN ({ph})
    GROUP BY cycle_id, status
    ORDER BY cycle_id, status
""", ORDER_IDS).fetchall()
for r in rows:
    print(f"  cycle={str(r['cycle_id']):<25} status={r['status']:<22} n={r['n']}")

print()
print("=" * 80)
print("3. LE DERNIER CYCLE : quels ordres a-t-il produit ?")
print("=" * 80)
last_cycle = cur.execute("""
    SELECT cycle_id FROM orders
    WHERE cycle_id IS NOT NULL
    ORDER BY created_at DESC LIMIT 1
""").fetchone()
if last_cycle:
    cid = last_cycle["cycle_id"]
    print(f"  Dernier cycle = {cid}")
    rows = cur.execute(f"""
        SELECT o.id, i.{SYM_COL} AS ticker, o.side, o.quantity, o.status,
               o.created_at, o.validated_at
        FROM orders o
        LEFT JOIN instruments i ON i.id = o.instrument_id
        WHERE o.cycle_id = ?
        ORDER BY o.id
    """, (cid,)).fetchall()
    for r in rows:
        print(f"    #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} qty={r['quantity']:<4} "
              f"status={r['status']:<22} created={r['created_at']} validated={r['validated_at']}")
else:
    print("  Aucun cycle_id present dans orders")

print()
print("=" * 80)
print("4. HISTORIQUE VALIDATION (created vs validated)")
print("=" * 80)
rows = cur.execute(f"""
    SELECT o.id, i.{SYM_COL} AS ticker, o.side, o.status,
           o.created_at, o.validated_at,
           (julianday(o.validated_at) - julianday(o.created_at)) * 86400 AS delta_seconds
    FROM orders o
    LEFT JOIN instruments i ON i.id = o.instrument_id
    WHERE o.id IN ({ph})
    ORDER BY o.id
""", ORDER_IDS).fetchall()
for r in rows:
    delta = r["delta_seconds"]
    delta_str = f"{delta:.1f}s" if delta is not None else "N/A (jamais validated)"
    print(f"  #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} status={r['status']:<22} "
          f"created={r['created_at']} validated={r['validated_at']} delta={delta_str}")

print()
print("=" * 80)
print("5. CHEMINS D'INSERTION")
print("=" * 80)
row = cur.execute(f"""
    SELECT
        SUM(CASE WHEN validated_at IS NOT NULL THEN 1 ELSE 0 END) AS approved_path,
        SUM(CASE WHEN validated_at IS NULL THEN 1 ELSE 0 END) AS direct_path,
        COUNT(*) AS total
    FROM orders
    WHERE id IN ({ph})
""", ORDER_IDS).fetchone()
print(f"  Total                       : {row['total']}")
print(f"  Via approve (validated_at)  : {row['approved_path']}")
print(f"  Direct (jamais validated)   : {row['direct_path']}")

print()
print("=" * 80)
print("6. MARKERS DANS execution_engine.py")
print("=" * 80)
ee_path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
if os.path.exists(ee_path):
    with open(ee_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    markers = [
        "PATCH_EXECUTION_APPROVAL_WORKFLOW_V1",
        "FIX_CYCLE_ID_PAREN_V1",
        "FIX_APPROVE_ACCEPT_PV_V1",
        "FIX_STATUS_APPROVED_INLINE_V1",
        "PATCH_ORDERS_CYCLE_ID_V1",
    ]
    for m in markers:
        n = content.count(m)
        print(f"  {m:<45} : {n} occurrence(s)")
    inserts = re.findall(r"INSERT\s+INTO\s+orders", content, re.IGNORECASE)
    print(f"  INSERT INTO orders (regex)                    : {len(inserts)} occurrence(s)")
    updates_filled = re.findall(r"UPDATE\s+orders\s+SET[^;]{0,200}status\s*=\s*['\"]filled['\"]",
                                content, re.IGNORECASE | re.DOTALL)
    print(f"  UPDATE orders SET ... status='filled' (regex) : {len(updates_filled)} occurrence(s)")
    pv = content.count("pending_validation")
    print(f"  Mentions 'pending_validation'                  : {pv}")
else:
    print(f"  Fichier introuvable : {ee_path}")

con.close()
print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
