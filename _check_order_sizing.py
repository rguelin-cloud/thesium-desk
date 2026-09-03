import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

# Recup NAV
nav = c.execute("SELECT total_value FROM portfolio_state ORDER BY id DESC LIMIT 1").fetchone()['total_value']
print(f'NAV = {nav:,.2f} EUR')
print()

# Pour chaque order pending
print('=== Verification sizing des orders pending ===')
print(f"{'TICKER':<8} {'SIDE':<5} {'QTY':>8} {'PX':>10} {'NOTIONAL':>12} {'IMPACT%':>9} {'POS%':>7} {'TGT%':>7} {'DELTA%':>8} {'NEW POS%':>9} {'VERDICT'}")
for r in c.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity,
           p.weight_pct as pos_pct, p.current_price,
           t.target_weight_pct as tgt_pct
    FROM orders o
    JOIN instruments i ON o.instrument_id=i.id
    LEFT JOIN portfolio_positions p ON p.instrument_id=i.id
    LEFT JOIN portfolio_targets t ON t.ticker=i.ticker AND t.active=1
    WHERE o.status = 'pending_validation'
    ORDER BY o.id DESC
"""):
    d = dict(r)
    qty = d['quantity']
    px = d['current_price'] or 0
    notional = qty * px
    impact = (notional / nav) * 100
    pos = d['pos_pct'] or 0
    tgt = d['tgt_pct'] or 0
    delta_needed = tgt - pos
    if d['side'].lower() == 'sell':
        new_pos = pos - impact
    else:
        new_pos = pos + impact
    overshoot = abs(new_pos - tgt)
    verdict = 'OK' if overshoot < 0.5 else ('OVERSHOOT' if overshoot < 2 else 'EXCESSIF')
    print(f"{d['ticker']:<8} {d['side']:<5} {qty:>8.2f} {px:>10.4f} {notional:>12,.0f} {impact:>8.2f}% {pos:>6.2f}% {tgt:>6.2f}% {delta_needed:>+7.2f}% {new_pos:>8.2f}% {verdict}")
