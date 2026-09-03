# -*- coding: utf-8 -*-
"""
[DEDUPE_UNIV_CANDIDATES_V1]
Pour chaque ticker en status='pending', garde uniquement le candidat avec l'id le plus eleve
(scan le plus recent). Les anciens passent en status='superseded' (preserve l'historique).

Affiche avant/apres pour controle.
"""
import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

def section(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)

def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    section("1) AVANT — pending par ticker")
    rows = cur.execute(
        """SELECT ticker, COUNT(*) AS n, GROUP_CONCAT(id) AS ids, MAX(id) AS keep_id
           FROM universe_candidates 
           WHERE status='pending'
           GROUP BY ticker
           ORDER BY ticker"""
    ).fetchall()
    print(f"  {len(rows)} ticker(s) distincts en pending")
    to_supersede = []
    for r in rows:
        marker = "  DUPLI" if r['n'] > 1 else "       "
        print(f"  {marker} {r['ticker']:8s}  n={r['n']}  ids=[{r['ids']}]  keep #{r['keep_id']}")
        if r['n'] > 1:
            ids = [int(x) for x in r['ids'].split(',')]
            for i in ids:
                if i != r['keep_id']:
                    to_supersede.append((r['ticker'], i))

    if not to_supersede:
        print("\n  Aucun doublon, rien a faire")
        con.close()
        return

    section(f"2) Marquage 'superseded' pour {len(to_supersede)} entrees")
    for ticker, cid in to_supersede:
        cur.execute(
            """UPDATE universe_candidates 
               SET status='superseded', 
                   notes=COALESCE(notes,'') || ' [auto-superseded by dedupe]',
                   reviewed_at=datetime('now')
               WHERE id=? AND status='pending'""",
            (cid,)
        )
        print(f"  superseded #{cid} ({ticker})")
    con.commit()

    section("3) APRES — pending par ticker")
    rows = cur.execute(
        """SELECT ticker, COUNT(*) AS n, GROUP_CONCAT(id) AS ids
           FROM universe_candidates 
           WHERE status='pending'
           GROUP BY ticker
           ORDER BY ticker"""
    ).fetchall()
    print(f"  {len(rows)} ticker(s) en pending")
    for r in rows:
        print(f"    {r['ticker']:8s}  n={r['n']}  ids=[{r['ids']}]")

    # Recap final tries par score
    print()
    print("Recap des pending uniques, tries par score :")
    for r in cur.execute(
        """SELECT id, ticker, asset_class, score, sharpe_90d, momentum_12m_minus_1m, suggested_cap_pct
           FROM universe_candidates WHERE status='pending'
           ORDER BY score DESC"""
    ):
        print(f"  [#{r['id']}] {r['ticker']:8s} ({r['asset_class']:7s}) "
              f"score={r['score']:.3f}  sharpe={r['sharpe_90d']:.2f}  "
              f"mom12-1={r['momentum_12m_minus_1m']:+.3f}  cap={r['suggested_cap_pct']*100:.1f}%")

    con.close()
    print()
    print("=" * 60)
    print("Recharge l'UI (Ctrl+F5) — plus de doublons.")
    print("=" * 60)

if __name__ == "__main__":
    main()
