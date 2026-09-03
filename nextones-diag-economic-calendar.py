# [DIAG_ECONOMIC_CALENDAR_V1]
# Localise la source des donnees du widget Economic Calendar :
#   - HTML : div/section qui contient "GDP (Advance Estimate)" / "Initial Jobless Claims"
#   - JS   : fetch d'endpoint type /api/economic-calendar
#   - API  : endpoint @app.get servant ces donnees
#   - DB   : table economic_events / calendar_events
#   - Module : fichier .py qui retourne ces enregistrements

from pathlib import Path
import re
import sqlite3

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = ROOT / "thesium.db"
HTML = ROOT / "index.html"
API = ROOT / "api_server.py"


def section(t):
    print("\n" + "=" * 72)
    print(t)
    print("=" * 72)


# 1) HTML : reperage des ancres
section("[1] HTML : ancres et endpoints fetch")
if HTML.exists():
    raw = HTML.read_text(encoding="utf-8-sig", errors="replace")
    for marker in ["Economic Calendar", "GDP (Advance", "Initial Jobless", "economic_calendar",
                   "economicCalendar", "loadEconomicCalendar", "loadCalendar"]:
        for m in re.finditer(re.escape(marker), raw, re.IGNORECASE):
            line_no = raw[:m.start()].count("\n") + 1
            ctx = raw[max(0, m.start() - 60):m.end() + 100].replace("\n", " ")[:200]
            print(f"  L{line_no:>5} | {marker:25} | ...{ctx}...")
            break  # une occurrence par marker pour rester lisible
    print("\n  Endpoints /api/* references dans le HTML :")
    for m in re.finditer(r"/api/[a-z\-_/]+", raw):
        ep = m.group(0)
        if any(k in ep for k in ["calendar", "economic", "event"]):
            line_no = raw[:m.start()].count("\n") + 1
            print(f"  L{line_no:>5} | {ep}")


# 2) API : endpoints calendar
section("[2] api_server.py : endpoints calendar/economic/event")
if API.exists():
    txt = API.read_text(encoding="utf-8-sig", errors="replace")
    for m in re.finditer(r'@app\.(?:get|post)\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)\s*\n(?:async\s+)?def\s+(\w+)', txt):
        route = m.group(1)
        if any(k in route.lower() for k in ["calendar", "economic", "event", "macro"]):
            line_no = txt[:m.start()].count("\n") + 1
            # cherche le body
            body_start = m.end()
            next_def = re.search(r"\n(?:@app\.|def\s+|async\s+def\s+)", txt[body_start:])
            body_end = body_start + (next_def.start() if next_def else 1500)
            body = txt[body_start:body_end]
            # extract premieres lignes interessantes
            interesting = []
            for line in body.split("\n")[:25]:
                ls = line.strip()
                if any(k in ls for k in ["import", "fetch", "execute", "data_", "return", "SELECT", "JSONResponse"]):
                    interesting.append(line.rstrip())
            print(f"  L{line_no:>5}  {route:40} -> {m.group(2)}()")
            for ln in interesting[:8]:
                print(f"          {ln[:140]}")


# 3) DB : tables qui contiennent ces events
section("[3] DB : tables economic / calendar / event")
con = sqlite3.connect(str(DB))
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
candidates = [t for t in tables if any(k in t.lower() for k in ["calendar", "economic", "event", "macro"])]
print(f"  Tables candidates : {candidates}")

for t in candidates:
    print(f"\n  --- {t} ---")
    cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"  cols = {cols}")
    n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  count = {n}")
    if n > 0:
        # cherche lignes du 28/05/2026
        try:
            # cherche colonne date probable
            date_cols = [c for c in cols if any(k in c.lower() for k in ["date", "time", "ts", "release", "event"])]
            print(f"  date_cols probables : {date_cols}")
            # GDP / Jobless
            for kw in ["GDP", "Jobless", "Advance"]:
                # cherche dans toutes les colonnes texte
                for c in cols:
                    if c.lower() in ("id",):
                        continue
                    try:
                        rows = cur.execute(
                            f"SELECT * FROM {t} WHERE {c} LIKE ? LIMIT 3",
                            (f"%{kw}%",)
                        ).fetchall()
                        if rows:
                            print(f"\n  Match '{kw}' dans col {c} :")
                            for r in rows:
                                print(f"    {dict(zip(cols, r))}")
                            break
                    except Exception:
                        pass
        except Exception as e:
            print(f"  erreur : {e}")
con.close()


# 4) Modules Python qui contiennent ces noms d'events
section("[4] Fichiers .py qui mentionnent 'GDP Advance' ou 'Initial Jobless'")
for py in ROOT.rglob("*.py"):
    if any(p in str(py) for p in ["__pycache__", "_backups_", ".venv", "venv"]):
        continue
    if ".bak." in py.name:
        continue
    try:
        t = py.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        continue
    for kw in ["GDP (Advance", "Initial Jobless", "Advance Estimate", "Jobless Claims"]:
        if kw in t:
            # cherche les 2-3 premieres lignes
            for m in re.finditer(re.escape(kw), t):
                line_no = t[:m.start()].count("\n") + 1
                line_start = t.rfind("\n", 0, m.start()) + 1
                line_end = t.find("\n", m.end())
                line = t[line_start:line_end].strip()
                print(f"  {py.relative_to(ROOT)}:{line_no}  [{kw}]")
                print(f"    {line[:160]}")
                break  # 1 par fichier par kw
