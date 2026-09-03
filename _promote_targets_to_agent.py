"""
_promote_targets_to_agent.py
============================
Bascule les cibles actuelles (seed_v6_1) en mode 'agent_decided' afin que
le PortfolioConstructionAgent puisse les ré-évaluer librement.

Sans cette étape, l'agent voit les 4 cibles comme MANUELLES et ne les
touchera pas.

Usage :
    py -3.13 _promote_targets_to_agent.py                 # liste l'état
    py -3.13 _promote_targets_to_agent.py --apply         # bascule en agent
    py -3.13 _promote_targets_to_agent.py --lock META     # re-verrouille META
    py -3.13 _promote_targets_to_agent.py --unlock LINK   # libère LINK

Recommandation : en Jalon 1, applique sur LINK/ETH/BTC mais garde META en
manuel le temps de calibrer (LINK & ETH ont des thèses CryptoAgent récentes
qui donneront un score, META a probablement peu d'historique).
"""
import argparse
import sqlite3
import sys
from pathlib import Path


def _detect_db():
    here = Path(__file__).resolve().parent
    for c in (here / "thesium.db", Path("thesium.db").resolve()):
        if c.exists():
            return c
    return here / "thesium.db"


def list_state(conn):
    rows = conn.execute("""
        SELECT ticker, target_weight_pct, active,
               COALESCE(agent_decided, 0) AS agent_decided,
               source, updated_at
        FROM portfolio_targets
        ORDER BY target_weight_pct DESC
    """).fetchall()
    print(f"\n{'TICKER':<8} {'POIDS%':>7} {'ACTIVE':>7} {'TYPE':<8} "
          f"{'SOURCE':<14} MAJ")
    print("-" * 75)
    for r in rows:
        kind = "AGENT" if r["agent_decided"] else "MANUEL"
        print(f"{r['ticker']:<8} {r['target_weight_pct']:>6.2f}% "
              f"{'OUI' if r['active'] else 'NON':>7} "
              f"{kind:<8} {r['source'] or '-':<14} {r['updated_at']}")


def promote_all(conn):
    cur = conn.execute("""
        UPDATE portfolio_targets
        SET agent_decided = 1, updated_at = datetime('now')
        WHERE COALESCE(agent_decided, 0) = 0
    """)
    conn.commit()
    return cur.rowcount


def set_flag(conn, ticker: str, agent_decided: int) -> bool:
    cur = conn.execute("""
        UPDATE portfolio_targets
        SET agent_decided = ?, updated_at = datetime('now')
        WHERE ticker = ?
    """, (agent_decided, ticker.upper()))
    conn.commit()
    return cur.rowcount > 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Bascule toutes les cibles non agent_decided en agent")
    p.add_argument("--lock", default=None,
                   help="Verrouille un ticker en MANUEL (l'agent ne le touchera plus)")
    p.add_argument("--unlock", default=None,
                   help="Libère un ticker (l'agent peut le piloter)")
    args = p.parse_args()

    db = _detect_db()
    if not db.exists():
        print(f"ERREUR : DB introuvable ({db})")
        sys.exit(1)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    print("=== État AVANT ===")
    list_state(conn)

    if args.lock:
        ok = set_flag(conn, args.lock, 0)
        print(f"\n{'OK' if ok else 'KO'} : {args.lock} → MANUEL (verrouillé)")
    elif args.unlock:
        ok = set_flag(conn, args.unlock, 1)
        print(f"\n{'OK' if ok else 'KO'} : {args.unlock} → AGENT (libéré)")
    elif args.apply:
        n = promote_all(conn)
        print(f"\nOK : {n} ticker(s) basculé(s) en AGENT")
    else:
        print("\n(lecture seule — ajoute --apply / --lock / --unlock pour modifier)")

    print("\n=== État APRÈS ===")
    list_state(conn)
    conn.close()


if __name__ == "__main__":
    main()
