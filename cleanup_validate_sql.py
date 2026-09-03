# =====================================================================
# cleanup_validate_sql.py
# Cleanup + validation DIRECTE en SQL (pas d'API, pas de login)
# =====================================================================
import sqlite3
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

REJECT_IDS   = [165, 166]
VALIDATE_IDS = [167, 168, 169]
REJECT_REASON = "Stale duplicate from cycle 17:57 - superseded by fresh cycle 20:59 (post-v6.5.1)"

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("  CLEANUP + VALIDATE v6.5.1  -  SQL direct")
print("=" * 70)

# ---------------------------------------------------------------------
# 1. Snapshot AVANT
# ---------------------------------------------------------------------
print()
print("[1] AVANT")
print("-" * 70)
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status
      FROM orders o JOIN instruments i ON i.id=o.instrument_id
     WHERE o.id IN (165,166,167,168,169)
     ORDER BY o.id
""")
for r in cur.fetchall():
    print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  qty={r['quantity']:<8}  status={r['status']}")

# Confirmation
print()
ans = input("Confirmer rejet #165/#166 + validation #167/#168/#169 ? (o/N) : ").strip().lower()
if ans != "o":
    print("Annule.")
    con.close()
    raise SystemExit(0)

now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

# ---------------------------------------------------------------------
# 2. Reject doublons
# ---------------------------------------------------------------------
print()
print("[2] Rejet #165 et #166...")
print("-" * 70)
for oid in REJECT_IDS:
    cur.execute("""
        UPDATE orders
           SET status='rejected',
               rejection_reason=?,
               validated_at=?
         WHERE id=? AND status='pending_validation'
    """, (REJECT_REASON, now, oid))
    if cur.rowcount == 1:
        print(f"  Reject #{oid}  OK")
    else:
        print(f"  Reject #{oid}  SKIP (deja traite ou introuvable)")

# ---------------------------------------------------------------------
# 3. Valider + filler #167/#168/#169 et mettre a jour les positions
# ---------------------------------------------------------------------
print()
print("[3] Validation + fill #167/#168/#169 + maj positions...")
print("-" * 70)

for oid in VALIDATE_IDS:
    cur.execute("""
        SELECT o.id, o.instrument_id, i.ticker, o.side, o.quantity, o.status
          FROM orders o JOIN instruments i ON i.id=o.instrument_id
         WHERE o.id=?
    """, (oid,))
    order = cur.fetchone()
    if not order:
        print(f"  #{oid}  introuvable - SKIP")
        continue
    if order["status"] != "pending_validation":
        print(f"  #{oid}  status={order['status']} - SKIP")
        continue

    iid = order["instrument_id"]
    side = order["side"]
    qty  = float(order["quantity"])

    # Prix courant (depuis portfolio_positions ou table prices)
    cur.execute("SELECT current_price FROM portfolio_positions WHERE instrument_id=?", (iid,))
    pp = cur.fetchone()
    px = pp["current_price"] if pp and pp["current_price"] else 0.0
    if not px:
        # Fallback : derniere ligne prices
        cur.execute("""
            SELECT close FROM prices
             WHERE instrument_id=? ORDER BY date DESC LIMIT 1
        """, (iid,))
        pr = cur.fetchone()
        px = pr["close"] if pr else 0.0

    delta_qty = qty if side.lower() == "buy" else -qty
    cash_flow = -delta_qty * px   # buy : cash diminue, sell : cash augmente

    # 3a. Marquer ordre filled
    cur.execute("""
        UPDATE orders
           SET status='filled',
               validated_at=?,
               validated_by='sql_direct_v6.5.1'
         WHERE id=?
    """, (now, oid))

    # 3b. Mettre a jour position
    if pp:
        new_qty = float(pp["quantity"] if "quantity" in pp.keys() else 0) + delta_qty if False else None
        # Recharger ligne complete pour avoir avg_cost et quantity
        cur.execute("SELECT quantity, avg_cost FROM portfolio_positions WHERE instrument_id=?", (iid,))
        cur_pos = cur.fetchone()
        cur_qty = float(cur_pos["quantity"])
        cur_avg = float(cur_pos["avg_cost"]) if cur_pos["avg_cost"] else px

        new_qty = cur_qty + delta_qty
        if side.lower() == "buy" and new_qty > 0:
            # Weighted average cost
            new_avg = (cur_qty * cur_avg + qty * px) / new_qty
        else:
            new_avg = cur_avg  # sell ne change pas l'avg_cost

        cur.execute("""
            UPDATE portfolio_positions
               SET quantity=?, avg_cost=?, current_price=?,
                   unrealized_pnl=(?-?)*?,
                   updated_at=?
             WHERE instrument_id=?
        """, (new_qty, new_avg, px, px, new_avg, new_qty, now, iid))
    else:
        cur.execute("""
            INSERT INTO portfolio_positions
                (instrument_id, quantity, avg_cost, current_price, unrealized_pnl, weight_pct, updated_at)
            VALUES (?, ?, ?, ?, 0, 0, ?)
        """, (iid, delta_qty, px, px, now))

    # 3c. Mettre a jour cash
    cur.execute("""
        UPDATE portfolio_state
           SET cash = cash + ?
         WHERE id = (SELECT MAX(id) FROM portfolio_state)
    """, (cash_flow,))

    print(f"  #{oid}  {order['ticker']:<6}  {side:<4}  qty={qty}  @ {px:.2f}  delta_cash={cash_flow:+.2f}  OK")

con.commit()

# ---------------------------------------------------------------------
# 4. Recalcul weight_pct des positions
# ---------------------------------------------------------------------
print()
print("[4] Recalcul weight_pct des positions...")
print("-" * 70)
cur.execute("SELECT total_value FROM portfolio_state ORDER BY id DESC LIMIT 1")
tv = cur.fetchone()
total_value = tv["total_value"] if tv else 0
if total_value:
    cur.execute("""
        UPDATE portfolio_positions
           SET weight_pct = ROUND(100.0 * quantity * current_price / ?, 4)
         WHERE quantity != 0
    """, (total_value,))
    con.commit()
    print(f"  Recalcul OK (total_value={total_value:,.2f})")

# Recalcule total_value = cash + somme(positions * px)
cur.execute("""
    SELECT cash FROM portfolio_state ORDER BY id DESC LIMIT 1
