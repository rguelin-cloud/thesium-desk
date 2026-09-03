"""
Diagnostic: pourquoi le Run Decision Cycle ne genere rien pour AAPL/NVDA/GOOGL/...
Lit la base thesium.db et affiche:
  1. Les thèses des 2 derniers jours (toutes convictions)
  2. La couverture par ticker (qui produit des thèses sur quoi)
  3. Croisement portfolio_targets vs thèses récentes -> tickers ORPHELINS (cible mais aucun agent)
  4. Les types d'agents qui tournent
Aucune dependance externe. Compatible Windows / py -3.13.
"""
import sqlite3
import os
import sys

DB_PATH = "thesium.db"

if not os.path.exists(DB_PATH):
    print(f"[ERREUR] {DB_PATH} introuvable. Lance le script depuis C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk")
    sys.exit(1)

c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. Thèses des 2 derniers jours
# ---------------------------------------------------------------------------
section("1. THESES DES 2 DERNIERS JOURS (toutes convictions)")

rows = c.execute(
    """
    SELECT instrument_id, agent_type, conviction_score, proposed_action, status,
           datetime(created_at) as ts
    FROM theses
    WHERE datetime(created_at) > datetime('now','-2 days')
    ORDER BY created_at DESC
    LIMIT 100
    """
).fetchall()

if not rows:
    print("(aucune thèse des 2 derniers jours)")
else:
    print(f"{'TICKER':<10} {'AGENT':<20} {'CONV':>5} {'ACTION':<10} {'STATUS':<12} {'TS':<20}")
    print("-" * 78)
    for r in rows:
        print(
            f"{(r['instrument_id'] or '?'):<10} "
            f"{(r['agent_type'] or '?'):<20} "
            f"{(r['conviction_score'] or 0):>5} "
            f"{(r['proposed_action'] or '?'):<10} "
            f"{(r['status'] or '?'):<12} "
            f"{(r['ts'] or '?'):<20}"
        )
    print(f"\nTotal: {len(rows)} thèses sur 2 jours")

# ---------------------------------------------------------------------------
# 2. Couverture par ticker (toutes thèses, pas seulement récentes)
# ---------------------------------------------------------------------------
section("2. COUVERTURE PAR TICKER (toutes thèses en base)")

rows = c.execute(
    """
    SELECT instrument_id,
           COUNT(*) as n,
           MAX(conviction_score) as max_conv,
           MAX(datetime(created_at)) as last_ts
    FROM theses
    GROUP BY instrument_id
    ORDER BY n DESC
    """
).fetchall()

if not rows:
    print("(aucune thèse en base)")
else:
    print(f"{'TICKER':<10} {'N_THESES':>10} {'MAX_CONV':>10} {'LAST_TS':<20}")
    print("-" * 60)
    for r in rows:
        print(
            f"{(r['instrument_id'] or '?'):<10} "
            f"{r['n']:>10} "
            f"{(r['max_conv'] or 0):>10} "
            f"{(r['last_ts'] or '?'):<20}"
        )

# ---------------------------------------------------------------------------
# 3. Croisement portfolio_targets vs thèses -> tickers ORPHELINS
# ---------------------------------------------------------------------------
section("3. TICKERS ORPHELINS (cible définie mais aucun agent ne produit de thèse)")

try:
    rows = c.execute(
        """
        SELECT pt.ticker,
               pt.target_weight_pct,
               pt.source,
               pt.agent_decided,
               COALESCE(t.n_theses, 0) as n_theses,
               COALESCE(t.max_conv, 0) as max_conv,
               COALESCE(t.n_recent, 0) as n_recent
        FROM portfolio_targets pt
        LEFT JOIN (
            SELECT instrument_id,
                   COUNT(*) as n_theses,
                   MAX(conviction_score) as max_conv,
                   SUM(CASE WHEN datetime(created_at) > datetime('now','-2 days') THEN 1 ELSE 0 END) as n_recent
            FROM theses
            GROUP BY instrument_id
        ) t ON t.instrument_id = pt.ticker
        WHERE pt.active = 1
        ORDER BY pt.target_weight_pct DESC
        """
    ).fetchall()

    if not rows:
        print("(aucune target active)")
    else:
        print(f"{'TICKER':<10} {'CIBLE%':>8} {'SOURCE':<12} {'AGENT_DEC':>10} {'N_TOT':>6} {'MAX_C':>6} {'N_2J':>6}  STATUT")
        print("-" * 78)
        orphan_count = 0
        for r in rows:
            statut = "OK" if r["n_recent"] > 0 else "ORPHELIN (aucune thèse récente)"
            if r["n_recent"] == 0:
                orphan_count += 1
            print(
                f"{r['ticker']:<10} "
                f"{r['target_weight_pct']:>7.2f}% "
                f"{(r['source'] or '?'):<12} "
                f"{r['agent_decided']:>10} "
                f"{r['n_theses']:>6} "
                f"{r['max_conv']:>6} "
                f"{r['n_recent']:>6}  "
                f"{statut}"
            )
        print(f"\n{orphan_count} tickers ORPHELINS sur {len(rows)} cibles actives")
except sqlite3.OperationalError as e:
    print(f"[WARN] portfolio_targets inaccessible: {e}")

# ---------------------------------------------------------------------------
# 4. Liste des agent_type qui tournent
# ---------------------------------------------------------------------------
section("4. TYPES D'AGENTS QUI PRODUISENT DES THESES")

rows = c.execute(
    """
    SELECT agent_type,
           COUNT(*) as n,
           COUNT(DISTINCT instrument_id) as n_tickers,
           MAX(datetime(created_at)) as last_ts
    FROM theses
    GROUP BY agent_type
    ORDER BY n DESC
    """
).fetchall()

if not rows:
    print("(aucun agent n'a produit de thèse)")
else:
    print(f"{'AGENT_TYPE':<25} {'N_THESES':>10} {'N_TICKERS':>10} {'LAST_TS':<20}")
    print("-" * 70)
    for r in rows:
        print(
            f"{(r['agent_type'] or '?'):<25} "
            f"{r['n']:>10} "
            f"{r['n_tickers']:>10} "
            f"{(r['last_ts'] or '?'):<20}"
        )

# ---------------------------------------------------------------------------
# 5. Dernier cycle (si table run_cycles existe)
# ---------------------------------------------------------------------------
section("5. DERNIERS RUN CYCLES")

try:
    rows = c.execute(
        """
        SELECT * FROM run_cycles
        ORDER BY rowid DESC
        LIMIT 5
        """
    ).fetchall()
    if rows:
        cols = rows[0].keys()
        print(" | ".join(cols))
        print("-" * 78)
        for r in rows:
            print(" | ".join(str(r[k])[:20] for k in cols))
    else:
        print("(table vide)")
except sqlite3.OperationalError:
    # essaie d'autres noms
    for tbl in ("decision_cycles", "cycles", "agent_runs"):
        try:
            rows = c.execute(f"SELECT * FROM {tbl} ORDER BY rowid DESC LIMIT 5").fetchall()
            print(f"[table: {tbl}]")
            if rows:
                cols = rows[0].keys()
                print(" | ".join(cols))
                print("-" * 78)
                for r in rows:
                    print(" | ".join(str(r[k])[:20] for k in cols))
            break
        except sqlite3.OperationalError:
            continue
    else:
        print("(aucune table run_cycles / decision_cycles / cycles trouvée)")

print()
print("=" * 78)
print("FIN DIAGNOSTIC")
print("=" * 78)
c.close()
