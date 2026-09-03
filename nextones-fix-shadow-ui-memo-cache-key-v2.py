"""
Fix v2: Shadow UI memo modal - cache key bug
============================================

Diag confirme:
- L7481: shadowRowsCache[r.id] = r;
- L7492: ... recoBadge(r.recommendation, r.id, hasMemo) ...
- markers reels: /* [SHADOW_UI_V1] BEGIN */ ... /* [SHADOW_UI_V1] END */
  (C-style, pas //)

Strategie: remplacement de chaines textuelles uniques dans tout le fichier.
- "shadowRowsCache[r.id]" apparait 1 seule fois -> safe
- "recoBadge(r.recommendation, r.id, hasMemo)" apparait 1 seule fois -> safe

Les 2 autres r.id (L6121 risk-card, L6430 risks.find) sont sur un domaine
different (risks) et ne sont PAS touches.

Idempotent via marker /* [SHADOW_UI_V1_FIX_CACHE_KEY] */ insere apres
/* [SHADOW_UI_V1] BEGIN */.
"""

import os
import shutil
import time
import sys

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
MARK_BEGIN = "/* [SHADOW_UI_V1] BEGIN */"
MARK_FIX = "/* [SHADOW_UI_V1_FIX_CACHE_KEY] */"
TS = time.strftime("%Y%m%d_%H%M%S")

OLD1 = "shadowRowsCache[r.id] = r;"
NEW1 = "shadowRowsCache[r.variant_id] = r;"

OLD2 = "recoBadge(r.recommendation, r.id, hasMemo)"
NEW2 = "recoBadge(r.recommendation, r.variant_id, hasMemo)"


def main():
    if not os.path.exists(UI):
        print("[ERR] file not found:", UI)
        return 2

    with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_FIX in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    if MARK_BEGIN not in src:
        print("[ERR] BEGIN marker not found:", MARK_BEGIN)
        return 3

    c1 = src.count(OLD1)
    c2 = src.count(OLD2)
    print("[INFO] occurrences OLD1 (shadowRowsCache[r.id]):", c1)
    print("[INFO] occurrences OLD2 (recoBadge ...):", c2)

    if c1 != 1:
        print("[ERR] expected exactly 1 occurrence of OLD1, got", c1)
        return 4
    if c2 != 1:
        print("[ERR] expected exactly 1 occurrence of OLD2, got", c2)
        return 5

    new_src = src.replace(OLD1, NEW1, 1).replace(OLD2, NEW2, 1)

    # Sanity post-patch
    if OLD1 in new_src:
        print("[ERR] post-patch: OLD1 still present")
        return 6
    if OLD2 in new_src:
        print("[ERR] post-patch: OLD2 still present")
        return 7
    if NEW1 not in new_src:
        print("[ERR] post-patch: NEW1 not present")
        return 8
    if NEW2 not in new_src:
        print("[ERR] post-patch: NEW2 not present")
        return 9

    # Inject marker fix juste apres MARK_BEGIN (sur sa propre ligne)
    new_src = new_src.replace(
        MARK_BEGIN,
        MARK_BEGIN + "\n" + MARK_FIX + " /* " + TS + " */",
        1,
    )

    if new_src == src:
        print("[ERR] no change produced")
        return 10

    bak = UI + ".bak." + TS
    shutil.copy2(UI, bak)
    print("[BAK]", bak)

    with open(UI, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("[OK] written:", UI)
    print("[OK] patched shadowRowsCache: 1 occurrence")
    print("[OK] patched recoBadge: 1 occurrence")
    print("[NEXT] Ctrl+Shift+R puis clic sur chaque badge -> 4 memos differents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
