# -*- coding: utf-8 -*-
"""
Diag: pourquoi 20 theses + 2 memos mais 0 ordres ce matin ?
Verifie:
 A) cycles_daily : que dit la table sur le cycle 28/05 ?
 B) construction targets : que veut le PCA aujourd hui ?
 C) gap entre positions actuelles et targets : est-on deja a l equilibre ?
 D) cycle_reconciliation_log : trace des transitions
 E) double execution : 2 memos -> 2 cycles ?
"""
import os, sqlite3, json
from datetime import datetime

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

def head(t): print("\n" + "="*70); print(t); print("="*70)

today = "2026-05-28"

# A) cycles_daily
head("A) cycles_daily")
info = c.execute("PRAGMA table_info(cycles_daily)").fetchall()
cols = [r[1] for r in info]
print(f"  Cols: {cols}")
ts_col = next((cc for cc in ['date','run_date','created_at','ts'] if cc in cols), None)
rows = c.execute(f"SELECT * FROM cycles_daily ORDER BY rowid DESC LIMIT 5").fetchall()
for r in rows:
    print(f"  {dict(r)}")

# B) construction targets recents
head("B) Tables liees aux targets / construction")
ts = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
target_tables = [t['name'] for t in ts if 'target' in t['name'].lower() or 'construction' in t['name'].lower()]
print(f"  Tables candidates: {target_tables}")
for tn in target_tables:
    try:
        info = c.execute(f"PRAGMA table_info({tn})").fetchall()
        cols = [r[1] for r in info]
        n = c.execute(f"SELECT COUNT(*) FROM {tn}").fetchone()[0]
        print(f"\n  --- {tn} (rows={n}) cols={cols}")
        last = c.execute(f"SELECT * FROM {tn} ORDER BY rowid DESC LIMIT 5").fetchall()
        for r in last:
            print(f"    {dict(r)}")
    except Exception as e:
        print(f"  ERREUR {tn}: {e}")

# C) Positions actuelles vs target
head("C) Positions actuelles (portfolio_positions)")
try:
    rows = c.execute("""
      SELECT pp.instrument_id, i.ticker, pp.quantity, pp.avg_cost, pp.current_price, pp.weight_pct
      FROM portfolio_positions pp JOIN instruments i ON i.id=pp.instrument_id
      ORDER BY pp.weight_pct DESC
    """).fetchall()
    total_w = 0
    for r in rows:
        print(f"  {r['ticker']:<6} qty={r['quantity']:<10} avg={r['avg_cost']:<10} cur={r['current_price']:<10} w={r['weight_pct']:.2f}%")
        total_w += r['weight_pct'] or 0
    print(f"  TOTAL weight = {total_w:.2f}%")
except Exception as e:
    print(f"  ERREUR: {e}")

# D) cycle_reconciliation_log
head("D) cycle_reconciliation_log (10 derniers)")
try:
    info = c.execute("PRAGMA table_info(cycle_reconciliation_log)").fetchall()
    cols = [r[1] for r in info]
    print(f"  Cols: {cols}")
    rows = c.execute(f"SELECT * FROM cycle_reconciliation_log ORDER BY rowid DESC LIMIT 10").fetchall()
    for r in rows:
        d = dict(r)
        # tronquer les longs textes
        short = {k: (str(v)[:80] + '...' if v and len(str(v))>80 else v) for k,v in d.items()}
        print(f"  {short}")
except Exception as e:
    print(f"  ERREUR: {e}")

# E) 2 IC memos -> les comparer
head("E) Les 2 IC memos du 28/05 sont-ils identiques ?")
try:
    rows = c.execute("SELECT id, date, title, length(full_markdown) AS L, proposed_changes FROM ic_memos WHERE date LIKE ? ORDER BY id ASC", (f"{today}%",)).fetchall()
    for r in rows:
        pc = (r['proposed_changes'] or '')[:200]
        print(f"  #{r['id']} {r['date']} L={r['L']} proposed_changes(extrait)={pc!r}")
except Exception as e:
    print(f"  ERREUR: {e}")

c.close()
print("\nDone.")
