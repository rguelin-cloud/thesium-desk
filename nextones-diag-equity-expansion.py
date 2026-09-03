# -*- coding: utf-8 -*-
"""
NEXTONES - Diag Equity Expansion v1
Marker: [DIAG_EQUITY_EXPANSION]

Objectif : comprendre pourquoi aucun candidat equity n'est apparu
apres application du patch nextones-universe-expansion-equity-v1.py.

Verifie dans l'ordre :
  1. Le fichier universe_expansion_agent.py contient bien le marker
     [EQUITY_EXPANSION_V1] et la constante EQUITY_WATCHLIST_V1
  2. Le module est importable et expose EQUITY_WATCHLIST_V1
  3. Le scan le plus recent dans universe_candidates contient-il des equity ?
  4. Si oui en DB mais pas en UI : verifier le filtre status='pending'
  5. Combien de tickers de la watchlist sont deja dans instruments (exclus)
  6. Pour 5 tickers de la watchlist : tester fetch_etf_history()
     pour voir si yfinance / prices renvoie de l'historique

Usage :
    py -3.13 nextones-diag-equity-expansion.py
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import traceback
from pathlib import Path

DB_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
AGENT_PATH = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\universe_expansion_agent.py")

MARKER = "[EQUITY_EXPANSION_V1]"


def section(title: str) -> None:
    print("")
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)


def step1_check_file() -> bool:
    section("1. Verification du fichier source")
    if not AGENT_PATH.exists():
        print(f"  [KO] Fichier introuvable : {AGENT_PATH}")
        return False
    src = AGENT_PATH.read_text(encoding="utf-8-sig")
    has_marker_begin = src.count("[EQUITY_EXPANSION_V1] BEGIN")
    has_marker_end = src.count("[EQUITY_EXPANSION_V1] END")
    has_watchlist = "EQUITY_WATCHLIST_V1" in src
    has_loop = "for eq in EQUITY_WATCHLIST_V1" in src
    print(f"  Fichier : {AGENT_PATH}")
    print(f"  Taille : {len(src)} chars, {src.count(chr(10))} lignes")
    print(f"  [EQUITY_EXPANSION_V1] BEGIN trouve : {has_marker_begin} occurrence(s)")
    print(f"  [EQUITY_EXPANSION_V1] END   trouve : {has_marker_end} occurrence(s)")
    print(f"  EQUITY_WATCHLIST_V1 defini : {has_watchlist}")
    print(f"  Boucle for eq in EQUITY_WATCHLIST_V1 : {has_loop}")
    ok = has_marker_begin >= 2 and has_marker_end >= 2 and has_watchlist and has_loop
    if not ok:
        print("  [KO] Patch NON applique correctement, relancer :")
        print("       py -3.13 nextones-universe-expansion-equity-v1.py")
        return False
    print("  [OK] Patch applique correctement dans le fichier")
    return True


def step2_import_module():
    section("2. Import du module patche")
    try:
        spec = importlib.util.spec_from_file_location(
            "universe_expansion_agent", AGENT_PATH
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:
        print(f"  [KO] Import echoue : {exc}")
        traceback.print_exc()
        return None
    wl = getattr(mod, "EQUITY_WATCHLIST_V1", None)
    if wl is None:
        print("  [KO] EQUITY_WATCHLIST_V1 non expose par le module")
        return None
    print(f"  [OK] Module importe, EQUITY_WATCHLIST_V1 contient {len(wl)} tickers")
    print(f"       Premiers : {[w['ticker'] for w in wl[:5]]}")
    print(f"       Derniers : {[w['ticker'] for w in wl[-5:]]}")
    return mod


def step3_check_candidates_db():
    section("3. Verification base universe_candidates (status='pending')")
    if not DB_PATH.exists():
        print(f"  [KO] DB introuvable : {DB_PATH}")
        return
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT asset_class, COUNT(*) AS n FROM universe_candidates "
            "WHERE status='pending' GROUP BY asset_class ORDER BY n DESC;"
        )
        rows = cur.fetchall()
        if not rows:
            print("  Aucun candidat pending en base")
        else:
            print("  Repartition par asset_class :")
            for r in rows:
                print(f"    - {r['asset_class']:10s} : {r['n']}")
        # Detail equity le cas echeant
        cur = conn.execute(
            "SELECT ticker, score, scan_batch FROM universe_candidates "
            "WHERE asset_class='equity' ORDER BY scan_batch DESC, score DESC LIMIT 10;"
        )
        rows = cur.fetchall()
        if rows:
            print("  Detail des 10 derniers equity (tous statuts) :")
            for r in rows:
                print(f"    {r['ticker']:8s} score={r['score']:.3f} batch={r['scan_batch']}")
        else:
            print("  Aucun equity n'a jamais ete insere en base")
        # Derniers batchs
        cur = conn.execute(
            "SELECT scan_batch, COUNT(*) AS n, MIN(proposed_at) AS t "
            "FROM universe_candidates GROUP BY scan_batch ORDER BY t DESC LIMIT 5;"
        )
        print("  Derniers scan_batch :")
        for r in cur.fetchall():
            print(f"    {r['scan_batch']} n={r['n']} t={r['t']}")
    finally:
        conn.close()


def step4_check_existing_overlap(mod):
    section("4. Tickers de la watchlist deja dans instruments (exclus du scan)")
    if mod is None or not DB_PATH.exists():
        print("  Skip : module ou DB indispo")
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("SELECT ticker FROM instruments;")
        existing = {r[0].upper() for r in cur.fetchall()}
        wl = mod.EQUITY_WATCHLIST_V1
        already_in = [w["ticker"] for w in wl if w["ticker"].upper() in existing]
        to_scan = [w["ticker"] for w in wl if w["ticker"].upper() not in existing]
        print(f"  Watchlist : {len(wl)} tickers")
        print(f"  Deja dans instruments (exclus) : {len(already_in)}")
        if already_in:
            print(f"    {already_in}")
        print(f"  A scanner : {len(to_scan)}")
        print(f"    premiers : {to_scan[:10]}")
    finally:
        conn.close()


def step5_test_fetch_history(mod):
    section("5. Test fetch_etf_history sur 5 equity (acces prices + yfinance)")
    if mod is None or not DB_PATH.exists():
        print("  Skip : module ou DB indispo")
        return
    fetch_fn = getattr(mod, "fetch_etf_history", None)
    if fetch_fn is None:
        print("  [KO] fetch_etf_history non expose")
        return
    sample = ["AVGO", "JPM", "V", "COST", "LLY"]
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        for ticker in sample:
            print(f"  --- {ticker} ---")
            # 1) presence dans prices ?
            try:
                # Le schema prices a instrument_id, pas de col ticker directe.
                # On joint via instruments.
                cur = conn.execute(
                    "SELECT COUNT(*) AS n FROM prices p "
                    "JOIN instruments i ON i.id = p.instrument_id "
                    "WHERE i.ticker = ?;",
                    (ticker,),
                )
                n = cur.fetchone()["n"]
                print(f"    prices via instruments JOIN : {n} barre(s)")
            except sqlite3.OperationalError as exc:
                print(f"    [WARN] join prices/instruments KO : {exc}")
            # 2) appel direct fetch_etf_history (utilise sa propre logique)
            try:
                s = fetch_fn(conn, ticker, days=365)
                if s is None:
                    print(f"    fetch_etf_history -> None (history < 90j)")
                else:
                    print(f"    fetch_etf_history -> {len(s)} barres, "
                          f"de {s.index.min().date()} a {s.index.max().date()}")
            except Exception as exc:
                print(f"    [WARN] fetch_etf_history a leve : {exc}")
    finally:
        conn.close()


def step6_check_logs_hint():
    section("6. Indices a chercher dans les logs uvicorn")
    print("  Au prochain scan, on doit voir cette ligne dans uvicorn :")
    print(f"    {MARKER} equity candidates injectes: NN")
    print("  Si elle n'apparait pas, le patch n'est pas pris en compte")
    print("  (probable cache .pyc ou import deja en memoire).")
    print("")
    print("  Pour forcer le rechargement :")
    print("    1. CTRL+C l'uvicorn")
    print("    2. Vider le cache : rm -r __pycache__")
    print("    3. Relancer : py -3.13 -m uvicorn api_server_with_static:app "
          "--host 0.0.0.0 --port 8000")
    print("    4. Declencher un scan via POST /api/universe/scan")


def main() -> int:
    print(f"NEXTONES diag equity expansion - DB={DB_PATH}")
    ok = step1_check_file()
    mod = step2_import_module() if ok else None
    step3_check_candidates_db()
    if mod is not None:
        step4_check_existing_overlap(mod)
        step5_test_fetch_history(mod)
    step6_check_logs_hint()
    return 0


if __name__ == "__main__":
    sys.exit(main())
