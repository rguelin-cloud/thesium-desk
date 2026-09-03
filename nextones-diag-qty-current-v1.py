# Verifie qty_current dans replay_orders cycle 2 et 3 (run_id=12)
# Si qty_current=0 partout, c'est que _get_current_position_qty ne voit pas la position existante
# (joue sur la base prod portfolio_positions au lieu du replay)
import os, sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
conn = sqlite3.connect(DB, timeout=10.0)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

RUN_ID = 12

print("=== replay_orders run_id=12 par day_t (qty_current breakdown) ===")
rows = cur.execute(
    "SELECT day_t, ticker, side, qty, qty_target, qty_current, status, fill_price "
    "FROM replay_orders WHERE run_id=? "
    "AND ticker IN ('AAPL', 'AMD', 'ARM') "
    "ORDER BY day_t, ticker",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {r['day_t']} {r['ticker']:6s} {r['side']:5s} qty={r['qty']:6.1f} target={r['qty_target']:6.1f} current={r['qty_current']:6.1f} status={r['status']}")

# Vue agregee
print("\n=== Agg qty/cycle ===")
rows = cur.execute(
    "SELECT day_t, COUNT(*) as n, SUM(qty) as sum_qty, SUM(qty_current) as sum_qty_curr, SUM(fill_price * qty) as sum_notional "
    "FROM replay_orders WHERE run_id=? AND status='filled' GROUP BY day_t",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {r['day_t']} n={r['n']} sum_qty={r['sum_qty']:.0f} sum_qty_curr={r['sum_qty_curr']:.0f} notional_filled=${r['sum_notional']:,.2f}")

# Verifie aussi les positions par cycle
print("\n=== replay_positions par cycle_id_replay ===")
rows = cur.execute(
    "SELECT cycle_id_replay, COUNT(*) as n, SUM(quantity) as total_qty, "
    "SUM(quantity * current_price) as pos_value "
    "FROM replay_positions WHERE run_id=? GROUP BY cycle_id_replay ORDER BY cycle_id_replay",
    (RUN_ID,),
).fetchall()
for r in rows:
    pv = r['pos_value'] or 0
    print(f"  cycle_id_replay={r['cycle_id_replay']} n_pos={r['n']} total_qty={r['total_qty']:.0f} pos_value=${pv:,.2f}")

# Total notional cumul des 3 cycles
print("\n=== Verif fills cycle par cycle ===")
rows = cur.execute(
    "SELECT day_t, COUNT(*) as n, SUM(notional) as sum_not "
    "FROM replay_fills WHERE run_id=? GROUP BY day_t",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {r['day_t']} n_fills={r['n']} sum_notional=${r['sum_not']:,.2f}")

# Cash dans portfolio_state replay
print("\n=== NAV/cash cycle par cycle ===")
rows = cur.execute(
    "SELECT day_t, nav, cash, positions_value, n_positions "
    "FROM replay_nav_history WHERE run_id=? ORDER BY day_t",
    (RUN_ID,),
).fetchall()
for r in rows:
    print(f"  {r['day_t']} nav=${r['nav']:,.2f} cash=${r['cash']:,.2f} pos_val=${r['positions_value']:,.2f} n={r['n_positions']}")

conn.close()
