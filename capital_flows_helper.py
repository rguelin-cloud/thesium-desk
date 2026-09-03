# -*- coding: utf-8 -*-
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
DB_PATH = r"C:\\Users\\RichardGUELIN\\Prod\\ThesiumDesk\\thesium.db"


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
