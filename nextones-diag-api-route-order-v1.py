# -*- coding: utf-8 -*-
# [DIAG_API_ROUTE_ORDER_V1]
# Verifie l'ordre dans api_server_with_static.py :
#   - position du app.mount("/", StaticFiles) (catch-all)
#   - position des @app.get/post nouvellement ajoutees par PATCH_API_ORDERS_APPROVAL_V1
# Si les routes patchees sont APRES le mount, FastAPI les ignore -> 404.
# Liste aussi toutes les routes enregistrees dans l'app live via /openapi.json.

import io
import os
import re
import urllib.request
import json

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def main():
    src = read_text(API)
    lines = src.splitlines()

    print("=" * 78)
    print("DIAG API ROUTE ORDER V1")
    print("=" * 78)

    # 1) Position du mount
    print("\n--- 1) app.mount(...) positions ---")
    mount_lines = []
    for i, ln in enumerate(lines, 1):
        if "app.mount(" in ln:
            mount_lines.append(i)
            print("  L{0:5d}: {1}".format(i, ln.strip()[:150]))

    # 2) Position du marker PATCH
    print("\n--- 2) Marker PATCH_API_ORDERS_APPROVAL_V1 ---")
    patch_lines = []
    for i, ln in enumerate(lines, 1):
        if "PATCH_API_ORDERS_APPROVAL_V1" in ln:
            patch_lines.append(i)
            print("  L{0:5d}: {1}".format(i, ln.strip()[:150]))

    # 3) Toutes les routes @app.get / @app.post
    print("\n--- 3) Routes @app.get / @app.post ---")
    rx = re.compile(r"@app\.(get|post|put|delete|patch)\s*\(\s*[\"']([^\"']+)[\"']")
    for i, ln in enumerate(lines, 1):
        m = rx.search(ln)
        if m:
            print("  L{0:5d}: @app.{1}  {2}".format(i, m.group(1), m.group(2)))

    # 4) Verdict
    print("\n--- 4) Verdict ---")
    if mount_lines and patch_lines:
        last_mount = max(mount_lines)
        first_patch = min(patch_lines)
        print("  Last mount L: {0}".format(last_mount))
        print("  First patch L: {0}".format(first_patch))
        if first_patch > last_mount:
            print("  [BUG] Les routes patches sont APRES le mount StaticFiles -> FastAPI les ignore.")
            print("  Solution : deplacer le bloc PATCH_API_ORDERS_APPROVAL_V1 AVANT app.mount.")
        else:
            print("  [OK] Les routes patches sont AVANT le mount.")
    else:
        print("  Donnees incompletes (mount={0}, patch={1})".format(
            len(mount_lines), len(patch_lines)))

    # 5) Routes live dans openapi.json
    print("\n--- 5) Routes enregistrees dans l'app live (openapi.json) ---")
    try:
        with urllib.request.urlopen("http://127.0.0.1:8000/openapi.json", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        paths = sorted(data.get("paths", {}).keys())
        targets = ["/api/orders/pending_approval", "/api/orders/{order_id}/execute",
                   "/api/orders/{order_id}/reject"]
        print("  Total routes:", len(paths))
        for t in targets:
            present = t in paths
            sym = "[OK]" if present else "[MISSING]"
            print("  {0} {1}".format(sym, t))
        # Liste toutes les routes /api/orders/*
        print("\n  Routes /api/orders/* live:")
        for p in paths:
            if p.startswith("/api/orders"):
                print("   ", p)
    except Exception as e:
        print("  openapi.json error:", e)


if __name__ == "__main__":
    main()
