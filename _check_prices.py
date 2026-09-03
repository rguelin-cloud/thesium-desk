"""Script de diagnostic — à placer dans C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\
Lance : py -3.13 _check_prices.py
"""
import sqlite3

c = sqlite3.connect("thesium.db")
c.row_factory = sqlite3.Row

# 1. Toutes les tables contenant "price"
print("=== Tables contenant 'price' ===")
tables = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%price%'"
)]
print(tables)
print()

# 2. Schéma de la table prices
print("=== Schéma table 'prices' ===")
for r in c.execute("PRAGMA table_info(prices)"):
    print(dict(r))
print()

# 3. Count + range de dates par ticker
print("=== Historique prices par ticker ===")
sql = """
SELECT i.ticker, i.asset_class,
       COUNT(p.date) AS nb_prices,
       MIN(p.date) AS first_date,
       MAX(p.date) AS last_date
FROM instruments i
LEFT JOIN prices p ON p.instrument_id = i.id
GROUP BY i.ticker
ORDER BY i.asset_class, i.ticker
"""
for r in c.execute(sql):
    print(dict(r))
