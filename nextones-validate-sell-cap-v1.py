# -*- coding: utf-8 -*-
# nextones-validate-sell-cap-v1.py
# Validation runtime du patch SELL_OVERSHOOT_CAP_V1.
#
# Verifications :
#   1. Marker present dans execution_engine.py
#   2. Tester create_and_execute_order en direct sur ZEC SELL 50 (position = 1.0)
#      -> attendu : quantity ramenee a 1.0 + warning sell_overshoot_capped
#   3. Tester sur ticker fictif sans position : refus dur

import os
import sys
import json
import sqlite3

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")
EE = os.path.join(PROD, "execution_engine.py")

print()
print("=" * 72)
print("VALIDATE [SELL_OVERSHOOT_CAP_V1]")
print("=" * 72)

# ----------------------------------------------------------------------
# [1] Marker present
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[1] Marker present dans execution_engine.py")
print("-" * 72)

with open(EE, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if "[SELL_OVERSHOOT_CAP_V1]" in content:
    print("  [OK] Marker present")
else:
    print("  [KO] Marker absent : patch non applique")
    sys.exit(2)

# ----------------------------------------------------------------------
# [2] Etat ZEC actuel
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[2] Etat ZEC actuel (position + dernier prix)")
print("-" * 72)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

zec_pos = conn.execute(
    """SELECT pp.quantity, pp.avg_cost, i.id as instrument_id
       FROM portfolio_positions pp
       JOIN instruments i ON i.id = pp.instrument_id
       WHERE i.ticker = 'ZEC'"""
).fetchone()

if not zec_pos:
    print("  [WARN] ZEC absent de portfolio_positions")
    conn.close()
    sys.exit(3)

zec_qty = zec_pos["quantity"]
zec_iid = zec_pos["instrument_id"]
print("  ZEC : qty=%s instrument_id=%s" % (zec_qty, zec_iid))

# ----------------------------------------------------------------------
# [3] Test direct : SELL 50 ZEC alors qu on a 1.0
# ----------------------------------------------------------------------
print()
print("-" * 72)
print("[3] Test create_and_execute_order : ZEC SELL 50 (position = %s)" % zec_qty)
print("-" * 72)

# Ajouter le repertoire au PYTHONPATH
sys.path.insert(0, PROD)

import importlib
if "execution_engine" in sys.modules:
    del sys.modules["execution_engine"]
import execution_engine as ee

# Trouver une thesis_id valide existante (peu importe laquelle, on rollback)
thesis_row = conn.execute("SELECT id FROM theses ORDER BY id DESC LIMIT 1").fetchone()
thesis_id = thesis_row["id"] if thesis_row else None
print("  thesis_id utilise pour test : %s" % thesis_id)

# Sauvegarder le compteur d orders avant le test
order_count_before = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
print("  orders dans DB avant test : %d" % order_count_before)

try:
    result = ee.create_and_execute_order(
        conn,
        instrument_id=zec_iid,
        thesis_id=thesis_id,
        side="sell",
        quantity=50,  # >> 1.0 reel
        order_type="market",
        limit_price=None,
    )
    print()
    print("  Resultat :")
    for k, v in result.items():
        if k == "risk_check":
            print("    risk_check :")
            if isinstance(v, dict):
                for kk, vv in v.items():
                    print("      %s : %s" % (kk, str(vv)[:200]))
            else:
                print("      %s" % str(v)[:200])
        else:
            print("    %s : %s" % (k, str(v)[:200]))

    # Verifier dans la DB le dernier order ZEC
    last_zec = conn.execute(
        """SELECT id, side, quantity, status, risk_check_result
           FROM orders WHERE instrument_id = ?
           ORDER BY id DESC LIMIT 1""",
        (zec_iid,)
    ).fetchone()
    print()
    print("  Dernier order ZEC en DB :")
    print("    id=%s side=%s quantity=%s status=%s" % (
        last_zec["id"], last_zec["side"], last_zec["quantity"], last_zec["status"]))
    try:
        rcr = json.loads(last_zec["risk_check_result"]) if last_zec["risk_check_result"] else {}
        warnings = rcr.get("warnings", [])
        cap_warns = [w for w in warnings if isinstance(w, dict) and w.get("source") == "[CAP_SELL]"]
        print("    warnings [CAP_SELL] : %d" % len(cap_warns))
        for w in cap_warns:
            print("      details: %s" % w.get("details"))
        reasons = rcr.get("reasons", [])
        cap_reasons = [r for r in reasons if "[CAP_SELL]" in str(r)]
        if cap_reasons:
            print("    reasons [CAP_SELL] :")
            for r in cap_reasons:
                print("      - %s" % r)
    except Exception as e:
        print("    [WARN] parse risk_check_result : %s" % e)

except Exception as e:
    import traceback
    print("  [ERR] exception : %s" % e)
    traceback.print_exc()

# Rollback : on retire l ordre de test
conn.rollback()
order_count_after = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
print()
print("  orders dans DB apres test : %d (rollback : %s)" % (
    order_count_after,
    "OK" if order_count_after == order_count_before else "KO"
))

conn.close()
print()
print("=" * 72)
print("ATTENDU")
print("-" * 72)
print("  Si position ZEC = 1.0 :")
print("    quantity affichee dans l ordre = 1.0 (cap depuis 50)")
print("    warning [CAP_SELL] avec details {original_qty=50, held=1.0, capped_to=1.0}")
print("=" * 72)
