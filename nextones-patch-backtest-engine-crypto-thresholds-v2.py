#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch V2 backtest_engine.py - Resserre vol_calm crypto 25 -> 15.

Probleme V1: vol_calm=25% trop haut pour crypto -> 139 jours CALM,
PM perd l'upside du bull market.

Fix: vol_calm=15% (vrai calme rare en crypto), garde vol_stress=45,
dd_long_stress=-15. Resultat attendu: CALM ~30, NORMAL ~280, STRESS ~50.

Marker: # [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V2]
Idempotent + backup .bak.<timestamp>
"""
import ast
import io
import os
import py_compile
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(ROOT, "backtest_engine.py")
MARKER_V1 = "# [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V1]"
MARKER_V2 = "# [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V2]"

print("=" * 70)
print("PATCH V2 backtest_engine.py - vol_calm crypto 25 -> 15")
print("=" * 70)

if not os.path.isfile(TARGET):
    print("[ERR] introuvable:", TARGET)
    sys.exit(1)

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER_V1 not in src:
    print("[ERR] V1 non applique, abort")
    sys.exit(1)

if MARKER_V2 in src:
    print("[SKIP] V2 deja applique, idempotent")
    sys.exit(0)

# Backup
ts = time.strftime("%Y%m%d-%H%M%S")
bak = TARGET + ".bak." + ts
shutil.copy2(TARGET, bak)
print("[BACKUP]", bak)

lines = src.split("\n")

# Cherche la ligne exacte du V1
# V1 a ecrit: "        vol_stress, vol_calm = 45.0, 25.0  # [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V1]"
old_str = "vol_stress, vol_calm = 45.0, 25.0  " + MARKER_V1
new_str = "vol_stress, vol_calm = 45.0, 15.0  " + MARKER_V2

idx = -1
for i, ln in enumerate(lines):
    if ln.strip() == old_str:
        idx = i
        break

if idx < 0:
    print("[ERR] ligne V1 vol_calm=25 introuvable")
    # Diag
    for i, ln in enumerate(lines):
        if "vol_stress, vol_calm" in ln and "crypto" not in ln.lower():
            print("  L" + str(i+1) + ":", ln.rstrip())
    sys.exit(1)

print("[ANCHOR] L" + str(idx + 1) + ":", lines[idx].rstrip())

# Preserve indentation
indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
lines[idx] = indent + new_str

print("[PATCH]   L" + str(idx + 1) + ":", lines[idx].rstrip())

new_src = "\n".join(lines)

try:
    ast.parse(new_src)
    print("[VALIDATE] ast.parse: OK")
except SyntaxError as e:
    print("[ERR] AST:", e)
    sys.exit(1)

with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_src)

try:
    py_compile.compile(TARGET, doraise=True)
    print("[VALIDATE] py_compile: OK")
except py_compile.PyCompileError as e:
    print("[ERR] py_compile:", e)
    shutil.copy2(bak, TARGET)
    sys.exit(1)

print("[OK] marker:", MARKER_V2)
print()
print("Changement: vol_calm crypto 25.0 -> 15.0")
print("Attendu: CALM ~30 (au lieu de 139), STRESS ~50 (au lieu de 33)")
print("Delta Sharpe et Delta Max DD devraient repasser en positif")
