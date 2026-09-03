# -*- coding: utf-8 -*-
"""
Diag precis avant insertion carte 'Controles pre-trade'.
 1) extrait pplx-geo-section pour caler le style/structure (modele a imiter)
 2) cherche pattern d'enregistrement d'endpoints (FastAPI router/app)
 3) verifie classes CSS disponibles (section-header, table-section, kpi-card, ...)
 4) verifie schema risk_pretrade_log -> liste des colonnes (pour endpoint)
"""
import os, re, sqlite3

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
HTML = os.path.join(ROOT, "index.html")
API  = os.path.join(ROOT, "api_server_with_static.py")
DB   = os.path.join(ROOT, "thesium.db")

def head(t):
    print("\n" + "="*70); print(t); print("="*70)

with open(HTML, "r", encoding="utf-8-sig", errors="replace") as f:
    html = f.read()
lines = html.split("\n")

# 1) extrait pplx-geo-section (L1525) sur ~80 lignes pour avoir le modele
head("1) pplx-geo-section -> modele de carte a imiter")
for i, ln in enumerate(lines, 1):
    if 'pplx-geo-section' in ln and 'class' in ln:
        print(f"  DEBUT L{i}")
        for j in range(i-1, min(i+70, len(lines))):
            print(f"  L{j+1:>5}: {lines[j]}")
        break

# 2) Pattern d'enregistrement d'endpoints
head("2) Endpoints API: pattern utilise dans api_server_with_static.py")
with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    api_src = f.read()
# 5 premiers endpoints @app.get / @app.post
hits = list(re.finditer(r'@app\.(get|post)\(\s*"([^"]+)"', api_src))
print(f"  Total endpoints: {len(hits)}")
for m in hits[:8]:
    line = api_src.count("\n", 0, m.start()) + 1
    # ligne suivante = nom de fonction
    after = api_src[m.end():m.end()+200]
    fn = re.search(r'def\s+(\w+)\s*\(', after)
    print(f"  L{line:>5}: {m.group(1).upper():4s} {m.group(2):40s} -> {fn.group(1) if fn else '?'}")

# 3) Verifier classes CSS frequentes
head("3) Classes CSS recurrentes (echantillon)")
classes = re.findall(r'class="([^"]+)"', html)
from collections import Counter
ct = Counter()
for c in classes:
    for token in c.split():
        ct[token] += 1
for cls, n in ct.most_common(20):
    print(f"  {n:>4d}x {cls}")

# 4) Schema risk_pretrade_log
head("4) Schema risk_pretrade_log")
c = sqlite3.connect(DB)
try:
    info = c.execute("PRAGMA table_info(risk_pretrade_log)").fetchall()
    for row in info:
        print(f"  cid={row[0]} name={row[1]} type={row[2]} notnull={row[3]} default={row[4]}")
    n = c.execute("SELECT COUNT(*) FROM risk_pretrade_log").fetchone()[0]
    print(f"  TOTAL rows = {n}")
except Exception as e:
    print(f"  ERREUR: {e}")
c.close()

# 5) Fin du tab-today / debut tab suivant pour insertion
head("5) Recherche fin de tab-today + section apres KPI")
for i, ln in enumerate(lines, 1):
    if 'tab-today' in ln and 'section' in ln:
        print(f"  DEBUT tab-today L{i}: {ln.strip()[:120]}")
        break
# Cherche le 1er </section> apres tab-today
in_today = False
for i, ln in enumerate(lines, 1):
    if 'tab-today' in ln and 'section' in ln:
        in_today = True
        continue
    if in_today and '</section>' in ln:
        print(f"  FIN tab-today (1ere </section>) L{i}: {ln.strip()[:120]}")
        break

print("\nDone.")
