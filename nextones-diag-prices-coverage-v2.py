#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pre-jalon 8A v2 : diag couverture prix DB (schema normalise).

V1 supposait colonne ticker directe. V2 detecte le schema normalise:
prices (instrument_id) -> instruments (ticker/symbol).

ASCII pur, idempotent, read-only DB.
"""
import io
import os
import sqlite3
import sys
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

print("=" * 70)
print("DIAG COUVERTURE PRIX V2 - PRE-JALON 8A")
print("=" * 70)

if not os.path.isfile(DB):
    print("[ERR] DB introuvable:", DB)
    sys.exit(1)

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Detecte la table instruments
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instruments'")
if not cur.fetchall():
    print("[ERR] table instruments absente")
    # Fallback: liste tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("Tables disponibles:", [r[0] for r in cur.fetchall()])
    sys.exit(1)

# Schema instruments
cur.execute("PRAGMA table_info(instruments)")
inst_cols = [r["name"] for r in cur.fetchall()]
print("instruments cols:", inst_cols)

# Detecte colonne ticker
col_ticker_inst = None
for c in inst_cols:
    if c.lower() in ("ticker", "symbol", "code"):
        col_ticker_inst = c
        break
if not col_ticker_inst:
    print("[ERR] colonne ticker/symbol introuvable dans instruments")
    sys.exit(1)
print("Colonne ticker dans instruments:", col_ticker_inst)

# Detecte colonne asset_class
col_class = None
for c in inst_cols:
    if c.lower() in ("asset_class", "class", "type", "category"):
        col_class = c
        break
print("Colonne asset_class:", col_class)
print()

# Schema prices
cur.execute("PRAGMA table_info(prices)")
price_cols = [r["name"] for r in cur.fetchall()]
print("prices cols:", price_cols)
cur.execute("SELECT COUNT(*) FROM prices")
n_total = cur.fetchone()[0]
print("prices rows:", n_total)
print()

# Liste instruments
if col_class:
    cur.execute(f"SELECT id, {col_ticker_inst}, {col_class} FROM instruments ORDER BY {col_ticker_inst}")
    instruments = [(r[0], r[1], r[2]) for r in cur.fetchall()]
else:
    cur.execute(f"SELECT id, {col_ticker_inst} FROM instruments ORDER BY {col_ticker_inst}")
    instruments = [(r[0], r[1], None) for r in cur.fetchall()]

print("Total instruments:", len(instruments))
print()

# Couverture par instrument
print("=" * 80)
print("COUVERTURE PAR INSTRUMENT")
print("=" * 80)
print(f"{'TICKER':<12} {'CLASS':<10} {'MIN':<12} {'MAX':<12} {'JOURS':>7} {'MOIS':>6}")
print("-" * 80)

ranges = []
for inst_id, ticker, asset_class in instruments:
    cur.execute(
        "SELECT MIN(date), MAX(date), COUNT(*) FROM prices WHERE instrument_id = ?",
        (inst_id,),
    )
    row = cur.fetchone()
    dmin, dmax, n = row[0], row[1], row[2]
    if not dmin or not dmax or n == 0:
        ranges.append((ticker, asset_class or "?", None, None, 0, 0.0))
        continue
    try:
        d1 = datetime.fromisoformat(str(dmin)[:10])
        d2 = datetime.fromisoformat(str(dmax)[:10])
        months = (d2 - d1).days / 30.4
    except Exception:
        months = 0.0
    ranges.append((ticker, asset_class or "?", str(dmin)[:10], str(dmax)[:10], n, months))

# Sort par couverture decroissante
ranges.sort(key=lambda r: -r[5])
for ticker, klass, dmin, dmax, n, months in ranges:
    dmin_s = dmin or "-"
    dmax_s = dmax or "-"
    print(f"{ticker:<12} {klass:<10} {dmin_s:<12} {dmax_s:<12} {n:>7} {months:>6.1f}")

print()
print("=" * 80)
print("VERDICT")
print("=" * 80)

ranges_with_data = [r for r in ranges if r[5] > 0]
if not ranges_with_data:
    print("[ERR] aucun instrument avec historique")
    sys.exit(1)

months_list = sorted([r[5] for r in ranges_with_data])
median_m = months_list[len(months_list) // 2]
min_m = min(months_list)
max_m = max(months_list)
print(f"Instruments avec donnees: {len(ranges_with_data)} / {len(ranges)}")
print(f"Couverture mois (instruments avec donnees) - min: {min_m:.1f} / mediane: {median_m:.1f} / max: {max_m:.1f}")
print()

n6 = sum(1 for r in ranges_with_data if r[5] >= 6)
n12 = sum(1 for r in ranges_with_data if r[5] >= 12)
n18 = sum(1 for r in ranges_with_data if r[5] >= 18)
n24 = sum(1 for r in ranges_with_data if r[5] >= 24)
print(f"Instruments >=  6 mois: {n6}")
print(f"Instruments >= 12 mois: {n12}")
print(f"Instruments >= 18 mois: {n18}")
print(f"Instruments >= 24 mois: {n24}")
print()

# Couverture par classe
if col_class:
    by_class = {}
    for r in ranges_with_data:
        k = r[1]
        by_class.setdefault(k, []).append(r[5])
    print("Par classe:")
    for k, ms in sorted(by_class.items()):
        ms_sorted = sorted(ms)
        med = ms_sorted[len(ms_sorted) // 2]
        print(f"  {k:<10} n={len(ms):3d}  median {med:5.1f} mois  min {min(ms):4.1f}  max {max(ms):5.1f}")
    print()

# Recommandation
print("Recommandation fenetre 8C:")
if n24 >= len(ranges_with_data) * 0.7:
    print("  >>> 24 mois (70%+ instruments couverts)")
elif n12 >= len(ranges_with_data) * 0.7:
    print("  >>> 12 mois (24 mois necessiterait fetch additionnel)")
else:
    print("  >>> Reduire univers ou fetch historique prealable")

# Verifie VIX / macro
print()
print("=" * 80)
print("VIX / FRED / MACRO")
print("=" * 80)
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name LIKE '%vix%' OR name LIKE '%fred%' OR name LIKE '%macro%' OR name LIKE '%calendar%')")
fred_tables = [r[0] for r in cur.fetchall()]
print("Tables macro:", fred_tables)
for t in fred_tables:
    try:
        cur.execute("SELECT COUNT(*) FROM " + t)
        n = cur.fetchone()[0]
        print("  " + t + ": " + str(n) + " lignes")
        # Si <20 lignes, dump
        if 0 < n <= 20:
            cur.execute("SELECT * FROM " + t + " LIMIT 5")
            for row in cur.fetchall():
                print("    sample:", dict(row))
    except Exception as e:
        print("  " + t + ": ERR", e)

# Check si VIX est dans instruments
print()
cur.execute(f"SELECT id, {col_ticker_inst} FROM instruments WHERE "
            f"{col_ticker_inst} IN ('VIX', '^VIX', 'VIXY')")
vix_inst = cur.fetchall()
if vix_inst:
    for inst_id, t in vix_inst:
        cur.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM prices WHERE instrument_id=?", (inst_id,))
        r = cur.fetchone()
        print(f"VIX trouve dans instruments: ticker={t}, n={r[0]}, min={r[1]}, max={r[2]}")
else:
    print("[WARN] VIX absent de instruments - sera a fetch pour le replay")

conn.close()
print()
print("[DONE]")
