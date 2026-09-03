"""
Localise app.js et verifie quel fichier contient le bloc [SHADOW_UI_V1].
Pas de modif, juste diag.
"""
import os
import sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MARK = "[SHADOW_UI_V1]"

candidates = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    # skip backups et venv
    dirnames[:] = [
        d for d in dirnames
        if not d.startswith(".")
        and d.lower() not in ("__pycache__", "node_modules", "venv", ".venv", "env", "backups", "backup")
    ]
    for fn in filenames:
        if fn == "app.js":
            full = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(full)
            except OSError:
                size = -1
            has_mark = False
            try:
                with open(full, "r", encoding="utf-8-sig", errors="replace") as f:
                    has_mark = MARK in f.read()
            except OSError:
                pass
            candidates.append((full, size, has_mark))

print("[INFO] app.js found:", len(candidates))
for full, size, has_mark in candidates:
    flag = "  <-- HAS [SHADOW_UI_V1]" if has_mark else ""
    print(f"  {full}  ({size} bytes){flag}")

if not candidates:
    print("[ERR] no app.js found anywhere under", ROOT)
    sys.exit(1)
