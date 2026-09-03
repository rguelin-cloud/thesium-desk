# -*- coding: utf-8 -*-
"""
Diag: pourquoi pas d ordres ce matin 28/05 ?
Hypotheses:
 A) Cycle n a tout simplement pas tourne ce matin
 B) Cycle a tourne mais 0 proposition (toutes filtrees)
 C) Cycle a tourne, propositions OK, mais [RISK_V2_WIRED] gate les a toutes rejetees
 D) Verrou run_cycle bloque
"""
import os, sqlite3, json
from datetime import datetime, timedelta

DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

def head(t): print("\n" + "="*70); print(t); print("="*70)

now = datetime.now()
today = now.strftime("%Y-%m-%d")
yest  = (now - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"Now = {now}, today = {today}, yest = {yest}")

# 1) Derniers ordres : quand a ete cree le dernier ?
head("1) Derniers ordres (10)")
rows = c.execute("""
  SELECT id, instrument_id, side, quantity, status,
         COALESCE(created_at, '') AS ts,
         COALESCE(risk_check_result,'') AS rc
  FROM orders ORDER BY id DESC LIMIT 10
""").fetchall()
for r in rows:
    has_v2 = "risk_v2" in r["rc"] if r["rc"] else False
    print(f"  #{r['id']:>4} {r['ts'][:19]:>19} inst={r['instrument_id']:>3} {r['side']:<5} qty={r['quantity']:<6} status={r['status']:<12} risk_v2={'YES' if has_v2 else 'NO'}")

# 2) Cycles enregistres (table run_cycle ou equivalente)
head("2) Tables decision/cycle existantes")
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%cycle%' OR name LIKE '%decision%' OR name LIKE '%proposal%'").fetchall()
for t in tables:
    print(f"  - {t['name']}")

# 3) Pour chaque table candidate, derniers enregistrements
for tname in ['decision_cycles','run_cycles','proposals','cycle_log']:
    try:
        info = c.execute(f"PRAGMA table_info({tname})").fetchall()
        if not info: continue
        cols = [r[1] for r in info]
        head(f"3) {tname} (cols: {','.join(cols)})")
        ts_col = None
        for cand in ['created_at','ts','timestamp','date','run_at']:
            if cand in cols: ts_col = cand; break
        order_by = ts_col or 'rowid'
        last = c.execute(f"SELECT * FROM {tname} ORDER BY {order_by} DESC LIMIT 5").fetchall()
        for r in last:
            print(f"  {dict(r)}")
    except Exception as e:
        pass

# 4) Theses generees ce matin ?
head("4) Theses generees aujourd hui")
try:
    info = c.execute("PRAGMA table_info(theses)").fetchall()
    cols = [r[1] for r in info]
    ts_col = 'created_at' if 'created_at' in cols else ('ts' if 'ts' in cols else None)
    if ts_col:
        rows = c.execute(f"SELECT id, COALESCE({ts_col},'') AS ts, instrument_id FROM theses WHERE {ts_col} LIKE ? ORDER BY id DESC LIMIT 20", (f"{today}%",)).fetchall()
        print(f"  Theses du {today}: {len(rows)}")
        for r in rows[:5]:
            print(f"    #{r['id']:>5} {r['ts'][:19]} inst={r['instrument_id']}")
        rows2 = c.execute(f"SELECT id, {ts_col}, instrument_id FROM theses ORDER BY id DESC LIMIT 5").fetchall()
        print(f"  5 dernieres theses (toutes dates):")
        for r in rows2:
            print(f"    #{r['id']:>5} {r[ts_col]} inst={r['instrument_id']}")
except Exception as e:
    print(f"  ERREUR: {e}")

# 5) IC memos d aujourd hui
head("5) IC memos aujourd hui")
try:
    rows = c.execute("SELECT id, date, title FROM ic_memos WHERE date LIKE ? ORDER BY id DESC", (f"{today}%",)).fetchall()
    print(f"  Memos du {today}: {len(rows)}")
    for r in rows:
        print(f"    #{r['id']} {r['date']} {r['title']}")
    last = c.execute("SELECT id, date, title FROM ic_memos ORDER BY id DESC LIMIT 3").fetchall()
    print("  3 derniers memos:")
    for r in last:
        print(f"    #{r['id']} {r['date']} {r['title']}")
except Exception as e:
    print(f"  ERREUR: {e}")

# 6) Verrou cycle ?
head("6) Verrous / fichiers lock")
for fname in ['cycle.lock','run_cycle.lock','.lock','cycle_running.flag']:
    p = os.path.join(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk", fname)
    if os.path.exists(p):
        mtime = datetime.fromtimestamp(os.path.getmtime(p))
        print(f"  PRESENT: {p} (mtime={mtime})")
# Cherche aussi colonne is_running dans une table de cycle
for tname in ['cycle_state','run_state','decision_cycles']:
    try:
        info = c.execute(f"PRAGMA table_info({tname})").fetchall()
        cols = [r[1] for r in info]
        if 'is_running' in cols or 'status' in cols:
            r = c.execute(f"SELECT * FROM {tname} ORDER BY rowid DESC LIMIT 3").fetchall()
            print(f"  {tname}:")
            for row in r:
                print(f"    {dict(row)}")
    except: pass

# 7) risk_pretrade_log count
head("7) risk_pretrade_log activite")
try:
    n = c.execute("SELECT COUNT(*) FROM risk_pretrade_log").fetchone()[0]
    n_today = c.execute("SELECT COUNT(*) FROM risk_pretrade_log WHERE ts LIKE ?", (f"{today}%",)).fetchone()[0]
    print(f"  Total = {n}, today = {n_today}")
except Exception as e:
    print(f"  ERREUR: {e}")

c.close()
print("\nDone.")
