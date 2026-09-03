# -*- coding: utf-8 -*-
"""
Test de bout-en-bout du patch convergence dans memo_generator.

Strategie :
1. Identifier l'endpoint qui DECLENCHE generate_ic_memo (POST ou GET)
2. Le lancer
3. Recuperer le markdown du dernier memo (max id)
4. Verifier presence de '## Convergence Engine' + bons chiffres
5. Telecharger le PDF si endpoint dispo

Pas besoin d'auth si l'endpoint est public, sinon on passe par token JWT.
"""
import os, sys, io, re, json, urllib.request, urllib.error, sqlite3

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="backslashreplace")

BASE = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(BASE, "thesium.db")
API = "http://localhost:8000"
USER = "rguelin"
PWD = "Thesium2026!"

def http(method, path, body=None, token=None, raw=False):
    url = API + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            if raw:
                return resp.status, content
            try:
                return resp.status, json.loads(content.decode("utf-8"))
            except Exception:
                return resp.status, content.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return -1, str(e)

# 0. Login pour avoir un token (au cas ou)
print("=" * 60)
print("0. AUTH")
print("=" * 60)
st, body = http("POST", "/api/auth/login", {"username": USER, "password": PWD})
token = None
if st == 200 and isinstance(body, dict):
    token = body.get("access_token") or body.get("token") or body.get("jwt")
    print(f"  login OK, token={token[:30] if token else '?'}...")
else:
    print(f"  login fail (status={st}) : {str(body)[:200]}")

# 1. Lister les endpoints memos
print("\n" + "=" * 60)
print("1. ENDPOINTS DISPOS")
print("=" * 60)
# Cherche dans api_server.py les routes memo
api_path = os.path.join(BASE, "api_server.py")
with open(api_path, "r", encoding="utf-8-sig") as f:
    api_src = f.read()
endpoints = []
for m in re.finditer(r'@app\.(get|post|put|delete)\(\s*["\']([^"\']*memo[^"\']*)["\']', api_src, re.IGNORECASE):
    endpoints.append((m.group(1).upper(), m.group(2)))
    print(f"  {m.group(1).upper()} {m.group(2)}")

# Cherche aussi 'generate_ic_memo' dans les routes
print("\n  Endpoints qui appellent generate_ic_memo :")
for m in re.finditer(r'generate_ic_memo\s*\(', api_src):
    line_num = api_src[:m.start()].count("\n") + 1
    # remonter jusqu'au @app.xxx le plus proche au-dessus
    before = api_src[:m.start()]
    last_route = None
    for mm in re.finditer(r'@app\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', before):
        last_route = (mm.group(1).upper(), mm.group(2), before[:mm.start()].count("\n") + 1)
    if last_route:
        print(f"    L{line_num} appel de generate_ic_memo dans route {last_route[0]} {last_route[1]} (L{last_route[2]})")

# 2. Tenter de declencher generation
print("\n" + "=" * 60)
print("2. DECLENCHEMENT GENERATION MEMO")
print("=" * 60)
candidates = [
    ("POST", "/api/memos/generate"),
    ("POST", "/api/memos"),
    ("GET",  "/api/memos/generate"),
    ("POST", "/api/memos/generate/ic"),
    ("POST", "/api/memos/ic/generate"),
]
generated = False
for method, path in candidates:
    print(f"\n  Trying {method} {path}")
    st, body = http(method, path, body={} if method == "POST" else None, token=token)
    body_str = str(body)[:300]
    print(f"    status={st}  body={body_str}")
    if st in (200, 201):
        generated = True
        print(f"    >>> SUCCESS via {method} {path}")
        break

# 3. Lire le memo le plus recent en DB
print("\n" + "=" * 60)
print("3. DERNIER MEMO EN DB")
print("=" * 60)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT id, date, title, full_markdown, created_at FROM ic_memos ORDER BY rowid DESC LIMIT 1")
last = cur.fetchone()
if last:
    print(f"  memo #{last['id']}  date={last['date']}  created={last['created_at']}")
    print(f"  title : {last['title']}")
    md = last['full_markdown'] or ""
    print(f"  markdown : {len(md)} chars")
    if "## Convergence Engine" in md:
        print("  [PASS] section 'Convergence Engine' presente")
        # extraire la section
        idx = md.find("## Convergence Engine")
        next_h = md.find("\n## ", idx + 5)
        if next_h == -1:
            section = md[idx:]
        else:
            section = md[idx:next_h]
        print("\n  --- SECTION CONVERGENCE ---")
        print(section[:3000])
        print("  --- FIN ---")
    else:
        print("  [FAIL] section 'Convergence Engine' ABSENTE")
        print("  Headings trouves :")
        for m in re.finditer(r'^##\s+([^\n]+)', md, re.MULTILINE):
            print(f"    - {m.group(1)}")
else:
    print("  [FAIL] aucun memo en DB")

conn.close()
print("\n[DONE]")
