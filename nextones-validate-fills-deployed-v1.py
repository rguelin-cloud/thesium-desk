# -*- coding: utf-8 -*-
# [VALIDATE_FILLS_DEPLOYED_V1]
# Confirme que les 3 orders #343 #344 #345 sont reellement filled en DB.
import io, os, sqlite3, json
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

con = sqlite3.connect(DB, timeout=10)
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=" * 70)
print("1) Status orders 343/344/345")
print("=" * 70)
for r in cur.execute("SELECT id, instrument_id, side, quantity, status, validated_by, validated_at FROM orders WHERE id IN (343,344,345) ORDER BY id"):
    print("  #%d %s %s qty=%s status=%s by=%s at=%s" % (
        r["id"], r["side"], r["instrument_id"], r["quantity"],
        r["status"], r["validated_by"], r["validated_at"]))

print("\n" + "=" * 70)
print("2) Fills lies (order_id IN 343,344,345)")
print("=" * 70)
for r in cur.execute("SELECT id, order_id, fill_price, fill_quantity, slippage, fees, filled_at FROM fills WHERE order_id IN (343,344,345) ORDER BY order_id"):
    print("  fill_id=%d order=%d px=%s qty=%s slip=%s fees=%s at=%s" % (
        r["id"], r["order_id"], r["fill_price"], r["fill_quantity"],
        r["slippage"], r["fees"], r["filled_at"]))

print("\n" + "=" * 70)
print("3) Position AAPL et MSFT")
print("=" * 70)
for sym in ("AAPL", "MSFT"):
    r = cur.execute("SELECT instrument_id, quantity, avg_cost, current_price, unrealized_pnl FROM portfolio_positions WHERE instrument_id = ?", (sym,)).fetchone()
    if r:
        print("  %s qty=%s avg=%s px=%s unrealized=%s" % (
            r["instrument_id"], r["quantity"], r["avg_cost"], r["current_price"], r["unrealized_pnl"]))
    else:
        print("  %s : pas de position (peut etre normal si SELL clos)" % sym)

print("\n" + "=" * 70)
print("4) Cash + portfolio_state")
print("=" * 70)
r = cur.execute("SELECT cash, total_value, total_pnl, updated_at FROM portfolio_state WHERE id=1").fetchone()
if r:
    print("  cash=%s total_value=%s total_pnl=%s updated_at=%s" % (
        r["cash"], r["total_value"], r["total_pnl"], r["updated_at"]))

print("\n" + "=" * 70)
print("5) log_event order_filled_human / order_rejected_human (10 derniers)")
print("=" * 70)
for r in cur.execute("SELECT id, event_type, ref_type, ref_id, agent, created_at FROM event_log WHERE event_type IN ('order_filled_human','order_rejected_human') ORDER BY id DESC LIMIT 10"):
    print("  #%d %s ref=%s:%s by=%s at=%s" % (
        r["id"], r["event_type"], r["ref_type"], r["ref_id"], r["agent"], r["created_at"]))

print("\n[DONE]")
con.close()
