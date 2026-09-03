"""
_migrate_targets_v6_1.py — Migration v6 → v6.1
==============================================
Crée la table portfolio_targets et seed les valeurs initiales basées sur
ce qu'affiche l'UI "Portfolio idéal".

Usage : py -3.13 _migrate_targets_v6_1.py
Idempotent : peut être relancé sans risque.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "thesium.db"
if not DB_PATH.exists():
    # fallback : current working dir
    DB_PATH = Path("thesium.db").resolve()

# Targets initiaux — alignés sur l'UI "Portfolio idéal"
SEED_TARGETS = {
    "META": 2.0,
    "LINK": 1.0,
    "ETH": 0.8,
    "BTC": 1.0,
}

def main():
    print(f"=== Migration target_weights v6.1 ===")
    print(f"DB    : {DB_PATH}")
    if not DB_PATH.exists():
        print("ERREUR : thesium.db introuvable. Lance ce script depuis ThesiumDesk/.")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # 1) Création de la table si absente
    conn.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            target_weight_pct REAL NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            source TEXT DEFAULT 'manual',
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    print("OK Table portfolio_targets prête")

    # 2) Index utile pour le Reconciler
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pt_active_ticker
        ON portfolio_targets(active, ticker)
    """)
    conn.commit()

    # 3) Etat actuel
    existing = {
        r["ticker"]: r["target_weight_pct"]
        for r in conn.execute(
            "SELECT ticker, target_weight_pct FROM portfolio_targets"
        ).fetchall()
    }
    print(f"\nTickers déjà présents : {len(existing)}")
    for t, w in existing.items():
        print(f"  - {t:<6} {w:.2f} %")

    # 4) Seed des targets manquants uniquement
    inserted = 0
    for ticker, target_pct in SEED_TARGETS.items():
        if ticker in existing:
            continue
        conn.execute("""
            INSERT INTO portfolio_targets (ticker, target_weight_pct, active, source)
            VALUES (?, ?, 1, 'seed_v6_1')
        """, (ticker, target_pct))
        inserted += 1
        print(f"  + SEED {ticker:<6} {target_pct:.2f} %")
    conn.commit()

    if inserted == 0:
        print("\nRien à seeder — table déjà complète.")
    else:
        print(f"\nOK {inserted} ticker(s) seedé(s)")

    # 5) Vérification finale
    print("\n=== État final portfolio_targets ===")
    rows = conn.execute("""
        SELECT ticker, target_weight_pct, active, source, updated_at
        FROM portfolio_targets ORDER BY target_weight_pct DESC
    """).fetchall()
    total = 0.0
    for r in rows:
        flag = "OK" if r["active"] else "OFF"
        print(f"  [{flag}] {r['ticker']:<6} {r['target_weight_pct']:>5.2f} %  "
              f"({r['source']}, {r['updated_at']})")
        if r["active"]:
            total += r["target_weight_pct"]
    print(f"\nTotal target actif : {total:.2f} % NAV")
    print(f"Cash visé          : {100 - total:.2f} % NAV")

    conn.close()
    print("\n=== Migration terminée ===")
    print("Tu peux maintenant relancer le serveur ; le Reconciler verra les targets.")

if __name__ == "__main__":
    main()