""")
cash = cur.fetchone()["cash"]
cur.execute("""
    SELECT SUM(quantity * current_price) AS inv
      FROM portfolio_positions
""")
inv = cur.fetchone()["inv"] or 0
new_total = cash + inv
cur.execute("""
    UPDATE portfolio_state
       SET total_value=?
     WHERE id=(SELECT MAX(id) FROM portfolio_state)
""", (new_total,))
con.commit()
print(f"  Nouvelle NAV : cash={cash:,.2f} + invested={inv:,.2f} = total_value={new_total:,.2f}")

# ---------------------------------------------------------------------
# 5. Snapshot APRES
# ---------------------------------------------------------------------
print()
print("[5] APRES")
print("-" * 70)
cur.execute("""
    SELECT o.id, i.ticker, o.side, o.quantity, o.status,
           datetime(o.validated_at,'localtime') AS validated,
           o.rejection_reason
      FROM orders o JOIN instruments i ON i.id=o.instrument_id
     WHERE o.id IN (165,166,167,168,169)
     ORDER BY o.id
""")
for r in cur.fetchall():
    reason = (r['rejection_reason'] or "")[:45]
    print(f"  #{r['id']:>4}  {r['ticker']:<6}  {r['side']:<4}  qty={r['quantity']:<8}  "
          f"status={r['status']:<12}  validated={r['validated'] or '-':<20}  {reason}")

print()
print("[positions cles] post-fills :")
cur.execute("""
    SELECT i.ticker, pp.quantity, pp.weight_pct, pt.target_weight_pct AS tgt
      FROM portfolio_positions pp
      JOIN instruments i ON i.id=pp.instrument_id
 LEFT JOIN portfolio_targets pt ON pt.ticker=i.ticker AND pt.active=1
     WHERE i.ticker IN ('META','LINK','ETH')
     ORDER BY i.ticker
""")
for r in cur.fetchall():
    tgt = r['tgt'] or 0
    drift = (r['weight_pct'] or 0) - tgt
    print(f"  {r['ticker']:<6} qty={r['quantity']:<10}  weight={r['weight_pct']:>6.2f}%  "
          f"target={tgt:>6.2f}%  drift={drift:+.2f}%")

con.close()
print()
print("=" * 70)
print("  TERMINE")
print("=" * 70)
