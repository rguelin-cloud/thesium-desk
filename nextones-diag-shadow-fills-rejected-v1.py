"""Diag : simule fills en memoire pour cycle 20260611-144234 et liste rejected detaille.

Ne touche pas la DB. Reproduit la logique shadow_simulate_fills mais affiche
chaque rejected avec ticker + side + rejection_reason.
"""
import os, sys, sqlite3
os.environ["NEXTONES_REPLAY_MODE"] = "1"

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
CYCLE = "20260611-144234"
NAV_PLACEHOLDER = 1_000_000.0

sys.path.insert(0, r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
from replay_adapters import MarketDataAdapter
from fill_simulator import simulate_fill

conn = sqlite3.connect(DB, timeout=30)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Recuperer day_t depuis snapshot
cur.execute("SELECT day_t FROM shadow_cycle_snapshots WHERE cycle_id=? LIMIT 1", (CYCLE,))
row = cur.fetchone()
if not row:
    print("Pas de snapshot pour ce cycle"); sys.exit(1)
day_decision = row["day_t"]
print(f"day_decision = {day_decision}")

# Charger orders
cur.execute("""
    SELECT o.id, o.variant_id, v.name as variant, o.ticker, o.side, o.qty,
           o.target_weight_pct, o.decision
    FROM shadow_orders o
    JOIN shadow_variants v ON v.variant_id = o.variant_id
    WHERE o.cycle_id = ?
    ORDER BY o.variant_id, o.ticker
""", (CYCLE,))
orders = cur.fetchall()
print(f"\n{len(orders)} shadow_orders chargees")

adapter = MarketDataAdapter(DB)

# Simuler chaque order, capturer rejected
rejected = []
filled = 0
skipped = 0

for o in orders:
    ticker = o["ticker"]
    side = o["side"]
    target_w = o["target_weight_pct"] or 0.0
    decision = o["decision"]

    # close pour calcul qty proxy
    close_raw = adapter.get_close_at(day_decision, ticker)
    if close_raw is None:
        rejected.append((o["variant"], ticker, side, decision, "no_close_decision_day"))
        continue
    # get_close_at peut retourner float OU dict selon adapter
    if isinstance(close_raw, dict):
        close_dec = close_raw.get("close")
    else:
        close_dec = float(close_raw)
    if not close_dec or close_dec <= 0:
        rejected.append((o["variant"], ticker, side, decision, "close_zero"))
        continue

    # Calcul qty proxy
    if side == "BUY":
        if target_w > 0:
            qty = NAV_PLACEHOLDER * (target_w / 100.0) / close_dec
        else:
            skipped += 1
            continue
    else:  # SELL
        if target_w == 0:  # exit
            qty = NAV_PLACEHOLDER * 0.05 / close_dec
        else:
            qty = NAV_PLACEHOLDER * 0.05 / close_dec  # proxy scale_down

    if qty <= 0:
        rejected.append((o["variant"], ticker, side, decision, "qty_zero"))
        continue

    # Simuler fill
    try:
        result = simulate_fill(adapter, ticker, side=side, qty=qty, day_decision=day_decision)
        if result.status == "filled":
            filled += 1
        else:
            rejected.append((o["variant"], ticker, side, decision,
                           getattr(result, "rejection_reason", "unknown")))
    except Exception as e:
        rejected.append((o["variant"], ticker, side, decision, f"exception:{e}"))

print(f"\nfilled={filled} rejected={len(rejected)} skipped={skipped}")
print(f"\n=== REJECTED DETAIL ===")
for variant, ticker, side, decision, reason in rejected:
    print(f"  {variant:20s} {ticker:8s} {side:5s} decision={decision:12s} reason={reason}")

conn.close()
