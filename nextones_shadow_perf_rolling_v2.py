# -*- coding: utf-8 -*-
"""
nextones-shadow-perf-rolling-v2.py
===================================
JALON 9 - Phase 9.7 - CORRECTIF PERF ROLLING + LOGIQUE DE PROMOTION

PROBLEME CORRIGE
----------------
L'ancien shadow_perf_rolling comparait nav_variant a nav_prod sans jamais
verifier que ces valeurs etaient physiquement possibles. Resultat au
2026-09-02 :

    variant 2 : nav = -1 881 445   ret = -288.14%   maxDD = -432.73%
    prod      : nav = -1 904 370   ret = -290.44%   maxDD = -413.91%
    delta     : +2.29%             ->  recommendation = "champion"

Le systeme promouvait un variant parce qu'il etait MOINS negatif qu'un
autre. Aucune de ces valeurs n'a de sens financier.

CE MODULE
---------
1. Lit shadow_nav_series_v2 (produit par nextones-shadow-nav-engine-v2)
2. Calcule les metriques rolling sur fenetres 30/60/90 jours
3. REFUSE de publier une recommandation si :
     - une NAV de la fenetre est <= 0
     - n_cycles < MIN_CYCLES_FOR_RECO
     - une metrique sort des bornes physiques
     - le variant OU la prod est marque INVALID
4. Ecrit dans shadow_perf_rolling_v2 avec un champ data_quality explicite

RECOMMANDATIONS POSSIBLES
-------------------------
  champion        delta significatif positif, echantillon suffisant
  promising       delta positif mais echantillon insuffisant
  neutral         delta non significatif
  reject          delta significatif negatif
  insufficient    pas assez de cycles pour conclure
  invalid_data    donnees non exploitables -> AUCUNE conclusion

USAGE
-----
    py -3.13 nextones-shadow-perf-rolling-v2.py --self-test
    py -3.13 nextones-shadow-perf-rolling-v2.py --db thesium.db --dry-run
    py -3.13 nextones-shadow-perf-rolling-v2.py --db thesium.db --apply

AUTEUR : audit Perplexity - 2026-09-03
"""

from __future__ import annotations

import argparse
import math
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

MARKER = "SHADOW_PERF_V2"

# Variant de reference (baseline prod simulee).
PROD_VARIANT_ID = 1

# Fenetres calculees.
WINDOWS = (30, 60, 90)

# Garde-fous.
MIN_CYCLES_FOR_RECO = 60
MIN_OBS_FOR_METRICS = 3
MAX_ABS_RETURN_PCT = 500.0
MAX_DD_FLOOR_PCT = -100.0
TRADING_DAYS = 252

# Seuil de significativite du delta (points de pourcentage).
DELTA_SIGNIFICANT_PCT = 1.0

# Seuil de p-value pour declarer un ecart significatif.
PVALUE_THRESHOLD = 0.10


# ----------------------------------------------------------------------------
# METRIQUES
# ----------------------------------------------------------------------------

