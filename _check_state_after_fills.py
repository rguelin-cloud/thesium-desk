import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Positions actuelles (META, LINK, ETH) ===')
for r in c.execute("""
    SELECT i.ticker, p.quantity, p.avg_price, p.market_value
    FROM positions p JOIN instruments i ON p.instrument_id=i.id
    WHERE i.ticker IN ('META','LINK','ETH','LINK-USD','ETH-USD')
"""):
    print(dict(r))

print()
print('=== Derniers fills META/LINK/ETH ===')
for r in c.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status, o.validated_at
    FROM orders o JOIN instruments i ON o.instrument_id=i.id
    WHERE i.ticker IN ('META','LINK','ETH','LINK-USD','ETH-USD')
      AND o.status IN ('filled','executed')
    ORDER BY o.id DESC LIMIT 6
"""):
    print(dict(r))

print()
print('=== Targets actifs ===')
for r in c.execute("""
    SELECT ticker, target_weight_pct, source, updated_at
    FROM portfolio_targets WHERE active=1
    ORDER BY target_weight_pct DESC
"""):
    print(dict(r))

print()
print('=== NAV & cash actuels ===')
for r in c.execute("SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1"):
    print(dict(r))
