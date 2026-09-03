# -*- coding: utf-8 -*-
# [DIAG_IC_MEMO_ORDERS_SOURCE_V2]
# v2 : decouvre d'abord le schema orders puis adapte les SELECT (SELECT *)

import sqlite3
from pathlib import Path
import os, re

BASE = Path(r"C:\Users\RichardGUELIN\Prod\ThesiumDesk")
DB = BASE / "thesium.db"

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# ====================================================================
print("=" * 70)
print("0. Schema orders")
print("=" * 70)
cols = conn.execute("PRAGMA table_info(orders)").fetchall()
col_names = [c["name"] for c in cols]
for c in cols:
    print("  " + c["name"] + " (" + c["type"] + ")")

# ====================================================================
print()
print("=" * 70)
print("1. orders #322-#342 : detail (SELECT *)")
print("=" * 70)
rows = conn.execute("SELECT * FROM orders WHERE id BETWEEN 320 AND 345 ORDER BY id").fetchall()
if not rows:
    print("  (aucun ordre dans cette plage)")
for r in rows:
    d = dict(r)
    print("  #" + str(d.get("id")) + " " + str({k: v for k, v in d.items() if v is not None})[:300])

# ====================================================================
print()
print("=" * 70)
print("2. orders : count par status (total + today)")
print("=" * 70)
print("  Total :")
for r in conn.execute("SELECT status, COUNT(*) AS n FROM orders GROUP BY status"):
    print("    " + str(r["status"]) + " : " + str(r["n"]))
date_col = "created_at" if "created_at" in col_names else ("executed_at" if "executed_at" in col_names else None)
if date_col:
    print("  Today (" + date_col + ") :")
    for r in conn.execute(
        f"SELECT status, COUNT(*) AS n FROM orders "
        f"WHERE substr({date_col},1,10) IN ('2026-06-10','2026-06-11') "
        f"GROUP BY status"
    ):
        print("    " + str(r["status"]) + " : " + str(r["n"]))

# ====================================================================
print()
print("=" * 70)
print("3. Dernier cycle : cycle_id, regime_log")
print("=" * 70)
try:
    last_cycle = conn.execute(
        "SELECT cycle_id, created_at FROM regime_log ORDER BY id DESC LIMIT 5"
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
    latest = conn.execute("SELECT cycle_id FROM regime_log ORDER BY id DESC LIMIT 1").fetchone()
    if latest:
        cid = latest["cycle_id"]
        print("  cycle_id = " + str(cid))
        if "cycle_id" in col_names:
            rows = conn.execute("SELECT * FROM orders WHERE cycle_id = ? ORDER BY id", (cid,)).fetchall()
        else:
            print("  (orders n'a pas de colonne cycle_id)")
            rows = []
        if not rows:
            print("  (aucun ordre pour ce cycle)")
        for r in rows:
            d = dict(r)
            print("  #" + str(d.get("id")) + " " + str({k: v for k, v in d.items() if v is not None})[:300])
except Exception as e:
    print("  ERR : " + str(e))

# ====================================================================
print()
print("=" * 70)
print("5. Top 20 derniers orders (DESC) - tous status confondus")
print("=" * 70)
order_by = "id DESC"
rows = conn.execute(f"SELECT * FROM orders ORDER BY {order_by} LIMIT 20").fetchall()
for r in rows:
    d = dict(r)
    print("  #" + str(d.get("id")) + " " + str({k: v for k, v in d.items() if v is not None})[:300])

conn.close()

# ====================================================================
print()
print("=" * 70)
print("6. Code : qui genere 'Proposed Changes & Executions' ?")
print("=" * 70)
keywords = ["Proposed Changes", "proposed_changes", "Proposed Changes & Executions",
            "RISK NOTES", "execution_summary", "scaled_down"]
seen_files = set()
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
                for i, line in enumerate(text.splitlines(), 1):
                    if kw in line:
                        rel = os.path.relpath(fp, BASE)
                        print("  " + rel + ":L" + str(i) + " [" + kw + "] " + line.strip()[:130])

# ====================================================================
print()
print("=" * 70)
print("7. Chemins qui ecrivent status='filled'")
print("=" * 70)
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
            l = line.strip()
            if "'filled'" in l or "\"filled\"" in l:
                if "status" in l.lower() or "INSERT" in l.upper() or "UPDATE" in l.upper() or "SET " in l.upper():
                    rel = os.path.relpath(fp, BASE)
                    print("  " + rel + ":L" + str(i) + " : " + l[:130])

print()
print("DONE [DIAG_IC_MEMO_ORDERS_SOURCE_V2]")
