# -*- coding: utf-8 -*-
# [DIAG_PA_BLOCK_DETAIL_V1]
# Dump complet du bloc [PATCH_UI_PENDING_APPROVALS_V2] dans app.js
# pour identifier la ligne qui lit result.portfolio.xxx
import io, os, sys

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def read(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

src = read(os.path.join(ROOT, "app.js"))
lines = src.splitlines()

# Trouver bornes du bloc
start = end = -1
for i, ln in enumerate(lines, 1):
    if "[PATCH_UI_PENDING_APPROVALS_V2]" in ln and "[/PATCH" not in ln:
        start = i
    if "[/PATCH_UI_PENDING_APPROVALS_V2]" in ln:
        end = i
        break

if start < 0 or end < 0:
    print("FAIL: bornes du bloc introuvables")
    sys.exit(1)

print("Bloc app.js L%d - L%d" % (start, end))
print("=" * 70)
# Encoder UTF-8 force pour la sortie (sinon cp1252 plante sur fleches)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for i in range(start - 1, end):
    print("L%04d: %s" % (i + 1, lines[i]))
print("=" * 70)
print("[DONE]")
