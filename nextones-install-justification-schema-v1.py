"""
Patch 1/6 - Schema justification BUY/SELL
==========================================

Ajoute 3 colonnes a la table orders :
  - justification         TEXT    (note structuree, ~200 chars, calculee sync)
  - justification_memo    TEXT    (memo IA long, calcule a la demande via LLM)
  - justification_generated_at TEXT (timestamp ISO du memo IA, NULL au depart)

Idempotent : verifie l'existence de chaque colonne avant ALTER.
Aucune donnee touchee (les 488 ordres existants restent NULL sur ces 3 champs).
"""
import os
import sqlite3
import sys
import time

DB = os.environ.get("THESIUM_DB", r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
TS = time.strftime("%Y%m%d_%H%M%S")


NEW_COLS = [
    ("justification", "TEXT"),
    ("justification_memo", "TEXT"),
    ("justification_generated_at", "TEXT"),
]


def main():
    if not os.path.exists(DB):
        print("[ERR] DB not found:", DB)
        return 2

    conn = sqlite3.connect(DB, timeout=15.0)
    conn.execute("PRAGMA busy_timeout=15000")
    cur = conn.cursor()

    # Snapshot schema before
    cur.execute("PRAGMA table_info(orders)")
    existing = {r[1] for r in cur.fetchall()}
    print("[INFO] existing columns count:", len(existing))
    print("[INFO] justification present :", "justification" in existing)
    print("[INFO] justification_memo    :", "justification_memo" in existing)
    print("[INFO] justification_generated_at:", "justification_generated_at" in existing)

    added = []
    skipped = []
    for col, typ in NEW_COLS:
        if col in existing:
            skipped.append(col)
            continue
        try:
            cur.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
            added.append(col)
            print(f"[OK] ADD COLUMN orders.{col} {typ}")
        except sqlite3.OperationalError as e:
            print(f"[ERR] ALTER failed for {col}: {e}")
            conn.rollback()
            conn.close()
            return 3

    conn.commit()

    # Sanity re-read
    cur.execute("PRAGMA table_info(orders)")
    after = {r[1] for r in cur.fetchall()}
    for col, _ in NEW_COLS:
        if col not in after:
            print(f"[ERR] post-alter check: {col} still missing")
            conn.close()
            return 4

    # Compte des lignes (verif aucune perte)
    cur.execute("SELECT COUNT(*) FROM orders")
    n = cur.fetchone()[0]
    print(f"[OK] orders row count post-migration: {n}")

    conn.close()

    print()
    print(f"[SUMMARY] added={added} skipped={skipped} ts={TS}")
    print("[NEXT] Patch 2 : justification_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
