# -*- coding: utf-8 -*-
# [VALIDATE_OPTION_A_E2E_V1]
# Verification end-to-end de Option A apres tous les patches.
import io, os, sqlite3, sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

con = sqlite3.connect(DB, timeout=10)
con.row_factory = sqlite3.Row
cur = con.cursor()

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

# 1) Cycle courant
section("1) Cycle courant (regime_log derniere ligne)")
r = cur.execute("SELECT id, cycle_id, regime, created_at FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
if r:
    current_cycle = r["cycle_id"]
    print(f"  cycle_id={current_cycle} regime={r['regime']} created_at={r['created_at']}")
else:
    print("  FAIL: regime_log vide")
    sys.exit(1)

# 2) Tous les orders du cycle courant
section(f"2) Orders du cycle courant ({current_cycle})")
rows = list(cur.execute(
    "SELECT id, instrument_id, side, quantity, status, validated_by, validated_at, created_at "
    "FROM orders WHERE cycle_id = ? ORDER BY id",
    (current_cycle,)
))
print(f"  Total: {len(rows)} orders")
for r in rows:
    print(f"  #{r['id']} {r['side']} {r['instrument_id']} qty={r['quantity']} "
          f"status={r['status']} by={r['validated_by']} at={r['validated_at']}")

# 3) Cycle anterieur (compare)
section("3) Cycle precedent (compare)")
prev = cur.execute(
    "SELECT cycle_id FROM regime_log WHERE id < (SELECT MAX(id) FROM regime_log) "
    "ORDER BY id DESC LIMIT 1"
).fetchone()
if prev:
    print(f"  cycle precedent: {prev['cycle_id']}")
    prev_count = cur.execute("SELECT COUNT(*) FROM orders WHERE cycle_id = ?", (prev["cycle_id"],)).fetchone()[0]
    print(f"  orders dans ce cycle: {prev_count}")
else:
    print("  pas de cycle precedent")

# 4) Distribution status global
section("4) Distribution status global (sur tous les orders)")
for r in cur.execute("SELECT status, COUNT(*) as n FROM orders GROUP BY status ORDER BY n DESC"):
    print(f"  {r['status']:20s} : {r['n']}")

# 5) Verifier que approve_and_fill_order n'a plus de cycle filled automatique
section("5) Orders 'approved' actuels (queue UI)")
rows = list(cur.execute("SELECT id, instrument_id, side, quantity, cycle_id FROM orders WHERE status = 'approved' ORDER BY id"))
print(f"  {len(rows)} orders en attente")
for r in rows:
    print(f"  #{r['id']} {r['side']} {r['instrument_id']} qty={r['quantity']} cycle={r['cycle_id']}")

# 6) Le cycle courant a-t-il cree des orders ?
section(f"6) Diagnostic : ce cycle a-t-il cree des orders ?")
cur_orders = cur.execute("SELECT COUNT(*) FROM orders WHERE cycle_id = ?", (current_cycle,)).fetchone()[0]
print(f"  Orders dans cycle {current_cycle}: {cur_orders}")
if cur_orders == 0:
    print("  EXPLICATION: le portfolio est deja aligne avec les targets")
    print("  -> Solution: regarder construction_targets_snapshot vs positions actuelles")

# 7) Construction targets vs positions actuelles
section("7) Construction targets snapshot (dernier)")
try:
    snap = cur.execute(
        "SELECT cycle_id, snapshot_json FROM construction_snapshots "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if snap:
        print(f"  snapshot cycle={snap['cycle_id']} (json {len(snap['snapshot_json'])} chars)")
except sqlite3.OperationalError as e:
    print(f"  (table construction_snapshots: {e})")

# 8) Positions courantes
section("8) Positions courantes")
positions = list(cur.execute(
    "SELECT instrument_id, quantity, avg_cost, current_price, unrealized_pnl "
    "FROM portfolio_positions WHERE quantity > 0 ORDER BY (quantity * current_price) DESC LIMIT 15"
))
for r in positions:
    val = r["quantity"] * r["current_price"]
    print(f"  {r['instrument_id']:8s} qty={r['quantity']:>10.2f} px={r['current_price']:>10.2f} val={val:>12.2f}")

# 9) portfolio_state
section("9) portfolio_state actuel")
r = cur.execute("SELECT cash, total_value, total_pnl, total_pnl_pct, daily_pnl, updated_at FROM portfolio_state WHERE id=1").fetchone()
if r:
    print(f"  cash={r['cash']}")
    print(f"  total_value={r['total_value']}")
    print(f"  total_pnl={r['total_pnl']} ({r['total_pnl_pct']}%)")
    print(f"  daily_pnl={r['daily_pnl']}")
    print(f"  updated_at={r['updated_at']}")

print("\n[DONE]")
con.close()
