# -*- coding: utf-8 -*-
# nextones-diag-orders-risk-check-result.py
# Marker : [DIAG_ORDERS_RISK_CHECK_RESULT]
#
# Inspecte le contenu exact de orders.risk_check_result pour les rows
# affichees dans le memo (ZEC #263, #265, et autres BLOCK recents).
# But : voir si details["broker_mapping_ok"]["reason"] existe ou pas.

import os
import json
import sqlite3

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

print()
print("=" * 78)
print("DIAG : contenu orders.risk_check_result pour ordres bloques")
print("=" * 78)

# Schemas
cur.execute("PRAGMA table_info(orders)")
print("  Colonnes orders : %s" % [r["name"] for r in cur.fetchall()])

# --- Rows orders bloquees recentes
print()
print("-" * 78)
print("[1] 10 derniers orders avec status REJECT/BLOCK ou risk_check_result non vide")
print("-" * 78)

cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status, o.created_at, o.risk_check_result, o.rejection_reason
    FROM orders o LEFT JOIN instruments i ON i.id = o.instrument_id
    ORDER BY o.id DESC LIMIT 15
""")
rows = cur.fetchall()
print("  %d rows" % len(rows))

for r in rows:
    d = dict(r)
    rcr = d.get("risk_check_result") or ""
    print()
    print("  --- id=%s ticker=%s side=%s qty=%s status=%s ---" % (
        d.get("id"), d.get("ticker"), d.get("side"), d.get("quantity"), d.get("status")))
    print("  created_at=%s" % d.get("created_at"))
    print("  rejection_reason=%s" % d.get("rejection_reason"))
    if not rcr:
        print("  risk_check_result : VIDE")
        continue
    try:
        j = json.loads(rcr)
    except Exception as e:
        print("  risk_check_result raw : %s..." % str(rcr)[:200])
        continue

    print("  risk_check_result top keys : %s" % list(j.keys())[:10])
    v2 = j.get("risk_v2")
    if v2:
        print("  risk_v2 keys : %s" % list(v2.keys()))
        print("    passed     : %s" % v2.get("passed"))
        print("    blocked_by : %s" % v2.get("blocked_by"))
        det = v2.get("details") or {}
        print("    details keys : %s" % list(det.keys()))
        # Specifiquement le sous-objet broker_mapping_ok
        bmo = det.get("broker_mapping_ok")
        if bmo:
            print("    details[broker_mapping_ok] :")
            print("      %s" % json.dumps(bmo, indent=2, ensure_ascii=False)[:600])
        else:
            print("    details[broker_mapping_ok] : ABSENT")
        # Dump complet details (court)
        print("    details full (court) :")
        print("      %s" % json.dumps(det, indent=2, ensure_ascii=False)[:1000])
    else:
        # Peut etre que c'est direct
        print("  pas de cle risk_v2, dump 600 chars :")
        print("    %s" % json.dumps(j, indent=2, ensure_ascii=False)[:600])

c.close()
print()
print("=" * 78)
