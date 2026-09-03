"""
_show_construction_snapshot.py
==============================
Affiche le dernier snapshot du PortfolioConstructionAgent avec le détail
par ticker : score, composantes normalisées, target poussé, cap/floor.

Usage :
    py -3.13 _show_construction_snapshot.py
    py -3.13 _show_construction_snapshot.py --snapshot snap-...
    py -3.13 _show_construction_snapshot.py --history 5
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _detect_db():
    here = Path(__file__).resolve().parent
    for c in (here / "thesium.db", Path("thesium.db").resolve()):
        if c.exists():
            return c
    return here / "thesium.db"


def show_snapshot(conn, snapshot_id):
    rows = conn.execute("""
        SELECT * FROM portfolio_targets_history
        WHERE snapshot_id = ?
        ORDER BY score DESC
    """, (snapshot_id,)).fetchall()
    if not rows:
        print(f"(aucun snapshot {snapshot_id})")
        return

    head = rows[0]
    print(f"\n{'=' * 75}")
    print(f"Snapshot   : {head['snapshot_id']}")
    print(f"Cycle      : {head['cycle_id'] or '-'}")
    print(f"Régime     : {head['regime']}")
    print(f"Créé le    : {head['created_at']}")
    print(f"Tickers    : {len(rows)} évalués, "
          f"{sum(1 for r in rows if r['included'])} inclus")
    print("=" * 75)

    print(f"\n{'TICKER':<8} {'IN':>3} {'SCORE':>7} "
          f"{'C':>6} {'R':>6} {'M':>6} {'D':>6} {'V':>6}  "
          f"{'PREV%':>7} {'NEW%':>7}  CAP/FLOOR")
    print("-" * 95)
    for r in rows:
        comps = {}
        try:
            comps = json.loads(r["components_json"] or "{}")
        except Exception:
            pass
        flag = " * " if r["included"] else " - "
        print(f"{r['ticker']:<8}{flag:>3} {r['score']:>7.3f} "
              f"{comps.get('C_norm', 0):>6.3f} "
              f"{comps.get('R_norm', 0):>6.3f} "
              f"{comps.get('M_norm', 0):>6.3f} "
              f"{comps.get('D_norm', 0):>6.3f} "
              f"{comps.get('V_norm', 0):>6.3f}  "
              f"{r['prev_target_weight_pct']:>6.2f}% "
              f"{r['target_weight_pct']:>6.2f}%  "
              f"{r['cap_floor_applied'] or ''}")

    # Totaux
    total_new = sum(r["target_weight_pct"] for r in rows if r["included"])
    total_prev = sum(r["prev_target_weight_pct"] for r in rows)
    print("-" * 95)
    print(f"{'TOTAL':<11} {'':>10} {'':>30}  {total_prev:>6.2f}% {total_new:>6.2f}%")


def list_recent(conn, n=5):
    rows = conn.execute("""
        SELECT snapshot_id, MIN(cycle_id) AS cycle_id,
               MIN(regime) AS regime,
               MIN(created_at) AS created_at,
               COUNT(*) AS n_tickers,
               SUM(included) AS n_included
        FROM portfolio_targets_history
        GROUP BY snapshot_id
        ORDER BY created_at DESC
        LIMIT ?
    """, (n,)).fetchall()
    if not rows:
        print("(aucun snapshot)")
        return None
    print(f"\n{'SNAPSHOT_ID':<32} {'RÉGIME':<10} {'#TICKERS':>9} "
          f"{'INCL':>5}  {'CRÉÉ LE':<20}")
    print("-" * 80)
    for r in rows:
        print(f"{r['snapshot_id']:<32} {r['regime'] or '-':<10} "
              f"{r['n_tickers']:>9} {r['n_included']:>5}  {r['created_at']}")
    return rows[0]["snapshot_id"]


def show_current_targets(conn):
    """Tableau de bord des portfolio_targets actuels."""
    rows = conn.execute("""
        SELECT ticker, target_weight_pct, active,
               COALESCE(agent_decided, 0) AS agent_decided,
               source, score, updated_at
        FROM portfolio_targets
        WHERE active = 1
        ORDER BY target_weight_pct DESC
    """).fetchall()
    if not rows:
        print("(aucun target actif)")
        return
    print(f"\n=== portfolio_targets actifs ===")
    print(f"{'TICKER':<8} {'POIDS%':>7} {'TYPE':<8} {'SCORE':>7} {'SOURCE':<14} MAJ")
    print("-" * 70)
    total = 0.0
    for r in rows:
        kind = "AGENT" if r["agent_decided"] else "MANUEL"
        score = f"{r['score']:.3f}" if r["score"] is not None else "  -  "
        print(f"{r['ticker']:<8} {r['target_weight_pct']:>6.2f}% "
              f"{kind:<8} {score:>7} {r['source'] or '-':<14} {r['updated_at']}")
        total += r["target_weight_pct"]
    print("-" * 70)
    print(f"{'TOTAL':<8} {total:>6.2f}% NAV  (cash résiduel ≈ {100-total:.2f}%)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", default=None,
                   help="ID snapshot précis (sinon: dernier)")
    p.add_argument("--history", type=int, default=0,
                   help="Liste les N derniers snapshots et sort")
    args = p.parse_args()

    db = _detect_db()
    if not db.exists():
        print(f"ERREUR : DB {db} introuvable")
        sys.exit(1)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    show_current_targets(conn)

    if args.history:
        list_recent(conn, args.history)
        return

    snap = args.snapshot
    if not snap:
        last = list_recent(conn, 1)
        snap = last
    if snap:
        show_snapshot(conn, snap)
    conn.close()


if __name__ == "__main__":
    main()
