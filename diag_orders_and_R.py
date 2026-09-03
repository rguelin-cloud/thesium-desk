# diag_orders_and_R.py
# 1) Schema + dernieres rows de 'orders' (verif BTC pending)
# 2) Trace pourquoi R_norm = 0.5 dans le dernier snapshot portfolio_targets_history

import sqlite3, os, json, sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 70)
print("1) TABLE orders - schema")
print("=" * 70)
cols = [r["name"] for r in c.execute("PRAGMA table_info(orders)")]
print(f"colonnes: {cols}")

print()
print("=" * 70)
print("2) 15 derniers rows de orders")
print("=" * 70)
order_col = "created_at" if "created_at" in cols else "id"
for r in c.execute(f"SELECT * FROM orders ORDER BY {order_col} DESC LIMIT 15"):
    d = dict(r)
    for k, v in list(d.items()):
        if isinstance(v, str) and len(v) > 80:
            d[k] = v[:80] + "..."
    print(f"  {d}")

print()
print("=" * 70)
print("3) BTC dans orders (5 derniers)")
print("=" * 70)
if "ticker" in cols:
    for r in c.execute(f"SELECT * FROM orders WHERE ticker='BTC' ORDER BY {order_col} DESC LIMIT 5"):
        print(f"  {dict(r)}")
else:
    print("  pas de colonne ticker - cherche via instrument_id")
    inst = c.execute("SELECT id FROM instruments WHERE ticker='BTC'").fetchone()
    if inst:
        for r in c.execute(f"SELECT * FROM orders WHERE instrument_id=? ORDER BY {order_col} DESC LIMIT 5", (inst["id"],)):
            print(f"  {dict(r)}")

print()
print("=" * 70)
print("4) Dernier snapshot portfolio_targets_history - components_json")
print("=" * 70)
rows = list(c.execute(
    "SELECT snapshot_id, MAX(created_at) AS last_ts FROM portfolio_targets_history "
    "GROUP BY snapshot_id ORDER BY last_ts DESC LIMIT 1"
))
if rows:
    snap = rows[0]["snapshot_id"]
    print(f"snapshot_id = {snap}  ({rows[0]['last_ts']})")
    print()
    for r in c.execute(
        "SELECT ticker, score, target_weight_pct, components_json "
        "FROM portfolio_targets_history WHERE snapshot_id=? ORDER BY ticker",
        (snap,)
    ):
        comps = {}
        try:
            comps = json.loads(r["components_json"])
        except Exception:
            pass
        r_norm = comps.get("R_norm", "?")
        c_norm = comps.get("C_norm", "?")
        marker = " !!! " if r_norm == 0.5 else "     "
        print(f"  {marker}{r['ticker']:<8} score={r['score']:<8} tw={r['target_weight_pct']:<5} "
              f"R_norm={r_norm}  C_norm={c_norm}")

print()
print("=" * 70)
print("5) target_construction_config.params_json (enable_realized)")
print("=" * 70)
for r in c.execute("SELECT id, params_json FROM target_construction_config ORDER BY id DESC LIMIT 3"):
    print(f"  id={r['id']}")
    try:
        p = json.loads(r["params_json"])
        print(f"    enable_realized = {p.get('enable_realized', '?')}")
        print(f"    weights = C:{p.get('weight_C','?')} R:{p.get('weight_R','?')} M:{p.get('weight_M','?')} D:{p.get('weight_D','?')} V:{p.get('weight_V','?')}")
        print(f"    full keys: {list(p.keys())}")
    except Exception as e:
        print(f"    ERR JSON: {e}")
        print(f"    raw[:200]: {r['params_json'][:200]}")

c.close()
