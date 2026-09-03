# -*- coding: utf-8 -*-
"""
Verifie l'etat de XLE et XLK :
  - dans target_universe (table cible de l'approbation)
  - dans universe_candidates (toutes statuts confondus)
  - et liste l'ensemble du target_universe pour contexte.
"""

import sqlite3
from pathlib import Path

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

TICKERS_FOCUS = ("XLE", "XLK", "XLI", "XLB", "XLRE")

def main():
    if not DB.exists():
        print(f"DB introuvable : {DB}")
        return

    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 60)
    print("1) Schemas")
    print("=" * 60)
    for table in ("target_universe", "universe_candidates"):
        try:
            cols = cur.execute(f"PRAGMA table_info({table})").fetchall()
            if not cols:
                print(f"  {table} : table absente")
                continue
            print(f"  {table} : {', '.join(c['name'] for c in cols)}")
        except sqlite3.OperationalError as e:
            print(f"  {table} : erreur {e}")

    print()
    print("=" * 60)
    print("2) target_universe — contenu complet")
    print("=" * 60)
    try:
        rows = cur.execute("SELECT * FROM target_universe ORDER BY ticker").fetchall()
        if not rows:
            print("  (vide)")
        else:
            cols = rows[0].keys()
            print("  Cols :", ", ".join(cols))
            for r in rows:
                d = dict(r)
                ticker = d.get("ticker") or d.get("symbol") or "?"
                print(f"    - {ticker:<8} {d}")
    except sqlite3.OperationalError as e:
        print(f"  Erreur : {e}")

    print()
    print("=" * 60)
    print("3) universe_candidates — focus XLE / XLK / XLI / XLB / XLRE")
    print("=" * 60)
    placeholders = ",".join("?" * len(TICKERS_FOCUS))
    try:
        rows = cur.execute(
            f"SELECT id, ticker, asset_type, score, status, scan_batch, created_at "
            f"FROM universe_candidates WHERE ticker IN ({placeholders}) "
            f"ORDER BY ticker, id",
            TICKERS_FOCUS,
        ).fetchall()
        if not rows:
            print("  (aucun)")
        else:
            for r in rows:
                d = dict(r)
                print(
                    f"  [#{d['id']:>3}] {d['ticker']:<6} {str(d.get('asset_type') or ''):<7} "
                    f"score={d.get('score')} status={d.get('status')} "
                    f"batch={d.get('scan_batch')} created={d.get('created_at')}"
                )
    except sqlite3.OperationalError as e:
        print(f"  Erreur : {e}")

    print()
    print("=" * 60)
    print("4) universe_candidates — comptage par status")
    print("=" * 60)
    try:
        rows = cur.execute(
            "SELECT status, COUNT(*) AS n FROM universe_candidates GROUP BY status ORDER BY n DESC"
        ).fetchall()
        for r in rows:
            print(f"  status={r['status']!r:<15} n={r['n']}")
    except sqlite3.OperationalError as e:
        print(f"  Erreur : {e}")

    print()
    print("=" * 60)
    print("5) Verdict XLE / XLK")
    print("=" * 60)
    try:
        # On essaie de detecter la colonne ticker (peut s'appeler symbol)
        cols = [c["name"] for c in cur.execute("PRAGMA table_info(target_universe)").fetchall()]
        ticker_col = "ticker" if "ticker" in cols else ("symbol" if "symbol" in cols else None)
        for t in ("XLE", "XLK"):
            in_tu = False
            if ticker_col:
                row = cur.execute(
                    f"SELECT 1 FROM target_universe WHERE {ticker_col} = ?", (t,)
                ).fetchone()
                in_tu = bool(row)
            row_pending = cur.execute(
                "SELECT id, status FROM universe_candidates "
                "WHERE ticker = ? ORDER BY id DESC LIMIT 1",
                (t,),
            ).fetchone()
            cand_state = (
                f"dernier candidat #{row_pending['id']} status={row_pending['status']}"
                if row_pending
                else "aucun candidat"
            )
            print(f"  {t}: target_universe={'OUI' if in_tu else 'NON'} | {cand_state}")
    except sqlite3.OperationalError as e:
        print(f"  Erreur : {e}")

    conn.close()
    print()
    print("=" * 60)
    print("Termine.")
    print("=" * 60)


if __name__ == "__main__":
    main()
