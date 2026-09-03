# -*- coding: utf-8 -*-
"""
Diag 401 sur /api/shadow/perf-rolling depuis UI :
  1. Refait login JWT (rguelin / Thesium2026!)
  2. Appelle /api/shadow/perf-rolling AVEC token -> doit etre 200
  3. Appelle /api/shadow/perf-rolling SANS token -> doit etre 401
  4. Dump les premieres lignes du handler dans api_server.py pour voir si Depends(get_current_user) est bien la
  5. Dump le code dans app.js qui peuple state.token (login + localStorage)
"""
import urllib.request
import urllib.error
import json
import re

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

# 1. Login
print("=== [1] Login ===")
code, body = http("POST", "/api/auth/login", {"username": "rguelin", "password": "Thesium2026!"})
print("status:", code)
print("body:", body[:300])
token = None
try:
    j = json.loads(body)
    token = j.get("access_token") or j.get("token")
except Exception as e:
    print("parse err:", e)
print("token len:", len(token) if token else "NONE")
print()

# 2. Avec token
print("=== [2] GET /api/shadow/perf-rolling AVEC token ===")
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=token)
print("status:", code)
print("body[:400]:", body[:400])
print()

# 3. Sans token
print("=== [3] GET /api/shadow/perf-rolling SANS token ===")
code, body = http("GET", "/api/shadow/perf-rolling?window=30", token=None)
print("status:", code)
print("body[:400]:", body[:400])
print()

# 4. Dump signature des handlers shadow dans api_server.py
print("=== [4] Signature handlers shadow dans api_server.py ===")
API = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\api_server.py"
with open(API, "r", encoding="utf-8-sig", errors="replace") as f:
    lines = f.readlines()
for i, line in enumerate(lines, 1):
    if "/api/shadow/" in line or "shadow_list_variants" in line or "shadow_perf_rolling" in line:
        print("  L{:5d} | {}".format(i, line.rstrip()))
print()

# 5. Dump login + state.token write sites dans app.js
print("=== [5] Sites qui ecrivent state.token dans app.js ===")
JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    js_lines = f.readlines()
for i, line in enumerate(js_lines, 1):
    if "state.token" in line:
        print("  L{:5d} | {}".format(i, line.rstrip()))
print()

print("DONE")
