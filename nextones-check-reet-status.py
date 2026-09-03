# -*- coding: utf-8 -*-
# nextones-check-reet-status.py
# Verification globale de l'integration REET apres scan.
#
# Usage : py -3.13 nextones-check-reet-status.py

import sqlite3
import os
import sys

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
TICKER = "REET"


def main():
    if not os.path.exists(DB_PATH):
        print(f"FATAL DB introuvable : {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()

    print("=" * 70)
    print(f"VERIFICATION INTEGRATION {TICKER}")
    print("=" * 70)

    # 1. instruments
    print(f"\n[1] instruments")
    cur.execute("SELECT id, ticker, name, asset_class, sector FROM instruments WHERE ticker = ?", (TICKER,))
    row = cur.fetchone()
    inst_id = None
    if row:
        inst_id = row[0]
        print(f"  OK : id={row[0]} ticker={row[1]} name={row[2]} class={row[3]} sector={row[4]}")
    else:
        print(f"  KO : {TICKER} absent")

    # 2. instrument_broker_mapping
    print(f"\n[2] instrument_broker_mapping")
    cur.execute("""
        SELECT thesium_ticker, broker_symbol, instrument_type,
               contract_size, lot_step, quote_ccy, tradable
        FROM instrument_broker_mapping WHERE thesium_ticker = ?
    """, (TICKER,))
    row = cur.fetchone()
    if row:
        print(f"  OK : {row}")
    else:
        print(f"  KO : pas de mapping broker")

    # 3. broker_universe_activtrades
    print(f"\n[3] broker_universe_activtrades (REET.US)")
    cur.execute("""
        SELECT broker_symbol, asset_class, underlying_ticker, quote_ccy
        FROM broker_universe_activtrades WHERE broker_symbol = ?
    """, (f"{TICKER}.US",))
    row = cur.fetchone()
    if row:
        print(f"  OK : {row}")
    else:
        print(f"  KO : REET.US absent du seed ActivTrades")

    # 4. prices
    print(f"\n[4] prices")
    if inst_id:
        cur.execute("""
            SELECT COUNT(*), MIN(date), MAX(date),
                   ROUND(MIN(close), 2), ROUND(MAX(close), 2),
                   ROUND(AVG(close), 2)
            FROM prices WHERE instrument_id = ?
        """, (inst_id,))
        cnt, dmin, dmax, cmin, cmax, cavg = cur.fetchone()
        print(f"  {cnt} lignes du {dmin} au {dmax}")
        print(f"  close min={cmin} max={cmax} moyen={cavg} USD")

    # 5. universe_candidates (toutes occurrences REET)
    print(f"\n[5] universe_candidates (historique REET)")
    cur.execute("""
        SELECT id, status, score,
               ROUND(momentum_12m_minus_1m, 4) as mom12,
               ROUND(momentum_3m, 4) as mom3,
               ROUND(sharpe_90d, 3) as sharpe,
               ROUND(max_correl_existing, 3) as corr_max,
               max_correl_with,
               ROUND(suggested_cap_pct, 4) as cap,
               scan_batch, proposed_at, reviewed_at
        FROM universe_candidates WHERE ticker = ?
        ORDER BY id DESC
    """, (TICKER,))
    rows = cur.fetchall()
    if not rows:
        print(f"  KO : aucune entree REET")
    else:
        for r in rows:
            print(f"  id={r[0]} status={r[1]}")
            print(f"    score={r[2]} cap={r[8]} sharpe={r[5]}")
            print(f"    mom12-1={r[3]} mom3={r[4]}")
            print(f"    corr_max={r[6]} avec={r[7]}")
            print(f"    scan_batch={r[9]}")
            print(f"    proposed_at={r[10]} reviewed_at={r[11]}")

    # 6. scan_batch global le plus recent
    print(f"\n[6] Dernier scan_batch global (univers)")
    cur.execute("""
        SELECT scan_batch, COUNT(*) as n, MIN(proposed_at), MAX(proposed_at)
        FROM universe_candidates
        GROUP BY scan_batch
        ORDER BY MAX(proposed_at) DESC
        LIMIT 5
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:50s} : {r[1]:3d} candidats, du {r[2]} au {r[3]}")

    # 7. statut global des candidats
    print(f"\n[7] Statut global candidats univers")
    cur.execute("""
        SELECT status, COUNT(*) FROM universe_candidates
        GROUP BY status ORDER BY 2 DESC
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:15s} : {r[1]}")

    conn.close()
    print("\n" + "=" * 70)
    print("FIN")
    print("=" * 70)


if __name__ == "__main__":
    main()
