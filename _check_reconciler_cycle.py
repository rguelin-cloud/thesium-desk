import sqlite3
c = sqlite3.connect('thesium.db')
c.row_factory = sqlite3.Row

print('=== Reconciler log complet pour cycle 20260524-204616 (META inclus ?) ===')
for r in c.execute("""
    SELECT ticker, action, reason, qty_in, side_in, delta_signal_pct, delta_target_pct
    FROM cycle_reconciliation_log
    WHERE cycle_id = '20260524-204616'
    ORDER BY ticker
"""):
    d = dict(r)
    print(f"  {d['ticker']:<6} action={d['action']:<8} side={d['side_in']:<5} qty={d['qty_in']:>6} dSig={d['delta_signal_pct']:>+6.2f}% dTgt={d['delta_target_pct']:>+6.2f}% | {d['reason']}")

print()
print('=== ExitAgent : ou est le code DRIFT rebalance ? ===')
