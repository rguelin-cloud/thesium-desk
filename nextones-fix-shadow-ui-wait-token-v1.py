# -*- coding: utf-8 -*-
"""
Fix UI : renderShadowVariants() etait appele AVANT que state.token soit hydrate.
Resultat : 401 sur le 1er appel auto au load.

Patch chirurgical : remplace le bloc d'auto-init dans le JS shadow_variants par :
  - Check state.token avant le 1er call
  - Si absent, retry 500ms plus tard (jusqu'a 5s)
  - Le bouton Rafraichir reste manuel
  - Le tab click hook reste OK

Idempotent via marker [SHADOW_UI_V1_FIX_WAIT_TOKEN].
"""
import os
import shutil
from datetime import datetime

JS = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\app.js"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
MARK_FIX = "/* [SHADOW_UI_V1_FIX_WAIT_TOKEN] */"

OLD = (
    "    if (document.querySelector('#tab-backtest.active') || (location.hash === \"#backtest\")){\n"
    "      renderShadowVariants();\n"
    "    }\n"
)

NEW = (
    "    " + MARK_FIX + "\n"
    "    function tryInitialLoad(attemptsLeft){\n"
    "      if (typeof state === 'undefined' || !state || !state.token){\n"
    "        if (attemptsLeft > 0){\n"
    "          setTimeout(function(){ tryInitialLoad(attemptsLeft - 1); }, 500);\n"
    "        }\n"
    "        return;\n"
    "      }\n"
    "      if (document.querySelector('#tab-backtest.active') || (location.hash === \"#backtest\")){\n"
    "        renderShadowVariants();\n"
    "      }\n"
    "    }\n"
    "    tryInitialLoad(10);\n"
)

with open(JS, "r", encoding="utf-8-sig", errors="replace") as f:
    src = f.read()

print("File size :", len(src))

if MARK_FIX in src:
    print("[SKIP] marker fix wait_token deja present")
elif OLD not in src:
    print("[ERR] bloc OLD introuvable - dump des lignes contenant 'tab-backtest.active' :")
    for i, line in enumerate(src.split("\n"), 1):
        if "tab-backtest.active" in line or "location.hash" in line:
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

print()
print("Next : Ctrl+Shift+R sur navigateur, onglet Backtest")
print("DONE")
