# -*- coding: utf-8 -*-
"""
[ADD_SOL_INSTRUMENT_V1]
Ajout manuel de SOL dans la table instruments pour debloquer
le PortfolioConstructionAgent (SOL est deja dans target_universe id=11).

Usage:
    py -3.13 nextones-add-sol-instrument.py
"""
import sqlite3
import sys

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"

TICKER      = "SOL"
NAME        = "Solana"
SECTOR      = "smart_chain"
ASSET_CLASS = "crypto"


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        # 1) Etat AVANT
        row = conn.execute(
            "SELECT id, ticker, name, sector, asset_class FROM instruments WHERE ticker = ?;",
            (TICKER,),
        ).fetchone()
        print(f"[AVANT] instruments SOL = {row}")

        if row is not None:
            print(f"[SKIP] SOL deja present dans instruments (id={row[0]}). Rien a faire.")
        else:
            conn.execute(
                """INSERT INTO instruments (ticker, name, sector, asset_class)
                   VALUES (?, ?, ?, ?);""",
                (TICKER, NAME, SECTOR, ASSET_CLASS),
            )
            conn.commit()
            print("[INSERT] SOL ajoute dans instruments.")

        # 2) Etat APRES (instruments + target_universe)
        i = conn.execute(
            "SELECT id, ticker, name, sector, asset_class FROM instruments WHERE ticker = ?;",
            (TICKER,),
        ).fetchone()
        t = conn.execute(
            "SELECT id, ticker, asset_class, sector, is_active, max_weight_pct "
            "FROM target_universe WHERE ticker = ?;",
            (TICKER,),
        ).fetchone()

        print()
        print("=" * 60)
        print(f"INSTRUMENT      : {i}")
        print(f"TARGET_UNIVERSE : {t}")
        print("=" * 60)

        if i is None:
            print("[FAIL] SOL toujours absent d'instruments.")
            return 1
        if t is None:
            print("[WARN] SOL absent de target_universe (attendu id=11).")
            return 0

        print("[OK] SOL est aligne entre instruments et target_universe.")
        print("     Prochain cycle PortfolioConstructionAgent pourra creer une target SOL.")
        return 0

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
