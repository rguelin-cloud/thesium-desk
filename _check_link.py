"""Diagnostic — Pourquoi LINK est ignoré dans le calcul Total P&L
À placer dans C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\
Lance : py -3.13 _check_link.py
"""
import sqlite3

c = sqlite3.connect("thesium.db")
c.row_factory = sqlite3.Row

print("=== 1. Positions actuelles (jointure instruments) ===")
for r in c.execute("""
    SELECT p.id AS pos_id, i.ticker, i.asset_class,
           p.instrument_id AS pos_iid, i.id AS inst_id,
           p.quantity, p.avg_cost, p.current_price, p.unrealized_pnl
    FROM portfolio_positions p
    LEFT JOIN instruments i ON p.instrument_id = i.id
"""):
    print(dict(r))
print()

print("=== 2. Tous les instruments LINK (éventuels doublons) ===")
for r in c.execute("SELECT * FROM instruments WHERE ticker = 'LINK'"):
    print(dict(r))
print()

print("=== 3. Schéma table instruments ===")
for r in c.execute("PRAGMA table_info(instruments)"):
    print(dict(r))
print()

print("=== 4. Dernier prix LINK (instrument_id utilisé par portfolio_positions) ===")
link_pos_iid = c.execute(
    "SELECT instrument_id FROM portfolio_positions p JOIN instruments i ON p.instrument_id=i.id WHERE i.ticker='LINK'"
).fetchone()
if link_pos_iid:
    iid = link_pos_iid[0]
    print(f"instrument_id LINK dans portfolio_positions = {iid}")
    last = c.execute(
        "SELECT date, close FROM prices WHERE instrument_id = ? ORDER BY date DESC LIMIT 3",
        (iid,)
    ).fetchall()
    for r in last:
        print(dict(r))
else:
    print("Pas de position LINK trouvée via la jointure")
print()

print("=== 5. Test exact de la requête utilisée par api_server ===")
# Réplique exacte de la requête de _update_portfolio_from_latest_prices
positions = c.execute(
    'SELECT id, instrument_id, quantity, avg_cost FROM portfolio_positions'
).fetchall()
print(f"Nb positions retournées : {len(positions)}")
for pos in positions:
    pos = dict(pos)
    print(f"  Position {pos}")
    price_row = c.execute(
        'SELECT close FROM prices WHERE instrument_id = ? ORDER BY date DESC LIMIT 1',
        (pos['instrument_id'],)
    ).fetchone()
    if price_row:
        print(f"    → prix trouvé : close={price_row['close']}")
    else:
        print(f"    → AUCUN PRIX TROUVÉ (la position serait SKIPPÉE)")
