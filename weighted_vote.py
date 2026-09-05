# weighted_vote.py
# [SWARM_WEIGHTED_VOTE_V1]
"""Consensus pondere de l'essaim THESIUM — jalon 1.

Formule
-------
    w_i = max(0, (c_i - 5) / 5)          poids nul pour l'abstention
    C   = |somme(w_i * s_i)| / somme(w_i)

    c_i = conviction 0-10, s_i = +1 long / -1 short / 0 neutral

Gardes obligatoires
-------------------
    MIN_VOTERS       = 3     agents de poids > 0
    MIN_TOTAL_WEIGHT = 1.0   somme des poids

Sans ces gardes, six agents qui s'abstiennent laissent le septieme
obtenir C = 1.0 mecaniquement. Mesure sur 14 620 snapshots historiques :
45,8 % des convictions valent exactement 5,0, et 3 295 snapshots (22,5 %)
affichent C >= 0,95 avec un seul votant.

Seuils par regime
-----------------
    risk_on  0.700    neutral 0.768    risk_off 0.850    crisis 0.900

Le seuil est secondaire : MIN_VOTERS = 3 elimine 45,3 points de
snapshots, le passage de 0,700 a 0,900 n'en elimine que 6,9.

Usage
-----
    py -3.13 weighted_vote.py                 auto-test
    py -3.13 weighted_vote.py --backfill      retro-calcul historique
    py -3.13 weighted_vote.py --backfill --limit 500
    py -3.13 weighted_vote.py --compare       rapport de divergence
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

MARKER = "[SWARM_WEIGHTED_VOTE_V1]"
DB_PATH = os.environ.get("THESIUM_DB", "thesium.db")

# --- Parametres valides le 3 septembre 2026 sur 14 620 snapshots -------------
WEIGHT_FLOOR = 0.0
MIN_VOTERS = 3
MIN_TOTAL_WEIGHT = 1.0
NEUTRAL_POINT = 5.0
CONVICTION_MAX = 10.0

THRESHOLDS = {
    "risk_on": 0.700,
    "neutral": 0.768,
    "risk_off": 0.850,
    "crisis": 0.900,
}
DEFAULT_REGIME = "neutral"

SIZING_TABLE = [
    (0.950, 1.50),
    (0.850, 1.25),
    (0.768, 1.00),
    (0.700, 0.50),
]

DIR_LONG, DIR_SHORT, DIR_NEUTRAL = "long", "short", "neutral"
_SIGN = {DIR_LONG: 1, DIR_SHORT: -1, DIR_NEUTRAL: 0}
_COMPACT_DIR = {"L": DIR_LONG, "S": DIR_SHORT, "N": DIR_NEUTRAL}


# ---------------------------------------------------------------------------
# Coeur : poids, signe, consensus
# ---------------------------------------------------------------------------

def weight_of(conviction, floor=WEIGHT_FLOOR):
    """Poids d'un vote. Conviction <= 5 donne un poids nul (abstention)."""
    if conviction is None:
        return 0.0
    try:
        c = float(conviction)
    except (TypeError, ValueError):
        return 0.0
    return max(floor, (c - NEUTRAL_POINT) / NEUTRAL_POINT)


def sign_of(direction):
    """Signe d'une direction. Accepte 'long'/'short'/'neutral' ou 'L'/'S'/'N'."""
    if direction is None:
        return 0
    d = str(direction).strip()
    if d in _COMPACT_DIR:
        d = _COMPACT_DIR[d]
    return _SIGN.get(d.lower(), 0)


def threshold_for(regime):
    """Seuil de convergence du regime. Defaut : neutral."""
    if not regime:
        return THRESHOLDS[DEFAULT_REGIME]
    key = str(regime).strip().lower().replace("-", "_")
    aliases = {
        "riskon": "risk_on", "risk_on": "risk_on", "trend": "risk_on",
        "bull": "risk_on", "build": "risk_on",
        "riskoff": "risk_off", "risk_off": "risk_off", "bear": "risk_off",
        "neutral": "neutral", "maintain": "neutral", "range": "neutral",
        "crisis": "crisis", "halt": "crisis", "stress": "crisis",
    }
    return THRESHOLDS.get(aliases.get(key, DEFAULT_REGIME),
                          THRESHOLDS[DEFAULT_REGIME])


