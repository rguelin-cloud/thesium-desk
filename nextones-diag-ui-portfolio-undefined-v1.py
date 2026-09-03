# -*- coding: utf-8 -*-
# [DIAG_UI_PORTFOLIO_UNDEFINED_V1]
# Trouve dans app.js (et index.html) la ligne qui lit result.portfolio.xxx
# pour les boutons Execute / Reject.
import io, os, re

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

def read(p):
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()

# 1) app.js : chercher patch UI v2 et acces .portfolio
for fname in ("app.js", "index.html"):
    fp = os.path.join(ROOT, fname)
    if not os.path.exists(fp):
        continue
    src = read(fp)
    print("=" * 70)
    print(fname + " : recherche acces .portfolio + endpoints execute/reject")
    print("=" * 70)
    for i, ln in enumerate(src.splitlines(), 1):
        if ".portfolio" in ln or "/execute" in ln or "/reject" in ln or "PATCH_UI_PENDING_APPROVALS" in ln or "executeOrder" in ln or "rejectOrder" in ln:
            print("  L%d: %s" % (i, ln.strip()[:160]))
    print()

print("[DONE]")
