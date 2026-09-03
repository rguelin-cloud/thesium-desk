"""
Fix: Shadow UI memo modal - cache key bug
=========================================

Symptome: quelque soit le badge Shadow Variant clique, le modal affiche
toujours le meme memo (celui du dernier variant: defensive_crypto).

Cause: dans le bloc IIFE [SHADOW_UI_V1] de app.js, on utilise `r.id` comme
cle de cache:
    shadowRowsCache[r.id] = r;
    recoBadge(r.recommendation, r.id, hasMemo)

Mais les rows JSON renvoyees par /api/shadow/perf-rolling n'ont PAS de
champ `id`. La cle primaire est `variant_id` (table shadow_variants).
Donc shadowRowsCache[undefined] = r pour les 4 rows, le dernier ecrase
tous les autres -> tous les clics ouvrent le memo de defensive_crypto.

Fix: remplacer `r.id` par `r.variant_id` aux 2 endroits dans le bloc
SHADOW_UI_V1 de app.js.

Idempotent via marker [SHADOW_UI_V1_FIX_CACHE_KEY].
"""

import os
import re
import shutil
import time
import sys

UI = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
MARK_BEGIN = "// [SHADOW_UI_V1] BEGIN"
MARK_END = "// [SHADOW_UI_V1] END"
MARK_FIX = "// [SHADOW_UI_V1_FIX_CACHE_KEY]"
TS = time.strftime("%Y%m%d_%H%M%S")


def main():
    if not os.path.exists(UI):
        print("[ERR] file not found:", UI)
        return 2

    with open(UI, "r", encoding="utf-8-sig", errors="replace") as f:
        src = f.read()

    if MARK_FIX in src:
        print("[SKIP] fix already applied (marker present)")
        return 0

    if MARK_BEGIN not in src or MARK_END not in src:
        print("[ERR] SHADOW_UI_V1 block markers not found")
        return 3

    i_begin = src.index(MARK_BEGIN)
    i_end = src.index(MARK_END, i_begin) + len(MARK_END)
    block = src[i_begin:i_end]

    # Compte les occurrences avant patch
    count_cache = block.count("shadowRowsCache[r.id]")
    count_badge = len(re.findall(r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,", block))
    print("[INFO] occurrences shadowRowsCache[r.id]:", count_cache)
    print("[INFO] occurrences recoBadge(...r.id...):", count_badge)

    if count_cache == 0 and count_badge == 0:
        print("[ERR] no occurrence of r.id found in block - aborting")
        return 4

    # Patch 1: shadowRowsCache[r.id] -> shadowRowsCache[r.variant_id]
    new_block = block.replace(
        "shadowRowsCache[r.id]",
        "shadowRowsCache[r.variant_id]",
    )

    # Patch 2: recoBadge(r.recommendation, r.id, ...) -> r.variant_id
    new_block = re.sub(
        r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,",
        "recoBadge(r.recommendation, r.variant_id,",
        new_block,
    )

    # Sanity check post-patch
    if "shadowRowsCache[r.id]" in new_block:
        print("[ERR] post-patch: shadowRowsCache[r.id] still present")
        return 5
    if re.search(r"recoBadge\(\s*r\.recommendation\s*,\s*r\.id\s*,", new_block):
        print("[ERR] post-patch: recoBadge(...r.id...) still present")
        return 6
    if "shadowRowsCache[r.variant_id]" not in new_block:
        print("[ERR] post-patch: shadowRowsCache[r.variant_id] not present")
        return 7

    # Inject marker fix (en commentaire JS) juste apres MARK_BEGIN
    new_block = new_block.replace(
        MARK_BEGIN,
        MARK_BEGIN + "\n" + MARK_FIX + " " + TS,
        1,
    )

    new_src = src[:i_begin] + new_block + src[i_end:]

    if new_src == src:
        print("[ERR] no change produced")
        return 8

    bak = UI + ".bak." + TS
    shutil.copy2(UI, bak)
    print("[BAK]", bak)

    with open(UI, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)
    print("[OK] written:", UI)
    print("[OK] patched shadowRowsCache:", count_cache, "occurrence(s)")
    print("[OK] patched recoBadge:", count_badge, "occurrence(s)")
    print("[NEXT] Ctrl+Shift+R dans le navigateur puis clic sur chaque badge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
