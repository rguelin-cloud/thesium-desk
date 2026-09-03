"""
[DIAG_BLOCK_263_ZEC]
Diagnostic ciblé : pourquoi l'ordre #263 (SELL 55 ZEC) est-il BLOCK
et pourquoi le motif affiche 'broker_mapping_ok' au lieu du vrai motif ?

Objectifs :
 1. Localiser la table de log pretrade (risk_pretrade_log / pretrade_verdicts / ...)
 2. Dumper le verdict complet de l'ordre #263 (tous les champs)
 3. Vérifier l'état de la position ZEC (qty détenue vs qty proposée 55)
 4. Lister les tables 'risk' / 'pretrade' / 'verdict' disponibles
 5. Confirmer l'hypothèse "qty SELL > qty détenue"
"""
from __future__ import annotations
import os
import sys
import sqlite3
import json

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"


def main() -> int:
    if not os.path.exists(DB_PATH):
        print(f"[ERR] DB introuvable : {DB_PATH}")
        return 1
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print("=" * 70)
    print("DIAG BLOCK #263 ZEC - 10/06/2026")
    print("=" * 70)

    # ------------------------------------------------------------------
    # 1. Lister les tables candidates risk/pretrade/verdict
    # ------------------------------------------------------------------
    print("\n[1] Tables candidates (risk / pretrade / verdict / broker)")
    print("-" * 70)
    tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE '%risk%' OR name LIKE '%pretrade%' OR name LIKE '%verdict%' "
        "OR name LIKE '%broker_shadow%' OR name LIKE '%orders%' OR name LIKE '%position%') "
        "ORDER BY name"
    ).fetchall()
    for t in tables:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {t['name']}").fetchone()[0]
        except Exception as e:
            n = f"ERR: {e}"
        print(f"  - {t['name']:40s} rows={n}")

    # ------------------------------------------------------------------
    # 2. Chercher le verdict de l'ordre #263 dans toutes les tables candidates
    # ------------------------------------------------------------------
    print("\n[2] Recherche order_id=263 (ou ticker ZEC, SELL, qty=55)")
    print("-" * 70)
    candidate_tables = [t["name"] for t in tables]
    for table in candidate_tables:
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        except Exception:
            continue
        # tente différents champs id
        id_cols = [c for c in cols if c in ("order_id", "id", "proposal_id")]
        ticker_cols = [c for c in cols if c in ("ticker", "symbol")]
        if not id_cols and not ticker_cols:
            continue

        # 2a. par order_id = 263
        for id_col in id_cols:
            try:
                rows = cur.execute(
                    f"SELECT * FROM {table} WHERE {id_col}=? LIMIT 5", (263,)
                ).fetchall()
                if rows:
                    print(f"\n  *** {table}.{id_col}=263 -> {len(rows)} hit(s)")
                    for r in rows:
                        d = dict(r)
                        for k, v in d.items():
                            s = str(v)
                            if len(s) > 200:
                                s = s[:200] + "..."
                            print(f"      {k:30s} = {s}")
                        print("      ---")
            except Exception as e:
                pass

        # 2b. par ticker = ZEC, side SELL, dernier
        for tcol in ticker_cols:
            try:
                # ordre par created_at desc si dispo, sinon par rowid
                order_clause = "ORDER BY rowid DESC"
                for c in ("created_at", "ts", "timestamp", "checked_at"):
                    if c in cols:
                        order_clause = f"ORDER BY {c} DESC"
                        break
                rows = cur.execute(
                    f"SELECT * FROM {table} WHERE {tcol}='ZEC' {order_clause} LIMIT 3"
                ).fetchall()
                if rows:
                    print(f"\n  *** {table} ZEC (3 plus recents)")
                    for r in rows:
                        d = dict(r)
                        for k, v in d.items():
                            s = str(v)
                            if len(s) > 200:
                                s = s[:200] + "..."
                            print(f"      {k:30s} = {s}")
                        print("      ---")
            except Exception as e:
                pass

    # ------------------------------------------------------------------
    # 3. Position ZEC actuelle
    # ------------------------------------------------------------------
    print("\n[3] Position actuelle ZEC")
    print("-" * 70)
    for table in ("positions", "portfolio_positions", "portfolio_state", "current_positions"):
        if not any(t["name"] == table for t in tables):
            continue
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
            ticker_col = "ticker" if "ticker" in cols else ("symbol" if "symbol" in cols else None)
            if ticker_col:
                rows = cur.execute(
                    f"SELECT * FROM {table} WHERE {ticker_col}='ZEC'"
                ).fetchall()
                for r in rows:
                    print(f"  [{table}] {dict(r)}")
        except Exception as e:
            print(f"  [{table}] ERR: {e}")

    conn.close()
    print("\n" + "=" * 70)
    print("FIN DIAG")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
