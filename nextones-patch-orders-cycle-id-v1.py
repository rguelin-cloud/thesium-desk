# -*- coding: utf-8 -*-
# [PATCH_ORDERS_CYCLE_ID_V1]
# Ajoute la colonne `cycle_id` a la table orders + index + backfill best-effort
# par jointure created_at <-> regime_log.cycle_id (cycle le plus proche dans le temps).
# Idempotent (skip si colonne deja presente). ASCII pur, Windows-safe.

import io
import os
import sys
import sqlite3
import shutil
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")


def _has_column(cur, table, col):
    rows = cur.execute("PRAGMA table_info({0})".format(table)).fetchall()
    return any(r[1] == col for r in rows)


def main():
    if not os.path.exists(DB):
        print("MISSING DB:", DB)
        sys.exit(2)

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = DB + ".bak." + ts
    shutil.copy2(DB, bak)
    print("Backup created:", bak)

    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()

    # 1) Ajout colonne si absente
    if _has_column(cur, "orders", "cycle_id"):
        print("[SKIP] orders.cycle_id already exists")
    else:
        cur.execute("ALTER TABLE orders ADD COLUMN cycle_id TEXT")
        print("[OK] ADDED orders.cycle_id (TEXT)")

    # 2) Index
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_cycle_id ON orders(cycle_id)")
    print("[OK] INDEX idx_orders_cycle_id")

    # 3) Backfill best-effort : pour chaque order sans cycle_id, on cherche
    # le cycle_id du regime_log dont created_at est le plus proche.
    # Strategie : sous-requete SQL pure (rapide, robuste).
    n_before = cur.execute(
        "SELECT COUNT(*) FROM orders WHERE cycle_id IS NULL OR cycle_id = ''"
    ).fetchone()[0]
    print("[INFO] orders sans cycle_id avant backfill:", n_before)

    if n_before > 0:
        # On joint par proximite temporelle : cycle dont created_at <= order.created_at
        # le plus grand (i.e. le cycle qui a engendre l'ordre). Fallback : cycle global le plus proche.
        cur.execute("""
            UPDATE orders
            SET cycle_id = (
                SELECT r.cycle_id FROM regime_log r
                WHERE r.created_at <= orders.created_at
                ORDER BY r.created_at DESC LIMIT 1
            )
            WHERE cycle_id IS NULL OR cycle_id = ''
        """)
        # Pour les orders anciens (anterieurs au 1er regime_log), on prend le 1er cycle
        cur.execute("""
            UPDATE orders
            SET cycle_id = (
                SELECT r.cycle_id FROM regime_log r
                ORDER BY r.created_at ASC LIMIT 1
            )
            WHERE cycle_id IS NULL OR cycle_id = ''
        """)
        con.commit()

    n_after = cur.execute(
        "SELECT COUNT(*) FROM orders WHERE cycle_id IS NULL OR cycle_id = ''"
    ).fetchone()[0]
    print("[INFO] orders sans cycle_id apres backfill:", n_after)

    # 4) Sample des 10 derniers orders avec cycle_id
    print("")
    print("--- 10 derniers orders post-backfill ---")
    for r in cur.execute(
        "SELECT id, instrument_id, side, status, cycle_id, created_at "
        "FROM orders ORDER BY id DESC LIMIT 10"
    ).fetchall():
        print("  id={0} inst={1} side={2} status={3} cycle_id={4} created={5}".format(*r))

    # 5) Distribution par cycle (top 10)
    print("")
    print("--- Distribution orders par cycle (top 10) ---")
    for r in cur.execute(
        "SELECT cycle_id, COUNT(*) AS n FROM orders "
        "GROUP BY cycle_id ORDER BY n DESC LIMIT 10"
    ).fetchall():
        print("  cycle_id={0} n={1}".format(r[0], r[1]))

    con.close()
    print("")
    print("[DONE] Patch orders.cycle_id V1 applied.")


if __name__ == "__main__":
    main()
