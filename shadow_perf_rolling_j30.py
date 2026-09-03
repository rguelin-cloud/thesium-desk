# -*- coding: utf-8 -*-
"""
shadow_perf_rolling_j30.py - Phase 9.5

Calcule la perf rolling J-30 pour chaque variant actif et insere dans
shadow_perf_rolling.

Architecture :
- Pour chaque variant : reconstruire les positions cumulees depuis shadow_fills
  sur fenetre [as_of_day - 30 jours, as_of_day]
- Calculer NAV journaliere par mark-to-market simple :
    NAV(d) = cash_residuel + somme(position_qty_ticker(d) * close_ticker(d))
  cash_residuel = K0 - notional_net (achats - ventes)
- Computer return_pct, sharpe (daily returns), max_dd
- Variant_id=1 (prod) sert de baseline : delta_pct = return_variant - return_prod
- UNIQUE(variant_id, window_days, as_of_day) -> idempotent via DELETE WHERE

Usage :
  py -3.13 shadow_perf_rolling_j30.py [--as-of YYYYMMDD] [--db PATH] [--window 30]

Default as-of = aujourd hui (UTC), default window = 30 jours.
"""
import argparse
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

K0 = 1_000_000.0  # capital initial $1M strict (regle utilisateur)


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
    p.add_argument("--as-of", default=None, help="YYYYMMDD ; default = aujourd hui UTC")
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def as_of_day_iso(yyyymmdd):
    return "{}-{}-{}".format(yyyymmdd[0:4], yyyymmdd[4:6], yyyymmdd[6:8])


def daterange_iso(start_iso, end_iso):
    s = datetime.strptime(start_iso, "%Y-%m-%d").date()
    e = datetime.strptime(end_iso, "%Y-%m-%d").date()
    cur = s
    out = []
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def get_close_for_day(cur, ticker, day_iso):
    """
    Retourne le close du ticker au jour donne ou au dernier jour < day_iso
    si non dispo (weekend / jour ferie).
    """
    row = cur.execute(
        "SELECT p.close FROM prices p "
        "JOIN instruments i ON i.id = p.instrument_id "
        "WHERE i.ticker = ? AND p.date <= ? "
        "ORDER BY p.date DESC LIMIT 1",
        (ticker, day_iso),
    ).fetchone()
    if row and row[0] is not None:
        return float(row[0])
    return None


def compute_variant_nav_series(cur, variant_id, start_iso, end_iso, verbose=False):
    """
    Reconstruit la serie NAV journaliere pour le variant donne sur [start, end].

    Logique :
      - On part de cash = K0 et positions = {}
      - On rejoue les fills jour apres jour (en ordre fill_day)
        BUY  : cash -= notional + fees ; positions[ticker] += qty
        SELL : cash += notional - fees ; positions[ticker] -= qty
      - Pour chaque jour de la fenetre, on calcule
          nav = cash + sum(pos_qty * close)
      - On retourne la liste [(day_iso, nav), ...]

    Note : les fills d avant start_iso doivent etre integres pour avoir l etat
    initial correct ; on commence donc par charger TOUS les fills du variant
    jusqu a end_iso, puis on filtre la serie NAV sur [start, end].
    """
    fills = cur.execute(
        "SELECT fill_day, side, ticker, fill_price, fill_quantity, fees, notional "
        "FROM shadow_fills WHERE variant_id=? AND fill_day <= ? "
        "ORDER BY fill_day ASC, id ASC",
        (variant_id, end_iso),
    ).fetchall()

    if verbose:
        print("  variant={} : {} fills loaded (jusqu a {})".format(
            variant_id, len(fills), end_iso
        ))

    cash = K0
    positions = {}  # ticker -> qty
    fills_by_day = {}
    for f in fills:
        d = f[0]
        fills_by_day.setdefault(d, []).append(f)

    # Pour chaque jour de [start_iso, end_iso], appliquer les fills du jour
    # puis snapshot NAV au close.
    # On etend la plage en arriere pour englober tous les fills anterieurs.
    all_days = sorted(set([f[0] for f in fills] + daterange_iso(start_iso, end_iso)))
    series = []
    for d in all_days:
        for f in fills_by_day.get(d, []):
            side = f[1]
            ticker = f[2]
            qty = float(f[4])
            fees = float(f[5])
            notional = float(f[6])
            if side == "BUY":
                cash -= notional + fees
                positions[ticker] = positions.get(ticker, 0.0) + qty
            elif side == "SELL":
                cash += notional - fees
                positions[ticker] = positions.get(ticker, 0.0) - qty
        # NAV au close du jour
        if d >= start_iso and d <= end_iso:
            mkt = 0.0
            for tk, q in positions.items():
                if abs(q) < 1e-12:
                    continue
                c = get_close_for_day(cur, tk, d)
                if c is None:
                    # pas de prix dispo -> on ignore cette position pour ce jour
                    continue
                mkt += q * c
            nav = cash + mkt
            series.append((d, nav))

    return series


