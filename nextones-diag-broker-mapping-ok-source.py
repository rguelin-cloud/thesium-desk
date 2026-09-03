# -*- coding: utf-8 -*-
# nextones-diag-broker-mapping-ok-source.py
# Marker : [DIAG_BROKER_MAPPING_OK_SOURCE]
#
# But : comprendre pourquoi 'broker_mapping_ok' apparait dans
# risk_pretrade_log.blocked_by pour ZEC #72 et HYPE #68/69.
# - Dump des verdicts complets (details_json) pour ces 3 rows
# - Cherche dans risk_pretrade.py / nextones-risk-broker-check.py / execution_engine.py
#   ou est ecrit 'broker_mapping_ok' dans blocked_by

import os
import re
import json
import sqlite3

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")

print()
print("=" * 78)
print("DIAG : source de 'broker_mapping_ok' dans blocked_by")
print("=" * 78)

# --- 1) Dump complet rows 68, 69, 72 (et un row OK pour comparer)
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row
cur = c.cursor()

print()
print("-" * 78)
print("ROWS RISK_PRETRADE_LOG bloques par 'broker_mapping_ok'")
print("-" * 78)

cur.execute(
    "SELECT * FROM risk_pretrade_log "
    "WHERE blocked_by='broker_mapping_ok' OR blocked_by LIKE '%broker_mapping%' "
    "ORDER BY id DESC LIMIT 10"
)
rows = cur.fetchall()
print("  %d rows trouvees" % len(rows))
for r in rows:
    d = dict(r)
    print()
    print("  --- id=%s symbol=%s side=%s passed=%s ---" % (d.get("id"), d.get("symbol"), d.get("side"), d.get("passed")))
    print("  ts          : %s" % d.get("ts"))
    print("  qty/price   : %s / %s" % (d.get("qty"), d.get("price")))
    print("  blocked_by  : %s" % d.get("blocked_by"))
    print("  marker      : %s" % d.get("marker"))
    dj = d.get("details_json") or ""
    if dj:
        try:
            j = json.loads(dj)
            print("  details_json (parse) :")
            print("    %s" % json.dumps(j, indent=2, ensure_ascii=False)[:1200])
        except Exception:
            print("  details_json (raw) : %s" % str(dj)[:600])

# --- 2) Pour comparer, un row OK et un row block legitime
print()
print("-" * 78)
print("EXEMPLE row PASS (id=73 AAPL) + row BLOCK legitime (id=71 ETH)")
print("-" * 78)
for rid in (73, 71):
    cur.execute("SELECT * FROM risk_pretrade_log WHERE id=?", (rid,))
    r = cur.fetchone()
    if not r:
        continue
    d = dict(r)
    print()
    print("  --- id=%s symbol=%s side=%s passed=%s ---" % (d.get("id"), d.get("symbol"), d.get("side"), d.get("passed")))
    print("  blocked_by  : %s" % d.get("blocked_by"))
    print("  marker      : %s" % d.get("marker"))
    dj = d.get("details_json") or ""
    if dj:
        try:
            j = json.loads(dj)
            print("  details_json :")
            print("    %s" % json.dumps(j, indent=2, ensure_ascii=False)[:1200])
        except Exception:
            print("  details_json (raw) : %s" % str(dj)[:600])

c.close()

# --- 3) Grep 'broker_mapping_ok' dans le code
print()
print("-" * 78)
print("GREP 'broker_mapping_ok' / 'broker_mapping' dans .py")
print("-" * 78)

for root, dirs, files in os.walk(PROD):
    # Skip workspace / .git / __pycache__
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "venv")]
    for f in files:
        if not f.endswith(".py"):
            continue
        # Skip backups
        if ".bak." in f:
            continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
        except Exception:
            continue
        if "broker_mapping_ok" in content or "broker_mapping" in content:
            for i, line in enumerate(content.split("\n"), 1):
                if "broker_mapping" in line:
                    rel = os.path.relpath(p, PROD)
                    print("  %s L%d : %s" % (rel, i, line.strip()[:160]))

print()
print("-" * 78)
print("GREP : ou est INSERT dans risk_pretrade_log")
print("-" * 78)
for root, dirs, files in os.walk(PROD):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules", ".venv", "venv")]
    for f in files:
        if not f.endswith(".py"):
            continue
        if ".bak." in f:
            continue
        p = os.path.join(root, f)
        try:
            with open(p, "r", encoding="utf-8-sig", errors="replace") as fh:
                content = fh.read()
        except Exception:
            continue
        if "risk_pretrade_log" in content and "INSERT" in content.upper():
            for i, line in enumerate(content.split("\n"), 1):
                if "risk_pretrade_log" in line:
                    rel = os.path.relpath(p, PROD)
                    print("  %s L%d : %s" % (rel, i, line.strip()[:160]))

print()
print("=" * 78)
print("DIAG TERMINE")
print("=" * 78)
