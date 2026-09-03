#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Diag : ou est calcule le Total P&L affiche dans l UI ?
# Recherche :
# - endpoints API qui retournent total_pnl / portfolio_value / dashboard
# - patches pnl deja deployes (api-server-pnl-patch)
# - schema portfolio / portfolio_history / cash
# - valeur actuelle des comptes

import os
import re
import sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")

PATTERNS = [
    r"total_pnl",
    r"portfolio_value",
    r"daily_pnl",
    r"cash_available",
    r"compute_pnl",
    r"def\s+get_portfolio_summary",
    r"def\s+get_dashboard",
    r"/api/portfolio",
    r"/api/dashboard",
    r"/api/pnl",
    r"initial_capital",
    r"starting_capital",
    r"K_INITIAL",
    r"INITIAL_NAV",
]

def main():
    # 1) Localiser dans le code
    print("=== 1. Patterns dans le code source ===")
    hits_by_file = {}
    for fname in os.listdir(ROOT):
        if not fname.endswith(".py"):
            continue
        if fname.startswith("nextones-diag") or "_backup" in fname:
            continue
        path = os.path.join(ROOT, fname)
        try:
            with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            continue
        local = []
        for i, ln in enumerate(lines, 1):
            for pat in PATTERNS:
                if re.search(pat, ln, re.IGNORECASE):
                    local.append((i, pat, ln.rstrip()[:160]))
                    break
        if local:
            hits_by_file[fname] = local

    # Priorite : api_server.py, api_server_with_static.py, models.py
    priority = ["api_server.py", "api_server_with_static.py", "models.py",
                "nextones-api-server-pnl-patch.py"]
    for f in priority:
        if f in hits_by_file:
            print(f"\n--- {f} ({len(hits_by_file[f])} hits) ---")
            for i, pat, ln in hits_by_file[f][:40]:
                print(f"  L{i:5d} [{pat[:25]}] : {ln}")

    print("\n--- Autres fichiers (top 5) ---")
    others = sorted(
        [(f, h) for f, h in hits_by_file.items() if f not in priority],
        key=lambda x: -len(x[1])
    )
    for f, h in others[:5]:
        print(f"  {f} : {len(h)} hits")

    # 2) Tables DB pertinentes
    print()
    print("=== 2. Schemas DB pertinents ===")
    if not os.path.isfile(DB):
        print("DB introuvable")
        return
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    for tbl in ["portfolio_history", "portfolio_state", "positions",
                "cash", "accounts", "fills", "orders"]:
        try:
            cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            if cols:
                print(f"\n[{tbl}] :")
                for c in cols:
                    print(f"  {c['name']} {c['type']}")
            else:
                print(f"\n[{tbl}] : N/A")
        except Exception as e:
            print(f"\n[{tbl}] err :", e)

    # 3) Dernieres valeurs portfolio_history
    print()
    print("=== 3. Derniere(s) ligne(s) portfolio_history ===")
    try:
        rows = conn.execute("""
            SELECT * FROM portfolio_history
            ORDER BY id DESC LIMIT 3
        """).fetchall()
        for r in rows:
            d = dict(r)
            print("  ", d)
    except Exception as e:
        print("  ERR :", e)

    # 4) Etat positions actuelles + cash
    print()
    print("=== 4. Positions actuelles (sum valeur) ===")
    try:
        for tbl in ["positions", "portfolio_positions", "broker_positions"]:
            cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
            if cols:
                print(f"\n[{tbl}] :")
                rows = conn.execute(f"SELECT * FROM {tbl} LIMIT 50").fetchall()
                for r in rows:
                    print("  ", dict(r))
                break
    except Exception as e:
        print("  ERR positions :", e)

    print()
    print("=== 5. Recherche initial_capital / starting / 1000000 dans DB ===")
    try:
        for tbl in ["config", "system_config", "settings", "params",
                    "portfolio_config"]:
            try:
                cols = conn.execute(f"PRAGMA table_info({tbl})").fetchall()
                if cols:
                    print(f"\n[{tbl}] :")
                    for r in conn.execute(f"SELECT * FROM {tbl} LIMIT 30"):
                        print("  ", dict(r))
            except Exception:
                pass
    except Exception as e:
        print("  ERR config :", e)

    conn.close()
    print()
    print("=== DONE diag P&L ===")


if __name__ == "__main__":
    main()
