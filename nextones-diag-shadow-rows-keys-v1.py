# -*- coding: utf-8 -*-
"""
Dump le contenu complet d'une row de /api/shadow/perf-rolling
pour voir tous les noms de champs EXACTS retournes par l'API.
"""
import urllib.request
import urllib.error
import json

BASE = "http://127.0.0.1:8000"

def http(method, path, body=None, token=None):
    url = BASE + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

# Login
_, body = http("POST", "/api/auth/login", {"username": "rguelin", "password": "Thesium2026!"})
token = json.loads(body).get("access_token")

# Perf rolling
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=token)
print("status:", code)
j = json.loads(body)
print("Top-level keys :", list(j.keys()))
print("Number of rows :", len(j.get("rows", [])))
print()
rows = j.get("rows", [])
if rows:
    print("=== Row[0] complet (prod) ===")
    print(json.dumps(rows[0], indent=2, ensure_ascii=False))
    print()
    print("=== Row[1] complet (tight_conv = champion attendu) ===")
    if len(rows) > 1:
        print(json.dumps(rows[1], indent=2, ensure_ascii=False))
print()

# Variants
code, body = http("GET", "/api/shadow/variants", token=token)
print("=== /api/shadow/variants Row[0] ===")
j2 = json.loads(body)
vs = j2.get("variants", [])
if vs:
    print(json.dumps(vs[0], indent=2, ensure_ascii=False))

print()
print("DONE")
