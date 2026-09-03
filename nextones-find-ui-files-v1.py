# -*- coding: utf-8 -*-
# [FIND_UI_FILES_V1]
# Localise les fichiers index.html et app.js reellement servis par
# api_server_with_static. Inspecte StaticFiles mounts dans le code et liste
# les .html / .js dans ThesiumDesk (limite 2 niveaux de profondeur).

import io
import os
import re
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
API = os.path.join(ROOT, "api_server_with_static.py")


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def main():
    print("=" * 78)
    print("FIND UI FILES V1")
    print("=" * 78)

    # 1) Inspect api_server_with_static : StaticFiles, mount, FileResponse
    print("\n--- 1) StaticFiles / mount / FileResponse dans api_server ---")
    src = read_text(API)
    patterns = [
        r"StaticFiles\([^)]*\)",
        r"app\.mount\([^)]*\)",
        r"FileResponse\([^)]*\)",
        r"directory\s*=\s*[\"'][^\"']+[\"']",
        r"\"static[^\"]*\"|'static[^']*'",
    ]
    for pat in patterns:
        rx = re.compile(pat)
        for m in rx.finditer(src):
            # Find line number
            line_no = src[:m.start()].count("\n") + 1
            print("  L{0:5d}: {1}".format(line_no, m.group(0)[:160]))

    # 2) List all .html and .js in tree (depth <= 3)
    print("\n--- 2) Liste fichiers .html / .js (depth <= 3) ---")
    for root, dirs, files in os.walk(ROOT):
        rel = os.path.relpath(root, ROOT)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 3:
            dirs[:] = []
            continue
        # Skip backup / cache dirs
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", "venv", ".venv")]
        for fn in files:
            if fn.endswith(".html") or fn.endswith(".js"):
                full = os.path.join(root, fn)
                try:
                    size = os.path.getsize(full)
                except Exception:
                    size = -1
                rel_full = os.path.relpath(full, ROOT)
                # Skip backups
                if ".bak." in fn:
                    continue
                print("  {0:>10}  {1}".format(size, rel_full))

    # 3) Identify the index.html most likely served : check for 'Nextones' keyword
    print("\n--- 3) index.html candidats (recherche 'Nextones' ou 'dashboard') ---")
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", "venv", ".venv")]
        for fn in files:
            if fn.lower() == "index.html":
                full = os.path.join(root, fn)
                try:
                    txt = read_text(full)
                    has_nx = "Nextones" in txt or "nextones" in txt
                    has_db = "dashboard" in txt.lower()
                    has_pa = "pending-approvals-card" in txt
                    print("  {0}  Nextones={1} dashboard={2} pa-card={3}".format(
                        os.path.relpath(full, ROOT), has_nx, has_db, has_pa))
                except Exception as e:
                    print("  ", full, "ERR", e)

    # 4) Identify app.js
    print("\n--- 4) app.js candidats (recherche 'renderKPIs' ou 'apiFetch') ---")
    for root, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "node_modules", "venv", ".venv")]
        for fn in files:
            if fn.lower() == "app.js":
                full = os.path.join(root, fn)
                try:
                    txt = read_text(full)
                    has_kpis = "renderKPIs" in txt
                    has_api = "apiFetch" in txt
                    has_pa = "renderPendingApprovals" in txt
                    print("  {0}  renderKPIs={1} apiFetch={2} pa={3}".format(
                        os.path.relpath(full, ROOT), has_kpis, has_api, has_pa))
                except Exception as e:
                    print("  ", full, "ERR", e)


if __name__ == "__main__":
    main()
