# Diag : pourquoi notional=$0 dans replay_fills run_id=12 ?
import os, sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

RUN_ID = 12

print(f"=== replay_fills run_id={RUN_ID} : sample 5 rows ===")
rows = cur.execute(
    "SELECT id, run_id, cycle_id_replay, day_t, ticker, side, fill_price, "
    "fill_quantity, open_j1, slippage_bps, fees, notional, created_at "
    "FROM replay_fills WHERE run_id=? LIMIT 5",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {dict(r)}")

print(f"\n=== Aggregate ===")
agg = cur.execute(
    "SELECT COUNT(*) as n, "
    "SUM(fill_price * fill_quantity) as sum_calc, "
    "SUM(notional) as sum_notional, "
    "SUM(CASE WHEN side='BUY' THEN 1 ELSE 0 END) as nb_buy, "
    "SUM(CASE WHEN side='SELL' THEN 1 ELSE 0 END) as nb_sell, "
    "SUM(CASE WHEN notional IS NULL THEN 1 ELSE 0 END) as nb_null_notional "
    "FROM replay_fills WHERE run_id=?",
    (RUN_ID,),
).fetchone()
print(f"  n_fills          : {agg['n']}")
print(f"  nb BUY/SELL      : {agg['nb_buy']} / {agg['nb_sell']}")
print(f"  nb_null_notional : {agg['nb_null_notional']}")
print(f"  sum(notional)    : {agg['sum_notional']}")
print(f"  sum(fp * fq)     : {agg['sum_calc']}")

# Compare avec replay_orders
print(f"\n=== replay_orders run_id={RUN_ID} : sample 3 filled ===")
rows = cur.execute(
    "SELECT day_t, ticker, side, qty, qty_target, qty_current, status, fill_price, "
    "price_close_t, nav_before "
    "FROM replay_orders WHERE run_id=? AND status='filled' LIMIT 3",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {dict(r)}")

# Verifie la side dans orders vs fills
print(f"\n=== Side distribution dans replay_fills ===")
for r in cur.execute("SELECT side, COUNT(*) FROM replay_fills WHERE run_id=? GROUP BY side", (RUN_ID,)):
    print(f"  side={r[0]!r} : {r[1]}")

conn.close()
