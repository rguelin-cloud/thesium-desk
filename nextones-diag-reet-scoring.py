# -*- coding: utf-8 -*-
"""
nextones-diag-reet-scoring.py
Diagnostic ciblé : pourquoi REET apparaît dans universe_candidates SANS score ?

Hypothèses à tester :
  H1 : REET injecté par chemin "broker_universe_activtrades" (etf_us) au lieu de ETF_SPDR_SECTORIELS
       -> classe stockee "ETF" vs "etf" pour les SPDR
  H2 : prix REET insuffisants pour calcul mom12-1 (besoin >=252 jours, on a 82)
  H3 : instrument_id mismatch entre candidate et prices
  H4 : seuil min_history dans agent ou retour None silencieux
"""

import sqlite3, os, re, sys

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
AGENT = os.path.join(ROOT, "universe_expansion_agent.py")

def section(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)

def main():
    if not os.path.exists(DB):
        print(f"[ERREUR] DB introuvable : {DB}")
        sys.exit(1)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ----------------------------------------------------------------
    section("1) Toutes les lignes universe_candidates pour REET")
    # ----------------------------------------------------------------
    cur.execute("PRAGMA table_info(universe_candidates)")
    cols = [r["name"] for r in cur.fetchall()]
    print(f"Colonnes ({len(cols)}): {cols}")

    cur.execute("SELECT * FROM universe_candidates WHERE ticker = 'REET' ORDER BY id DESC")
    rows = cur.fetchall()
    print(f"\nNombre de lignes REET : {len(rows)}")
    for r in rows:
        print("-" * 60)
        for k in r.keys():
            v = r[k]
            if v is not None and v != "":
                print(f"  {k:25s} = {v}")

    # ----------------------------------------------------------------
    section("2) Comparaison classe stockee : REET vs XLRE vs equity")
    # ----------------------------------------------------------------
    cur.execute("""
        SELECT ticker, asset_class, score, momentum_12m_minus_1m, sharpe_90d, max_correl_existing,
               scan_batch, status, proposed_at
        FROM universe_candidates
        WHERE ticker IN ('REET','XLRE','XLU','XLY','UNP','MRK','RAIN','LEO')
        ORDER BY scan_batch DESC, ticker
        LIMIT 30
    """)
    for r in cur.fetchall():
        print(f"  {r['ticker']:6s} | class={r['asset_class']:8s} | "
              f"score={str(r['score']):6s} | mom={str(r['momentum_12m_minus_1m']):8s} | "
              f"sharpe={str(r['sharpe_90d']):8s} | corr={str(r['max_correl_existing']):6s} | "
              f"status={r['status']:10s} | {r['scan_batch']}")

    # ----------------------------------------------------------------
    section("3) Instrument REET dans `instruments`")
    # ----------------------------------------------------------------
    cur.execute("SELECT * FROM instruments WHERE ticker = 'REET'")
    for r in cur.fetchall():
        for k in r.keys():
            print(f"  {k:20s} = {r[k]}")
        reet_id = r["id"]
    
    # ----------------------------------------------------------------
    section("4) Prix REET : count + bornes dates + sample")
    # ----------------------------------------------------------------
    cur.execute("""
        SELECT COUNT(*) AS n, MIN(date) AS d_min, MAX(date) AS d_max,
               MIN(close) AS c_min, MAX(close) AS c_max, AVG(close) AS c_avg
        FROM prices WHERE instrument_id = ?
    """, (reet_id,))
    r = cur.fetchone()
    print(f"  Lignes prix REET (instrument_id={reet_id}): {r['n']}")
    print(f"  Plage dates : {r['d_min']} -> {r['d_max']}")
    print(f"  Close : min={r['c_min']:.2f} | max={r['c_max']:.2f} | avg={r['c_avg']:.2f}")

    print("\n  Premieres / dernieres lignes :")
    cur.execute("""
        SELECT date, close FROM prices WHERE instrument_id = ?
        ORDER BY date ASC LIMIT 3
    """, (reet_id,))
    for x in cur.fetchall():
        print(f"    {x['date']} | close={x['close']}")
    print("    ...")
    cur.execute("""
        SELECT date, close FROM prices WHERE instrument_id = ?
        ORDER BY date DESC LIMIT 3
    """, (reet_id,))
    for x in cur.fetchall():
        print(f"    {x['date']} | close={x['close']}")

    # Comparaison avec un ETF score (XLRE)
    cur.execute("""
        SELECT COUNT(*) AS n, MIN(date) AS d_min, MAX(date) AS d_max
        FROM prices p
        JOIN instruments i ON p.instrument_id = i.id
        WHERE i.ticker = 'XLRE'
    """)
    r = cur.fetchone()
    print(f"\n  REFERENCE XLRE : {r['n']} lignes, {r['d_min']} -> {r['d_max']}")

    # ----------------------------------------------------------------
    section("5) Source d'injection : ETF_SPDR_SECTORIELS vs broker_universe_activtrades")
    # ----------------------------------------------------------------
    if os.path.exists(AGENT):
        with open(AGENT, "r", encoding="utf-8-sig") as f:
            content = f.read()
        print(f"Fichier agent : {AGENT}")
        print(f"Taille : {len(content)} chars")
        
        # Cherche marker
        if "[ADD_REET_V1]" in content:
            print("  [OK] Marker [ADD_REET_V1] PRESENT dans le fichier")
            for i, line in enumerate(content.splitlines(), 1):
                if "[ADD_REET_V1]" in line:
                    print(f"  Ligne {i}: {line.strip()}")
        else:
            print("  [WARN] Marker [ADD_REET_V1] ABSENT du fichier sur disque")
        
        # Cherche tous les usages de REET
        print("\n  Toutes occurrences 'REET' dans agent :")
        for i, line in enumerate(content.splitlines(), 1):
            if "REET" in line:
                print(f"    L{i}: {line.strip()[:120]}")

    # ----------------------------------------------------------------
    section("6) Cherche min_history / score / mom_12_1 dans agent")
    # ----------------------------------------------------------------
    if os.path.exists(AGENT):
        patterns = [
            r"min_history|MIN_HISTORY|min_days|MIN_DAYS",
            r"momentum_12m_minus_1m|momentum_12|12_minus_1m|min_history|min_days",
            r"def\s+score|def\s+compute_score|def\s+_score",
            r"INSERT\s+INTO\s+universe_candidates",
            r"asset_class\s*=",
        ]
        for pat in patterns:
            print(f"\n  Pattern : {pat}")
            for i, line in enumerate(content.splitlines(), 1):
                if re.search(pat, line, re.IGNORECASE):
                    print(f"    L{i}: {line.strip()[:130]}")

    # ----------------------------------------------------------------
    section("7) broker_universe_activtrades : verif REET.US")
    # ----------------------------------------------------------------
    try:
        cur.execute("""
            SELECT * FROM broker_universe_activtrades WHERE broker_symbol = 'REET.US'
        """)
        for r in cur.fetchall():
            for k in r.keys():
                print(f"  {k:25s} = {r[k]}")
    except Exception as e:
        print(f"  [INFO] {e}")

    con.close()
    print("\n[FIN diag]")

if __name__ == "__main__":
    main()
