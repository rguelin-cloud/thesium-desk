"""
shadow_simulate_fills.py - Phase 9.3

Pour un cycle prod donne, lit shadow_orders (genere par shadow_engine Phase 9.2)
et simule les fills via fill_simulator (slip + open J+1). Ecrit dans shadow_fills.

Difference avec prod : ici on travaille en parallele, sans toucher les positions
reelles. NAV/cash placeholders (1M) tant que Phase 9.4 n a pas wire le scheduler.

Markers : [SHADOW_FILLS_V1]
"""

import os
import sqlite3
import sys
from datetime import datetime, timezone

# Active le mode replay AVANT import fill_simulator
os.environ["NEXTONES_REPLAY_MODE"] = "1"

from fill_simulator import simulate_fill, FillResult
from replay_adapters import MarketDataAdapter


DB_DEFAULT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
NAV_PLACEHOLDER = 1000000.0
FEE_BPS = 1.0  # 1 bp commission par defaut, modifiable plus tard


def cycle_to_day(cycle_id):
    """Cycle YYYYMMDD-HHMMSS -> YYYY-MM-DD."""
    if len(cycle_id) < 8:
        return None
    d = cycle_id[:8]
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def load_shadow_orders(conn, cycle_id, variant_id=None):
    """Lit shadow_orders du cycle. variant_id=None -> tous variants actifs."""
    cur = conn.cursor()
    if variant_id is None:
        cur.execute("""
            SELECT o.* FROM shadow_orders o
            JOIN shadow_variants v ON v.variant_id = o.variant_id
            WHERE o.cycle_id=? AND v.active=1
            ORDER BY o.variant_id, o.ticker
        """, (cycle_id,))
    else:
        cur.execute("""
            SELECT * FROM shadow_orders
            WHERE cycle_id=? AND variant_id=?
            ORDER BY ticker
        """, (cycle_id, variant_id))
    return [dict(r) for r in cur.fetchall()]


def purge_existing_fills(conn, cycle_id, variant_ids):
    """Idempotence : purge fills existants pour ce cycle x variants."""
    if not variant_ids:
        return 0
    cur = conn.cursor()
    placeholders = ','.join('?' for _ in variant_ids)
    cur.execute(
        f"DELETE FROM shadow_fills WHERE cycle_id=? AND variant_id IN ({placeholders})",
        [cycle_id] + variant_ids
    )
    return cur.rowcount


def compute_qty_from_weight(target_weight_pct, nav, price):
    """qty = (target_weight_pct/100) * NAV / price.

    Pour exit/scale_down avec shadow_weight=0 : qty=0 cote shadow_orders, mais on a
    besoin d une qty positive pour le fill. En MVP, on simule qty = baseline_weight
    (10% par defaut) / price * NAV pour avoir un volume non-nul.
    """
    if price <= 0:
        return 0.0
    w = max(target_weight_pct, 0.0) / 100.0
    return (nav * w) / price


