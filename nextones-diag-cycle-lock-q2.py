# -*- coding: utf-8 -*-
"""
Q2 - Diag verrou RUN CYCLE 1x/jour.
 1) cycles_daily : contenu actuel + colonne 'forced'
 2) Localiser run_decision_cycle dans le code
 3) Voir l endpoint qui declenche le cycle depuis le bouton 'Run Decision Cycle'
 4) Detecter mecanisme de verrou existant (s il y en a un)
"""
import os, re, sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")

def head(t): print("\n"+"="*70); print(t); print("="*70)

# 1) cycles_daily
head("1) cycles_daily - contenu")
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
rows = c.execute("SELECT * FROM cycles_daily ORDER BY rowid DESC LIMIT 10").fetchall()
for r in rows:
    d = dict(r)
    # tronquer les longs
    if d.get('agents_result'):
        d['agents_result'] = str(d['agents_result'])[:100] + '...'
    print(f"  {d}")
n_today = c.execute("SELECT COUNT(*) FROM cycles_daily WHERE cycle_date = ?", ("2026-05-28",)).fetchone()[0]
print(f"\n  Cycles 2026-05-28 = {n_today}")
c.close()

# 2) Localiser run_decision_cycle
head("2) Definition de run_decision_cycle")
for root, dirs, files in os.walk(ROOT):
    if "_backup" in root or "__pycache__" in root or ".git" in root: continue
    for f in files:
        if not f.endswith(".py"): continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
        except: continue
        for m in re.finditer(r'def\s+(run_decision_cycle|run_agents|run_full_cycle)\s*\(', src):
            line = src.count("\n", 0, m.start()) + 1
            print(f"  {os.path.relpath(p, ROOT)}:L{line}  def {m.group(1)}(")

# 3) Endpoint declencheur depuis le bouton UI
head("3) Endpoints API contenant 'cycle' ou 'run'")
for fn in ["api_server.py", "api_server_with_static.py"]:
    p = os.path.join(ROOT, fn)
    if not os.path.exists(p): continue
    with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()
    for m in re.finditer(r'@app\.(get|post)\(\s*"([^"]+)"', src):
        path = m.group(2)
        if 'cycle' in path.lower() or 'run' in path.lower() or 'decision' in path.lower():
            line = src.count("\n", 0, m.start()) + 1
            # extraire le nom de la fonction qui suit
            tail = src[m.end():m.end()+200]
            fn_m = re.search(r'def\s+(\w+)', tail)
            print(f"  {fn}:L{line}  {m.group(1).upper():5s} {path:35s} -> {fn_m.group(1) if fn_m else '?'}")

# 4) Cherche pattern existant de verrou (cycle_date, today, forced, already_ran)
head("4) Patterns de verrou existants dans le code")
patterns = [
    (r'cycles_daily.*WHERE.*cycle_date', 'select cycles_daily by date'),
    (r'forced\s*=\s*(True|False|1|0)', 'usage de forced'),
    (r'already_ran|already_run|cycle_already', 'guard already_ran'),
    (r'INSERT\s+INTO\s+cycles_daily', 'insert cycles_daily'),
]
for root, dirs, files in os.walk(ROOT):
    if "_backup" in root or "__pycache__" in root or ".git" in root: continue
    for f in files:
        if not f.endswith(".py"): continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                src = fh.read()
        except: continue
        for pat, desc in patterns:
            for m in re.finditer(pat, src, re.IGNORECASE):
                line = src.count("\n", 0, m.start()) + 1
                snippet = src[max(0,m.start()-20):m.end()+60].replace("\n"," ")
                print(f"  [{desc}] {os.path.relpath(p, ROOT)}:L{line}  ...{snippet[:120]}...")

print("\nDone.")
