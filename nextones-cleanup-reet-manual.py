# -*- coding: utf-8 -*-
"""
nextones-cleanup-reet-manual.py
Supprime la ligne universe_candidates id=71 (insertion manuelle REET sans score)
pour permettre a l'agent de re-scanner REET et calculer mom/sharpe/score.

CONSERVE :
  - instruments id=30 (REET)
  - instrument_broker_mapping REET <-> REET.US
  - broker_universe_activtrades REET.US
  - prices instrument_id=30 (82 jours)

Idempotent : si la ligne id=71 n'existe pas, ne fait rien.
"""

import sqlite3, sys, os

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

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

    section("1) Etat AVANT cleanup")
    cur.execute("""
        SELECT id, ticker, asset_class, status, scan_batch, score
        FROM universe_candidates WHERE ticker = 'REET'
    """)
    rows = cur.fetchall()
    print(f"Lignes REET dans universe_candidates : {len(rows)}")
    for r in rows:
        print(f"  id={r['id']} | class={r['asset_class']} | status={r['status']} | "
              f"score={r['score']} | batch={r['scan_batch']}")

    section("2) Verification que tout le reste est conserve")
    cur.execute("SELECT id, ticker FROM instruments WHERE ticker='REET'")
    inst = cur.fetchone()
    print(f"  instruments REET : id={inst['id'] if inst else 'ABSENT'}")

    cur.execute("""
        SELECT broker_symbol FROM instrument_broker_mapping
        WHERE thesium_ticker = 'REET'
    """)
    map_rows = cur.fetchall()
    print(f"  instrument_broker_mapping REET : {[r['broker_symbol'] for r in map_rows]}")

    cur.execute("""
        SELECT COUNT(*) AS n FROM prices p
        JOIN instruments i ON p.instrument_id = i.id
        WHERE i.ticker = 'REET'
    """)
    n_prices = cur.fetchone()["n"]
    print(f"  prices REET : {n_prices} lignes")

    cur.execute("""
        SELECT broker_symbol, asset_class FROM broker_universe_activtrades
        WHERE broker_symbol = 'REET.US'
    """)
    bu = cur.fetchone()
    print(f"  broker_universe_activtrades : {bu['broker_symbol']} ({bu['asset_class']})" if bu else "ABSENT")

    section("3) DELETE universe_candidates id=71 (manual-add-reet)")
    cur.execute("""
        DELETE FROM universe_candidates
        WHERE ticker = 'REET' AND scan_batch LIKE 'manual-add-reet-%'
    """)
    deleted = cur.rowcount
    con.commit()
    print(f"  Lignes supprimees : {deleted}")

    section("4) Etat APRES cleanup")
    cur.execute("""
        SELECT id, ticker, asset_class, status, scan_batch, score
        FROM universe_candidates WHERE ticker = 'REET'
    """)
    rows = cur.fetchall()
    print(f"Lignes REET dans universe_candidates : {len(rows)}")
    for r in rows:
        print(f"  id={r['id']} | class={r['asset_class']} | status={r['status']} | "
              f"score={r['score']} | batch={r['scan_batch']}")
    if not rows:
        print("  [OK] Aucune ligne REET en candidates, l'agent pourra re-scorer au prochain scan.")

    con.close()

    section("PROCHAINES ETAPES")
    print("""
  1) Redemarrer uvicorn (commandes PowerShell directes) :

     Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force}

     Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk; py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000"

  2) Attendre ~5s puis declencher scan :

     $tok = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/auth/login" `
             -Body '{"username":"rguelin","password":"Thesium2026!"}' `
             -ContentType "application/json").access_token
     Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/universe/scan" `
             -Headers @{Authorization="Bearer $tok"}

  3) Verifier :

     py -3.13 .\\nextones-check-reet-status.py

  4) ATTENDU : nouvelle ligne REET avec asset_class='etf' (minuscule, source agent),
     score / mom / sharpe calcules, scan_batch=scan-YYYYMMDDTHHMMSS-xxxx
""")

if __name__ == "__main__":
    main()