def compute_metrics(series, k0=K0):
    """
    A partir de la serie [(day, nav), ...] :
      - return_pct  = (nav_final - K0) / K0 * 100
      - sharpe annualise sur daily returns
      - max_dd_pct sur la serie
    """
    if not series:
        return {
            "nav_final": None, "return_pct": None,
            "sharpe": None, "max_dd_pct": None,
        }
    nav_final = series[-1][1]
    return_pct = (nav_final - k0) / k0 * 100.0

    # Daily returns
    rets = []
    for i in range(1, len(series)):
        prev = series[i - 1][1]
        cur = series[i][1]
        if prev and prev > 0:
            rets.append((cur - prev) / prev)
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        sharpe = (mean / std * math.sqrt(252.0)) if std > 1e-12 else None
    else:
        sharpe = None

    # Max drawdown
    peak = series[0][1]
    max_dd = 0.0
    for _, nav in series:
        if nav > peak:
            peak = nav
        if peak > 0:
            dd = (nav - peak) / peak * 100.0
            if dd < max_dd:
                max_dd = dd

    return {
        "nav_final": nav_final,
        "return_pct": return_pct,
        "sharpe": sharpe,
        "max_dd_pct": max_dd,
    }


def get_n_cycles_n_orders(cur, variant_id, start_iso, end_iso):
    row = cur.execute(
        "SELECT COUNT(DISTINCT cycle_id) AS n_cyc, COUNT(*) AS n_ord "
        "FROM shadow_fills "
        "WHERE variant_id=? AND fill_day >= ? AND fill_day <= ?",
        (variant_id, start_iso, end_iso),
    ).fetchone()
    return int(row[0] or 0), int(row[1] or 0)


def recommendation(delta_pct):
    if delta_pct is None:
        return "no_data"
    if delta_pct >= 1.0:
        return "champion"
    if delta_pct <= -1.0:
        return "reject"
    return "neutral"


