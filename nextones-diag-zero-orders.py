# Diag complet : pourquoi 0 ordre genere depuis 2 cycles ?
# Verifie :
#   1. Dernier cycle execute (date, statut)
#   2. Propositions generees par les agents
#   3. Targets calcules par PortfolioConstructionAgent
#   4. Reconciler : ecart targets vs positions actuelles
#   5. Ordres en base
#   6. Risk Engine : aucun BLOCK qui filtrerait tout

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

def show(title):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def query(sql, params=()):
    try:
        return cur.execute(sql, params).fetchall()
    except Exception as e:
        return [{"_err": str(e)}]

def print_rows(rows, cols=None):
    if not rows:
        print("  (vide)")
        return
    if isinstance(rows[0], sqlite3.Row):
        keys = cols or rows[0].keys()
        print("  " + " | ".join(str(k)[:18] for k in keys))
        for r in rows[:30]:
            print("  " + " | ".join(str(r[k] if k in r.keys() else '?')[:30] for k in keys))
    else:
        for r in rows[:30]:
            print(f"  {r}")

show("[1] Tables existantes")
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("  " + ", ".join(tables))

show("[2] Dernier RUN CYCLE (decision_cycles ou cycles)")
for t in ["decision_cycles", "cycles", "run_cycles", "decision_cycle_runs"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 5")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[3] Propositions (proposals) - 10 dernieres")
for t in ["proposals", "agent_proposals", "decision_proposals"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[4] Targets - dernier snapshot")
for t in ["construction_snapshots", "portfolio_targets", "targets"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[5] Reconciler log - 10 dernieres entrees")
for t in ["cycle_reconciliation_log", "reconciliation_log", "reconciler_log"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[6] Orders - 10 derniers")
for t in ["orders", "execution_orders", "trade_orders"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[7] Positions actuelles")
for t in ["positions", "portfolio_positions", "holdings"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 20")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[8] Risk pre-trade : 10 dernieres verifications")
for t in ["risk_pretrade_log", "risk_checks", "pretrade_checks"]:
    if t in tables:
        rows = query(f"SELECT * FROM {t} ORDER BY rowid DESC LIMIT 10")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

show("[9] Theses generees aujourd'hui ?")
for t in ["theses", "agent_theses"]:
    if t in tables:
        rows = query(f"SELECT COUNT(*) as n, MAX(created_at) as last FROM {t}")
        print(f"  Table {t} : {dict(rows[0])}")
        # Aujourd'hui
        today = datetime.now().strftime("%Y-%m-%d")
        rows = query(f"SELECT COUNT(*) as n FROM {t} WHERE created_at LIKE ?", (f"{today}%",))
        print(f"  Aujourd'hui ({today}) : {dict(rows[0])}")

show("[10] Comptage proposals par jour (7 jours)")
for t in ["proposals", "agent_proposals"]:
    if t in tables:
        rows = query(f"SELECT substr(created_at,1,10) as d, COUNT(*) as n FROM {t} GROUP BY d ORDER BY d DESC LIMIT 7")
        if rows and not (isinstance(rows[0], dict) and "_err" in rows[0]):
            print(f"  Table {t} :")
            print_rows(rows)
            break

con.close()
print("\n[DONE]")
