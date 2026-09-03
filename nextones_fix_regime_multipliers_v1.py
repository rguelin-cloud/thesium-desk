# -*- coding: utf-8 -*-
"""
nextones-fix-regime-multipliers-v1.py
======================================
CORRECTIF 3/4 - Revision des multiplicateurs de regime de marche

PROBLEME
--------
Diagnostic du 2026-09-03, dernier cycle 20260903-061003 :

  equity : regime=CALM  VIX=16.34  vol=7.19%   dd_5j=-0.77%  score=-2.0
           buy_mult=0.70  sell_mult=1.50  conv_thresh=0.65
  crypto : regime=CALM  vol=35.42%  dd_5j=-1.22%  score=-2.0
           buy_mult=0.70  sell_mult=1.50  conv_thresh=0.65

Le regime est qualifie CALM, le VIX est NORMAL a 16.34, la volatilite
realisee equity n'est que de 7.19%, le drawdown 5 jours est de -0.77%.
Ce sont des conditions favorables.

Et pourtant le systeme reduit les achats de 30% (buy_mult 0.70) tout en
amplifiant les ventes de 50% (sell_mult 1.50).

CONSEQUENCE : biais vendeur structurel permanent.
  - cash immobilise a 38.5% du NAV (384 765 USD)
  - portefeuille en mode MAINTAIN en continu
  - rendement plat : -0.01% sur 101 jours
  - 594 enregistrements de regime, tous avec buy 0.70 / sell 1.50

ANALYSE DU SCORE
----------------
Le score de -2.0 en conditions CALM suggere que le calcul penalise
systematiquement, ou que la table de correspondance score -> multiplicateurs
est decalee. Un score negatif en regime calme est contre-intuitif.

CE MODULE
---------
1. Analyse l'historique complet de market_regime_log
2. Verifie la coherence regime / score / multiplicateurs
3. Propose une grille revisee, symetrique et fonction du regime reel
4. Simule l'impact sur l'exposition cible
5. Ne modifie RIEN sans validation explicite

SECURITE
--------
  - Par defaut : ANALYSE SEULE, aucune ecriture
  - --apply n'ecrit que dans regime_multiplier_config (table nouvelle)
  - Ne touche jamais market_regime_log (historique preserve)
  - Le code de production doit lire la nouvelle table pour prendre effet

USAGE
-----
    py -3.13 nextones-fix-regime-multipliers-v1.py --self-test
    py -3.13 nextones-fix-regime-multipliers-v1.py --db thesium.db --analyze
    py -3.13 nextones-fix-regime-multipliers-v1.py --db thesium.db --dry-run
    py -3.13 nextones-fix-regime-multipliers-v1.py --db thesium.db --apply

AUTEUR : audit Perplexity - 2026-09-03
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple

MARKER = "REGIME_MULT_V1"

# ----------------------------------------------------------------------------
# GRILLE REVISEE
# ----------------------------------------------------------------------------
# Principe : le multiplicateur d'achat doit etre >= 1.0 quand les conditions
# sont favorables, et ne descendre que lorsque le risque est reellement eleve.
#
# La grille actuelle applique 0.70 / 1.50 en permanence, quel que soit le
# regime. Elle est remplacee par une grille dependante du regime.

REVISED_GRID: Dict[str, Dict[str, Dict[str, float]]] = {
    "equity": {
        "CALM":   {"buy_mult": 1.00, "sell_mult": 1.00, "conv_thresh": 0.60},
        "NORMAL": {"buy_mult": 0.90, "sell_mult": 1.10, "conv_thresh": 0.62},
        "ALERT":  {"buy_mult": 0.60, "sell_mult": 1.40, "conv_thresh": 0.68},
        "STRESS": {"buy_mult": 0.30, "sell_mult": 1.80, "conv_thresh": 0.75},
    },
    "crypto": {
        # Le crypto est structurellement plus volatil : on reste prudent
        # mais sans brider en permanence.
        "CALM":   {"buy_mult": 0.90, "sell_mult": 1.10, "conv_thresh": 0.62},
        "NORMAL": {"buy_mult": 0.75, "sell_mult": 1.25, "conv_thresh": 0.65},
        "ALERT":  {"buy_mult": 0.50, "sell_mult": 1.50, "conv_thresh": 0.70},
        "STRESS": {"buy_mult": 0.25, "sell_mult": 1.90, "conv_thresh": 0.78},
    },
}

# Grille actuellement observee en base, pour comparaison.
CURRENT_OBSERVED = {"buy_mult": 0.70, "sell_mult": 1.50, "conv_thresh": 0.65}

# Bornes de securite : aucun multiplicateur hors de ces plages.
BUY_MULT_MIN, BUY_MULT_MAX = 0.0, 1.50
SELL_MULT_MIN, SELL_MULT_MAX = 0.5, 2.50
CONV_MIN, CONV_MAX = 0.40, 0.90


def validate_grid(grid: Dict) -> List[str]:
    """Verifie la coherence de la grille. Retourne la liste des erreurs."""
    errors: List[str] = []
    for asset, regimes in grid.items():
        prev_buy: Optional[float] = None
        prev_sell: Optional[float] = None
        for regime in ("CALM", "NORMAL", "ALERT", "STRESS"):
            if regime not in regimes:
                errors.append("{}: regime {} manquant".format(asset, regime))
                continue
            cfg = regimes[regime]
            b, s, c = cfg["buy_mult"], cfg["sell_mult"], cfg["conv_thresh"]

            if not (BUY_MULT_MIN <= b <= BUY_MULT_MAX):
                errors.append("{}/{}: buy_mult {} hors bornes".format(
                    asset, regime, b))
            if not (SELL_MULT_MIN <= s <= SELL_MULT_MAX):
                errors.append("{}/{}: sell_mult {} hors bornes".format(
                    asset, regime, s))
            if not (CONV_MIN <= c <= CONV_MAX):
                errors.append("{}/{}: conv_thresh {} hors bornes".format(
                    asset, regime, c))

            # Monotonie : plus le regime se degrade, moins on achete
            # et plus on vend.
            if prev_buy is not None and b > prev_buy:
                errors.append(
                    "{}/{}: buy_mult {} > {} du regime precedent "
                    "(non monotone)".format(asset, regime, b, prev_buy))
            if prev_sell is not None and s < prev_sell:
                errors.append(
                    "{}/{}: sell_mult {} < {} du regime precedent "
                    "(non monotone)".format(asset, regime, s, prev_sell))
            prev_buy, prev_sell = b, s
    return errors


# ----------------------------------------------------------------------------
# ANALYSE DE L'HISTORIQUE
# ----------------------------------------------------------------------------

def analyze_history(conn: sqlite3.Connection) -> dict:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    out: Dict[str, object] = {}

    print()
    print("DISTRIBUTION DES REGIMES ET MULTIPLICATEURS")
    print("-" * 74)
    print("{:10s} {:10s} {:>7s} {:>7s} {:>7s} {:>7s}  {}".format(
        "CLASSE", "REGIME", "N", "BUY", "SELL", "CONV", "PART"))
    print("-" * 74)

    cur.execute("SELECT COUNT(*) FROM market_regime_log")
    total = int(cur.fetchone()[0])

    cur.execute(
        """
        SELECT asset_class, regime, buy_mult, sell_mult, convergence_thresh,
               COUNT(*) n
        FROM market_regime_log
        GROUP BY asset_class, regime, buy_mult, sell_mult, convergence_thresh
        ORDER BY asset_class, n DESC
        """
    )
    combos = cur.fetchall()
    for r in combos:
        pct = 100.0 * r["n"] / total if total else 0.0
        print("{:10s} {:10s} {:>7d} {:>7.2f} {:>7.2f} {:>7.2f}  {:>5.1f}%".format(
            str(r["asset_class"])[:10], str(r["regime"])[:10], r["n"],
            float(r["buy_mult"] or 0), float(r["sell_mult"] or 0),
            float(r["convergence_thresh"] or 0), pct))
    print("-" * 74)
    print("{:10s} {:10s} {:>7d}".format("TOTAL", "", total))
    out["total_records"] = total
    out["combos"] = len(combos)

    # Multiplicateurs distincts : revele si la grille est figee.
    cur.execute(
        "SELECT COUNT(DISTINCT buy_mult) b, COUNT(DISTINCT sell_mult) s, "
        "COUNT(DISTINCT convergence_thresh) c FROM market_regime_log"
    )
    row = cur.fetchone()
    print()
    print("VARIABILITE DES MULTIPLICATEURS")
    print("-" * 74)
    print("  valeurs distinctes de buy_mult    : {}".format(row["b"]))
    print("  valeurs distinctes de sell_mult   : {}".format(row["s"]))
    print("  valeurs distinctes de conv_thresh : {}".format(row["c"]))
    if row["b"] <= 1 and row["s"] <= 1:
        print()
        print("  DIAGNOSTIC : les multiplicateurs sont FIGES.")
        print("  Le regime detecte n'a aucun effet sur le sizing.")
        out["frozen"] = True
    else:
        out["frozen"] = False

    # Coherence score / regime
    print()
    print("SCORE PAR REGIME")
    print("-" * 74)
    print("{:10s} {:10s} {:>9s} {:>9s} {:>9s} {:>7s}".format(
        "CLASSE", "REGIME", "SCORE_MIN", "SCORE_AVG", "SCORE_MAX", "N"))
    print("-" * 74)
    cur.execute(
        """
        SELECT asset_class, regime, MIN(score) mn, AVG(score) av,
               MAX(score) mx, COUNT(*) n
        FROM market_regime_log
        GROUP BY asset_class, regime ORDER BY asset_class, av
        """
    )
    for r in cur.fetchall():
        print("{:10s} {:10s} {:>9.2f} {:>9.2f} {:>9.2f} {:>7d}".format(
            str(r["asset_class"])[:10], str(r["regime"])[:10],
            float(r["mn"] or 0), float(r["av"] or 0),
            float(r["mx"] or 0), r["n"]))

    # Conditions de marche en regime CALM
    print()
    print("CONDITIONS OBSERVEES EN REGIME CALM")
    print("-" * 74)
    cur.execute(
        """
        SELECT asset_class, COUNT(*) n,
               AVG(vix_value) vix, AVG(realized_vol_pct) vol,
               AVG(drawdown_5d_pct) dd, AVG(score) sc
        FROM market_regime_log WHERE regime = 'CALM'
        GROUP BY asset_class
        """
    )
    for r in cur.fetchall():
        vix = r["vix"]
        print("  {:10s} n={:<5d} VIX={:>6s}  vol={:>6.2f}%  "
              "dd5j={:>6.2f}%  score={:>5.2f}".format(
                  str(r["asset_class"])[:10], r["n"],
                  "{:.2f}".format(vix) if vix is not None else "n/a",
                  float(r["vol"] or 0), float(r["dd"] or 0),
                  float(r["sc"] or 0)))

    print()
    print("  Interpretation : un score negatif en regime CALM avec un VIX")
    print("  a 16 et une volatilite realisee sous 8% indique que la table")
    print("  de correspondance score -> multiplicateurs est trop defensive.")

    return out


# ----------------------------------------------------------------------------
# SIMULATION D'IMPACT
# ----------------------------------------------------------------------------

def simulate_impact(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    row = cur.execute(
        "SELECT total_value, cash FROM portfolio_state WHERE id = 1"
    ).fetchone()
    nav = float(row["total_value"] or 0)
    cash = float(row["cash"] or 0)
    invested = nav - cash

    print()
    print("IMPACT SUR L'EXPOSITION CIBLE")
    print("-" * 74)
    print("  Etat actuel :")
    print("    NAV            {:>14,.0f}".format(nav))
    print("    investi        {:>14,.0f}   {:>5.1f}%".format(
        invested, 100.0 * invested / nav if nav else 0))
    print("    cash           {:>14,.0f}   {:>5.1f}%".format(
        cash, 100.0 * cash / nav if nav else 0))

    print()
    print("  Effet du buy_mult sur une allocation cible de 10% :")
    print("  {:>10s} {:>14s} {:>14s} {:>12s}".format(
        "BUY_MULT", "TAILLE CIBLE", "TAILLE REELLE", "PERTE"))
    print("  " + "-" * 54)
    target = nav * 0.10
    for bm in (0.70, 0.90, 1.00):
        real = target * bm
        loss = target - real
        mark = "  <-- actuel" if abs(bm - 0.70) < 1e-9 else ""
        print("  {:>10.2f} {:>14,.0f} {:>14,.0f} {:>12,.0f}{}".format(
            bm, target, real, loss, mark))

    print()
    print("  Sur 11 lignes Technology, un buy_mult de 0.70 au lieu de 1.00")
    print("  represente une sous-exposition cumulee significative, qui se")
    print("  reporte mecaniquement en cash.")


# ----------------------------------------------------------------------------
# PERSISTANCE
# ----------------------------------------------------------------------------

CONFIG_SCHEMA = """
CREATE TABLE IF NOT EXISTS regime_multiplier_config (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_class      TEXT    NOT NULL,
    regime           TEXT    NOT NULL,
    buy_mult         REAL    NOT NULL,
    sell_mult        REAL    NOT NULL,
    conv_thresh      REAL    NOT NULL,
    active           INTEGER NOT NULL DEFAULT 1,
    rationale        TEXT,
    engine_version   TEXT    NOT NULL DEFAULT 'REGIME_MULT_V1',
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(asset_class, regime)
)
"""

RATIONALE = {
    "CALM":   "conditions favorables : pas de brake sur les achats",
    "NORMAL": "leger biais defensif",
    "ALERT":  "reduction des achats, amplification des sorties",
    "STRESS": "protection du capital prioritaire",
}


def persist_grid(conn: sqlite3.Connection, apply: bool) -> int:
    cur = conn.cursor()
    if apply:
        cur.execute(CONFIG_SCHEMA)

    n = 0
    print()
    print("  {:10s} {:10s} {:>7s} {:>7s} {:>7s}  {}".format(
        "CLASSE", "REGIME", "BUY", "SELL", "CONV", "MOTIF"))
    print("  " + "-" * 70)
    for asset, regimes in REVISED_GRID.items():
        for regime in ("CALM", "NORMAL", "ALERT", "STRESS"):
            cfg = regimes[regime]
            print("  {:10s} {:10s} {:>7.2f} {:>7.2f} {:>7.2f}  {}".format(
                asset, regime, cfg["buy_mult"], cfg["sell_mult"],
                cfg["conv_thresh"], RATIONALE.get(regime, "")[:30]))
            if apply:
                cur.execute(
                    """
                    INSERT INTO regime_multiplier_config
                      (asset_class, regime, buy_mult, sell_mult,
                       conv_thresh, active, rationale)
                    VALUES (?,?,?,?,?,1,?)
                    ON CONFLICT(asset_class, regime) DO UPDATE SET
                      buy_mult = excluded.buy_mult,
                      sell_mult = excluded.sell_mult,
                      conv_thresh = excluded.conv_thresh,
                      rationale = excluded.rationale
                    """,
                    (asset, regime, cfg["buy_mult"], cfg["sell_mult"],
                     cfg["conv_thresh"], RATIONALE.get(regime, "")),
                )
            n += 1
    return n


INTEGRATION_SNIPPET = '''
# ---------------------------------------------------------------------------
# LECTURE DE LA GRILLE REVISEE  -  a coller dans le module de regime
# Marqueur d'idempotence : REGIME_MULT_V1_READER
# ---------------------------------------------------------------------------

# Valeurs de repli si la table est absente : NEUTRES, pas defensives.
_FALLBACK = {"buy_mult": 1.00, "sell_mult": 1.00, "conv_thresh": 0.60}


def get_regime_multipliers(conn, asset_class, regime):
    """
    Retourne {'buy_mult','sell_mult','conv_thresh'} pour la classe d'actif
    et le regime donnes, depuis regime_multiplier_config.

    Remplace les constantes figees 0.70 / 1.50 / 0.65 qui s'appliquaient
    quel que soit le regime (diagnostic 2026-09-03 : 594 enregistrements,
    une seule valeur de buy_mult).
    """
    try:
        row = conn.execute(
            """
            SELECT buy_mult, sell_mult, conv_thresh
            FROM regime_multiplier_config
            WHERE asset_class = ? AND regime = ? AND active = 1
            """,
            (asset_class, regime),
        ).fetchone()
    except Exception:
        return dict(_FALLBACK)

    if not row:
        return dict(_FALLBACK)

    return {"buy_mult": float(row[0]),
            "sell_mult": float(row[1]),
            "conv_thresh": float(row[2])}


# --- Integration ---
#
# AVANT (constantes figees) :
#   buy_mult = 0.70
#   sell_mult = 1.50
#   conv_thresh = 0.65
#
# APRES :
#   m = get_regime_multipliers(conn, asset_class, regime)
#   buy_mult   = m["buy_mult"]
#   sell_mult  = m["sell_mult"]
#   conv_thresh = m["conv_thresh"]
#
# Puis journaliser la source dans market_regime_log.notes :
#   notes = "mult_source=regime_multiplier_config"
# ---------------------------------------------------------------------------
'''


# ----------------------------------------------------------------------------
# SELF-TEST
# ----------------------------------------------------------------------------

def self_test() -> bool:
    print("=" * 74)
    print("SELF-TEST  nextones-fix-regime-multipliers-v1")
    print("=" * 74)
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        if not cond:
            ok = False
        print("  [{}] {}{}".format(
            "PASS" if cond else "FAIL", label, "  " + detail if detail else ""))

    print("\n--- validation de la grille revisee ---")
    errors = validate_grid(REVISED_GRID)
    check("grille coherente", len(errors) == 0,
          "; ".join(errors[:3]) if errors else "")

    print("\n--- correction du biais en regime CALM ---")
    eq_calm = REVISED_GRID["equity"]["CALM"]
    check("equity CALM buy_mult passe de 0.70 a 1.00",
          eq_calm["buy_mult"] == 1.00,
          "buy={}".format(eq_calm["buy_mult"]))
    check("equity CALM sell_mult passe de 1.50 a 1.00",
          eq_calm["sell_mult"] == 1.00,
          "sell={}".format(eq_calm["sell_mult"]))
    check("equity CALM symetrique",
          eq_calm["buy_mult"] == eq_calm["sell_mult"])

    cr_calm = REVISED_GRID["crypto"]["CALM"]
    check("crypto CALM reste legerement prudent",
          cr_calm["buy_mult"] < 1.00 and cr_calm["buy_mult"] >= 0.85,
          "buy={}".format(cr_calm["buy_mult"]))

    print("\n--- monotonie ---")
    for asset in ("equity", "crypto"):
        buys = [REVISED_GRID[asset][r]["buy_mult"]
                for r in ("CALM", "NORMAL", "ALERT", "STRESS")]
        sells = [REVISED_GRID[asset][r]["sell_mult"]
                 for r in ("CALM", "NORMAL", "ALERT", "STRESS")]
        check("{}: buy decroissant".format(asset),
              all(buys[i] >= buys[i + 1] for i in range(3)), str(buys))
        check("{}: sell croissant".format(asset),
              all(sells[i] <= sells[i + 1] for i in range(3)), str(sells))

    print("\n--- protection en STRESS ---")
    for asset in ("equity", "crypto"):
        st = REVISED_GRID[asset]["STRESS"]
        check("{}: STRESS bride fortement".format(asset),
              st["buy_mult"] <= 0.35 and st["sell_mult"] >= 1.75,
              "buy={} sell={}".format(st["buy_mult"], st["sell_mult"]))

    print("\n--- detection de grille invalide ---")
    bad = {"equity": {
        "CALM":   {"buy_mult": 0.30, "sell_mult": 1.80, "conv_thresh": 0.60},
        "NORMAL": {"buy_mult": 1.00, "sell_mult": 1.00, "conv_thresh": 0.62},
        "ALERT":  {"buy_mult": 0.60, "sell_mult": 1.40, "conv_thresh": 0.68},
        "STRESS": {"buy_mult": 0.30, "sell_mult": 1.80, "conv_thresh": 0.75},
    }}
    check("grille non monotone detectee", len(validate_grid(bad)) > 0,
          "{} erreurs".format(len(validate_grid(bad))))

    bad2 = {"equity": {
        "CALM":   {"buy_mult": 3.00, "sell_mult": 1.00, "conv_thresh": 0.60},
        "NORMAL": {"buy_mult": 0.90, "sell_mult": 1.10, "conv_thresh": 0.62},
        "ALERT":  {"buy_mult": 0.60, "sell_mult": 1.40, "conv_thresh": 0.68},
        "STRESS": {"buy_mult": 0.30, "sell_mult": 1.80, "conv_thresh": 0.75},
    }}
    check("buy_mult hors bornes detecte", len(validate_grid(bad2)) > 0)

    print("\n--- impact quantifie ---")
    nav = 999306.0
    target = nav * 0.10
    gain = target * 1.00 - target * 0.70
    check("passage 0.70 -> 1.00 libere ~30% de la cible",
          abs(gain - target * 0.30) < 1.0,
          "{:,.0f} USD par ligne a 10%".format(gain))

    print("=" * 74)
    print("RESULTAT :", "TOUS LES TESTS PASSENT" if ok else "ECHEC")
    print("=" * 74)
    return ok


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def backup_db(db_path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = "{}.backup-regime-{}".format(db_path, ts)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest


def main() -> int:
    p = argparse.ArgumentParser(
        description="Revision des multiplicateurs de regime"
    )
    p.add_argument("--db", default="thesium.db")
    p.add_argument("--analyze", action="store_true",
                   help="analyse seule, aucune proposition")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--skip-backup", action="store_true")
    p.add_argument("--emit-reader", action="store_true",
                   help="ecrit le snippet de lecture")
    args = p.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    if not os.path.exists(args.db):
        print("ERREUR : base introuvable : {}".format(os.path.abspath(args.db)))
        return 1

    if not any([args.apply, args.dry_run, args.analyze]):
        args.analyze = True

    print("=" * 74)
    print("REVISION DES MULTIPLICATEURS DE REGIME")
    print("DB   : {}".format(os.path.abspath(args.db)))
    print("Mode : {}".format(
        "APPLY" if args.apply else ("DRY-RUN" if args.dry_run else "ANALYSE")))
    print("=" * 74)

    conn = sqlite3.connect(args.db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")

    try:
        print()
        print("ETAPE 1 - ANALYSE DE L'HISTORIQUE")
        print("=" * 74)
        stats = analyze_history(conn)

        print()
        print("ETAPE 2 - SIMULATION D'IMPACT")
        print("=" * 74)
        simulate_impact(conn)

        if args.analyze:
            print()
            print("=" * 74)
            print("ANALYSE TERMINEE - aucune modification proposee")
            print("Pour voir la grille revisee :")
            print("  py -3.13 {} --db {} --dry-run".format(
                os.path.basename(__file__), args.db))
            print("=" * 74)
            return 0

        print()
        print("ETAPE 3 - GRILLE REVISEE PROPOSEE")
        print("=" * 74)
        errors = validate_grid(REVISED_GRID)
        if errors:
            print("  GRILLE INVALIDE :")
            for e in errors:
                print("    - {}".format(e))
            return 1
        print("  Validation de la grille : OK")

        if args.apply and not args.skip_backup:
            conn.commit()
            dest = backup_db(args.db)
            print()
            print("  Backup : {}  ({:.1f} Mo)".format(
                dest, os.path.getsize(dest) / (1024.0 * 1024.0)))

        n = persist_grid(conn, args.apply)

        if args.emit_reader:
            path = "regime_multiplier_reader_snippet.py"
            with open(path, "w", encoding="utf-8") as f:
                f.write(INTEGRATION_SNIPPET)
            print()
            print("  Snippet ecrit : {}".format(os.path.abspath(path)))

        if args.apply:
            conn.commit()
            print()
            print("  {} lignes ecrites dans regime_multiplier_config. "
                  "COMMIT.".format(n))
        else:
            conn.rollback()
            print()
            print("  [DRY-RUN] {} lignes seraient ecrites.".format(n))

        print()
        print("=" * 74)
        print("SYNTHESE")
        print("=" * 74)
        print("  enregistrements de regime analyses : {}".format(
            stats.get("total_records", 0)))
        print("  multiplicateurs figes              : {}".format(
            "OUI" if stats.get("frozen") else "non"))
        print("  lignes de grille                   : {}".format(n))
        print()
        print("  IMPORTANT : la nouvelle grille ne prend effet que lorsque")
        print("  le code de production lit regime_multiplier_config.")
        print("  Utiliser --emit-reader puis integrer le snippet.")
        print()
        if args.dry_run:
            print("  Pour appliquer :")
            print("    py -3.13 {} --db {} --apply --emit-reader".format(
                os.path.basename(__file__), args.db))
        else:
            print("  Etape suivante :")
            print("    1. integrer regime_multiplier_reader_snippet.py")
            print("    2. relancer un cycle et verifier market_regime_log")
            print("    3. observer l'evolution du cash sur 2 semaines")
        print("=" * 74)
        return 0

    except Exception as exc:
        conn.rollback()
        print()
        print("ERREUR : {}".format(exc))
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
        sys.exit(main())
