# find_btc_everywhere.py
# Liste toutes les tables, identifie celles qui contiennent un champ ticker,
# et cherche BTC dans le dernier cycle.

import sqlite3, os, sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
if not os.path.exists(DB):
    print(f"[KO] DB introuvable : {DB}"); sys.exit(1)

c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

print("=" * 70)
print("TABLES de la DB")
print("=" * 70)
tables = [r["name"] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
for t in tables:
    print(f"  - {t}")

print()
print("=" * 70)
print("TABLES contenant un champ 'ticker' (+ schema)")
print("=" * 70)
ticker_tables = []
for t in tables:
    cols = [r["name"] for r in c.execute(f"PRAGMA table_info({t})")]
    if "ticker" in cols:
        ticker_tables.append((t, cols))
        print(f"\n  [{t}]")
        print(f"    colonnes: {cols}")
        try:
            n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"    rows: {n}")
        except Exception as e:
            print(f"    rows: ERR {e}")

print()
print("=" * 70)
print("DERNIER CYCLE")
print("=" * 70)
last_cycle = None
try:
    rows = list(c.execute(
        "SELECT cycle_id, MAX(created_at) AS last_ts "
        "FROM cycle_reconciliation_log GROUP BY cycle_id "
        "ORDER BY last_ts DESC LIMIT 1"
    ))
    if rows:
        last_cycle = rows[0]["cycle_id"]
        print(f"cycle_id = {last_cycle}  ({rows[0]['last_ts']})")
except Exception as e:
    print(f"ERR: {e}")

print()
print("=" * 70)
print("BTC dans chaque table 'ticker' (5 derniers rows)")
print("=" * 70)
for t, cols in ticker_tables:
    print(f"\n  ### {t}")
    # tente created_at puis id
    order_col = "created_at" if "created_at" in cols else ("id" if "id" in cols else "rowid")
    try:
        for r in c.execute(
            f"SELECT * FROM {t} WHERE ticker='BTC' ORDER BY {order_col} DESC LIMIT 5"
        ):
            d = dict(r)
            # tronque les longs champs
            for k, v in list(d.items()):
                if isinstance(v, str) and len(v) > 200:
                    d[k] = v[:200] + "...(tronque)"
            print(f"    {d}")
    except Exception as e:
        print(f"    ERR: {e}")

print()
print("=" * 70)
print("DERNIER CYCLE - reconciliation complete")
print("=" * 70)
if last_cycle:
    for r in c.execute(
        "SELECT ticker, action, qty_in, delta_signal_pct, reason "
        "FROM cycle_reconciliation_log WHERE cycle_id=? ORDER BY ticker",
        (last_cycle,)
    ):
        action = r["action"]
        marker = " <-- " if action in ("DROPPED", "REJECTED") or r["ticker"] == "BTC" else "     "
        print(f"  {marker}{r['ticker']:<8} {action:<24} qty={r['qty_in']}  delta={r['delta_signal_pct']}")
        if action in ("DROPPED", "REJECTED") or r["ticker"] == "BTC":
            print(f"           raison: {r['reason']}")

c.close()
