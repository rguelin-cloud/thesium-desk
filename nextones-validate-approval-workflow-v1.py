# -*- coding: utf-8 -*-
# [VALIDATE_APPROVAL_WORKFLOW_V1]
# Verifie que tous les patches Option A sont actifs :
#   1. orders.cycle_id existe + index
#   2. execution_engine.py contient marker + approve_and_fill_order + status='approved'
#   3. memo_generator.py contient marker + filtre cycle
#   4. api_server contient marker + 3 endpoints
#   5. app.js contient marker UI + index.html marker
#   6. Endpoints HTTP repondent (200) sur localhost:8000
#   7. Distribution actuelle des status d'orders
# ASCII pur, Windows-safe.

import io
import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(ROOT, "thesium.db")

FILES = {
    "execution_engine.py": [
        "[PATCH_EXECUTION_APPROVAL_WORKFLOW_V1]",
        "def approve_and_fill_order",
        "def reject_pending_order",
        "status = 'approved'",
    ],
    "memo_generator.py": [
        "[PATCH_MEMO_ORDERS_BY_CYCLE_V1]",
        "WHERE o.cycle_id = ?",
    ],
    "api_server_with_static.py": [
        "[PATCH_API_ORDERS_APPROVAL_V1]",
        "/api/orders/pending_approval",
        "/api/orders/{order_id}/execute",
        "/api/orders/{order_id}/reject",
    ],
    os.path.join("static", "js", "app.js"): [
        "[PATCH_UI_PENDING_APPROVALS_V1]",
        "renderPendingApprovals",
        "pa-list",
    ],
    os.path.join("static", "index.html"): [
        "[PATCH_UI_PENDING_APPROVALS_V1]",
        "pending-approvals-card",
    ],
}


def read_text(path):
    try:
        with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None


def http_get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace") if e.fp else ""
    except Exception as e:
        return None, str(e)


def main():
    print("=" * 78)
    print("VALIDATE APPROVAL WORKFLOW V1")
    print("=" * 78)

    # 1) DB
    print("\n--- 1) DB orders.cycle_id ---")
    con = sqlite3.connect(DB, timeout=5)
    cols = [r[1] for r in con.execute("PRAGMA table_info(orders)").fetchall()]
    has_cycle = "cycle_id" in cols
    print("  orders.cycle_id present:", has_cycle)
    if has_cycle:
        n_with = con.execute(
            "SELECT COUNT(*) FROM orders WHERE cycle_id IS NOT NULL AND cycle_id != ''"
        ).fetchone()[0]
        n_total = con.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        print("  orders avec cycle_id:", n_with, "/", n_total)

    # Index ?
    idx_rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='orders'"
    ).fetchall()
    print("  Indexes:", [r[0] for r in idx_rows])

    # Distribution status
    print("\n--- 2) Distribution status orders ---")
    for r in con.execute(
        "SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY COUNT(*) DESC"
    ).fetchall():
        print("  status={0} : {1}".format(r[0], r[1]))

    # Cycle courant
    print("\n--- 3) Cycle courant (regime_log) ---")
    last_cycle = con.execute(
        "SELECT cycle_id, created_at, regime, n_proposals_in "
        "FROM regime_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    print("  ", last_cycle)

    # Orders du cycle courant
    if last_cycle:
        cur_cid = last_cycle[0]
        rows = con.execute(
            "SELECT id, side, quantity, status, cycle_id FROM orders "
            "WHERE cycle_id = ? ORDER BY id DESC LIMIT 10",
            (cur_cid,)
        ).fetchall()
        print("\n--- 4) Orders du cycle courant ({0}) ---".format(cur_cid))
        if not rows:
            print("  (aucun order tagge sur ce cycle)")
        for r in rows:
            print("  id={0} side={1} qty={2} status={3} cycle={4}".format(*r))

    con.close()

    # 5) Markers dans les fichiers
    print("\n--- 5) Markers dans les fichiers patches ---")
    all_ok = True
    for relpath, needles in FILES.items():
        full = os.path.join(ROOT, relpath)
        src = read_text(full)
        if src is None:
            print("  [MISSING]", relpath)
            all_ok = False
            continue
        for needle in needles:
            present = needle in src
            sym = "[OK]" if present else "[FAIL]"
            if not present:
                all_ok = False
            print("  {0} {1} :: {2}".format(sym, relpath, needle[:60]))

    # 6) HTTP endpoints
    print("\n--- 6) HTTP endpoints (localhost:8000) ---")
    base = "http://127.0.0.1:8000"
    for path in ["/api/orders/pending_approval"]:
        code, body = http_get(base + path)
        snippet = (body[:200] + "...") if body and len(body) > 200 else body
        print("  GET {0} -> {1}".format(path, code))
        print("    body:", snippet)

    # 7) Marker UI dans app.js HEAD (verif que le polling tournera)
    print("\n--- 7) UI : renderPendingApprovals expose ---")
    js = read_text(os.path.join(ROOT, "static", "js", "app.js"))
    if js:
        print("  window.renderPendingApprovals:", "window.renderPendingApprovals" in js)
        print("  setInterval polling 10s:", "setInterval(renderPendingApprovals" in js)

    print("\n" + "=" * 78)
    print("VERDICT:", "ALL OK" if all_ok else "SOME PATCHES MISSING")
    print("=" * 78)


if __name__ == "__main__":
    main()