def compute_metrics(nav_series: List[float]) -> dict:
    """Metriques robustes. Identique au moteur NAV pour coherence."""
    out = {
        "n_obs": len(nav_series),
        "total_return_pct": None,
        "ann_return_pct": None,
        "vol_ann_pct": None,
        "sharpe": None,
        "sortino": None,
        "max_dd_pct": None,
        "calmar": None,
        "valid": False,
        "invalid_reason": None,
    }

    clean = [v for v in nav_series if v is not None]
    if len(clean) < MIN_OBS_FOR_METRICS:
        out["invalid_reason"] = "insufficient_observations"
        return out
    if any(v <= 0 for v in clean):
        out["invalid_reason"] = "non_positive_nav_in_series"
        return out

    rets = []
    for i in range(1, len(clean)):
        if clean[i - 1] <= 0:
            out["invalid_reason"] = "non_positive_denominator"
            return out
        rets.append(clean[i] / clean[i - 1] - 1.0)
    if not rets:
        out["invalid_reason"] = "no_returns"
        return out

    tot = clean[-1] / clean[0] - 1.0
    out["total_return_pct"] = 100.0 * tot
    if abs(out["total_return_pct"]) > MAX_ABS_RETURN_PCT:
        out["invalid_reason"] = f"return_out_of_bounds({out['total_return_pct']:.1f}%)"
        return out

    n = len(rets)
    mean_r = sum(rets) / n
    var = sum((r - mean_r) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)

    out["ann_return_pct"] = 100.0 * ((1.0 + tot) ** (TRADING_DAYS / n) - 1.0)
    out["vol_ann_pct"] = 100.0 * std * math.sqrt(TRADING_DAYS)
    if std > 1e-12:
        out["sharpe"] = (mean_r * TRADING_DAYS) / (std * math.sqrt(TRADING_DAYS))

    dn = [r for r in rets if r < 0]
    if len(dn) > 1:
        dm = sum(dn) / len(dn)
        dv = sum((r - dm) ** 2 for r in dn) / (len(dn) - 1)
        ds = math.sqrt(dv)
        if ds > 1e-12:
            out["sortino"] = (mean_r * TRADING_DAYS) / (ds * math.sqrt(TRADING_DAYS))

    peak = clean[0]
    mdd = 0.0
    for v in clean:
        if v > peak:
            peak = v
        if peak <= 0:
            out["invalid_reason"] = "non_positive_peak"
            return out
        dd = (v - peak) / peak
        if dd < mdd:
            mdd = dd
    mp = 100.0 * mdd
    if mp < MAX_DD_FLOOR_PCT:
        out["invalid_reason"] = f"max_dd_impossible({mp:.1f}%)"
        return out

    out["max_dd_pct"] = mp
    if abs(mp) > 1e-9:
        out["calmar"] = out["ann_return_pct"] / abs(mp)
    out["valid"] = True
    return out


def paired_ttest_pvalue(a: List[float], b: List[float]) -> Optional[float]:
    """
    Test t apparie sur les rendements journaliers variant vs prod.
    Approximation normale de la p-value bilaterale (pas de scipy requis).
    """
    if len(a) != len(b) or len(a) < 5:
        return None
    d = [x - y for x, y in zip(a, b)]
    n = len(d)
    mean_d = sum(d) / n
    var_d = sum((x - mean_d) ** 2 for x in d) / (n - 1)
    if var_d <= 1e-18:
        return None
    se = math.sqrt(var_d / n)
    if se <= 1e-18:
        return None
    t = mean_d / se
    # p bilaterale via fonction de repartition normale
    p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(t) / math.sqrt(2.0))))
    return max(0.0, min(1.0, p))


# ----------------------------------------------------------------------------
# LOGIQUE DE RECOMMANDATION
# ----------------------------------------------------------------------------

def decide_recommendation(
    m_var: dict,
    m_prod: dict,
    n_cycles: int,
    pvalue: Optional[float],
    variant_has_invalid: bool,
    prod_has_invalid: bool,
) -> Tuple[str, str, str]:
    """
    Retourne (recommendation, data_quality, motif).

    REGLE ABSOLUE : aucune conclusion sur donnees invalides.
    C'est le garde-fou qui manquait et qui a laisse promouvoir un
    variant a NAV negative.
    """
    if variant_has_invalid or prod_has_invalid:
        return ("invalid_data", "INVALID",
                "serie contient des cycles marques invalides")

    if not m_var["valid"]:
        return ("invalid_data", "INVALID",
                f"metriques variant invalides : {m_var['invalid_reason']}")

    if not m_prod["valid"]:
        return ("invalid_data", "INVALID",
                f"metriques prod invalides : {m_prod['invalid_reason']}")

    delta = m_var["total_return_pct"] - m_prod["total_return_pct"]

    if n_cycles < MIN_CYCLES_FOR_RECO:
        if delta > DELTA_SIGNIFICANT_PCT:
            return ("promising", "PARTIAL",
                    f"delta +{delta:.2f}% mais {n_cycles} cycles "
                    f"< {MIN_CYCLES_FOR_RECO} requis")
        return ("insufficient", "PARTIAL",
                f"{n_cycles} cycles < {MIN_CYCLES_FOR_RECO} requis")

    if abs(delta) <= DELTA_SIGNIFICANT_PCT:
        return ("neutral", "OK",
                f"delta {delta:+.2f}% sous le seuil de "
                f"{DELTA_SIGNIFICANT_PCT}%")

    sig = (pvalue is not None and pvalue <= PVALUE_THRESHOLD)

    if delta > 0:
        if not sig:
            return ("promising", "OK",
                    f"delta +{delta:.2f}% mais non significatif "
                    f"(p={pvalue if pvalue is None else round(pvalue, 3)})")
        # Un gain de rendement paye par un drawdown bien pire n'est pas un gain.
        dd_var = m_var["max_dd_pct"]
        dd_prod = m_prod["max_dd_pct"]
        if dd_var is not None and dd_prod is not None and dd_var < dd_prod - 5.0:
            return ("neutral", "OK",
                    f"delta +{delta:.2f}% mais drawdown degrade "
                    f"({dd_var:.1f}% vs {dd_prod:.1f}%)")
        return ("champion", "OK",
                f"delta +{delta:.2f}% significatif (p={round(pvalue, 3)})")

    if not sig:
        return ("neutral", "OK",
                f"delta {delta:.2f}% non significatif")
    return ("reject", "OK",
            f"delta {delta:.2f}% significatif (p={round(pvalue, 3)})")


