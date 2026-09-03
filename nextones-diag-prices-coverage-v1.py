#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-jalon 8A : diag couverture prix DB.

Verifie pour chaque ticker de l'univers actuel:
  - date min / max disponible
  - nb de jours de cotation
  - gap median entre points consecutifs
  - couverture en mois (max - min) / 30

Objectif: decider fenetre 8C 12 ou 24 mois.

ASCII pur, idempotent, read-only DB.
"""
import io
import os
import sqlite3
import sys
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print("=" * 70)
print("DIAG COUVERTURE PRIX - PRE-JALON 8A")
print("=" * 70)

if not os.path.isfile(DB):
    print("[ERR] DB introuvable:", DB)
    sys.exit(1)

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Detecte schema de la table prices
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'price%'")
tables = [r[0] for r in cur.fetchall()]
print("Tables prix detectees:", tables)
print()

# Trouve la table principale (la plus peuplee)
main_table = None
max_rows = 0
for t in tables:
    try:
        cur.execute("SELECT COUNT(*) FROM " + t)
        n = cur.fetchone()[0]
        if n > max_rows:
            max_rows = n
            main_table = t
    except Exception as e:
        print("  skip", t, ":", e)

if not main_table:
    print("[ERR] aucune table prices peuplee")
    sys.exit(1)

print("Table principale:", main_table, "(" + str(max_rows) + " lignes)")
print()

# Schema
cur.execute("PRAGMA table_info(" + main_table + ")")
cols = [r["name"] for r in cur.fetchall()]
print("Colonnes:", cols)
print()

# Detecte colonnes ticker et date
col_ticker = None
col_date = None
for c in cols:
    cl = c.lower()
    if cl in ("ticker", "symbol", "instrument"):
        col_ticker = c
    if cl in ("date", "trade_date", "timestamp", "dt"):
        col_date = c

if not col_ticker or not col_date:
    print("[ERR] colonnes ticker/date introuvables")
    print("  candidats ticker:", col_ticker)
    print("  candidats date:", col_date)
    sys.exit(1)

print("Colonne ticker:", col_ticker)
print("Colonne date:  ", col_date)
print()

# Liste des tickers presents
cur.execute("SELECT DISTINCT " + col_ticker + " FROM " + main_table + " ORDER BY " + col_ticker)
tickers = [r[0] for r in cur.fetchall()]
print("Tickers presents:", len(tickers))
print(" ", ", ".join(tickers[:50]))
if len(tickers) > 50:
    print("  ...")
print()

# Couverture par ticker
print("=" * 70)
print("COUVERTURE PAR TICKER")
print("=" * 70)
print(f"{'TICKER':<12} {'MIN':<12} {'MAX':<12} {'JOURS':>7} {'MOIS':>6}")
print("-" * 60)

now = datetime.now()
ranges = []
for t in tickers:
    cur.execute(
        "SELECT MIN(" + col_date + "), MAX(" + col_date + "), COUNT(*) "
        "FROM " + main_table + " WHERE " + col_ticker + " = ?", (t,))
    row = cur.fetchone()
    dmin, dmax, n = row[0], row[1], row[2]
    if not dmin or not dmax:
        continue
    try:
        d1 = datetime.fromisoformat(dmin[:10])
        d2 = datetime.fromisoformat(dmax[:10])
        months = (d2 - d1).days / 30.4
    except Exception:
        months = 0
    ranges.append((t, dmin[:10], dmax[:10], n, months))

ranges.sort(key=lambda r: -r[4])
for t, dmin, dmax, n, months in ranges[:30]:
    print(f"{t:<12} {dmin:<12} {dmax:<12} {n:>7} {months:>6.1f}")

if len(ranges) > 30:
    print("... (+" + str(len(ranges) - 30) + " tickers)")

print()
print("=" * 70)
print("VERDICT")
print("=" * 70)
if not ranges:
    print("[ERR] aucun ticker avec historique")
    sys.exit(1)

# Mediane de couverture
months_list = sorted([r[4] for r in ranges])
median_m = months_list[len(months_list) // 2]
min_m = min(months_list)
max_m = max(months_list)
print(f"Couverture mois - min: {min_m:.1f} / mediane: {median_m:.1f} / max: {max_m:.1f}")
print()

# Compte tickers ayant >= 12 mois et >= 24 mois
n12 = sum(1 for r in ranges if r[4] >= 12)
n24 = sum(1 for r in ranges if r[4] >= 24)
print(f"Tickers >= 12 mois: {n12} / {len(ranges)}")
print(f"Tickers >= 24 mois: {n24} / {len(ranges)}")
print()

if n24 >= len(ranges) * 0.8:
    print(">>> Recommandation: jalon 8C fenetre 24 mois (80%+ univers couvre)")
elif n12 >= len(ranges) * 0.8:
    print(">>> Recommandation: jalon 8C fenetre 12 mois")
    print("    24 mois necessiterait fetch historique additionnel pour " +
          str(len(ranges) - n24) + " tickers")
else:
    print(">>> Couverture insuffisante, fetch historique necessaire avant 8C")

# Verifie VIX (FRED) - utile pour market_regime
print()
print("=" * 70)
print("VIX / FRED")
print("=" * 70)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name LIKE '%vix%' OR name LIKE '%fred%' OR name LIKE '%macro%')")
fred_tables = [r[0] for r in cur.fetchall()]
print("Tables macro/FRED/VIX:", fred_tables)
for t in fred_tables:
    try:
        cur.execute("SELECT COUNT(*) FROM " + t)
        n = cur.fetchone()[0]
        print(" ", t, ":", n, "lignes")
    except Exception:
        pass

conn.close()
print()
print("[DONE]")
