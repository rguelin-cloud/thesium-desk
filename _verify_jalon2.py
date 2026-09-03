"""
Script de verification dry-run — Jalon 2 Portfolio Construction Agent

Verifie le bon fonctionnement des 3 nouvelles composantes :
  - Macro affinity  : bucket + score pour chaque ticker
  - Vol penalty     : sigma 90j + score normalise
  - Diversification : correlation avec positions detenues

Compare avec Jalon 1 (conviction seule) pour montrer l'impact de Jalon 2.

Usage :
  py -3.13 _verify_jalon2.py
  py -3.13 _verify_jalon2.py --db /chemin/vers/thesium.db
"""
import argparse
import math
import os
import sqlite3
import sys

# ---- Localisation de la DB ----
def _find_db(path: str = None) -> str:
    if path and os.path.exists(path):
        return path
    candidates = ["thesium.db", os.path.join(os.path.dirname(__file__), "thesium.db")]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "thesium.db"


def main():
    parser = argparse.ArgumentParser(
        description="Verification dry-run Jalon 2 — PortfolioConstructionAgent"
    )
    parser.add_argument(
        "--db", default=None,
        help="Chemin vers thesium.db (defaut : auto-detecte)"
    )
    args = parser.parse_args()

    db_path = _find_db(args.db)
    if not os.path.exists(db_path):
        print(f"[ERREUR] DB introuvable : {db_path}")
        print("Lance depuis le repertoire ThesiumDesk/ ou passe --db /chemin/thesium.db")
        sys.exit(1)

    # ---- Import de l'agent Jalon 2 ----
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from portfolio_construction_agent_jalon2 import (
            run_construction_agent,
            compute_avg_conviction,
            compute_macro_affinity,
            compute_vol_penalty,
            _compute_vol_score,
            compute_diversification,
            _get_portfolio_macro_env,
            load_universe,
            load_config,
            ensure_construction_tables,
            seed_universe_if_empty,
            seed_config_if_empty,
        )
    except ImportError as e:
        print(f"[ERREUR] Impossible d'importer portfolio_construction_agent_jalon2 : {e}")
        print("Verifie que portfolio_construction_agent_jalon2.py est dans le meme dossier.")
        sys.exit(1)

    # ---- Connexion SQLite ----
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    print(f"[verify_jalon2] DB : {db_path}")

    # Bootstrap tables (idempotent)
    ensure_construction_tables(conn)
    seed_universe_if_empty(conn)
    seed_config_if_empty(conn)

    config = load_config(conn)
    universe = load_universe(conn)
    price_days = int(config.get("price_lookback_days", 90))
    lambda_vol = float(config.get("lambda_vol", 0.10))

    # ---- NAV + positions ----
    ps = conn.execute(
        "SELECT total_value, cash FROM portfolio_state WHERE id=1"
    ).fetchone()
    nav   = float(ps["total_value"]) if ps else 1_000_000.0
    cash  = float(ps["cash"])        if ps else 1_000_000.0
    print(f"[verify_jalon2] NAV = ${nav:,.0f}  |  Cash = ${cash:,.0f}")

    # ---- Positions detenues ----
    held_rows = conn.execute("""
        SELECT i.ticker, pp.quantity
        FROM portfolio_positions pp
        JOIN instruments i ON i.id = pp.instrument_id
        WHERE pp.quantity > 0
    """).fetchall()
    held_tickers = [r["ticker"] for r in held_rows]
    print(f"[verify_jalon2] Positions detenues ({len(held_tickers)}) : {held_tickers}")

    # ---- Environnement macro ----
    macro_env = _get_portfolio_macro_env(conn)
    print(f"[verify_jalon2] Environnement macro detecte : {macro_env}")

    # ---- Nombre de jours de prix disponibles par ticker ----
    print()
    print("=" * 78)
    print("JOURS DE PRIX DISPONIBLES PAR TICKER")
    print("=" * 78)
    for u in universe:
        t = u["ticker"]
        row = conn.execute("""
            SELECT COUNT(*) AS n_days
            FROM prices p
            JOIN instruments i ON p.instrument_id = i.id
            WHERE i.ticker = ? AND p.close IS NOT NULL
        """, (t,)).fetchone()
        n_days = row["n_days"] if row else 0
        note = ""
        if n_days < price_days:
            note = f"  <-- ATTENTION : seulement {n_days}j < {price_days}j requis"
        print(f"  {t:<6} : {n_days:>4} jours{note}")

    # ---- Calcul des sigmas pour normalisation univers ----
    sigma_map: dict = {}
    for u in universe:
        sigma_map[u["ticker"]] = compute_vol_penalty(conn, u["ticker"], price_days)
    sigmas_valid = [s for s in sigma_map.values() if s > 0]
    universe_sigma = sum(sigmas_valid) / len(sigmas_valid) if sigmas_valid else 1.0
    print(f"\n[verify_jalon2] Sigma univers moyen : {universe_sigma:.6f}"
          f" (sur {len(sigmas_valid)}/{len(universe)} tickers avec prix)")

    # ---- Rapport par ticker ----
    print()
    print("=" * 78)
    print("COMPOSANTES JALON 2 PAR TICKER")
    print("=" * 78)
    print(f"{'TICKER':<8} {'C_raw':>8} {'M':>6} {'BUCKET':<10} {'SIGMA':>10}"
          f" {'V_score':>8} {'D_score':>8} {'ENV':<8}")
    print("-" * 78)

    all_scores_j1 = {}   # Jalon 1 : conviction seule
    all_scores_j2 = {}   # Jalon 2 : conviction + M + V + D

    ticker_details = []
    for u in universe:
        t   = u["ticker"]
        ac  = u.get("asset_class", "")
        sec = u.get("sector", "")

        # Conviction (Jalon 1)
        C_raw = compute_avg_conviction(
            conn, t,
            float(config["conviction_halflife_days"]),
            int(config["conviction_lookback_days"]),
        )

        # Macro affinity (Jalon 2)
        M_score, M_bucket, env_used = compute_macro_affinity(
            conn, t, ac, sector=sec, env=macro_env
        )

        # Vol penalty (Jalon 2)
        sigma_t = sigma_map.get(t, 0.0)
        V_score = _compute_vol_score(sigma_t, universe_sigma, lambda_vol)

        # Diversification (Jalon 2)
        D_score = compute_diversification(conn, t, held_tickers, price_days)

        ticker_details.append({
            "ticker": t, "C_raw": C_raw, "M": M_score, "M_bucket": M_bucket,
            "sigma": sigma_t, "V": V_score, "D": D_score,
        })

        print(f"{t:<8} {C_raw:>8.3f} {M_score:>6.3f} {M_bucket:<10} {sigma_t:>10.6f}"
              f" {V_score:>8.4f} {D_score:>8.4f} {env_used:<8}")

    # ---- Comparaison Jalon 1 vs Jalon 2 (scores bruts avant normalisation) ----
    print()
    print("=" * 78)
    print("COMPARAISON SCORE BRUT : JALON 1 (conviction seule) vs JALON 2 (complet)")
    print("=" * 78)
    w_c = float(config["w_conviction"])
    w_m = float(config["w_macro"])
    w_d = float(config["w_diversif"])
    l_v = float(config["lambda_vol"])

    print(f"Poids : w_conv={w_c} | w_macro={w_m} | w_diversif={w_d} | lambda_vol={l_v}")
    print()
    print(f"{'TICKER':<8} {'J1_score':>10} {'J2_score':>10} {'Delta':>8}  EFFET JALON 2")
    print("-" * 65)

    rows_for_sort = []
    for d in ticker_details:
        score_j1 = w_c * d["C_raw"]
        score_j2 = (w_c * d["C_raw"] + w_m * d["M"] + w_d * d["D"] - l_v * d["V"])
        delta_s  = score_j2 - score_j1
        rows_for_sort.append((d["ticker"], score_j1, score_j2, delta_s, d))

    rows_for_sort.sort(key=lambda x: -x[2])

    for ticker, s1, s2, ds, d in rows_for_sort:
        effet = ""
        if abs(ds) < 0.01:
            effet = "inchange"
        elif ds > 0:
            effet = f"+ booste (M={d['M']:.2f} bucket={d['M_bucket']})"
        else:
            effet = f"- penalise (V={d['V']:.4f} sigma={d['sigma']:.4f})"
        print(f"{ticker:<8} {s1:>10.4f} {s2:>10.4f} {ds:>+8.4f}  {effet}")

    # ---- Dry-run complet de run_construction_agent ----
    print()
    print("=" * 78)
    print("DRY-RUN run_construction_agent (Jalon 2) — aucune ecriture")
    print("=" * 78)

    # Detecte le regime courant pour passer a l'agent
    try:
        regime_row = conn.execute(
            "SELECT regime FROM regime_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        regime = regime_row["regime"] if regime_row else "BUILD"
    except Exception:
        regime = "BUILD"

    result = run_construction_agent(
        conn,
        cycle_id="VERIFY_JALON2",
        regime_info={"regime": regime},
        dry_run=True,
    )

    print()
    print(f"[verify_jalon2] snapshot_id      : {result.get('snapshot_id')}")
    print(f"[verify_jalon2] regime           : {result.get('regime')}")
    print(f"[verify_jalon2] macro_env        : {result.get('macro_env')}")
    print(f"[verify_jalon2] tickers evalues  : {result.get('n_tickers_evaluated')}")
    print(f"[verify_jalon2] tickers inclus   : {result.get('n_tickers_included')}")
    print(f"[verify_jalon2] budget           : {result.get('budget_pct', 0):.1f} % NAV")

    targets_out = result.get("targets", [])
    if targets_out:
        print()
        print("Cibles calculees (dry-run) :")
        print(f"  {'TICKER':<8} {'POIDS%':>8} {'SCORE':>8}")
        print("  " + "-" * 30)
        for tgt in sorted(targets_out, key=lambda x: -x["weight_pct"]):
            print(f"  {tgt['ticker']:<8} {tgt['weight_pct']:>8.3f} % {tgt['score']:>8.4f}")

    conn.close()

    print()
    print("=" * 78)
    print("FIN VERIFICATION JALON 2 — DRY-RUN OK")
    print("=" * 78)


if __name__ == "__main__":
    main()