def main():
    args = parse_args()
    db = args.db
    if not os.path.exists(db):
        print("[ERR] DB not found:", db)
        sys.exit(1)

    if args.as_of is None:
        as_of = datetime.now(timezone.utc).strftime("%Y%m%d")
    else:
        as_of = args.as_of

    as_of_iso = as_of_day_iso(as_of)
    start_dt = datetime.strptime(as_of_iso, "%Y-%m-%d") - timedelta(days=args.window)
    start_iso = start_dt.strftime("%Y-%m-%d")

    print("=" * 78)
    print("SHADOW PERF ROLLING J-{}".format(args.window))
    print("DB        :", db)
    print("Window    : {} -> {} ({} jours)".format(start_iso, as_of_iso, args.window))
    print("=" * 78)

    conn = sqlite3.connect(db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    variants = cur.execute(
        "SELECT variant_id, name FROM shadow_variants WHERE active=1 ORDER BY variant_id"
    ).fetchall()
    print()
    print("Variants actifs :", [(v["variant_id"], v["name"]) for v in variants])
    print()

    # Compute prod (variant_id=1) en premier pour servir de baseline
    print("[1/2] Compute baseline (variant_id=1 = prod)")
    prod_series = compute_variant_nav_series(cur, 1, start_iso, as_of_iso, args.verbose)
    prod_metrics = compute_metrics(prod_series)
    prod_n_cyc, prod_n_ord = get_n_cycles_n_orders(cur, 1, start_iso, as_of_iso)
    print("  prod : nav_final={} return={:.3f}% sharpe={} max_dd={:.3f}% n_cyc={} n_ord={}".format(
        prod_metrics["nav_final"], prod_metrics["return_pct"] or 0.0,
        prod_metrics["sharpe"], prod_metrics["max_dd_pct"] or 0.0,
        prod_n_cyc, prod_n_ord
    ))

    # Compute pour tous les variants
    print()
    print("[2/2] Compute variants + insert")
    print()

    # Idempotence : DELETE WHERE puis INSERT
    cur.execute(
        "DELETE FROM shadow_perf_rolling WHERE window_days=? AND as_of_day=?",
        (args.window, as_of_iso),
    )

    inserted = 0
    for v in variants:
        vid = v["variant_id"]
        vname = v["name"]
        if vid == 1:
            series = prod_series
            metrics = prod_metrics
            n_cyc = prod_n_cyc
            n_ord = prod_n_ord
        else:
            series = compute_variant_nav_series(cur, vid, start_iso, as_of_iso, args.verbose)
            metrics = compute_metrics(series)
            n_cyc, n_ord = get_n_cycles_n_orders(cur, vid, start_iso, as_of_iso)

        if metrics["return_pct"] is not None and prod_metrics["return_pct"] is not None:
            delta = metrics["return_pct"] - prod_metrics["return_pct"]
        else:
            delta = None

        reco = recommendation(delta)

        cur.execute(
            "INSERT INTO shadow_perf_rolling ("
            "  variant_id, window_days, as_of_day, "
            "  nav_variant, nav_prod, "
            "  return_variant_pct, return_prod_pct, delta_pct, "
            "  sharpe_variant, sharpe_prod, "
            "  max_dd_variant_pct, max_dd_prod_pct, "
            "  n_cycles, n_orders_variant, n_orders_prod, "
            "  recommendation"
            ") VALUES (?, ?, ?,  ?, ?,  ?, ?, ?,  ?, ?,  ?, ?,  ?, ?, ?,  ?)",
            (
                vid, args.window, as_of_iso,
                metrics["nav_final"], prod_metrics["nav_final"],
                metrics["return_pct"], prod_metrics["return_pct"], delta,
                metrics["sharpe"], prod_metrics["sharpe"],
                metrics["max_dd_pct"], prod_metrics["max_dd_pct"],
                n_cyc, n_ord, prod_n_ord,
                reco,
            ),
        )
        inserted += 1
        print("  v{} ({}) : ret={:.3f}% delta={} sharpe={} dd={:.3f}% n_cyc={} n_ord={} reco={}".format(
            vid, vname,
            metrics["return_pct"] or 0.0,
            "{:.3f}%".format(delta) if delta is not None else "N/A",
            "{:.3f}".format(metrics["sharpe"]) if metrics["sharpe"] is not None else "N/A",
            metrics["max_dd_pct"] or 0.0,
            n_cyc, n_ord, reco,
        ))

    conn.commit()
    conn.close()

    print()
    print("=" * 78)
    print("PERF ROLLING DONE")
    print("  rows inserted :", inserted)
    print("  as_of_day     :", as_of_iso)
    print("  window_days   :", args.window)
    print("=" * 78)


if __name__ == "__main__":
    main()
