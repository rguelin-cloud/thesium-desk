# -*- coding: utf-8 -*-
"""
Diag HYPE v2 :
  1. Code complet data_ingestion.py (signature fetch + caller)
  2. Qui appelle data_ingestion (scheduler ? agent crypto ?)
  3. Schema prices (vraies colonnes)
  4. Derniers 5 prix HYPE en DB
  5. Recherche d'un client CoinGecko existant
  6. Liste des tickers crypto dans instruments
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"


def section(t):
    print(f"\n{'='*70}\n  {t}\n{'='*70}")


def main():
    # 1. Code complet data_ingestion.py
    section("1. data_ingestion.py (premieres 80 lignes)")
    di = ROOT / "data_ingestion.py"
    if di.exists():
        lines = di.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        for i, ln in enumerate(lines[:80], 1):
            print(f"  {i:4d}: {ln}")
        print(f"\n  Total lignes: {len(lines)}")
    else:
        print(f"  FAIL: {di} introuvable")

    # 2. Callers
    section("2. Qui appelle data_ingestion ?")
    pat = re.compile(r"(from\s+data_ingestion|import\s+data_ingestion)")
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        if pat.search(txt):
            # Affiche les lignes de match
            matches = []
            for i, ln in enumerate(txt.splitlines(), 1):
                if pat.search(ln) or "data_ingestion" in ln:
                    matches.append((i, ln.strip()))
            if matches:
                print(f"\n  {p.relative_to(ROOT)}:")
                for i, ln in matches[:8]:
                    print(f"    L{i}: {ln[:140]}")

    # 3. Schema prices
    section("3. Schema table prices")
    if DB.exists():
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cols = cur.execute("PRAGMA table_info(prices)").fetchall()
        print("  Colonnes:")
        for c in cols:
            print(f"    {c[1]:<20} {c[2]:<15} pk={c[5]}")

        # 4. Derniers 5 prix HYPE
        section("4. Derniers prix HYPE en DB")
        hype_id = cur.execute("SELECT id FROM instruments WHERE ticker='HYPE'").fetchone()
        if hype_id:
            hype_id = hype_id[0]
            # Detecter la colonne date
            col_names = [c[1] for c in cols]
            date_col = next((c for c in ("date", "ts", "dt", "day", "created_at") if c in col_names), None)
            order = f"ORDER BY {date_col} DESC" if date_col else "ORDER BY id DESC"
            rows = cur.execute(
                f"SELECT * FROM prices WHERE instrument_id=? {order} LIMIT 5", (hype_id,)
            ).fetchall()
            for r in rows:
                print(f"  {dict(r)}")
            # Premier et dernier
            first = cur.execute(
                f"SELECT * FROM prices WHERE instrument_id=? {order.replace('DESC','ASC')} LIMIT 1",
                (hype_id,)
            ).fetchone()
            last = cur.execute(
                f"SELECT * FROM prices WHERE instrument_id=? {order} LIMIT 1", (hype_id,)
            ).fetchone()
            if first and last:
                print(f"\n  Range: {dict(first).get(date_col or 'id')} -> {dict(last).get(date_col or 'id')}")
        conn.close()

    # 5. Client CoinGecko ?
    section("5. Code CoinGecko existant")
    cg_pat = re.compile(r"(coingecko|api\.coingecko|cg_throttle|coin_gecko)", re.IGNORECASE)
    cg_hits = []
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in str(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8-sig", errors="replace")
        except Exception:
            continue
        if cg_pat.search(txt):
            cg_hits.append(p)
    print(f"  {len(cg_hits)} fichier(s) avec mention CoinGecko:")
    for p in cg_hits[:15]:
        print(f"    {p.relative_to(ROOT)}")

    # 6. Crypto dans instruments
    section("6. Crypto dans instruments")
    if DB.exists():
        conn = sqlite3.connect(str(DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        rows = cur.execute(
            "SELECT id, ticker, name, asset_class, sector FROM instruments "
            "WHERE asset_class LIKE '%crypto%' OR asset_class='crypto' "
            "ORDER BY id"
        ).fetchall()
        for r in rows:
            print(f"  id={r['id']:<3} {r['ticker']:<8} {r['name']:<25} class={r['asset_class']}")
        conn.close()

    print("\n" + "=" * 70)
    print("  Diag HYPE v2 termine")
    print("=" * 70)


if __name__ == "__main__":
    sys.exit(main() or 0)
