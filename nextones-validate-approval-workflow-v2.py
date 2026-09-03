# -*- coding: utf-8 -*-
# [VALIDATE_APPROVAL_WORKFLOW_V2]
# Verifie patches Option A avec chemins UI corriges (racine ThesiumDesk).
# ASCII pur, Windows-safe.

import io
import os
import sys
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
    "app.js": [
        "[PATCH_UI_PENDING_APPROVALS_V2]",
        "renderPendingApprovals",
        "pa-list",
    ],
    "index.html": [
        "[PATCH_UI_PENDING_APPROVALS_V2]",
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
    print("VALIDATE APPROVAL WORKFLOW V2")
    print("=" * 78)

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

    print("\n--- 2) Distribution status orders ---")
    for r in con.execute(
        "SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY COUNT(*) DESC"
    ).fetchall():
        print("  status={0} : {1}".format(r[0], r[1]))

    print("\n--- 3) Orders approved (cible card UI) ---")
    rows = con.execute(
        "SELECT id, instrument_id, side, quantity, status, cycle_id, created_at "
        "FROM orders WHERE status = 'approved' ORDER BY id DESC LIMIT 10"
    ).fetchall()
    if not rows:
        print("  (aucun order en status='approved' - normal si cycle MAINTAIN sans proposal)")
    for r in rows:
        print("  ", r)

    con.close()

    print("\n--- 4) Markers dans les fichiers patches ---")
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

    print("\n--- 5) HTTP endpoints (localhost:8000) ---")
    base = "http://127.0.0.1:8000"
    for path in ["/api/orders/pending_approval"]:
        code, body = http_get(base + path)
        snippet = (body[:300] + "...") if body and len(body) > 300 else body
        print("  GET {0} -> {1}".format(path, code))
        print("    body:", snippet)

    print("\n--- 6) UI : assets servis ---")
    for path in ["/index.html", "/app.js"]:
        code, body = http_get(base + path)
        size = len(body) if body else 0
        has_pa = ("PATCH_UI_PENDING_APPROVALS_V2" in body) if body else False
        print("  GET {0} -> {1} size={2} pa_marker={3}".format(path, code, size, has_pa))

    print("\n" + "=" * 78)
    print("VERDICT:", "ALL OK" if all_ok else "SOME PATCHES MISSING")
    print("=" * 78)


if __name__ == "__main__":
    main()
