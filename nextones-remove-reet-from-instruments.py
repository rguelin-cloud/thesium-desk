# -*- coding: utf-8 -*-
"""
nextones-remove-reet-from-instruments.py
Supprime REET de la table instruments pour que run_scan() puisse le proposer
comme candidat avec scoring.

CONSERVE :
  - instrument_broker_mapping (REET <-> REET.US)
  - broker_universe_activtrades (REET.US)

ATTENTION FK :
  - prices a une FK sur instruments.id (CASCADE ?)
  - On copie d'abord les prix dans un fichier de backup avant DELETE

WORKFLOW APRES :
  1) DELETE FROM instruments WHERE ticker='REET' (id=30 disparait, prix purges si cascade)
  2) Restart uvicorn
  3) Scan -> REET sera dans candidates avec score
  4) Approve REET dans UI -> agent re-cree instruments id=N + recree les prix via fetch
"""

import sqlite3, sys, os, json
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
BACKUP_DIR = ROOT

def section(t):
    print("\n" + "=" * 70)
    print(t)
    print("=" * 70)

def main():
    if not os.path.exists(DB):
        print(f"[ERREUR] DB introuvable : {DB}")
        sys.exit(1)

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    section("1) Etat AVANT")
    cur.execute("SELECT * FROM instruments WHERE ticker='REET'")
    inst = cur.fetchone()
    if not inst:
        print("  [INFO] REET deja absent de instruments. Rien a faire.")
        return
    print(f"  instruments REET : id={inst['id']}")
    
    cur.execute("""
        SELECT COUNT(*) AS n FROM prices p
        JOIN instruments i ON p.instrument_id = i.id
        WHERE i.ticker = 'REET'
    """)
    n_prices = cur.fetchone()["n"]
    print(f"  prices lies a REET : {n_prices}")

    # PRAGMA foreign_keys ?
    cur.execute("PRAGMA foreign_keys")
    fk = cur.fetchone()
    print(f"  PRAGMA foreign_keys = {fk[0]}")

    # Schema prices
    cur.execute("PRAGMA foreign_key_list(prices)")
    for r in cur.fetchall():
        print(f"  prices FK: {dict(r)}")

    section("2) Backup des prix REET dans CSV")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_csv = os.path.join(BACKUP_DIR, f"reet_prices_backup_{ts}.csv")
    cur.execute("""
        SELECT p.date, p.open, p.high, p.low, p.close, p.volume
        FROM prices p
        JOIN instruments i ON p.instrument_id = i.id
        WHERE i.ticker = 'REET'
        ORDER BY p.date
    """)
    rows = cur.fetchall()
    with open(backup_csv, "w", encoding="utf-8") as f:
        f.write("date,open,high,low,close,volume\n")
        for r in rows:
            f.write(f"{r['date']},{r['open']},{r['high']},{r['low']},{r['close']},{r['volume']}\n")
    print(f"  Backup CSV : {backup_csv} ({len(rows)} lignes)")

    # Backup instrument
    backup_inst = os.path.join(BACKUP_DIR, f"reet_instrument_backup_{ts}.json")
    with open(backup_inst, "w", encoding="utf-8") as f:
        json.dump(dict(inst), f, indent=2, default=str)
    print(f"  Backup instrument : {backup_inst}")

    section("3) Verifie instrument_broker_mapping (NE DOIT PAS etre purge)")
    cur.execute("""
        SELECT * FROM instrument_broker_mapping WHERE thesium_ticker = 'REET'
    """)
    map_rows = cur.fetchall()
    print(f"  Lignes mapping REET avant : {len(map_rows)}")
    for r in map_rows:
        print(f"    {dict(r)}")

    section("4) DELETE FROM prices (avant DELETE instruments pour eviter FK)")
    cur.execute("DELETE FROM prices WHERE instrument_id = ?", (inst["id"],))
    print(f"  Lignes prix supprimees : {cur.rowcount}")
    con.commit()

    section("5) DELETE FROM instruments WHERE ticker='REET'")
    cur.execute("DELETE FROM instruments WHERE ticker = 'REET'")
    print(f"  Lignes instruments supprimees : {cur.rowcount}")
    con.commit()

    section("6) Verification APRES")
    cur.execute("SELECT COUNT(*) AS n FROM instruments WHERE ticker='REET'")
    print(f"  instruments REET : {cur.fetchone()['n']} (attendu 0)")
    
    cur.execute("""
        SELECT COUNT(*) AS n FROM instrument_broker_mapping WHERE thesium_ticker = 'REET'
    """)
    n_map = cur.fetchone()["n"]
    print(f"  instrument_broker_mapping REET : {n_map} (attendu {len(map_rows)})")
    
    cur.execute("""
        SELECT COUNT(*) AS n FROM broker_universe_activtrades WHERE broker_symbol = 'REET.US'
    """)
    print(f"  broker_universe_activtrades REET.US : {cur.fetchone()['n']} (attendu 1)")

    con.close()

    section("PROCHAINES ETAPES")
    print(f"""
  1) PAS BESOIN de redemarrer uvicorn (le module va re-lire existing depuis DB)

  2) Declencher scan :
     $tok = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/auth/login" -Body '{{"username":"rguelin","password":"Thesium2026!"}}' -ContentType "application/json").access_token
     $res = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/universe/scan" -Headers @{{Authorization="Bearer $tok"}} -ContentType "application/json" -Body '{{"top":10}}' -TimeoutSec 600
     $res | ConvertTo-Json -Depth 5

  3) Verifier REET dans candidates avec score :
     py -3.13 .\\nextones-check-reet-status.py

  ATTENDU :
   - REET dans top_tickers avec score ~0.55-0.65 (proche XLRE)
   - Une fois approuve dans UI : REET re-inserre en instruments via approve_candidate()

  EN CAS DE BESOIN DE RESTAURER :
     Backup CSV : {backup_csv}
     Backup instrument : {backup_inst}
""")

if __name__ == "__main__":
    main()
