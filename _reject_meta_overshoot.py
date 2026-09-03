import sqlite3
from datetime import datetime
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

# Trouver l'order META BUY pending
row = c.execute("""
    SELECT o.id FROM orders o JOIN instruments i ON o.instrument_id=i.id
    WHERE o.status='pending_validation' AND i.ticker='META' AND o.side IN ('buy','BUY')
    ORDER BY o.id DESC LIMIT 1
""").fetchone()

if not row:
    print('[reject] Aucun ordre META BUY pending trouve.')
else:
    oid = row['id']
    c.execute("""
        UPDATE orders
        SET status='rejected',
            rejection_reason='overshoot_sizing_bug_v6_5',
            validated_at=?, validated_by='manual_review'
        WHERE id=?
    """, (datetime.now().isoformat(timespec='seconds'), oid))
    c.commit()
    print(f'[reject] Order #{oid} META BUY rejete (overshoot 5.43% vs target 3.77%).')

print()
print('=== Orders pending restants ===')
for r in c.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity
    FROM orders o JOIN instruments i ON o.instrument_id=i.id
    WHERE o.status='pending_validation'
"""):
    print(f"  #{r[0]} {r[1]} {r[2]} qty={r[3]}")
