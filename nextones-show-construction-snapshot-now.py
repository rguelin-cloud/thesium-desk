# nextones-show-construction-snapshot-now.py
# Affiche le dernier snapshot portfolio_targets + coverage vs target_universe (17 actifs)
# ASCII pur, pas d'accents. Read utf-8-sig, write utf-8 sans BOM.

import sqlite3
import os
import sys
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

if not os.path.exists(DB):
    print(f"DB introuvable: {DB}")
    sys.exit(1)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

# 1) Dernier snapshot
print("=" * 70)
print("DERNIER SNAPSHOT portfolio_targets")
print("=" * 70)

row = cur.execute(
    "SELECT snapshot_id, MAX(updated_at) AS last_ts, COUNT(*) AS n "
    "FROM portfolio_targets "
    "GROUP BY snapshot_id "
    "ORDER BY last_ts DESC LIMIT 1"
).fetchone()

if not row:
    print("Aucun snapshot trouve dans portfolio_targets")
    con.close()
    sys.exit(0)

sid = row["snapshot_id"]
print(f"snapshot_id : {sid}")
print(f"updated_at  : {row['last_ts']}")
print(f"n actifs    : {row['n']}")
print()

# 2) Detail du snapshot
print("=" * 70)
print(f"DETAIL DU SNAPSHOT {sid}")
print("=" * 70)
print(f"{'TICKER':<10} {'WEIGHT_PCT':>12} {'SCORE':>10} {'ACTIVE':>8} {'SOURCE':<20} {'AGENT':>8}")
print("-" * 70)

rows = cur.execute(
    "SELECT ticker, target_weight_pct, score, active, source, agent_decided "
    "FROM portfolio_targets WHERE snapshot_id = ? "
    "ORDER BY target_weight_pct DESC",
    (sid,)
).fetchall()

snap_tickers = set()
total_w = 0.0
for r in rows:
    t = r["ticker"]
    w = r["target_weight_pct"] or 0.0
    s = r["score"]
    a = r["active"]
    src = r["source"] or ""
    ag = r["agent_decided"]
    snap_tickers.add(t)
    total_w += w
    s_str = f"{s:.4f}" if s is not None else "-"
    print(f"{t:<10} {w:>11.2f}% {s_str:>10} {str(a):>8} {src:<20} {str(ag):>8}")

print("-" * 70)
print(f"{'TOTAL':<10} {total_w:>11.2f}%")
print()

# 3) Coverage vs target_universe
print("=" * 70)
print("COVERAGE vs target_universe (17 actifs attendus)")
print("=" * 70)

uni_rows = cur.execute(
    "SELECT ticker FROM target_universe ORDER BY ticker"
).fetchall()
uni_tickers = [r["ticker"] for r in uni_rows]

print(f"target_universe : {len(uni_tickers)} tickers")
print(f"snapshot        : {len(snap_tickers)} tickers")
print()

ok_count = 0
mis_count = 0
print(f"{'TICKER':<10} {'STATUS':<10}")
print("-" * 25)
for t in uni_tickers:
    if t in snap_tickers:
        print(f"{t:<10} {'OK':<10}")
        ok_count += 1
    else:
        print(f"{t:<10} {'MIS':<10}")
        mis_count += 1

print("-" * 25)
print(f"OK  : {ok_count}/{len(uni_tickers)}")
print(f"MIS : {mis_count}/{len(uni_tickers)}")
print()

# 4) Pour les MIS, regarder l'historique prices disponible
if mis_count > 0:
    print("=" * 70)
    print("DIAG PRICES pour les tickers MIS")
    print("=" * 70)
    missing = [t for t in uni_tickers if t not in snap_tickers]
    print(f"{'TICKER':<10} {'N_PRICES':>10} {'FIRST_DT':<22} {'LAST_DT':<22}")
    print("-" * 70)
    for t in missing:
        # Essayer plusieurs schemas possibles
        try:
            r = cur.execute(
                "SELECT COUNT(*) AS n, MIN(date) AS first_dt, MAX(date) AS last_dt "
                "FROM prices WHERE ticker = ?",
                (t,)
            ).fetchone()
        except sqlite3.OperationalError:
            try:
                r = cur.execute(
                    "SELECT COUNT(*) AS n, MIN(ts) AS first_dt, MAX(ts) AS last_dt "
                    "FROM prices WHERE ticker = ?",
                    (t,)
                ).fetchone()
            except sqlite3.OperationalError:
                r = None
        if r:
            n = r["n"] or 0
            fd = r["first_dt"] or "-"
            ld = r["last_dt"] or "-"
            print(f"{t:<10} {n:>10} {str(fd):<22} {str(ld):<22}")
        else:
            print(f"{t:<10} {'?':>10} {'schema inconnu':<22}")
    print()

# 5) Compter les ordres du jour
print("=" * 70)
print("ORDRES DU JOUR")
print("=" * 70)
today = datetime.now().strftime("%Y-%m-%d")
try:
    r = cur.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE date(created_at) = ?",
        (today,)
    ).fetchone()
    print(f"orders created today ({today}) : {r['n']}")
except sqlite3.OperationalError as e:
    print(f"Erreur orders: {e}")

# Dernieres entrees orders
try:
    rows = cur.execute(
        "SELECT id, instrument_id, side, quantity, status, created_at "
        "FROM orders ORDER BY id DESC LIMIT 5"
    ).fetchall()
    if rows:
        print()
        print("5 derniers ordres:")
        for r in rows:
            print(f"  id={r['id']} instr={r['instrument_id']} side={r['side']} qty={r['quantity']} status={r['status']} at={r['created_at']}")
except sqlite3.OperationalError as e:
    print(f"Erreur orders detail: {e}")

con.close()
print()
print("Done.")
