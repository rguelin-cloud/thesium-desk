# -*- coding: utf-8 -*-
# nextones-diag-check9-fills-side-v1.py
# Diag : pourquoi check 9 lit buy=$0 sell=$0 alors que detail orders montre fills > 0.
# Hypothese : smoke-test filtre side='BUY'/'SELL' (upper) mais fills.side='buy'/'sell' (lower).
# Usage : py -3.13 nextones-diag-check9-fills-side-v1.py
import sqlite3
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

RUN_ID = 13

print("=" * 72)
print(f"DIAG check 9 - run_id={RUN_ID}")
print("=" * 72)

# 1. Distribution des side dans replay_fills
print("\n[1] Distribution side dans replay_fills :")
for r in cur.execute(
    "SELECT side, COUNT(*) n, SUM(notional) sn FROM replay_fills "
    "WHERE run_id=? GROUP BY side", (RUN_ID,)
).fetchall():
    print(f"    side={r['side']!r:12s}  n={r['n']:3d}  sum_notional=${r['sn']:>14,.2f}")

# 2. Distribution des side dans replay_orders (filled only)
print("\n[2] Distribution side dans replay_orders status='filled' :")
for r in cur.execute(
    "SELECT side, status, COUNT(*) n FROM replay_orders "
    "WHERE run_id=? GROUP BY side, status", (RUN_ID,)
).fetchall():
    print(f"    side={r['side']!r:12s}  status={r['status']!r:12s}  n={r['n']:3d}")

# 3. Filtres possibles : upper / lower / casefold
print("\n[3] Filtres test sum(notional) :")
for label, where in [
    ("side='BUY'",  "side='BUY'"),
    ("side='SELL'", "side='SELL'"),
    ("side='buy'",  "side='buy'"),
    ("side='sell'", "side='sell'"),
    ("UPPER(side)='BUY'",  "UPPER(side)='BUY'"),
    ("UPPER(side)='SELL'", "UPPER(side)='SELL'"),
]:
    row = cur.execute(
        f"SELECT COALESCE(SUM(notional),0) s, COUNT(*) n FROM replay_fills "
        f"WHERE run_id=? AND {where}", (RUN_ID,)
    ).fetchone()
    print(f"    {label:25s}  n={row['n']:3d}  sum=${row['s']:>14,.2f}")

# 4. NAV evolution + cash delta
print("\n[4] Cash delta :")
navs = cur.execute(
    "SELECT day_t, nav, cash FROM replay_nav_history "
    "WHERE run_id=? ORDER BY day_t", (RUN_ID,)
).fetchall()
for r in navs:
    print(f"    {r['day_t']}  NAV=${r['nav']:>12,.2f}  cash=${r['cash']:>12,.2f}")
K = 1_000_000.0
cash_final = navs[-1]['cash'] if navs else 0
print(f"    K - cash_final = ${K - cash_final:>14,.2f}")

# 5. Integrity correcte (avec UPPER pour etre robuste) :
print("\n[5] Integrity check correct (UPPER) :")
row = cur.execute(
    "SELECT COALESCE(SUM(CASE WHEN UPPER(side)='BUY' THEN notional ELSE 0 END),0) buy_n, "
    "       COALESCE(SUM(CASE WHEN UPPER(side)='SELL' THEN notional ELSE 0 END),0) sell_n "
    "FROM replay_fills WHERE run_id=?", (RUN_ID,)
).fetchone()
buy_n, sell_n = row['buy_n'], row['sell_n']
net = buy_n - sell_n
print(f"    buy_notional   = ${buy_n:>14,.2f}")
print(f"    sell_notional  = ${sell_n:>14,.2f}")
print(f"    net (buy-sell) = ${net:>14,.2f}")
print(f"    K - cash       = ${K - cash_final:>14,.2f}")
print(f"    diff           = ${abs(net - (K - cash_final)):>14,.2f}")
tol = 0.001 * K
verdict = "PASS" if abs(net - (K - cash_final)) <= tol else "FAIL"
print(f"    tolerance 0.1% = ${tol:>14,.2f}   verdict={verdict}")

con.close()
