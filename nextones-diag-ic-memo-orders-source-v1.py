# -*- coding: utf-8 -*-
# [DIAG_IC_MEMO_ORDERS_SOURCE_V1]
# Identifier d'ou vient le tableau "Proposed Changes & Executions" du memo IC
# qui affiche 10 ordres filled+approved alors que l'utilisateur n'a rien approuve.
#
# 1) Dump orders #322-#342 : status reel, cycle_id, created_at, executed_at
# 2) Count par status (pending_validation, approved, filled, rejected)
# 3) Trouver dans le code la SQL/section qui genere "Proposed Changes & Executions"
# 4) Identifier les chemins qui inserent status='filled' SANS passer par pending_validation

import sqlite3
from pathlib import Path
import os, re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = BASE / "thesium.db"

# ====================================================================
print("=" * 70)
print("1. orders #322-#342 : detail")
print("=" * 70)
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, instrument_id, side, quantity, status, fill_price, "
    "       slippage, cycle_id, created_at, executed_at, risk_notes "
    "FROM orders WHERE id BETWEEN 320 AND 345 ORDER BY id"
).fetchall()
if not rows:
    print("  (aucun ordre dans cette plage)")
else:
    for r in rows:
        d = dict(r)
        print("  #" + str(d.get("id")) +
              " instr=" + str(d.get("instrument_id")) +
              " " + str(d.get("side")) +
              " qty=" + str(d.get("quantity")) +
              " status=" + str(d.get("status")) +
              " cycle=" + str(d.get("cycle_id")) +
              " created=" + str(d.get("created_at")) +
              " executed=" + str(d.get("executed_at")) +
              " notes=" + str(d.get("risk_notes"))[:50])

# ====================================================================
print()
print("=" * 70)
print("2. orders : count par status (today + total)")
print("=" * 70)
print("  Total :")
for r in conn.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status"):
    print("    " + str(r["status"]) + " : " + str(r["n"]))
print("  Today (created_at LIKE '2026-06-10%' OR '2026-06-11%') :")
for r in conn.execute(
    "SELECT status, COUNT(*) AS n FROM orders "
    "WHERE substr(created_at,1,10) IN ('2026-06-10','2026-06-11') "
    "GROUP BY status"
):
    print("    " + str(r["status"]) + " : " + str(r["n"]))

# ====================================================================
print()
print("=" * 70)
print("3. Dernier cycle : cycle_id, regime_log")
print("=" * 70)
try:
    last_cycle = conn.execute(
        "SELECT cycle_id, created_at FROM regime_log ORDER BY id DESC LIMIT 3"
    ).fetchall()
    for r in last_cycle:
        print("  cycle_id=" + str(r["cycle_id"]) + " created=" + str(r["created_at"]))
except Exception as e:
    print("  ERR : " + str(e))

# ====================================================================
print()
print("=" * 70)
print("4. Orders du dernier cycle (cycle_id le plus recent)")
print("=" * 70)
try:
    latest_cid = conn.execute("SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
    if latest_cid:
        cid = latest_cid["cycle_id"]
        print("  cycle_id = " + str(cid))
        rows = conn.execute(
            "SELECT id, instrument_id, side, quantity, status, fill_price, created_at "
            "FROM orders WHERE cycle_id = ? ORDER BY id",
            (cid,)
        ).fetchall()
        if not rows:
            print("  (aucun ordre pour ce cycle)")
        for r in rows:
            d = dict(r)
            print("  #" + str(d["id"]) +
                  " instr=" + str(d["instrument_id"]) +
                  " " + str(d["side"]) +
                  " qty=" + str(d["quantity"]) +
                  " status=" + str(d["status"]) +
                  " price=" + str(d["fill_price"]) +
                  " created=" + str(d["created_at"]))
except Exception as e:
    print("  ERR : " + str(e))

conn.close()

# ====================================================================
print()
print("=" * 70)
print("5. Code : qui genere 'Proposed Changes & Executions' ?")
print("=" * 70)
keywords = ["Proposed Changes", "proposed_changes", "Proposed Changes & Executions",
            "proposed changes", "Order ID", "RISK NOTES", "execution_summary"]
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and "backup" not in d.lower()]
    for fn in files:
        if not (fn.endswith(".py") or fn.endswith(".html") or fn.endswith(".js") or fn.endswith(".md")):
            continue
        if ".bak." in fn:
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, "rb") as f:
                content = f.read()
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for kw in keywords:
            if kw in text:
                # Print toutes les lignes contenant kw
                for i, line in enumerate(text.splitlines(), 1):
                    if kw in line:
                        rel = os.path.relpath(fp, BASE)
                        print("  " + rel + ":L" + str(i) + " [" + kw + "] " + line.strip()[:120])
                break  # un seul kw par fichier dans le print pour eviter pollution

# ====================================================================
print()
print("=" * 70)
print("6. Chemins qui ecrivent status='filled' SANS pending_validation")
print("=" * 70)
patterns = [
    re.compile(r"status\s*=\s*['\"]filled['\"]"),
    re.compile(r"set\s+status\s*=\s*['\"]filled['\"]", re.IGNORECASE),
    re.compile(r"INSERT INTO orders.*filled", re.IGNORECASE | re.DOTALL),
    re.compile(r"\"filled\"|'filled'"),
]
for root, dirs, files in os.walk(BASE):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__" and "backup" not in d.lower()]
    for fn in files:
        if not fn.endswith(".py") or ".bak." in fn:
            continue
        fp = os.path.join(root, fn)
        try:
            with open(fp, "rb") as f:
                content = f.read()
            if content.startswith(b"\xef\xbb\xbf"):
                content = content[3:]
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "filled" in line and ("status" in line.lower() or "INSERT" in line.upper() or "UPDATE" in line.upper()):
                rel = os.path.relpath(fp, BASE)
                print("  " + rel + ":L" + str(i) + " : " + line.strip()[:130])

print()
print("DONE [DIAG_IC_MEMO_ORDERS_SOURCE_V1]")