# ----------------------------------------------------------------------------
# SCHEMA
# ----------------------------------------------------------------------------

SCHEMA_V2 = [
    """
    CREATE TABLE IF NOT EXISTS shadow_perf_rolling_v2 (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_id          INTEGER NOT NULL,
        variant_name        TEXT,
        window_days         INTEGER NOT NULL,
        as_of_day           TEXT    NOT NULL,
        n_cycles            INTEGER NOT NULL DEFAULT 0,
        n_invalid_cycles    INTEGER NOT NULL DEFAULT 0,
        nav_variant         REAL,
        nav_prod            REAL,
        return_variant_pct  REAL,
        return_prod_pct     REAL,
        delta_pct           REAL,
        sharpe_variant      REAL,
        sharpe_prod         REAL,
        sortino_variant     REAL,
        max_dd_variant_pct  REAL,
        max_dd_prod_pct     REAL,
        vol_variant_pct     REAL,
        calmar_variant      REAL,
        significance_pvalue REAL,
        recommendation      TEXT    NOT NULL,
        data_quality        TEXT    NOT NULL,
        decision_motive     TEXT,
        engine_version      TEXT    NOT NULL DEFAULT 'SHADOW_PERF_V2',
        created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(variant_id, window_days, as_of_day)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_perf_v2_asof
        ON shadow_perf_rolling_v2(as_of_day, variant_id, window_days)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_perf_v2_quality
        ON shadow_perf_rolling_v2(data_quality, recommendation)
    """,
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for sql in SCHEMA_V2:
        cur.execute(sql)


# ----------------------------------------------------------------------------
# DONNEES
# ----------------------------------------------------------------------------

def load_nav_series(
    conn: sqlite3.Connection, variant_id: int
) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cycle_id, day_t, nav, cash, valid, invalid_reason
        FROM shadow_nav_series_v2
        WHERE variant_id = ?
        ORDER BY day_t ASC, cycle_id ASC
        """,
        (variant_id,),
    )
    return cur.fetchall()


def load_variants(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        "SELECT variant_id, name FROM shadow_variants "
        "WHERE active = 1 ORDER BY variant_id"
    )
    return cur.fetchall()


def daily_last_nav(rows: List[sqlite3.Row]) -> List[Tuple[str, float, int]]:
    """
    Agrege plusieurs cycles d'un meme jour en gardant le dernier.
    Retourne [(day, nav, valid)].
    """
    per_day: Dict[str, Tuple[float, int]] = {}
    for r in rows:
        per_day[r["day_t"]] = (float(r["nav"]), int(r["valid"]))
    return [(d, v[0], v[1]) for d, v in sorted(per_day.items())]


def window_slice(
    series: List[Tuple[str, float, int]], as_of: str, window_days: int
) -> List[Tuple[str, float, int]]:
    try:
        end = datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError:
        return []
    start = end - timedelta(days=window_days)
    out = []
    for d, nav, valid in series:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
        except ValueError:
            continue
        if start <= dt <= end:
            out.append((d, nav, valid))
    return out


# ----------------------------------------------------------------------------
# CALCUL PRINCIPAL
# ----------------------------------------------------------------------------

def compute_rolling(
    conn: sqlite3.Connection,
    as_of: Optional[str] = None,
    windows: Tuple[int, ...] = WINDOWS,
    verbose: bool = False,
) -> List[dict]:
    variants = load_variants(conn)
    if not variants:
        return []

    cache: Dict[int, List[Tuple[str, float, int]]] = {}
    for v in variants:
        cache[v["variant_id"]] = daily_last_nav(
            load_nav_series(conn, v["variant_id"])
        )

    prod_series = cache.get(PROD_VARIANT_ID, [])
    if not prod_series:
        print(f"ATTENTION : aucune serie pour le variant prod "
              f"(id={PROD_VARIANT_ID}). Lancer d'abord le moteur NAV V2.")
        return []

    if as_of is None:
        all_days = sorted({d for s in cache.values() for d, _n, _v in s})
        if not all_days:
            return []
        as_of = all_days[-1]

    results: List[dict] = []

    for v in variants:
        vid, vname = v["variant_id"], v["name"]
        vser = cache.get(vid, [])
        if not vser:
            continue

        for w in windows:
            wv = window_slice(vser, as_of, w)
            wp = window_slice(prod_series, as_of, w)
            if not wv or not wp:
                continue

            # Aligner sur les jours communs pour un test apparie valide.
            days_v = {d: nav for d, nav, _ in wv}
            days_p = {d: nav for d, nav, _ in wp}
            common = sorted(set(days_v) & set(days_p))
            if len(common) < MIN_OBS_FOR_METRICS:
                continue

            navs_v = [days_v[d] for d in common]
            navs_p = [days_p[d] for d in common]

            n_invalid_v = sum(1 for _d, _n, ok in wv if ok == 0)
            n_invalid_p = sum(1 for _d, _n, ok in wp if ok == 0)

            m_v = compute_metrics(navs_v)
            m_p = compute_metrics(navs_p)

            pval = None
            if m_v["valid"] and m_p["valid"]:
                rv = [navs_v[i] / navs_v[i - 1] - 1.0
                      for i in range(1, len(navs_v))]
                rp = [navs_p[i] / navs_p[i - 1] - 1.0
                      for i in range(1, len(navs_p))]
                pval = paired_ttest_pvalue(rv, rp)

            reco, quality, motive = decide_recommendation(
                m_v, m_p, len(common), pval,
                n_invalid_v > 0, n_invalid_p > 0,
            )

            delta = None
            if m_v["valid"] and m_p["valid"]:
                delta = m_v["total_return_pct"] - m_p["total_return_pct"]

            row = {
                "variant_id": vid,
                "variant_name": vname,
                "window_days": w,
                "as_of_day": as_of,
                "n_cycles": len(common),
                "n_invalid_cycles": n_invalid_v + n_invalid_p,
                "nav_variant": navs_v[-1],
                "nav_prod": navs_p[-1],
                "return_variant_pct": m_v["total_return_pct"],
                "return_prod_pct": m_p["total_return_pct"],
                "delta_pct": delta,
                "sharpe_variant": m_v["sharpe"],
                "sharpe_prod": m_p["sharpe"],
                "sortino_variant": m_v["sortino"],
                "max_dd_variant_pct": m_v["max_dd_pct"],
                "max_dd_prod_pct": m_p["max_dd_pct"],
                "vol_variant_pct": m_v["vol_ann_pct"],
                "calmar_variant": m_v["calmar"],
                "significance_pvalue": pval,
                "recommendation": reco,
                "data_quality": quality,
                "decision_motive": motive,
            }
            results.append(row)

            if verbose:
                print(f"  v{vid} {vname[:16]:16s} w={w:3d}  "
                      f"n={len(common):3d}  "
                      f"reco={reco:13s} quality={quality:8s}  {motive}")

    return results


def persist_rolling(conn: sqlite3.Connection, rows: List[dict]) -> int:
    cur = conn.cursor()
    n = 0
    for r in rows:
        cur.execute(
            """
            INSERT OR REPLACE INTO shadow_perf_rolling_v2
              (variant_id, variant_name, window_days, as_of_day, n_cycles,
               n_invalid_cycles, nav_variant, nav_prod, return_variant_pct,
               return_prod_pct, delta_pct, sharpe_variant, sharpe_prod,
               sortino_variant, max_dd_variant_pct, max_dd_prod_pct,
               vol_variant_pct, calmar_variant, significance_pvalue,
               recommendation, data_quality, decision_motive, engine_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (r["variant_id"], r["variant_name"], r["window_days"],
             r["as_of_day"], r["n_cycles"], r["n_invalid_cycles"],
             r["nav_variant"], r["nav_prod"], r["return_variant_pct"],
             r["return_prod_pct"], r["delta_pct"], r["sharpe_variant"],
             r["sharpe_prod"], r["sortino_variant"],
             r["max_dd_variant_pct"], r["max_dd_prod_pct"],
             r["vol_variant_pct"], r["calmar_variant"],
             r["significance_pvalue"], r["recommendation"],
             r["data_quality"], r["decision_motive"], MARKER),
        )
        n += 1
    return n


# ----------------------------------------------------------------------------
# SELF-TEST
# ----------------------------------------------------------------------------

def self_test() -> bool:
    print("=" * 74)
    print("SELF-TEST  nextones-shadow-perf-rolling-v2")
    print("=" * 74)
    ok = True

    def check(label, cond, detail=""):
        nonlocal ok
        if not cond:
            ok = False
        print(f"  [{'PASS' if cond else 'FAIL'}] {label}"
              f"{('  ' + str(detail)) if detail else ''}")

    good_v = compute_metrics([100.0, 103.0, 105.0, 104.0, 109.0, 112.0])
    good_p = compute_metrics([100.0, 102.0, 103.0, 102.0, 105.0, 106.0])
    bad = compute_metrics([1_000_000.0, 500_000.0, -1_881_445.0])

    # LE test qui compte : reproduction du bug d'origine.
    reco, q, motive = decide_recommendation(bad, bad, 21, None, True, True)
    check("NAV negative -> invalid_data (pas champion)",
          reco == "invalid_data", f"reco={reco} q={q}")
    check("data_quality = INVALID", q == "INVALID")

    reco2, q2, _ = decide_recommendation(good_v, good_p, 21, 0.02, False, False)
    check("echantillon court -> promising, pas champion",
          reco2 in ("promising", "insufficient"), f"reco={reco2}")

    reco3, q3, _ = decide_recommendation(good_v, good_p, 80, 0.02, False, False)
    check("echantillon suffisant + significatif -> champion",
          reco3 == "champion", f"reco={reco3}")

    reco4, _, _ = decide_recommendation(good_v, good_p, 80, 0.80, False, False)
    check("non significatif -> promising", reco4 == "promising",
          f"reco={reco4}")

    reco5, _, _ = decide_recommendation(good_p, good_v, 80, 0.02, False, False)
    check("delta negatif significatif -> reject", reco5 == "reject",
          f"reco={reco5}")

    # Cycle invalide dans la fenetre -> blocage meme si metriques OK
    reco6, q6, _ = decide_recommendation(good_v, good_p, 80, 0.02, True, False)
    check("cycle invalide -> invalid_data", reco6 == "invalid_data",
          f"reco={reco6}")

    # Drawdown degrade annule le champion
    dd_bad = compute_metrics([100.0, 130.0, 80.0, 95.0, 115.0, 118.0])
    if dd_bad["valid"] and good_p["valid"]:
        reco7, _, m7 = decide_recommendation(dd_bad, good_p, 80, 0.02,
                                             False, False)
        check("drawdown degrade -> pas champion",
              reco7 != "champion", f"reco={reco7} dd={dd_bad['max_dd_pct']:.1f}%")

    p_same = paired_ttest_pvalue([0.01] * 10, [0.01] * 10)
    check("p-value None si series identiques", p_same is None)

    p_diff = paired_ttest_pvalue(
        [0.02, 0.01, 0.03, 0.02, 0.01, 0.02, 0.03, 0.01],
        [0.00, -0.01, 0.01, 0.00, -0.01, 0.00, 0.01, -0.01],
    )
    check("p-value calculee sur series differentes",
          p_diff is not None and 0.0 <= p_diff <= 1.0,
          f"p={p_diff if p_diff is None else round(p_diff, 4)}")

    print("=" * 74)
    print("RESULTAT :", "TOUS LES TESTS PASSENT" if ok else "ECHEC")
    print("=" * 74)
    return ok


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Perf rolling shadow V2 avec garde-fous de promotion"
    )
    p.add_argument("--db", default="thesium.db")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--as-of", default=None, help="YYYY-MM-DD")
    p.add_argument("--windows", default="30,60,90")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    if not os.path.exists(args.db):
        print(f"ERREUR : base introuvable : {os.path.abspath(args.db)}")
        return 1

    if not args.apply and not args.dry_run:
        args.dry_run = True

    windows = tuple(int(x.strip()) for x in args.windows.split(",")
                    if x.strip())

    print("=" * 74)
    print("SHADOW PERF ROLLING V2")
    print(f"DB       : {os.path.abspath(args.db)}")
    print(f"Fenetres : {windows}")
    print(f"Mode     : {'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"Min cycles pour recommandation : {MIN_CYCLES_FOR_RECO}")
    print("=" * 74)

    conn = sqlite3.connect(args.db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='shadow_nav_series_v2'"
        )
        if not cur.fetchone():
            print("ERREUR : table shadow_nav_series_v2 absente.")
            print("Lancer d'abord :")
            print("  py -3.13 nextones-shadow-nav-engine-v2.py "
                  "--db thesium.db --apply")
            return 1

        if args.apply:
            ensure_schema(conn)

        rows = compute_rolling(conn, as_of=args.as_of, windows=windows,
                               verbose=args.verbose)
        if not rows:
            print("Aucun resultat calculable.")
            return 1

        if args.apply:
            n = persist_rolling(conn, rows)
            conn.commit()
            print(f"\n{n} lignes ecrites dans shadow_perf_rolling_v2. COMMIT.")
        else:
            conn.rollback()
            print("\nDRY-RUN : aucune ecriture.")

        print("\n" + "=" * 108)
        print("RESULTATS")
        print("=" * 108)
        hdr = (f"{'ID':>3} {'variant':<18} {'w':>4} {'n':>4} "
               f"{'ret_var%':>9} {'ret_prod%':>10} {'delta%':>8} "
               f"{'Sharpe':>7} {'maxDD%':>8} {'p':>6} "
               f"{'reco':<13} {'qualite':<8}")
        print(hdr)
        print("-" * 108)

        def fmt(x, spec):
            return format(x, spec) if x is not None else "n/a"

        for r in sorted(rows, key=lambda z: (z["window_days"],
                                             z["variant_id"])):
            print(f"{r['variant_id']:>3} {str(r['variant_name'])[:18]:<18} "
                  f"{r['window_days']:>4} {r['n_cycles']:>4} "
                  f"{fmt(r['return_variant_pct'], '>+9.2f'):>9} "
                  f"{fmt(r['return_prod_pct'], '>+10.2f'):>10} "
                  f"{fmt(r['delta_pct'], '>+8.2f'):>8} "
                  f"{fmt(r['sharpe_variant'], '>7.3f'):>7} "
                  f"{fmt(r['max_dd_variant_pct'], '>8.2f'):>8} "
                  f"{fmt(r['significance_pvalue'], '>6.3f'):>6} "
                  f"{r['recommendation']:<13} {r['data_quality']:<8}")
        print("=" * 108)

        print("\nMOTIFS DE DECISION")
        print("-" * 74)
        for r in sorted(rows, key=lambda z: (z["window_days"],
                                             z["variant_id"])):
            print(f"  v{r['variant_id']} w{r['window_days']:<3} "
                  f"{r['recommendation']:<13} {r['decision_motive']}")

        n_invalid = sum(1 for r in rows if r["data_quality"] == "INVALID")
        n_champ = sum(1 for r in rows if r["recommendation"] == "champion")
        print("\n" + "=" * 74)
        print(f"lignes calculees        : {len(rows)}")
        print(f"lignes INVALID          : {n_invalid}")
        print(f"champions declares      : {n_champ}")
        if n_invalid:
            print("\nATTENTION : des fenetres restent invalides. Verifier")
            print("shadow_nav_series_v2 pour les cycles marques valid=0.")
        print("=" * 74)
        return 0

    except Exception as exc:
        conn.rollback()
        print(f"\nERREUR : {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
