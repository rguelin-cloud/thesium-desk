# nextones-reject-xlb-xli-finalize.py
# Option C : XLB et XLI rejetes + retires du target_universe
# 1) UPDATE universe_candidates SET status='rejected' WHERE ticker IN ('XLB','XLI') AND status IN ('approved','pending')
# 2) UPDATE target_universe SET is_active=0 WHERE ticker IN ('XLB','XLI')
# 3) Affiche etat avant/apres
# ASCII pur. Idempotent.

import sqlite3
import os
import sys
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if not os.path.exists(DB):
    print(f"DB introuvable: {DB}")
    sys.exit(1)

TICKERS = ["XLB", "XLI"]
REASON = "Option C: redondance cyclique avec XLE/XLK, exclus du nominal le 2026-05-29"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print(f"FINALISE Option C - rejeter {TICKERS}")
print("=" * 70)

# AVANT
print()
print("--- AVANT ---")
print("universe_candidates (toutes lignes XLB/XLI):")
for t in TICKERS:
    rows = cur.execute(
        "SELECT id, ticker, status, score, reviewed_at, reviewed_by, notes "
        "FROM universe_candidates WHERE ticker = ? ORDER BY id DESC", (t,)
    ).fetchall()
    for r in rows:
        print(f"  id={r['id']} {r['ticker']} status={r['status']} score={r['score']} "
              f"reviewed_at={r['reviewed_at']} by={r['reviewed_by']} notes={r['notes']}")

print()
print("target_universe (XLB/XLI):")
for t in TICKERS:
    r = cur.execute(
        "SELECT id, ticker, is_active, max_weight_pct, min_weight_pct, added_at "
        "FROM target_universe WHERE ticker = ?", (t,)
    ).fetchone()
    if r:
        print(f"  id={r['id']} {r['ticker']} is_active={r['is_active']} "
              f"max={r['max_weight_pct']} min={r['min_weight_pct']} added={r['added_at']}")
    else:
        print(f"  {t}: absent")

# PATCH
print()
print("--- PATCH ---")

now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 1) universe_candidates : rejeter approved et pending pour XLB/XLI
n_uc = 0
for t in TICKERS:
    cur.execute(
        "UPDATE universe_candidates "
        "SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, notes = ? "
        "WHERE ticker = ? AND status IN ('approved', 'pending')",
        (now, "rguelin", REASON, t)
    )
    n_uc += cur.rowcount
print(f"universe_candidates : {n_uc} ligne(s) marquees 'rejected'")

# 2) target_universe : desactiver
n_tu = 0
for t in TICKERS:
    cur.execute(
        "UPDATE target_universe SET is_active = 0 WHERE ticker = ?", (t,)
    )
    n_tu += cur.rowcount
print(f"target_universe     : {n_tu} ligne(s) is_active=0")

con.commit()

# APRES
print()
print("--- APRES ---")
print("universe_candidates (toutes lignes XLB/XLI):")
for t in TICKERS:
    rows = cur.execute(
        "SELECT id, ticker, status, reviewed_at, reviewed_by, notes "
        "FROM universe_candidates WHERE ticker = ? ORDER BY id DESC", (t,)
    ).fetchall()
    for r in rows:
        print(f"  id={r['id']} {r['ticker']} status={r['status']} "
              f"reviewed_at={r['reviewed_at']} by={r['reviewed_by']} notes={(r['notes'] or '')[:50]}")

print()
print("target_universe (XLB/XLI):")
for t in TICKERS:
    r = cur.execute(
        "SELECT id, ticker, is_active FROM target_universe WHERE ticker = ?", (t,)
    ).fetchone()
    if r:
        print(f"  id={r['id']} {r['ticker']} is_active={r['is_active']}")

# Compteur final target_universe is_active=1
n_active = cur.execute(
    "SELECT COUNT(*) AS n FROM target_universe WHERE is_active = 1"
).fetchone()["n"]
print()
print(f"target_universe is_active=1 : {n_active} tickers")

# Liste finale
rows = cur.execute(
    "SELECT ticker, asset_class FROM target_universe WHERE is_active = 1 ORDER BY asset_class, ticker"
).fetchall()
print()
print("Univers nominal final:")
for r in rows:
    print(f"  {r['ticker']:<8} ({r['asset_class']})")

con.close()
print()
print("Done.")
print()
print("Etape suivante : relancer /api/construction/run pour rebuild le snapshot final.")
