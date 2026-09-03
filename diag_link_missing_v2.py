# diag_link_missing_v2.py - portfolio_targets indexe par ticker
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

db = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("2. Target LINK dans portfolio_targets")
print("=" * 70)
cur.execute("SELECT * FROM portfolio_targets WHERE ticker = 'LINK'")
for r in cur.fetchall():
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("3. Target LINK dans dernier snapshot (snap-20260525T103852-f7835b)")
print("=" * 70)
cur.execute("""
    SELECT snapshot_id, ticker, score, target_weight_pct, prev_target_weight_pct,
           regime, included, cap_floor_applied
    FROM portfolio_targets_history
    WHERE ticker = 'LINK'
    ORDER BY created_at DESC LIMIT 3
""")
for r in cur.fetchall():
    print(f"  {dict(r)}")

print()
print("=" * 70)
print("4. Recap LINK")
print("=" * 70)
# Position
cur.execute("""
    SELECT quantity, current_price, weight_pct
    FROM portfolio_positions
    WHERE instrument_id = 17
""")
p = cur.fetchone()
# Target
cur.execute("SELECT target_weight_pct FROM portfolio_targets WHERE ticker='LINK'")
t = cur.fetchone()
# NAV
cur.execute("SELECT total_value FROM portfolio_state LIMIT 1")
nav = cur.fetchone()[0]

if p and t:
    qty, price, w_pct = p['quantity'], p['current_price'], p['weight_pct']
    tw = t['target_weight_pct']
    val = qty * price
    delta_pct = w_pct - tw
    delta_eur = (delta_pct / 100) * nav
    print(f"  NAV         = {nav:,.2f}")
    print(f"  LINK qty    = {qty}")
    print(f"  LINK price  = {price}")
    print(f"  LINK value  = {val:,.2f} ({w_pct}% du NAV)")
    print(f"  LINK target = {tw}%")
    print(f"  Delta       = {delta_pct:+.4f} % NAV  ({delta_eur:+,.2f} EUR)")
    print(f"  MIN_TRADE_WEIGHT_PCT = 0.3 %")
    if abs(delta_pct) < 0.3:
        print(f"  -> Ecart |{delta_pct:.4f}| < 0.3 % -> DROP par reconciler (comportement normal)")
    else:
        print(f"  -> Ecart {delta_pct:.4f} >= 0.3 % -> devrait proposer un trade")

print()
print("=" * 70)
print("5. cycle_reconciliation_log LINK -- tous cycles recents")
print("=" * 70)
cur.execute("PRAGMA table_info(cycle_reconciliation_log)")
cols = [c[1] for c in cur.fetchall()]
print(f"  cols : {cols}")
print()

cur.execute("""
    SELECT * FROM cycle_reconciliation_log
    WHERE ticker = 'LINK'
    ORDER BY created_at DESC
    LIMIT 5
""")
for r in cur.fetchall():
    d = dict(r)
    cycle = d.get('cycle_id', '?')
    action = d.get('action', '?')
    side = d.get('side', '?')
    qty = d.get('qty_net', d.get('quantity', '?'))
    sig = d.get('signal', d.get('dsig', '?'))
    reason = (d.get('reason') or d.get('rationale') or '')[:120]
    print(f"  cycle={cycle}")
    print(f"    action={action} side={side} qty={qty} signal={sig}")
    print(f"    reason={reason}")
    print()

con.close()
