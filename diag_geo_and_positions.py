"""
Diagnostic pour préparer le GeoAgent :
1) Trouve le panel risque géopolitique existant (GDELT) dans index.html / app.js / API
2) Identifie la structure des positions ouvertes en base
3) Liste les tables liées geo / risk
"""
import re, sqlite3
from pathlib import Path

ROOT = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB   = ROOT / "thesium.db"

# ---- 1) Panel géo dans UI ----
print("=" * 70)
print("1) Panel risque géopolitique dans index.html")
print("=" * 70)
html = (ROOT / "index.html").read_text(encoding="utf-8-sig", errors="replace")

# Cherche des mots-clés liés au geo
keywords = ["geo", "geopolit", "GEOPOLI", "GDELT", "gdelt", "risque", "risk-geo", "risk_geo", "macro-vuln"]
for kw in keywords:
    matches = [m.start() for m in re.finditer(re.escape(kw), html)]
    if matches:
        print(f"  '{kw}' : {len(matches)} occurrences → première à offset {matches[0]}")

# Cherche les blocs <div id="..."> ou <section id="..."> qui pourraient être le panel
print("\n  IDs intéressants (contenant geo, risk, gdelt, macro) :")
for m in re.finditer(r'\bid="([^"]*(?:geo|risk|gdelt|macro|vuln)[^"]*)"', html, re.IGNORECASE):
    print(f"    id='{m.group(1)}' @ offset {m.start()}")

# Cherche le bloc Macro US (tab-macro) — résumer son contenu
print("\n  Contenu de <section id='tab-macro'> (premières 400 chars) :")
m = re.search(r'<section[^>]*id="tab-macro"[^>]*>(.*?)</section>', html, re.DOTALL)
if m:
    # Affiche les 10 premiers sous-tags h2/h3/h4/div id
    content = m.group(1)
    print(f"    Taille tab-macro: {len(content)} chars")
    # Liste les h2/h3
    for hm in re.finditer(r'<(h[1-4])[^>]*>([^<]+)</\1>', content):
        print(f"    [{hm.group(1)}] {hm.group(2).strip()[:80]}")
    # Liste les sections internes
    for sm in re.finditer(r'<(section|div)[^>]*id="([^"]+)"', content):
        print(f"    <{sm.group(1)} id='{sm.group(2)}'>")
else:
    print("    tab-macro introuvable")

# ---- 2) API GDELT/geo dans api_server_with_static.py ----
print()
print("=" * 70)
print("2) Endpoints API liés au géo (api_server_with_static.py)")
print("=" * 70)
api = (ROOT / "api_server_with_static.py").read_text(encoding="utf-8-sig", errors="replace")
for m in re.finditer(r'@app\.(get|post)\("(/api/[^"]*(?:geo|risk|gdelt|macro)[^"]*)"', api, re.IGNORECASE):
    print(f"  {m.group(1).upper()} {m.group(2)}")

# ---- 3) Tables liées geo/risk en base ----
print()
print("=" * 70)
print("3) Tables SQLite liées geo/risk/macro")
print("=" * 70)
if DB.exists():
    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    
    geo_tables = [t for t in tables if any(k in t.lower() for k in ['geo', 'risk', 'gdelt', 'macro', 'event'])]
    print(f"  Tables candidates : {geo_tables}")
    for t in geo_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            cur.execute(f"PRAGMA table_info({t})")
            cols = [(r[1], r[2]) for r in cur.fetchall()]
            print(f"\n  [{t}] rows={count}")
            for cn, ct in cols:
                print(f"    - {cn:25} {ct}")
        except Exception as e:
            print(f"  [{t}] ERROR: {e}")
    
    # ---- 4) Positions ouvertes (pour mapping portfolio) ----
    print()
    print("=" * 70)
    print("4) Tables liées aux positions (portfolio, holdings, positions)")
    print("=" * 70)
    pos_tables = [t for t in tables if any(k in t.lower() for k in ['position', 'holding', 'portfolio', 'book'])]
    print(f"  Tables candidates : {pos_tables}")
    for t in pos_tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            count = cur.fetchone()[0]
            cur.execute(f"PRAGMA table_info({t})")
            cols = [(r[1], r[2]) for r in cur.fetchall()]
            print(f"\n  [{t}] rows={count}")
            for cn, ct in cols:
                print(f"    - {cn:25} {ct}")
            # Échantillon
            if count > 0 and count < 50:
                cur.execute(f"SELECT * FROM {t} LIMIT 5")
                rows = cur.fetchall()
                print(f"    Échantillon (top 5):")
                for r in rows:
                    print(f"      {r}")
        except Exception as e:
            print(f"  [{t}] ERROR: {e}")
    
    # ---- 5) Instruments (pour la liste des tickers actifs) ----
    print()
    print("=" * 70)
    print("5) Tickers actifs (depuis 'instruments' + dernières cycles)")
    print("=" * 70)
    try:
        cur.execute("SELECT ticker, name, sector, asset_class FROM instruments ORDER BY ticker")
        rows = cur.fetchall()
        print(f"  Total instruments: {len(rows)}")
        for r in rows[:25]:
            print(f"    {r[0]:8} {r[1][:30]:30} {(r[2] or '-')[:20]:20} {r[3]}")
    except Exception as e:
        print(f"  [instruments] ERROR: {e}")
    
    con.close()
else:
    print(f"[ERR] DB introuvable : {DB}")

# ---- 6) Variable PPLX dans pplx_client.py (rappel modèles disponibles) ----
print()
print("=" * 70)
print("6) Modèles Perplexity dans pplx_client.py")
print("=" * 70)
pc = ROOT / "pplx_client.py"
if pc.exists():
    txt = pc.read_text(encoding="utf-8-sig", errors="replace")
    for m in re.finditer(r'MODEL_\w+\s*=\s*["\']([^"\']+)["\']', txt):
        print(f"  {m.group(0)}")
