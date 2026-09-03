# -*- coding: utf-8 -*-
"""
nextones-diag-reet-in-scan.py
Repere pourquoi REET n'apparait pas dans top_tickers du scan, malgre :
  - Etre dans ETF_SPDR_SECTORIELS (patch L110 [ADD_REET_V1])
  - Avoir 82 jours de prix en DB
  - Top_n_per_class actif (XLP/XLF/XLV/USDS sont passes...)

Hypotheses :
  H1 : REET deja dans existing_instrument_tickers -> skippe ligne 704
       (REET id=30 dans instruments donc OUI, c'est pour ca !)
  H2 : REET dropped au filtre correlation (68 -> 64 = 4 drops)

Le test : voir si REET est dans existing_tickers
"""

import sys, os, sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

# 1. Trace existing_instrument_tickers
section("1) _existing_instrument_tickers() = liste deja exclue du scan")
import universe_expansion_agent as uea
conn = uea._conn()
try:
    existing = uea._existing_instrument_tickers(conn)
    print(f"  Tickers existants (count={len(existing)}):")
    existing_sorted = sorted(existing)
    for t in existing_sorted:
        print(f"    {t}")
    
    if "REET" in existing:
        print(f"\n  [DECOUVERTE] REET est dans existing -> il est SKIPPE par run_scan !")
        print(f"  Voir L704: if etf['ticker'].upper() in existing: continue")
finally:
    conn.close()

# 2. Verifie ce qu'est _existing_instrument_tickers
section("2) Implementation _existing_instrument_tickers")
import inspect
print(inspect.getsource(uea._existing_instrument_tickers))

# 3. Compte les ETF SPDR + verifie chacun
section("3) Tickers ETF_SPDR_SECTORIELS et leur statut")
for etf in uea.ETF_SPDR_SECTORIELS:
    t = etf["ticker"]
    in_inst = t in existing if 'existing' in dir() else "?"
    # Compte les prix
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""SELECT COUNT(*) FROM prices p JOIN instruments i ON p.instrument_id=i.id 
                   WHERE i.ticker=?""", (t,))
    n_prices = cur.fetchone()[0]
    conn.close()
    marker = "  >>> REET <<<" if t == "REET" else ""
    print(f"  {t:8s} (existing={in_inst}, prices_in_db={n_prices}){marker}")

section("CONCLUSION")
print("""
Si REET est dans 'existing' -> il est exclu du scan a la ligne 704.
La logique anti-doublon empeche REET d'etre re-score parce qu'il est deja 
en instruments id=30.

C'est INCOHERENT : on veut que l'agent re-score les ETF candidats meme s'ils
existent deja en instruments. La table 'instruments' devrait contenir uniquement
les positions en portefeuille, pas les candidats.

OPTIONS DE CORRECTION :
  A) Supprimer REET de la table 'instruments' temporairement -> il sera fetche par le scan
  B) Patcher run_scan pour autoriser REET dans le scan meme s'il est dans existing
  C) Inserer REET directement comme candidate avec scoring manuel (via fetch_etf_history)
""")
