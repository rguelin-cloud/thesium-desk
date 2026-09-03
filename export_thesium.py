import sqlite3, csv, os, sys

DB = "thesium.db"
OUT = "export"
os.makedirs(OUT, exist_ok=True)

if not os.path.exists(DB):
    sys.exit(f"Base introuvable: {os.path.abspath(DB)}")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

# Schema complet
with open(os.path.join(OUT, "thesium_schema.sql"), "w", encoding="utf-8") as f:
    for row in cur.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL ORDER BY type, name"
    ):
        f.write(f"-- {row['type']}: {row['name']}\n{row['sql']};\n\n")

tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
)]

summary = []
for t in tables:
    n = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    rows = cur.execute(f'SELECT * FROM "{t}"').fetchall()
    path = os.path.join(OUT, f"{t}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if rows:
            w.writerow(rows[0].keys())
            for r in rows:
                w.writerow(list(r))
        else:
            cols = [d[1] for d in cur.execute(f'PRAGMA table_info("{t}")')]
            w.writerow(cols)
    summary.append((t, n, os.path.getsize(path)))

with open(os.path.join(OUT, "_inventaire.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["table", "lignes", "octets_csv"])
    w.writerows(summary)

print(f"{len(tables)} tables exportees dans {os.path.abspath(OUT)}")
for t, n, s in summary:
    print(f"  {t:30s} {n:8d} lignes  {s/1024:8.1f} Ko")
con.close()