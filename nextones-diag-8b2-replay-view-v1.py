# -*- coding: utf-8 -*-
# nextones-diag-8b2-replay-view-v1.py
# Reproduit la sequence open_replay_conn_at en mode trace : chaque CREATE
# est execute individuellement avec capture d'exception, pour identifier
# pourquoi les state_tables et static_tables (sauf instruments) ne sont
# pas creees.

import os
import sqlite3
import traceback

DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
DAY_T = "2026-06-10"


def main():
    print("=" * 72)
    print("DIAG 8B.2 - trace open_replay_conn_at")
    print("=" * 72)

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    print(f"\n1. ATTACH prod : {DB_PATH}")
    cur.execute("ATTACH DATABASE ? AS prod", (DB_PATH,))
    print("   OK")

    # Liste les tables prod
    cur.execute("SELECT name FROM prod.sqlite_master WHERE type='table'")
    rows = cur.fetchall()
    prod_tables = set(r[0] for r in rows)
    print(f"\n2. prod_tables : {len(prod_tables)} tables")

    target_names = [
        "prices", "instruments", "macro_history",
        "target_universe", "target_construction_config", "crypto_context", "theses",
        "convergence_snapshots", "portfolio_targets", "portfolio_targets_history",
        "portfolio_positions", "portfolio_history", "portfolio_state", "regime_log",
        "market_regime_log", "agents_outputs", "agents_config", "universe_candidates",
    ]
    print("\n   Presence en prod :")
    for n in target_names:
        flag = "OK  " if n in prod_tables else "MISS"
        print(f"     [{flag}] {n}")

    # ----- prices -----
    print("\n3. CREATE prices (filtre <= day_t)")
    try:
        cur.execute(
            "CREATE TABLE main.prices AS SELECT * FROM prod.prices WHERE date <= ?",
            (DAY_T,),
        )
        cur.execute("CREATE INDEX idx_prices_instr_date ON prices(instrument_id, date)")
        n = cur.execute("SELECT COUNT(*) FROM main.prices").fetchone()[0]
        print(f"   OK ({n} rows)")
    except Exception as e:
        print(f"   FAIL: {e}")
        traceback.print_exc()

    # ----- macro_history -----
    print("\n4. CREATE macro_history (filtre <= day_t)")
    try:
        cur.execute(
            "CREATE TABLE main.macro_history AS SELECT * FROM prod.macro_history WHERE date <= ?",
            (DAY_T,),
        )
        cur.execute("CREATE INDEX idx_macro_date ON macro_history(series_code, date)")
        n = cur.execute("SELECT COUNT(*) FROM main.macro_history").fetchone()[0]
        print(f"   OK ({n} rows)")
    except Exception as e:
        print(f"   FAIL: {e}")

    # ----- static tables copie complete -----
    static_tables = [
        "instruments", "target_universe", "target_construction_config",
        "crypto_context", "theses", "agents_config",
    ]
    print(f"\n5. STATIC tables (copie complete) : {static_tables}")
    for tname in static_tables:
        if tname not in prod_tables:
            print(f"   [{tname}] SKIP (absent en prod)")
            continue
        try:
            cur.execute(f"CREATE TABLE main.{tname} AS SELECT * FROM prod.{tname}")
            n = cur.execute(f"SELECT COUNT(*) FROM main.{tname}").fetchone()[0]
            print(f"   [{tname}] OK ({n} rows)")
        except Exception as e:
            print(f"   [{tname}] FAIL: {e}")

    # ----- state tables : schema seul (WHERE 0) -----
    state_tables = [
        "convergence_snapshots", "portfolio_targets", "portfolio_targets_history",
        "portfolio_positions", "portfolio_history", "portfolio_state",
        "regime_log", "market_regime_log", "agents_outputs", "universe_candidates",
    ]
    print(f"\n6. STATE tables (schema seul WHERE 0) : {state_tables}")
    for tname in state_tables:
        if tname not in prod_tables:
            print(f"   [{tname}] SKIP (absent en prod)")
            continue
        try:
            cur.execute(f"CREATE TABLE main.{tname} AS SELECT * FROM prod.{tname} WHERE 0")
            print(f"   [{tname}] OK (schema only)")
        except Exception as e:
            print(f"   [{tname}] FAIL: {e}")

    # ----- DETACH -----
    print("\n7. DETACH prod")
    cur.execute("DETACH DATABASE prod")
    print("   OK")

    # ----- final state -----
    print("\n8. FINAL : tables dans :memory:")
    rows = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for r in rows:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM main.{r[0]}").fetchone()[0]
            print(f"   {r[0]:<32s} {n}")
        except Exception as e:
            print(f"   {r[0]:<32s} ERR {e}")

    conn.close()


if __name__ == "__main__":
    main()
