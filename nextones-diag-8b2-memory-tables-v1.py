# -*- coding: utf-8 -*-
# nextones-diag-8b2-memory-tables-v1.py
# Diag : liste TOUTES les tables presentes dans la conn :memory: apres
# open_replay_conn_at, et compare a la liste attendue par les agents prod.

import os
import sys

os.environ["NEXTONES_REPLAY_MODE"] = "1"

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
WORKSPACE = os.path.dirname(os.path.abspath(__file__))

if PROD_DIR not in sys.path:
    sys.path.insert(0, PROD_DIR)
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

from replay_db_view import open_replay_conn_at, get_snapshot_stats

DAY_T = "2026-06-10"

# Tables que les agents prod attendent (extrait des erreurs + signatures)
EXPECTED = [
    # lues
    "prices", "macro_history", "instruments", "agents_config", "universe_candidates",
    "theses",                        # convergence_engine
    "agents_outputs",                # peut-etre lu par PCA
    "regime_log",                    # macro_affinity
    "market_regime_log",             # log_market_regime
    "portfolio_state",               # PCA + cash check
    "portfolio_positions",           # PCA
    # ecrites
    "convergence_snapshots",
    "portfolio_targets",
    "portfolio_targets_history",
]


def main():
    print("=" * 72)
    print(f"DIAG 8B.2 - tables dans la conn :memory: au {DAY_T}")
    print("=" * 72)

    conn = open_replay_conn_at(DAY_T, DB_PATH)

    stats = get_snapshot_stats(conn)
    print(f"\nStats snapshot :")
    for k, v in sorted(stats.items()):
        print(f"  {k:<28s} = {v}")

    rows = conn.execute(
        "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
    ).fetchall()
    names = [r[0] for r in rows]
    print(f"\n{len(names)} objets dans :memory: :")
    for n, t in rows:
        print(f"  [{t}] {n}")

    print(f"\nCheck tables attendues :")
    missing = []
    for tname in EXPECTED:
        present = tname in names
        if not present:
            missing.append(tname)
        cnt = "-"
        if present:
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {tname}").fetchone()[0]
            except Exception as e:
                cnt = f"ERR {e}"
        flag = "OK  " if present else "MISS"
        print(f"  [{flag}] {tname:<32s} count={cnt}")

    print(f"\nManquantes : {len(missing)}")
    for m in missing:
        print(f"  - {m}")

    # Pour chaque table presente attendue, montrer son schema
    print(f"\nSchemas des tables critiques presentes :")
    for tname in ["portfolio_state", "portfolio_positions", "theses",
                  "convergence_snapshots", "portfolio_targets",
                  "portfolio_targets_history", "regime_log",
                  "market_regime_log", "agents_outputs"]:
        if tname in names:
            ddl = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name=?", (tname,)
            ).fetchone()
            print(f"\n--- {tname} ---")
            print((ddl[0] if ddl else "(no ddl)")[:600])

    conn.close()


if __name__ == "__main__":
    main()
