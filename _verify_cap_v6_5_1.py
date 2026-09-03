import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Reconciler log dernier cycle (CAPPED inclus) ===')
last_cycle = c.execute("SELECT cycle_id FROM cycle_reconciliation_log ORDER BY id DESC LIMIT 1").fetchone()[0]
print(f'Cycle: {last_cycle}')
print()
for r in c.execute("""
    SELECT ticker, action, side_in, qty_in, delta_signal_pct, delta_target_pct, reason
    FROM cycle_reconciliation_log
    WHERE cycle_id = ?
    ORDER BY ticker
""", (last_cycle,)):
    d = dict(r)
    print(f"  {d['ticker']:<6} {d['action']:<25} {d['side_in']:<5} qty={d['qty_in']:>6.0f} dSig={d['delta_signal_pct']:>+6.2f}% dTgt={d['delta_target_pct']:>+6.2f}% | {d['reason'][:80]}")

print()
print('=== Orders pending de ce cycle (avec verification sizing) ===')
nav = c.execute("SELECT total_value FROM portfolio_state ORDER BY id DESC LIMIT 1").fetchone()['total_value']
for r in c.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, p.current_price, p.weight_pct as pos_pct,
           t.target_weight_pct as tgt_pct
    FROM orders o
    JOIN instruments i ON o.instrument_id=i.id
    LEFT JOIN portfolio_positions p ON p.instrument_id=i.id
    LEFT JOIN portfolio_targets t ON t.ticker=i.ticker AND t.active=1
    WHERE o.status='pending_validation'
    ORDER BY o.id DESC
"""):
    d = dict(r)
    px = d['current_price'] or 0
    notional = d['quantity'] * px
    impact = notional/nav*100 if nav else 0
    pos = d['pos_pct'] or 0
    tgt = d['tgt_pct'] or 0
    new_pos = pos + impact if d['side'].lower()=='buy' else pos - impact
    overshoot = abs(new_pos - tgt)
    verdict = 'OK' if overshoot < 0.5 else ('OVERSHOOT' if overshoot < 2 else 'EXCESSIF')
    print(f"  #{d['id']} {d['ticker']:<6} {d['side']:<5} qty={d['quantity']:>6.0f} impact={impact:>5.2f}% pos={pos:>5.2f}% tgt={tgt:>5.2f}% new={new_pos:>5.2f}% {verdict}")
