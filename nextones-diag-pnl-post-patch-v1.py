# -*- coding: utf-8 -*-
# [DIAG_PNL_POST_PATCH_V1]
# Verifie apres les patches V3 (risk_engine + UI) :
#   1. portfolio_state : cash, total_value, total_pnl, unrealized_pnl, daily_pnl
#   2. /api/dashboard : structure renvoyee (cle portfolio + unrealized_pnl + total_return)
#   3. Bloc app.js juste apres "kpiGrid.innerHTML = `" pour voir si marker est dans le template

import sqlite3
import json
import urllib.request
from pathlib import Path

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = BASE / "thesium.db"

print("=" * 70)
print("1. portfolio_state (etat actuel apres patches)")
print("=" * 70)
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM portfolio_state WHERE id = 1").fetchone()
if row:
    for k in row.keys():
        print("  " + k + " = " + str(row[k]))
else:
    print("  (vide)")

print()
print("=" * 70)
print("2. Colonnes presentes dans portfolio_state")
print("=" * 70)
cols = conn.execute("PRAGMA table_info(portfolio_state)").fetchall()
for c in cols:
    print("  " + c["name"] + " (" + c["type"] + ")")

print()
print("=" * 70)
print("3. capital_flows : count + dump")
print("=" * 70)
try:
    cnt = conn.execute("SELECT COUNT(*) AS n FROM capital_flows").fetchone()
    print("  count = " + str(cnt["n"]))
    if cnt["n"] > 0:
        for r in conn.execute("SELECT * FROM capital_flows LIMIT 10"):
            print("  " + dict(r).__str__())
except Exception as e:
    print("  ERR : " + str(e))
conn.close()

print()
print("=" * 70)
print("4. /api/dashboard : recupere via login JWT puis dump portfolio block")
print("=" * 70)
try:
    # Login
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=json.dumps({"username": "rguelin", "password": "Thesium2026!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        tok = json.loads(r.read())["access_token"]
    # Dashboard
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/dashboard",
        headers={"Authorization": "Bearer " + tok},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    p = data.get("portfolio", {})
    print("  data.portfolio keys : " + str(list(p.keys())))
    print()
    print("  Champs cles renvoyes :")
    for k in ("total_value", "cash", "total_pnl", "total_pnl_pct",
              "unrealized_pnl", "unrealized_pnl_pct",
              "total_return", "total_return_pct",
              "daily_pnl", "daily_pnl_pct", "var_95"):
        v = p.get(k, "<ABSENT>")
        print("    " + k + " = " + str(v))
except Exception as e:
    print("  ERR : " + str(e))

print()
print("=" * 70)
print("5. app.js : lignes 1083-1095 (verifier ou est le marker V3)")
print("=" * 70)
with open(BASE / "app.js", "rb") as f:
    js = f.read()
if js.startswith(b"\xef\xbb\xbf"):
    js = js[3:]
lines = js.decode("utf-8").splitlines()
for i in range(1082, min(1096, len(lines))):
    print("  L" + str(i+1) + ": " + lines[i][:160])

print()
print("DONE [DIAG_PNL_POST_PATCH_V1]")
