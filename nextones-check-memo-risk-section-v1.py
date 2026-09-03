# -*- coding: utf-8 -*-
# nextones-check-memo-risk-section-v1.py
# Marker : [CHECK_MEMO_RISK_SECTION_V1]
#
# Recupere le memo #76 (ou le dernier) via API, extrait la section RISK_V2
# et verifie le motif humain. Aussi : fallback direct DB si API indisponible.

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import re

API = "http://127.0.0.1:8000"
DB = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db"
USER = "rguelin"
PWD = "Thesium2026!"

print()
print("=" * 78)
print("CHECK : motif humain dans le dernier memo")
print("=" * 78)

# Step 0 : login
def login():
    data = json.dumps({"username": USER, "password": PWD}).encode("utf-8")
    req = urllib.request.Request(
        API + "/api/auth/login",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        body = json.loads(r.read().decode("utf-8"))
    return body.get("access_token") or body.get("token")

# Step 1 : recuperer dernier memo_id depuis DB (plus simple)
print("-" * 78)
print("[1] Dernier memo_id en DB")
print("-" * 78)
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

# Trouver table memos / ic_memos / ...
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
memo_table = None
for cand in ("ic_memos", "memos", "memo", "memo_log"):
    if cand in tables:
        memo_table = cand
        break
if not memo_table:
    # fuzzy
    for t in tables:
        if "memo" in t.lower():
            memo_table = t
            break
print("  Table memo : %s" % memo_table)

last_memo_id = None
if memo_table:
    try:
        cur.execute("SELECT id FROM %s ORDER BY id DESC LIMIT 1" % memo_table)
        last_memo_id = cur.fetchone()["id"]
        print("  Dernier id : %s" % last_memo_id)
    except Exception as e:
        print("  Erreur : %s" % e)

c.close()

# Step 2 : login + fetch markdown
print()
print("-" * 78)
print("[2] Login + GET /api/memos/<id>/markdown")
print("-" * 78)
try:
    tok = login()
    print("  Token OK")
except Exception as e:
    print("  [KO] login : %s" % e)
    sys.exit(1)

target_id = last_memo_id or 76
print("  Cible memo_id=%s" % target_id)

md = None
for path in ("/api/memos/%d/markdown" % target_id, "/api/memos/%d" % target_id):
    url = API + path
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            ct = r.headers.get("Content-Type", "")
            raw = r.read().decode("utf-8", errors="replace")
            print("  %s -> %s (%d bytes)" % (path, ct, len(raw)))
            if "/markdown" in path:
                md = raw
                break
            else:
                # JSON probable
                try:
                    j = json.loads(raw)
                    md = j.get("markdown") or j.get("body") or j.get("content")
                except Exception:
                    pass
    except urllib.error.HTTPError as e:
        print("  %s -> HTTP %s" % (path, e.code))
    except Exception as e:
        print("  %s -> erreur : %s" % (path, e))

# Step 3 : extraire section RISK_V2
print()
print("-" * 78)
print("[3] Section RISK_V2 dans le memo")
print("-" * 78)

if not md:
    print("  [KO] Markdown vide")
    sys.exit(2)

# Cherche table pre-trade : on prend les lignes contenant ZEC/HYPE/BTC/ETH/SOL
# et tout bloc autour de "Pre-trade" / "RISK_V2"
lines = md.split("\n")
in_section = False
shown = 0
for i, line in enumerate(lines):
    low = line.lower()
    if any(k in low for k in ("pre-trade", "risk_v2", "pretrade", "controle pre", "pre trade")):
        in_section = True
    if in_section:
        print("  L%d| %s" % (i + 1, line[:170]))
        shown += 1
        if shown > 40:
            print("  ... (tronque a 40 lignes)")
            break

if shown == 0:
    print("  [INFO] Aucune section 'Pre-trade/RISK_V2' detectee, dump 60 dernieres lignes :")
    for line in lines[-60:]:
        print("  | %s" % line[:170])

# Step 4 : verif specifique BLOCK lignes
print()
print("-" * 78)
print("[4] Lignes BLOCK / motifs humains dans le memo")
print("-" * 78)
hits = [l for l in lines if "BLOCK" in l]
print("  %d lignes contiennent 'BLOCK'" % len(hits))
for l in hits[:30]:
    print("    | %s" % l[:170])

print()
print("-" * 78)
print("[5] Recherche litterales attendues")
print("-" * 78)
expected_bad = ["Mapping broker OK"]
expected_good = ["Non tradable", "Refus broker", "Convergence forced", "convergence_forced"]
for s in expected_bad:
    n = sum(1 for l in lines if s in l)
    flag = "OK (0)" if n == 0 else "BUG (%d occurrences)" % n
    print("  [%s] '%s' -> %s" % ("KO" if n > 0 else "OK", s, flag))
for s in expected_good:
    n = sum(1 for l in lines if s in l)
    print("  [%s] '%s' -> %d occurrence(s)" % ("OK" if n > 0 else "INFO", s, n))

print()
print("=" * 78)
