# -*- coding: utf-8 -*-
# [INSTALL_CAPITAL_FLOWS_V1]
# Cree la table capital_flows + ajoute les colonnes unrealized_pnl /
# unrealized_pnl_pct a portfolio_state (idempotent).
# Insere aussi un module helper capital_flows_helper.py si absent.

import os
import sqlite3
import sys
from pathlib import Path

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")

def column_exists(conn, table, col):
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())

def table_exists(conn, name):
    cur = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

print("=" * 60)
print("[INSTALL_CAPITAL_FLOWS_V1]")
print("=" * 60)

conn = sqlite3.connect(DB, timeout=10)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")

# 1. Table capital_flows
if table_exists(conn, "capital_flows"):
    print("[SKIP] table capital_flows existe deja")
else:
    conn.execute("""
        CREATE TABLE capital_flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            side TEXT NOT NULL CHECK(side IN ('deposit','withdrawal')),
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX idx_capital_flows_date ON capital_flows(date)")
    print("[OK] table capital_flows creee")

# 2. Colonnes unrealized_pnl / unrealized_pnl_pct dans portfolio_state
for col, ddl in [
    ("unrealized_pnl", "ALTER TABLE portfolio_state ADD COLUMN unrealized_pnl REAL DEFAULT 0"),
    ("unrealized_pnl_pct", "ALTER TABLE portfolio_state ADD COLUMN unrealized_pnl_pct REAL DEFAULT 0"),
]:
    if column_exists(conn, "portfolio_state", col):
        print(f"[SKIP] colonne portfolio_state.{col} existe deja")
    else:
        conn.execute(ddl)
        print(f"[OK] colonne portfolio_state.{col} ajoutee")

# 3. Initialise unrealized_pnl avec la valeur actuelle de total_pnl
#    (avant le patch, total_pnl contient deja l'unrealized car fix_crypto a ecrase)
cur = conn.execute("SELECT total_pnl, total_pnl_pct FROM portfolio_state WHERE id=1")
row = cur.fetchone()
if row:
    tpnl, tppct = row
    # Si unrealized_pnl est encore 0 (premier run), copie depuis total_pnl
    cur2 = conn.execute("SELECT unrealized_pnl FROM portfolio_state WHERE id=1")
    cur_unreal = cur2.fetchone()[0]
    if cur_unreal == 0 and tpnl != 0:
        conn.execute(
            "UPDATE portfolio_state SET unrealized_pnl=?, unrealized_pnl_pct=? WHERE id=1",
            (tpnl, tppct),
        )
        print(f"[OK] unrealized_pnl initialise a {tpnl} ({tppct}%)")

conn.commit()

# 4. Helper module
helper_path = BASE / "capital_flows_helper.py"
HELPER_CODE = '''# -*- coding: utf-8 -*-
# [CAPITAL_FLOWS_HELPER_V1]
"""
Helper pour calculer le Total Return = NAV - INITIAL_CAPITAL - SUM(capital_flows)
Convention :
  - deposit : amount > 0 (augmente le capital injecte)
  - withdrawal : amount > 0 stocke avec side='withdrawal' (=> soustrait)

Net flows = SUM(amount WHERE side='deposit') - SUM(amount WHERE side='withdrawal')
Total Return = NAV - INITIAL_CAPITAL - net_flows
"""
import sqlite3

INITIAL_CAPITAL = 1_000_000.0
DB_PATH = r"C:\\\\Users\\\\RichardGUELIN\\\\Prod\\\\ThesiumDesk\\\\thesium.db"


def get_net_capital_flows(conn=None):
    """Retourne le flux net deposit-withdrawal (positif = net deposit)."""
    own = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        own = True
    try:
        cur = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN side='deposit' THEN amount ELSE 0 END), 0) -
                COALESCE(SUM(CASE WHEN side='withdrawal' THEN amount ELSE 0 END), 0)
            FROM capital_flows
        """)
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0
    finally:
        if own:
            conn.close()


def compute_total_return(nav, conn=None):
    """Total Return = NAV - INITIAL_CAPITAL - net_capital_flows.
    Retourne (total_return_abs, total_return_pct) en base INITIAL_CAPITAL + net_flows."""
    net = get_net_capital_flows(conn)
    base = INITIAL_CAPITAL + net
    total_return = nav - base
    pct = (total_return / base * 100.0) if base > 0 else 0.0
    return total_return, pct
'''

if helper_path.exists():
    print(f"[SKIP] {helper_path.name} existe deja (pas d'overwrite)")
else:
    helper_path.write_bytes(HELPER_CODE.encode("utf-8"))
    print(f"[OK] {helper_path.name} cree ({helper_path.stat().st_size} bytes)")

# 5. Diag final
print()
print("=" * 60)
print("ETAT FINAL")
print("=" * 60)
cur = conn.execute("PRAGMA table_info(portfolio_state)")
print("portfolio_state columns:")
for r in cur.fetchall():
    print(f"  - {r[1]} ({r[2]})")

print()
print("capital_flows schema:")
cur = conn.execute("PRAGMA table_info(capital_flows)")
for r in cur.fetchall():
    print(f"  - {r[1]} ({r[2]})")

cur = conn.execute("SELECT COUNT(*) FROM capital_flows")
print(f"capital_flows rows : {cur.fetchone()[0]}")

cur = conn.execute("SELECT total_pnl, unrealized_pnl FROM portfolio_state WHERE id=1")
r = cur.fetchone()
print(f"portfolio_state : total_pnl={r[0]} unrealized_pnl={r[1]}")

conn.close()
print()
print("DONE [INSTALL_CAPITAL_FLOWS_V1]")
