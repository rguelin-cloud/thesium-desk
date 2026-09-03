# -*- coding: utf-8 -*-
"""
Test memo IC convergence v2 — recherche generate_ic_memo dans TOUS les .py
du repo, identifie la VRAIE route, declenche, lit le memo NOUVELLEMENT cree.
"""
import os, sys, io, re, json, urllib.request, urllib.error, sqlite3, glob

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
        with urllib.request.urlopen(req, timeout=180) as resp:
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

# 0. Auth
print("=" * 60); print("0. AUTH"); print("=" * 60)
st, body = http("POST", "/api/auth/login", {"username": USER, "password": PWD})
token = None
if st == 200 and isinstance(body, dict):
    token = body.get("access_token") or body.get("token") or body.get("jwt")
    print(f"  login OK, token={token[:30] if token else '?'}...")
else:
    print(f"  login fail (status={st}): {str(body)[:200]}")
    sys.exit(1)

# 1. Snapshot DB AVANT
print("\n" + "=" * 60); print("1. SNAPSHOT MEMO AVANT"); print("=" * 60)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute("SELECT MAX(id) as mx, COUNT(*) as c FROM ic_memos")
r = cur.fetchone()
id_before = r["mx"] or 0
count_before = r["c"] or 0
print(f"  max(id)={id_before}, count={count_before}")
conn.close()

# 2. Scan TOUS les .py pour generate_ic_memo
print("\n" + "=" * 60); print("2. SCAN generate_ic_memo DANS TOUS LES .py"); print("=" * 60)
py_files = []
for root, dirs, files in os.walk(BASE):
    # skip venvs et caches
    dirs[:] = [d for d in dirs if d not in (".venv", "venv", "__pycache__", "node_modules", ".git")]
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))

callsites = []  # (filepath, line, route_method, route_path, func_name)
for fp in py_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    if "generate_ic_memo" not in src:
        continue
    for m in re.finditer(r"generate_ic_memo\s*\(", src):
        line_num = src[:m.start()].count("\n") + 1
        before = src[:m.start()]
        # route la plus proche au-dessus
        last_route = None
        for mm in re.finditer(r'@app\.(get|post|put|delete)\(\s*[\"\']([^\"\']+)[\"\']', before):
            last_route = (mm.group(1).upper(), mm.group(2), before[:mm.start()].count("\n") + 1)
        # fonction qui contient l'appel
        last_func = None
        for mm in re.finditer(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", before, re.MULTILINE):
            last_func = (mm.group(1), before[:mm.start()].count("\n") + 1)
        callsites.append((fp, line_num, last_route, last_func))

print(f"  {len(callsites)} callsite(s) trouve(s):")
for fp, ln, route, func in callsites:
    rel = os.path.relpath(fp, BASE)
    print(f"    {rel}:L{ln}")
    if route:
        print(f"      route: {route[0]} {route[1]} (L{route[2]})")
    if func:
        print(f"      fonc: def {func[0]} (L{func[1]})")

# 3. Cherche aussi les routes qui parlent d'ic memo (insert dans ic_memos)
print("\n" + "=" * 60); print("3. SCAN INSERT INTO ic_memos"); print("=" * 60)
for fp in py_files:
    try:
        with open(fp, "r", encoding="utf-8-sig") as f:
            src = f.read()
    except Exception:
        continue
    if "ic_memos" not in src:
        continue
    for m in re.finditer(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+ic_memos", src, re.IGNORECASE):
        line_num = src[:m.start()].count("\n") + 1
        before = src[:m.start()]
        last_route = None
        for mm in re.finditer(r'@app\.(get|post|put|delete)\(\s*[\"\']([^\"\']+)[\"\']', before):
            last_route = (mm.group(1).upper(), mm.group(2), before[:mm.start()].count("\n") + 1)
        last_func = None
        for mm in re.finditer(r"^\s*(?:async\s+)?def\s+(\w+)\s*\(", before, re.MULTILINE):
            last_func = (mm.group(1), before[:mm.start()].count("\n") + 1)
        rel = os.path.relpath(fp, BASE)
        print(f"  {rel}:L{line_num}  INSERT INTO ic_memos")
        if route is not None and last_route:
            print(f"    route: {last_route[0]} {last_route[1]} (L{last_route[2]})")
        if last_func:
            print(f"    fonc: def {last_func[0]} (L{last_func[1]})")

# 4. Liste TOUTES les routes du serveur actuel via OpenAPI
print("\n" + "=" * 60); print("4. OPENAPI ROUTES /api/memo* et /api/ic*"); print("=" * 60)
st, body = http("GET", "/openapi.json")
if st == 200 and isinstance(body, dict):
    paths = body.get("paths", {})
    for p, methods in sorted(paths.items()):
        if "memo" in p.lower() or "/ic" in p.lower() or p.endswith("/generate"):
            for meth in methods.keys():
                if meth.upper() in ("GET", "POST", "PUT", "DELETE"):
                    print(f"  {meth.upper():6s} {p}")
else:
    print(f"  openapi fetch fail status={st}")

print("\n[DONE]")
