#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# [CLEANUP_SUPERSEDED_ORDERS_V1]
# Annule les 13 ordres pending_validation du cycle 13:02:42 (IDs #268-#280),
# remplaces par le cycle 13:15:16 (IDs #281-#293, post fix smoothing v2).
#
# Securite :
# - Mode DRY-RUN par defaut, --apply pour executer
# - Verifie qu il existe bien un doublon (ticker, side, quantity) plus recent
#   avec status pending_validation avant d annuler chaque vieil ordre
# - Status final : 'superseded' + rejection_reason explicite
# - Backup table orders (SELECT) en JSON avant modification

import os
import sys
import json
import sqlite3
import time

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
OLD_IDS = [268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279, 280]
NEW_STATUS = "cancelled"  # contrainte CHECK : pending|pending_validation|approved|filled|rejected|cancelled
REASON = "superseded_by_recent_cycle_2026-06-10_13:15"


def main():
    apply_mode = "--apply" in sys.argv
    print("Mode :", "APPLY" if apply_mode else "DRY-RUN (utilise --apply pour executer)")
    print()

    if not os.path.isfile(DB):
        print("ERR : DB introuvable :", DB)
        sys.exit(1)

    conn = sqlite3.connect(DB, timeout=10.0)
    conn.row_factory = sqlite3.Row

    # 1. Backup snapshot des 13 anciens
    print("=== 1. Snapshot des ordres a annuler ===")
    backup = []
    placeholders = ",".join("?" for _ in OLD_IDS)
    rows = conn.execute(f"""
        SELECT o.id, o.instrument_id, i.ticker, o.side, o.quantity,
               o.status, o.thesis_id, o.created_at, o.rejection_reason
        FROM orders o
        LEFT JOIN instruments i ON i.id = o.instrument_id
        WHERE o.id IN ({placeholders})
        ORDER BY o.id
    """, OLD_IDS).fetchall()
    for r in rows:
        d = dict(r)
        backup.append(d)
        print("  ", d)
    print("Total a annuler :", len(rows))
    print()

    # 2. Verifie pour chaque vieil ordre qu un doublon recent existe
    print("=== 2. Verification doublons recents ===")
    safe_to_cancel = []
    for old in backup:
        chk = conn.execute("""
            SELECT id, status, created_at
            FROM orders
            WHERE instrument_id = ?
              AND side = ?
              AND quantity = ?
              AND id != ?
              AND status = 'pending_validation'
              AND created_at > ?
            ORDER BY id DESC LIMIT 1
        """, (old["instrument_id"], old["side"], old["quantity"],
              old["id"], old["created_at"])).fetchone()
        if chk:
            print(f"  OK {old['ticker']} #{old['id']} -> recent #{chk['id']}")
            safe_to_cancel.append(old["id"])
        else:
            print(f"  KO {old['ticker']} #{old['id']} : PAS de doublon recent, on garde")

    print()
    print("Safe to cancel :", safe_to_cancel)
    print("Count :", len(safe_to_cancel))
    print()

    if len(safe_to_cancel) != 13:
        print("WARN : on attendait 13 cancellations, on a", len(safe_to_cancel))
        if apply_mode:
            ans = input("Continuer ? (yes/NO) : ").strip().lower()
            if ans != "yes":
                print("Abort")
                sys.exit(2)

    # 3. Sauvegarde JSON
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak_file = os.path.join(
        r"C:\Users\RichardGUELIN\Prod\ThesiumDesk",
        f"orders_cancel_backup_{ts}.json"
    )
    with open(bak_file, "w", encoding="utf-8") as f:
        json.dump(backup, f, indent=2)
    print("Backup JSON :", bak_file)
    print()

    # 4. UPDATE
    if not apply_mode:
        print("DRY-RUN : aucune modification appliquee")
        print("Relance avec : py -3.13 .\\nextones-cleanup-superseded-orders-v1.py --apply")
        conn.close()
        return

    print("=== 4. APPLY UPDATE ===")
    cur = conn.cursor()
    placeholders2 = ",".join("?" for _ in safe_to_cancel)
    cur.execute(f"""
        UPDATE orders
        SET status = ?, rejection_reason = ?, validated_at = ?, validated_by = ?
        WHERE id IN ({placeholders2})
    """, [NEW_STATUS, REASON, time.strftime("%Y-%m-%d %H:%M:%S"),
          "cleanup_script_v1"] + safe_to_cancel)
    n = cur.rowcount
    conn.commit()
    print("Rows updated :", n)

    # 5. Verification post-UPDATE
    print()
    print("=== 5. Post-UPDATE check ===")
    remaining = conn.execute("""
        SELECT COUNT(*) as n FROM orders
        WHERE status = 'pending_validation'
    """).fetchone()
    print("Orders pending_validation restants :", remaining["n"])

    conn.close()
    print()
    print("=== DONE [CLEANUP_SUPERSEDED_ORDERS_V1] ===")


if __name__ == "__main__":
    main()
