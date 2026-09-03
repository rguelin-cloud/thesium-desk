# -*- coding: utf-8 -*-
"""
DIAG : shadow_variants DDL complet + toutes les rows
(pour corriger la colonne 'id' qui n'existe pas)
"""
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 78)
print("shadow_variants : DDL")
print("=" * 78)
row = cur.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='shadow_variants'"
).fetchone()
print(row["sql"] if row else "[ERR] not found")

print()
print("PRAGMA table_info :")
for r in cur.execute("PRAGMA table_info(shadow_variants)").fetchall():
    print("  cid={} name={} type={} notnull={} pk={}".format(
        r["cid"], r["name"], r["type"], r["notnull"], r["pk"]
    ))

print()
print("ALL ROWS :")
for r in cur.execute("SELECT * FROM shadow_variants").fetchall():
    print("  ", dict(r))

print()
print("=" * 78)
print("Cross-check : variant_id utilises dans shadow_fills")
print("=" * 78)
for r in cur.execute(
    "SELECT variant_id, COUNT(*) AS n_fills FROM shadow_fills "
    "GROUP BY variant_id ORDER BY variant_id"
).fetchall():
    print("  variant_id={} n_fills={}".format(r["variant_id"], r["n_fills"]))

conn.close()
print()
print("DONE")
