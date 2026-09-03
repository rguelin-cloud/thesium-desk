# -*- coding: utf-8 -*-
"""
Diag : pourquoi seul TXN etait dans pending_validation alors que le cycle
a produit AAPL #347 + AMD + META + ETH + LINK + MSFT etc.

Hypotheses :
  H1 : tous les autres ordres ont ete inseres directement en 'filled'
       (bypass pending_validation) parce que le patch L1283 n'est pas
       sur tous les chemins d'insertion d'orders.
  H2 : il y a plusieurs cycles distincts, et seul le dernier a inserts
       pending_validation, les autres sont anterieurs (filled depuis).
  H3 : la card "Pending Approvals" affichait seulement TXN car les autres
       avaient deja ete approuves/filled avant le screenshot.
  H4 : certains ordres ont risk_check_result qui les a auto-approve.
"""
import sqlite3
import json
from collections import Counter

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

ORDER_IDS = [336, 337, 338, 339, 342, 343, 344, 345, 346, 347]

print("=" * 80)
print("1. ETAT ACTUEL DES 10 ORDERS RECENTS")
print("=" * 80)
rows = cur.execute("""
    SELECT o.id, i.symbol AS ticker, o.side, o.quantity, o.status,
           o.cycle_id, o.created_at, o.validated_at, o.validated_by,
           substr(coalesce(o.risk_check_result,''),1,60) AS risk_notes
    FROM orders o
    LEFT JOIN instruments i ON i.id = o.instrument_id
    WHERE o.id IN ({})
    ORDER BY o.id
""".format(",".join("?"*len(ORDER_IDS))), ORDER_IDS).fetchall()

for r in rows:
    print(f"  #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} qty={r['quantity']:<4} "
          f"status={r['status']:<20} cycle={r['cycle_id']} "
          f"created={r['created_at']} validated_by={r['validated_by']}")

print()
print("=" * 80)
print("2. DISTRIBUTION PAR CYCLE_ID")
print("=" * 80)
rows = cur.execute("""
    SELECT cycle_id, status, COUNT(*) AS n
    FROM orders
    WHERE id IN ({})
    GROUP BY cycle_id, status
    ORDER BY cycle_id, status
""".format(",".join("?"*len(ORDER_IDS))), ORDER_IDS).fetchall()
for r in rows:
    print(f"  cycle={r['cycle_id']:<25} status={r['status']:<22} n={r['n']}")

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
    rows = cur.execute("""
        SELECT o.id, i.symbol AS ticker, o.side, o.quantity, o.status,
               o.created_at, o.validated_at
        FROM orders o
        LEFT JOIN instruments i ON i.id = o.instrument_id
        WHERE o.cycle_id = ?
        ORDER BY o.id
    """, (cid,)).fetchall()
    for r in rows:
        print(f"    #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} qty={r['quantity']:<4} "
              f"status={r['status']:<22} created={r['created_at']} validated={r['validated_at']}")

print()
print("=" * 80)
print("4. HISTORIQUE PENDING_VALIDATION : quand chaque ordre a-t-il transit ?")
print("=" * 80)
# Verifier validated_at vs created_at
rows = cur.execute("""
    SELECT o.id, i.symbol AS ticker, o.side, o.status,
           o.created_at, o.validated_at,
           (julianday(o.validated_at) - julianday(o.created_at)) * 86400 AS delta_seconds
    FROM orders o
    LEFT JOIN instruments i ON i.id = o.instrument_id
    WHERE o.id IN ({})
    ORDER BY o.id
""".format(",".join("?"*len(ORDER_IDS))), ORDER_IDS).fetchall()
for r in rows:
    delta = r["delta_seconds"]
    delta_str = f"{delta:.1f}s" if delta is not None else "N/A"
    print(f"  #{r['id']:>3} {r['ticker']:<6} {r['side']:<4} status={r['status']:<22} "
          f"created={r['created_at']} validated={r['validated_at']} delta={delta_str}")

print()
print("=" * 80)
print("5. CHEMINS D'INSERTION : combien d'ordres ont passe par pending_validation ?")
print("=" * 80)
# Tous ordres avec validated_at non-null = sont passes par approve_and_fill
rows = cur.execute("""
    SELECT
        SUM(CASE WHEN validated_at IS NOT NULL THEN 1 ELSE 0 END) AS approved_path,
        SUM(CASE WHEN validated_at IS NULL THEN 1 ELSE 0 END) AS direct_path,
        COUNT(*) AS total
    FROM orders
    WHERE id IN ({})
""".format(",".join("?"*len(ORDER_IDS))), ORDER_IDS).fetchone()
print(f"  Total                       : {rows['total']}")
print(f"  Via approve (validated_at)  : {rows['approved_path']}")
print(f"  Direct (jamais validated)   : {rows['direct_path']}")

print()
print("=" * 80)
print("6. MARKERS DE PATCH PRESENTS DANS execution_engine.py")
print("=" * 80)
import os
ee_path = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\execution_engine.py"
if os.path.exists(ee_path):
    with open(ee_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    markers = [
        "PATCH_EXECUTION_APPROVAL_WORKFLOW_V1",
        "FIX_CYCLE_ID_PAREN_V1",
        "FIX_APPROVE_ACCEPT_PV_V1",
        "FIX_STATUS_APPROVED_INLINE_V1",
    ]
    for m in markers:
        n = content.count(m)
        print(f"  {m:<45} : {n} occurrence(s)")
    # Compter combien de INSERT INTO orders il y a
    import re
    inserts = re.findall(r"INSERT\s+INTO\s+orders", content, re.IGNORECASE)
    print(f"  INSERT INTO orders                            : {len(inserts)} occurrence(s)")
    # Compter combien d'UPDATE status='filled'
    updates_filled = re.findall(r"UPDATE\s+orders\s+SET[^;]*status\s*=\s*['\"]filled['\"]", content, re.IGNORECASE | re.DOTALL)
    print(f"  UPDATE orders SET status='filled' (regex)     : {len(updates_filled)} occurrence(s)")
    # Compter pending_validation
    pv = content.count("pending_validation")
    print(f"  Mentions 'pending_validation'                  : {pv}")
else:
    print(f"  Fichier introuvable : {ee_path}")

con.close()
print()
print("=" * 80)
print("FIN DU DIAG")
print("=" * 80)