def simulate_fills_for_cycle(conn, cycle_id, variant_id=None):
    """Boucle principale. Retourne stats par variant."""
    orders = load_shadow_orders(conn, cycle_id, variant_id)
    if not orders:
        print(f"[shadow_fills] Aucun shadow_order pour cycle {cycle_id}")
        return {}

    # Variants concernes par cette execution
    variant_ids = sorted(set(o['variant_id'] for o in orders))
    n_purged = purge_existing_fills(conn, cycle_id, variant_ids)
    if n_purged:
        print(f"[idempotence] purge {n_purged} shadow_fills existants")

    day_t = cycle_to_day(cycle_id)
    print(f"day_decision (= cycle day) : {day_t}")

    adapter = MarketDataAdapter(db_path=DB_DEFAULT)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

    # Map variant_id -> name
    cur.execute("SELECT variant_id, name FROM shadow_variants")
    vmap = {r['variant_id']: r['name'] for r in cur.fetchall()}

    stats = {}
    for o in orders:
        vid = o['variant_id']
        vname = vmap.get(vid, f"v{vid}")
        stats.setdefault(vname, {'filled': 0, 'rejected': 0, 'skipped_zero_w': 0, 'total_notional': 0.0})

        ticker = o['ticker']
        side_raw = o['side']
        # Pour exit/scale_down, target_weight_pct=0 -> on simule la qty depuis position implicite
        # MVP : pour vendre, qty = NAV * (10% / price) defaut (proxy position)
        # pour acheter, qty = NAV * (target_w/100) / price
        side = side_raw.upper() if side_raw else "BUY"

        # Recupere close au jour de decision pour estimer qty (proxy)
        close_dec = adapter.get_close_at(day_t, ticker)
        if close_dec is None or close_dec <= 0:
            stats[vname]['rejected'] += 1
            continue

        target_w = o['target_weight_pct'] or 0.0
        if side == "SELL" and target_w == 0:
            # exit : on simule la vente d une position proxy 5% NAV
            qty = compute_qty_from_weight(5.0, NAV_PLACEHOLDER, close_dec)
        elif side == "BUY" and target_w == 0:
            stats[vname]['skipped_zero_w'] += 1
            continue
        else:
            qty = compute_qty_from_weight(target_w, NAV_PLACEHOLDER, close_dec)

        if qty <= 0:
            stats[vname]['skipped_zero_w'] += 1
            continue

        # simulate_fill
        try:
            fr = simulate_fill(adapter, ticker, side, qty, day_t)
        except Exception as e:
            print(f"  WARN simulate_fill {ticker} {side} qty={qty}: {e}")
            stats[vname]['rejected'] += 1
            continue

        if fr.status != "filled":
            stats[vname]['rejected'] += 1
            continue

        notional = fr.price_filled * fr.qty
        fees = abs(notional) * (FEE_BPS / 10000.0)

        cur.execute("""
            INSERT INTO shadow_fills
              (cycle_id, variant_id, shadow_order_id, ticker, side,
               fill_price, fill_quantity, fees, slippage_bps, notional, fill_day, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (cycle_id, vid, o['id'], ticker, side,
              fr.price_filled, fr.qty, fees, fr.slippage_bps, notional, fr.day_fill, now))

        stats[vname]['filled'] += 1
        stats[vname]['total_notional'] += abs(notional)

    return stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="Shadow fills simulator MVP")
    p.add_argument("--db", default=DB_DEFAULT)
    p.add_argument("--cycle-id", required=True)
    p.add_argument("--variant-id", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    print("="*78)
    print("SHADOW FILLS SIMULATOR - Phase 9.3")
    print(f"DB        : {args.db}")
    print(f"Cycle ID  : {args.cycle_id}")
    print(f"Variant   : {args.variant_id if args.variant_id else 'ALL active'}")
    print(f"Mode      : {'DRY-RUN' if args.dry_run else 'APPLY'}")
    print("="*78)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    conn.execute("BEGIN")
    try:
        stats = simulate_fills_for_cycle(conn, args.cycle_id, args.variant_id)
        if args.dry_run:
            conn.execute("ROLLBACK")
            print("\n[DRY-RUN] ROLLBACK effectue")
        else:
            conn.execute("COMMIT")
            print("\n[APPLY] COMMIT effectue")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\n[ERROR] {e}")
        raise

    print("\n[RESULTATS]")
    for vname, s in stats.items():
        print(f"\n  Variant : {vname}")
        for k, v in s.items():
            if isinstance(v, float):
                print(f"    {k:20s} : {v:,.2f}")
            else:
                print(f"    {k:20s} : {v}")

    if not args.dry_run:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as n FROM shadow_fills WHERE cycle_id=?", (args.cycle_id,))
        n = cur.fetchone()['n']
        print(f"\n[VERIFICATION] shadow_fills total cycle : {n}")

    conn.close()
    print("\n" + "="*78)
    print("DONE")
    print("="*78)


if __name__ == "__main__":
    main()
