"""Diagnostic — Qui écrit dans portfolio_state et que contient-il actuellement ?
À placer dans C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\
Lance : py -3.13 _check_state.py
"""
import sqlite3

c = sqlite3.connect("thesium.db")
c.row_factory = sqlite3.Row

print("=== 1. Schéma portfolio_state ===")
for r in c.execute("PRAGMA table_info(portfolio_state)"):
    print(dict(r))
print()

print("=== 2. Contenu actuel portfolio_state ===")
for r in c.execute("SELECT * FROM portfolio_state"):
    print(dict(r))
print()

print("=== 3. Contenu portfolio_positions complet ===")
for r in c.execute("SELECT * FROM portfolio_positions"):
    print(dict(r))
print()

print("=== 4. Recalcul Total P&L ATTENDU ===")
positions = c.execute("""
    SELECT i.ticker, p.quantity, p.avg_cost, p.current_price, p.unrealized_pnl
    FROM portfolio_positions p
    JOIN instruments i ON p.instrument_id = i.id
""").fetchall()

total_mv = 0.0
total_cost = 0.0
total_unrealized = 0.0
for r in positions:
    r = dict(r)
    mv = r['quantity'] * r['current_price']
    cost = r['quantity'] * r['avg_cost']
    pnl = mv - cost
    total_mv += mv
    total_cost += cost
    total_unrealized += r['unrealized_pnl'] or 0
    print(f"  {r['ticker']:6s}  qty={r['quantity']:>8.2f}  avg_cost={r['avg_cost']:>10.4f}  "
          f"price={r['current_price']:>10.4f}  mv={mv:>10.2f}  pnl_calc={pnl:>+8.2f}  "
          f"pnl_stored={r['unrealized_pnl']}")

print()
print(f"  Total market value : {total_mv:>12.2f}")
print(f"  Total cost basis   : {total_cost:>12.2f}")
print(f"  Total P&L (calc)   : {total_mv - total_cost:>+12.2f}")
print(f"  Total P&L (stored sum unrealized_pnl) : {total_unrealized:>+12.2f}")

cash = c.execute("SELECT cash FROM portfolio_state WHERE id=1").fetchone()[0]
print(f"  Cash               : {cash:>12.2f}")
print(f"  Total NAV          : {cash + total_mv:>12.2f}")

print()
print("=== 5. portfolio_history (5 dernières lignes) ===")
for r in c.execute("SELECT * FROM portfolio_history ORDER BY date DESC LIMIT 5"):
    print(dict(r))