def sizing_for(convergence):
    """Multiplicateur de taille selon la convergence."""
    for floor, mult in SIZING_TABLE:
        if convergence >= floor:
            return mult
    return 0.0


def compute_consensus(votes, regime=DEFAULT_REGIME,
                      min_voters=MIN_VOTERS,
                      min_total_weight=MIN_TOTAL_WEIGHT,
                      weight_floor=WEIGHT_FLOOR,
                      forced_exit=False):
    """Calcule le consensus pondere et applique les gardes.

    votes : liste de dicts avec au minimum 'direction' et 'conviction'.
            Cle optionnelle 'agent'.

    Retour : dict complet, jamais d'exception.
    """
    prepared = []
    for v in votes or []:
        if not isinstance(v, dict):
            continue
        d = v.get("direction") or v.get("d")
        c = v.get("conviction")
        if c is None:
            c = v.get("c")
        if d is None or c is None:
            continue
        prepared.append({
            "agent": v.get("agent") or v.get("source") or "?",
            "direction": _COMPACT_DIR.get(str(d).strip(), str(d).strip().lower()),
            "conviction": float(c),
            "weight": weight_of(c, weight_floor),
            "sign": sign_of(d),
        })

    n_present = len(prepared)
    voting = [p for p in prepared if p["weight"] > 0]
    n_voting = len(voting)
    n_abstaining = n_present - n_voting
    total_weight = sum(p["weight"] for p in prepared)

    if total_weight > 0:
        signed = sum(p["weight"] * p["sign"] for p in prepared)
        convergence = abs(signed) / total_weight
        if signed > 0:
            direction = DIR_LONG
        elif signed < 0:
            direction = DIR_SHORT
        else:
            direction = DIR_NEUTRAL
    else:
        signed = 0.0
        convergence = 0.0
        direction = DIR_NEUTRAL

    # Comptage par tete, pour comparaison avec convergence_engine existant
    n_long = sum(1 for p in prepared if p["sign"] > 0)
    n_short = sum(1 for p in prepared if p["sign"] < 0)
    n_aligned = max(n_long, n_short)
    headcount = (n_aligned / n_present) if n_present else 0.0

    threshold = threshold_for(regime)

    guard_failed = None
    if n_voting < min_voters:
        guard_failed = "min_voters"
    elif total_weight < min_total_weight:
        guard_failed = "min_weight"
    elif convergence < threshold:
        guard_failed = "below_threshold"
    elif direction == DIR_NEUTRAL:
        guard_failed = "no_direction"

    mandate_formed = guard_failed is None
    multiplier = sizing_for(convergence) if mandate_formed else 0.0

    if forced_exit:
        # Une liquidation de protection court-circuite le consensus.
        mandate_formed = True
        guard_failed = None
        direction = DIR_SHORT
        multiplier = 1.0

    return {
        "direction_consensus": direction,
        "convergence_weighted": round(convergence, 6),
        "convergence_headcount": round(headcount, 6),
        "n_present": n_present,
        "n_voting": n_voting,
        "n_abstaining": n_abstaining,
        "n_aligned": n_aligned,
        "total_weight": round(total_weight, 6),
        "signed_sum": round(signed, 6),
        "threshold_applied": threshold,
        "min_voters_applied": min_voters,
        "min_weight_applied": min_total_weight,
        "regime": regime,
        "sizing_multiplier": multiplier,
        "mandate_formed": 1 if mandate_formed else 0,
        "guard_failed": guard_failed,
        "forced_exit": 1 if forced_exit else 0,
        "votes": prepared,
    }


