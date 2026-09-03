# -*- coding: utf-8 -*-
"""
Fix bug : apiFetch() retourne deja l'objet JSON parse, pas une Response.
Patch JS : remplace les 2 lignes "var perfResp = ..." + "var perf = await perfResp.json()"
par un seul appel direct "var perf = await apiFetch(...)".
Idempotent via marker [SHADOW_UI_V1_FIX_APIFETCH].
"""
import os
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_FIX = "/* [SHADOW_UI_V1_FIX_APIFETCH] */"

OLD = (
    '      var perfResp = await apiFetch("/api/shadow/perf-rolling?window=30");\n'
    '      var perf = await perfResp.json();'
)
NEW = (
    '      ' + MARK_FIX + '\n'
    '      var perf = await apiFetch("/api/shadow/perf-rolling?window=30");'
)

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

print("File size :", len(src))

if MARK_FIX in src:
    print("[SKIP] marker fix deja present")
elif OLD not in src:
    print("[ERR] bloc OLD introuvable - dump des lignes contenant perfResp :")
    for i, line in enumerate(src.split("\n"), 1):
        if "perfResp" in line:
            print("  L{} | {}".format(i, line.rstrip()))
else:
    bak = JS + ".bak." + TS
    shutil.copy2(JS, bak)
    print("[BAK]", bak)
    new = src.replace(OLD, NEW, 1)
    with open(JS, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("[OK] JS patche, delta={} chars".format(len(new) - len(src)))
    print("[INFO] count marker fix:", new.count(MARK_FIX))
    print("[INFO] count perfResp restant (doit etre 0):", new.count("perfResp"))

print()
print("Next : Ctrl+Shift+R sur navigateur, onglet Backtest, bouton Rafraichir")
print("DONE")
