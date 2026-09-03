# -*- coding: utf-8 -*-
"""
[DIAG_SCAN_EMPTY_V1]
1) Verifie contenu table universe_candidates (vraiment vide ?)
2) Verifie logs/state du dernier scan
3) Appelle directement la fonction run_scan() pour voir l'output et capturer toute exception
4) Verifie target_universe (deja existant)
"""
import sqlite3, sys, traceback
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"
sys.path.insert(0, str(ROOT))

def section(t):
    print()
    print("=" * 72)
    print(t)
    print("=" * 72)

def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()

    section("1) universe_candidates schema + count")
    for r in cur.execute("PRAGMA table_info(universe_candidates)"):
        print(f"  {r[0]:2d}  {r[1]:30s}  {r[2]}")
    print()
    print(f"  Total rows: {cur.execute('SELECT COUNT(*) FROM universe_candidates').fetchone()[0]}")
    print(f"  By status:")
    for r in cur.execute("SELECT status, COUNT(*) FROM universe_candidates GROUP BY status"):
        print(f"    {r[0]}: {r[1]}")
    print()
    print(f"  Last 5 rows:")
    for r in cur.execute("SELECT id, ticker, status, score, created_at FROM universe_candidates ORDER BY id DESC LIMIT 5"):
        print(f"    {r}")

    section("2) target_universe (deja existant)")
    try:
        for r in cur.execute("PRAGMA table_info(target_universe)"):
            print(f"  {r[0]:2d}  {r[1]:30s}  {r[2]}")
        print()
        print(f"  Rows: {cur.execute('SELECT COUNT(*) FROM target_universe').fetchone()[0]}")
        for r in cur.execute("SELECT * FROM target_universe LIMIT 15"):
            print(f"    {r}")
    except Exception as e:
        print(f"  [ERR] {e}")

    section("3) Test direct run_scan() avec capture stack")
    try:
        import universe_expansion_agent as uea
        print(f"  Module charge : {uea.__file__}")
        # Liste les fonctions exportees
        funcs = [n for n in dir(uea) if not n.startswith('_') and callable(getattr(uea, n, None))]
        print(f"  Fonctions : {funcs}")
        print()
        print("  Appel run_scan(top_n=5, dry_run=True)...")
        try:
            res = uea.run_scan(top_n=5, dry_run=True)
            print(f"  -> result type: {type(res).__name__}")
            print(f"  -> result: {res}")
            if isinstance(res, dict):
                for k, v in res.items():
                    if isinstance(v, list):
                        print(f"    {k}: {len(v)} items")
                        for it in v[:3]:
                            print(f"      - {it}")
                    else:
                        print(f"    {k}: {v}")
        except Exception as e:
            print(f"  [EXC dans run_scan] {type(e).__name__}: {e}")
            traceback.print_exc()
    except Exception as e:
        print(f"  [IMPORT EXC] {type(e).__name__}: {e}")
        traceback.print_exc()

    section("4) Test fetch_top_cryptos() isole")
    try:
        import universe_expansion_agent as uea
        cryptos = uea.fetch_top_cryptos(top=5)
        print(f"  fetch_top_cryptos returned: {len(cryptos)} items")
        for c in cryptos[:3]:
            print(f"    {c}")
    except Exception as e:
        print(f"  [EXC] {type(e).__name__}: {e}")
        traceback.print_exc()

    section("5) Test fetch des ETFs si presente")
    try:
        import universe_expansion_agent as uea
        for fn_name in ['fetch_spdr_etfs', 'fetch_etfs', 'fetch_etfs_universe']:
            if hasattr(uea, fn_name):
                print(f"  trying {fn_name}()")
                etfs = getattr(uea, fn_name)()
                print(f"    -> {len(etfs)} items")
                for e in etfs[:3]:
                    print(f"      {e}")
                break
        else:
            print("  Aucune fonction ETF trouvee")
    except Exception as e:
        print(f"  [EXC] {type(e).__name__}: {e}")
        traceback.print_exc()

    con.close()

if __name__ == "__main__":
    main()
