# diag_link_missing.py
# Pourquoi LINK est absent du cycle 20260525-104013 ?

import sqlite3
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("1. Position LINK actuelle dans portfolio_positions")
print("=" * 70)
cur.execute("PRAGMA table_info(portfolio_positions)")
cols_pp = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols_pp}")
cur.execute("""
    SELECT pp.*, i.ticker
    FROM portfolio_positions pp
    JOIN instruments i ON i.id = pp.instrument_id
    WHERE i.ticker = 'LINK'
""")
for r in cur.fetchall():
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("2. Target LINK dans portfolio_targets")
print("=" * 70)
cur.execute("PRAGMA table_info(portfolio_targets)")
cols_pt = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols_pt}")
cur.execute("""
    SELECT pt.*, i.ticker
    FROM portfolio_targets pt
    JOIN instruments i ON i.id = pt.instrument_id
    WHERE i.ticker = 'LINK'
""")
for r in cur.fetchall():
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("3. Target LINK dans dernier snapshot")
print("=" * 70)
cur.execute("""
    SELECT * FROM portfolio_targets_history
    WHERE ticker = 'LINK'
    ORDER BY created_at DESC
    LIMIT 3
""")
cur.execute("PRAGMA table_info(portfolio_targets_history)")
cols_pth = [c[1] for c in cur.fetchall()]
cur.execute("""
    SELECT * FROM portfolio_targets_history
    WHERE ticker = 'LINK'
    ORDER BY created_at DESC
    LIMIT 3
""")
for r in cur.fetchall():
    d = dict(zip(cols_pth, r))
    print(f"  snapshot={d.get('snapshot_id')} tw={d.get('target_weight_pct')} ptw={d.get('prev_target_weight_pct')} regime={d.get('regime')} included={d.get('included')} cap={d.get('cap_floor_applied')}")

print()
print("=" * 70)
print("4. Prix LINK actuel (close)")
print("=" * 70)
cur.execute("""
    SELECT date, close FROM prices
    WHERE instrument_id = 17
    ORDER BY date DESC
    LIMIT 3
""")
for r in cur.fetchall():
    print(f"  date={r[0]} close={r[1]}")

print()
print("=" * 70)
print("5. portfolio_state actuel")
print("=" * 70)
cur.execute("SELECT * FROM portfolio_state LIMIT 1")
cur.execute("PRAGMA table_info(portfolio_state)")
cols_ps = [c[1] for c in cur.fetchall()]
cur.execute("SELECT * FROM portfolio_state LIMIT 1")
r = cur.fetchone()
if r:
    d = dict(zip(cols_ps, r))
    print(f"  cash={d.get('cash')} total_value={d.get('total_value')} updated_at={d.get('updated_at')}")

print()
print("=" * 70)
print("6. Valeur position LINK estimee (qty * close)")
print("=" * 70)
cur.execute("""
    SELECT pp.quantity, p.close, pp.quantity * p.close as value_eur
    FROM portfolio_positions pp
    JOIN instruments i ON i.id = pp.instrument_id
    LEFT JOIN prices p ON p.instrument_id = pp.instrument_id
    WHERE i.ticker = 'LINK'
    ORDER BY p.date DESC
    LIMIT 1
""")
r = cur.fetchone()
if r:
    print(f"  qty={r[0]} close={r[1]} value={r[2]:.2f}")
    # Calcul ecart vs target
    cur.execute("SELECT total_value FROM portfolio_state LIMIT 1")
    tv = cur.fetchone()[0]
    actual_pct = (r[2] / tv) * 100 if tv else 0
    print(f"  actual_pct = {actual_pct:.3f}% du NAV {tv}")
    cur.execute("""
        SELECT target_weight_pct FROM portfolio_targets_history
        WHERE ticker = 'LINK'
        ORDER BY created_at DESC LIMIT 1
    """)
    tw = cur.fetchone()
    if tw:
        delta = actual_pct - tw[0]
        print(f"  target_pct = {tw[0]}% -> delta = {delta:+.3f}%")

print()
print("=" * 70)
print("7. cycle_reconciliation_log LINK dernier cycle")
print("=" * 70)
cur.execute("PRAGMA table_info(cycle_reconciliation_log)")
cols_log = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols_log}")
cur.execute("""
    SELECT * FROM cycle_reconciliation_log
    WHERE ticker = 'LINK' AND cycle_id = '20260525-104013'
""")
for r in cur.fetchall():
    print(f"  {dict(zip(cols_log, r))}")

print()
print("=" * 70)
print("8. cycle_reconciliation_log LINK -- tous cycles")
print("=" * 70)
cur.execute("""
    SELECT cycle_id, ticker, action, side, qty_net, signal, reason
    FROM cycle_reconciliation_log
    WHERE ticker = 'LINK'
    ORDER BY cycle_id DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  cycle={r[0]} action={r[1]} side={r[2]} qty={r[3]} signal={r[4]} reason={(r[5] or '')[:80]}")

con.close()
