import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Toutes les tables ===')
for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(f'  {r[0]}')

print()
print('=== Tables susceptibles de contenir positions/holdings ===')
candidates = c.execute("""
    SELECT name FROM sqlite_master WHERE type='table'
      AND (name LIKE '%position%' OR name LIKE '%holding%'
        OR name LIKE '%portfolio%' OR name LIKE '%state%'
        OR name LIKE '%nav%' OR name LIKE '%balance%')
""").fetchall()
for r in candidates:
    print(f'  --- {r[0]} ---')
    for col in c.execute(f"PRAGMA table_info({r[0]})"):
        print(f'    {col[1]} ({col[2]})')
    # Quelques lignes
    rows = c.execute(f"SELECT * FROM {r[0]} LIMIT 3").fetchall()
    if rows:
        print(f'    Sample ({len(rows)} rows):')
        for row in rows:
            print(f'      {dict(row)}')
    print()
