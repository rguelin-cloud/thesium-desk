import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== TOUTES les positions actuelles ===')
total_pf = 0
for r in c.execute("""
    SELECT i.ticker, p.quantity, p.avg_cost, p.current_price,
           p.unrealized_pnl, p.weight_pct, p.updated_at
    FROM portfolio_positions p JOIN instruments i ON p.instrument_id=i.id
    ORDER BY p.weight_pct DESC
"""):
    d = dict(r)
    total_pf += d['weight_pct']
    print(f"  {d['ticker']:<6} qty={d['quantity']:>10.2f} avg={d['avg_cost']:>10.4f} px={d['current_price']:>10.4f} wgt={d['weight_pct']:>5.2f}% pnl={d['unrealized_pnl']:>8.2f}")
print(f'  TOTAL invested: {total_pf:.2f}%')

print()
print('=== TOUS les targets actifs (PCA Jalon 2) ===')
for r in c.execute("""
    SELECT ticker, target_weight_pct, score, source, snapshot_id, updated_at
    FROM portfolio_targets WHERE active=1
    ORDER BY target_weight_pct DESC
"""):
    print(dict(r))

print()
print('=== Comparaison position vs target ===')
positions = {r['ticker']: r['weight_pct'] for r in c.execute("""
    SELECT i.ticker, p.weight_pct
    FROM portfolio_positions p JOIN instruments i ON p.instrument_id=i.id
""")}
targets = {r['ticker']: r['target_weight_pct'] for r in c.execute("""
    SELECT ticker, target_weight_pct FROM portfolio_targets WHERE active=1
""")}
all_t = set(positions) | set(targets)
print(f"  {'TICKER':<8} {'POS%':>8} {'TGT%':>8} {'DELTA':>8} {'SIDE'}")
for t in sorted(all_t):
    p = positions.get(t, 0.0)
    tg = targets.get(t, 0.0)
    delta = p - tg
    side = 'SELL' if delta > 0.5 else ('BUY' if delta < -0.5 else '---')
    print(f"  {t:<8} {p:>7.2f}% {tg:>7.2f}% {delta:>+7.2f}% {side}")