def mandate_hash(cycle_id, ticker, side, qty, convergence, n_voting):
    """Hash d'immuabilite verifie par VESKA avant execution."""
    raw = "|".join([
        str(cycle_id), str(ticker).upper(), str(side).lower(),
        "%.8f" % float(qty), "%.6f" % float(convergence), str(int(n_voting)),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Lecture des buckets historiques
# ---------------------------------------------------------------------------

def votes_from_buckets(buckets_json):
    """Extrait des votes depuis convergence_snapshots.buckets_json."""
    if not buckets_json:
        return []
    try:
        b = json.loads(buckets_json)
    except Exception:
        return []
    if not isinstance(b, dict):
        return []
    out = []
    for bucket, v in b.items():
        if not isinstance(v, dict):
            continue
        d = v.get("direction")
        c = v.get("conviction")
        if d is None or c is None:
            continue
        out.append({
            "agent": v.get("source") or bucket,
            "bucket": bucket,
            "direction": d,
            "conviction": c,
        })
    return out


# ---------------------------------------------------------------------------
# Retro-calcul
# ---------------------------------------------------------------------------

def db(readonly=False):
    if not os.path.exists(DB_PATH):
        print("ERREUR : %s introuvable." % DB_PATH)
        sys.exit(1)
    if readonly:
        c = sqlite3.connect("file:%s?mode=ro" % DB_PATH, uri=True)
    else:
        c = sqlite3.connect(DB_PATH, timeout=30.0)
        try:
            c.execute("PRAGMA busy_timeout=30000")
        except Exception:
            pass
    c.row_factory = sqlite3.Row
    return c


def table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def regime_by_cycle(conn):
    """Mappe cycle_id -> regime, depuis market_regime_log ou regime_log."""
    m = {}
    for table, col in (("market_regime_log", "regime"),
                       ("regime_log", "equity_regime"),
                       ("regime_log", "regime")):
        if not table_exists(conn, table):
            continue
        try:
            rows = conn.execute(
                "SELECT cycle_id, %s FROM %s WHERE cycle_id IS NOT NULL" % (col, table)
            ).fetchall()
        except Exception:
            continue
        for r in rows:
            if r[0] and r[1] and r[0] not in m:
                m[r[0]] = r[1]
    return m


def backfill(limit=None, dry_run=False):
    """Recalcule le consensus sur convergence_snapshots, ecrit source='backfill'."""
    conn = db(readonly=dry_run)
    if not table_exists(conn, "convergence_snapshots"):
        print("ERREUR : convergence_snapshots absente.")
        sys.exit(1)
    if not dry_run and not table_exists(conn, "swarm_consensus"):
        print("ERREUR : swarm_consensus absente. Lance d'abord migrate_swarm_v1.py")
        sys.exit(1)

    regimes = regime_by_cycle(conn)
    print("  regimes mappes depuis les logs : %d cycles" % len(regimes))

    sql = ("SELECT cycle_id, ticker, direction_consensus, n_aligned, n_present, "
           "convergence_pct, sizing_multiplier, forced_exit, is_crypto, "
           "buckets_json, created_at "
           "FROM convergence_snapshots WHERE buckets_json IS NOT NULL "
           "ORDER BY id")
    if limit:
        sql += " LIMIT %d" % int(limit)
    rows = conn.execute(sql).fetchall()
    print("  snapshots a traiter            : %d" % len(rows))

    stats = Counter()
    guards = Counter()
    mismatch_headcount = []
    divergence = Counter()
    batch = []

    for r in rows:
        votes = votes_from_buckets(r["buckets_json"])
        if not votes:
            stats["sans_votes"] += 1
            continue
        regime = regimes.get(r["cycle_id"], DEFAULT_REGIME)
        res = compute_consensus(votes, regime=regime,
                                forced_exit=bool(r["forced_exit"]))
        stats["traites"] += 1
        if res["mandate_formed"]:
            stats["mandats"] += 1
        if res["guard_failed"]:
            guards[res["guard_failed"]] += 1

        # Controle de non-regression : le comptage par tete doit coller
        hist = r["convergence_pct"]
        if hist is not None:
            if abs(res["convergence_headcount"] - float(hist)) > 0.011:
                mismatch_headcount.append(
                    (r["cycle_id"], r["ticker"], float(hist),
                     res["convergence_headcount"]))

        # Divergence des deux methodes au seuil du regime
        th = res["threshold_applied"]
        w_ok = res["convergence_weighted"] >= th
        h_ok = (float(hist) if hist is not None else 0.0) >= th
        divergence[(w_ok, h_ok)] += 1

        batch.append((
            r["cycle_id"], r["ticker"], res["direction_consensus"],
            res["convergence_weighted"], res["convergence_headcount"],
            res["n_voting"], res["n_abstaining"], res["total_weight"],
            res["threshold_applied"], res["min_voters_applied"],
            res["min_weight_applied"], regime, res["sizing_multiplier"],
            res["mandate_formed"], res["guard_failed"], None, None,
            json.dumps([{k: v[k] for k in ("agent", "direction", "conviction",
                                           "weight", "sign")}
                        for v in res["votes"]], ensure_ascii=False),
            "backfill", r["created_at"],
        ))

    if not dry_run and batch:
        conn.executemany("""
            INSERT INTO swarm_consensus
              (cycle_id, ticker, direction_consensus, convergence_weighted,
               convergence_headcount, n_voting, n_abstaining, total_weight,
               threshold_applied, min_voters_applied, min_weight_applied,
               regime, sizing_multiplier, mandate_formed, guard_failed,
               degraded_agents, liquidity_cap_qty, votes_json, source, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(cycle_id, ticker, source) DO UPDATE SET
               direction_consensus  = excluded.direction_consensus,
               convergence_weighted = excluded.convergence_weighted,
               convergence_headcount= excluded.convergence_headcount,
               n_voting             = excluded.n_voting,
               n_abstaining         = excluded.n_abstaining,
               total_weight         = excluded.total_weight,
               threshold_applied    = excluded.threshold_applied,
               regime               = excluded.regime,
               sizing_multiplier    = excluded.sizing_multiplier,
               mandate_formed       = excluded.mandate_formed,
               guard_failed         = excluded.guard_failed,
               votes_json           = excluded.votes_json
        """, batch)
        conn.commit()

    print()
    print("--- resultat du retro-calcul ---")
    print("  traites                        : %d" % stats["traites"])
    print("  sans votes exploitables        : %d" % stats["sans_votes"])
    n = stats["traites"] or 1
    print("  mandats formes                 : %d (%.1f%%)"
          % (stats["mandats"], 100 * stats["mandats"] / n))
    print()
    print("--- motifs de refus ---")
    for g, k in guards.most_common():
        print("  %-20s %6d (%.1f%%)" % (g, k, 100 * k / n))
    print()
    print("--- controle de non-regression (comptage par tete) ---")
    if mismatch_headcount:
        print("  ECARTS : %d snapshots" % len(mismatch_headcount))
        for cy, tk, h, c in mismatch_headcount[:10]:
            print("    %s %-8s historique=%.3f recalcule=%.3f" % (cy, tk, h, c))
    else:
        print("  OK : le comptage par tete reproduit convergence_pct partout")
    print()
    print("--- divergence pondere vs par-tete (au seuil du regime) ---")
    print("  %-24s %-24s %8s" % ("PONDERE", "PAR-TETE", "N"))
    for (w, h), k in sorted(divergence.items(), key=lambda x: -x[1]):
        print("  %-24s %-24s %8d"
              % ("accepte" if w else "refuse", "accepte" if h else "refuse", k))
    total_div = sum(k for (w, h), k in divergence.items() if w != h)
    print("  -> %d snapshots divergent (%.1f%%)" % (total_div, 100 * total_div / n))

    conn.close()
    if dry_run:
        print("\n--dry-run : aucune ecriture.")
    else:
        print("\nEcrit dans swarm_consensus avec source='backfill'.")


def compare_report():
    """Rapport de comparaison sur ce qui est deja en base."""
    conn = db(readonly=True)
    if not table_exists(conn, "swarm_consensus"):
        print("ERREUR : swarm_consensus absente.")
        sys.exit(1)
    n = conn.execute("SELECT COUNT(*) FROM swarm_consensus").fetchone()[0]
    print("  lignes swarm_consensus : %d" % n)
    if n == 0:
        print("  rien a comparer. Lance --backfill d'abord.")
        return

    print()
    print("--- par source ---")
    for r in conn.execute("SELECT source, COUNT(*) n, "
                          "SUM(mandate_formed) m FROM swarm_consensus "
                          "GROUP BY source"):
        print("  %-10s %6d lignes, %6d mandats (%.1f%%)"
              % (r["source"], r["n"], r["m"] or 0,
                 100 * (r["m"] or 0) / (r["n"] or 1)))

    print()
    print("--- distribution de n_voting ---")
    for r in conn.execute("SELECT n_voting, COUNT(*) n FROM swarm_consensus "
                          "GROUP BY n_voting ORDER BY n_voting"):
        print("  n_voting=%-3d %6d" % (r["n_voting"], r["n"]))

    print()
    print("--- cas dangereux : convergence elevee, peu de votants ---")
    for mv in (1, 2):
        k = conn.execute("SELECT COUNT(*) FROM swarm_consensus "
                         "WHERE convergence_weighted >= 0.95 AND n_voting <= ?",
                         (mv,)).fetchone()[0]
        print("  C >= 0.95 avec <= %d votant(s) : %6d (%.1f%%)"
              % (mv, k, 100 * k / n))

    print()
    print("--- effet des gardes ---")
    base = conn.execute("SELECT COUNT(*) FROM swarm_consensus "
                        "WHERE convergence_weighted >= threshold_applied"
                        ).fetchone()[0]
    print("  seuil seul                     : %6d (%.1f%%)" % (base, 100 * base / n))
    for mv in (2, 3, 4):
        k = conn.execute("SELECT COUNT(*) FROM swarm_consensus "
                         "WHERE convergence_weighted >= threshold_applied "
                         "AND n_voting >= ?", (mv,)).fetchone()[0]
        print("  + n_voting >= %d                : %6d (%.1f%%)"
              % (mv, k, 100 * k / n))
    for mw in (0.5, 1.0, 1.5):
        k = conn.execute("SELECT COUNT(*) FROM swarm_consensus "
                         "WHERE convergence_weighted >= threshold_applied "
                         "AND total_weight >= ?", (mw,)).fetchone()[0]
        print("  + total_weight >= %.1f          : %6d (%.1f%%)"
              % (mw, k, 100 * k / n))
    conn.close()


# ---------------------------------------------------------------------------
# Auto-test
# ---------------------------------------------------------------------------

def _autotest():
    failures = 0

    def check(label, got, expected):
        nonlocal failures
        ok = got == expected
        if not ok:
            failures += 1
        print("  %-56s %-22s %s"
              % (label, str(got), "OK" if ok else "ECHEC attendu=%s" % (expected,)))

    def v(agent, d, c):
        return {"agent": agent, "direction": d, "conviction": c}

    print(MARKER + " auto-test")
    print()
    print("--- poids ---")
    check("conviction 5.0 -> abstention", weight_of(5.0), 0.0)
    check("conviction 4.0 -> abstention", weight_of(4.0), 0.0)
    check("conviction 10.0 -> poids max", weight_of(10.0), 1.0)
    check("conviction 7.5 -> 0.5", weight_of(7.5), 0.5)
    check("conviction None -> 0", weight_of(None), 0.0)

    print()
    print("--- LA FAILLE : collusion par abstention ---")
    r = compute_consensus([
        v("A", "long", 9.0), v("B", "neutral", 5.0), v("C", "neutral", 5.0),
        v("D", "neutral", 5.0), v("E", "neutral", 5.0), v("F", "neutral", 5.0),
    ])
    check("C = 1.0 malgre 1 seul votant", r["convergence_weighted"], 1.0)
    check("n_voting = 1", r["n_voting"], 1)
    check("MANDAT REFUSE", r["mandate_formed"], 0)
    check("motif = min_voters", r["guard_failed"], "min_voters")

    print()
    print("--- garde min_total_weight ---")
    r = compute_consensus([v("A", "long", 5.6), v("B", "long", 5.6),
                           v("C", "long", 5.6)])
    check("3 votants faibles : n_voting=3", r["n_voting"], 3)
    check("total_weight < 1.0", r["total_weight"] < 1.0, True)
    check("MANDAT REFUSE", r["mandate_formed"], 0)
    check("motif = min_weight", r["guard_failed"], "min_weight")

    print()
    print("--- consensus valide ---")
    r = compute_consensus([v("A", "long", 9.0), v("B", "long", 8.0),
                           v("C", "long", 8.5), v("D", "neutral", 5.0)])
    check("direction long", r["direction_consensus"], "long")
    check("C = 1.0", r["convergence_weighted"], 1.0)
    check("n_voting = 3", r["n_voting"], 3)
    check("n_abstaining = 1", r["n_abstaining"], 1)
    check("MANDAT FORME", r["mandate_formed"], 1)
    check("multiplicateur 1.5", r["sizing_multiplier"], 1.5)

    print()
    print("--- opposition ---")
    r = compute_consensus([v("A", "long", 9.0), v("B", "short", 9.0),
                           v("C", "long", 8.0), v("D", "short", 8.0)])
    check("direction neutre", r["direction_consensus"], "neutral")
    check("C = 0.0", r["convergence_weighted"], 0.0)
    check("MANDAT REFUSE", r["mandate_formed"], 0)

    print()
    print("--- majorite avec dissident ---")
    r = compute_consensus([v("A", "long", 9.0), v("B", "long", 9.0),
                           v("C", "long", 9.0), v("D", "short", 6.0)])
    check("direction long", r["direction_consensus"], "long")
    check("C entre 0.7 et 0.9", 0.7 < r["convergence_weighted"] < 0.9, True)
    check("MANDAT FORME", r["mandate_formed"], 1)

    print()
    print("--- seuils par regime ---")
    votes6 = [v("A", "long", 8.0), v("B", "long", 8.0), v("C", "long", 8.0),
              v("D", "short", 6.0)]
    for reg in ("risk_on", "neutral", "risk_off", "crisis"):
        r = compute_consensus(votes6, regime=reg)
        print("  %-10s seuil=%.3f C=%.3f mandat=%d"
              % (reg, r["threshold_applied"], r["convergence_weighted"],
                 r["mandate_formed"]))
    check("seuil crisis = 0.900", threshold_for("crisis"), 0.900)
    check("regime inconnu -> neutral", threshold_for("zzz"), 0.768)
    check("regime None -> neutral", threshold_for(None), 0.768)

    print()
    print("--- forced_exit court-circuite le consensus ---")
    r = compute_consensus([v("MARIN", "short", 5.0)], forced_exit=True)
    check("mandat forme malgre 0 votant", r["mandate_formed"], 1)
    check("direction short", r["direction_consensus"], "short")
    check("multiplicateur 1.0", r["sizing_multiplier"], 1.0)

    print()
    print("--- format compact L/S/N ---")
    r = compute_consensus([{"agent": "A", "d": "L", "c": 9.0},
                           {"agent": "B", "d": "L", "c": 8.0},
                           {"agent": "C", "d": "L", "c": 8.0}])
    check("direction long depuis 'L'", r["direction_consensus"], "long")
    check("MANDAT FORME", r["mandate_formed"], 1)

    print()
    print("--- robustesse ---")
    check("liste vide", compute_consensus([])["mandate_formed"], 0)
    check("None", compute_consensus(None)["mandate_formed"], 0)
    check("votes malformes", compute_consensus(
        [{"x": 1}, "texte", None, v("A", "long", 9.0)])["n_voting"], 1)

    print()
    print("--- hash de mandat ---")
    h1 = mandate_hash("C1", "AAPL", "buy", 100, 0.85, 3)
    h2 = mandate_hash("C1", "AAPL", "buy", 100, 0.85, 3)
    h3 = mandate_hash("C1", "AAPL", "buy", 101, 0.85, 3)
    check("deterministe", h1 == h2, True)
    check("sensible a la quantite", h1 != h3, True)
    check("longueur 64", len(h1), 64)

    print()
    if failures == 0:
        print("RESULTAT : tous les tests passent. Module utilisable.")
        return 0
    print("RESULTAT : %d ECHEC(S)." % failures)
    return 1


def main():
    p = argparse.ArgumentParser(description="Consensus pondere THESIUM SWARM")
    p.add_argument("--backfill", action="store_true",
                   help="retro-calcule sur convergence_snapshots")
    p.add_argument("--compare", action="store_true",
                   help="rapport de comparaison des deux methodes")
    p.add_argument("--limit", type=int, default=None,
                   help="limite le nombre de snapshots")
    p.add_argument("--dry-run", action="store_true",
                   help="calcule sans ecrire")
    args = p.parse_args()

    if args.backfill:
        print(MARKER + " retro-calcul")
        print("  base : %s" % os.path.abspath(DB_PATH))
        print("  parametres : min_voters=%d min_weight=%.1f floor=%.1f"
              % (MIN_VOTERS, MIN_TOTAL_WEIGHT, WEIGHT_FLOOR))
        print()
        backfill(limit=args.limit, dry_run=args.dry_run)
        return 0
    if args.compare:
        print(MARKER + " rapport de comparaison")
        print()
        compare_report()
        return 0
    return _autotest()


if __name__ == "__main__":
    sys.exit(main())
