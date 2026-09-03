#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch V4 backtest_engine.py - Revert equity V3 (garde crypto V2).

V3 a sur-resserre equity: Delta Max DD passe de -2.13% a 0%.
La V0 (vol_calm=15) etait mieux calibree pour SPY car les
drawdowns SPY 2025-2026 arrivent en vol stable (12-14%),
captures par vol_calm=15 mais pas vol_calm=10.

Fix:
  equity vol_calm:        10 -> 15 (restaure V0)
  equity vix_proxy_calm:  12 -> 15 (restaure V0)
  crypto: AUCUN changement (V2 conserve)

Marker: # [PATCH_BACKTEST_ENGINE_EQUITY_REVERT_V4]
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
MARKER_V3 = "# [PATCH_BACKTEST_ENGINE_EQUITY_THRESHOLDS_V3]"
MARKER_V4 = "# [PATCH_BACKTEST_ENGINE_EQUITY_REVERT_V4]"

print("=" * 70)
print("PATCH V4 backtest_engine.py - revert equity V3")
print("=" * 70)

if not os.path.isfile(TARGET):
    print("[ERR] introuvable:", TARGET)
    sys.exit(1)

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER_V3 not in src:
    print("[ERR] V3 non applique, abort (rien a revert)")
    sys.exit(1)

if MARKER_V4 in src:
    print("[SKIP] V4 deja applique, idempotent")
    sys.exit(0)

ts = time.strftime("%Y%m%d-%H%M%S")
bak = TARGET + ".bak." + ts
shutil.copy2(TARGET, bak)
print("[BACKUP]", bak)

lines = src.split("\n")

# ===== Patch 1: equity vol_calm 10 -> 15 =====
# V3 a ecrit: "vol_stress, vol_calm = 25.0, 10.0  # [PATCH_BACKTEST_ENGINE_EQUITY_THRESHOLDS_V3]"
old1 = "vol_stress, vol_calm = 25.0, 10.0  " + MARKER_V3
new1 = "vol_stress, vol_calm = 25.0, 15.0  " + MARKER_V4
idx1 = -1
for i, ln in enumerate(lines):
    if ln.strip() == old1:
        idx1 = i
        break
if idx1 < 0:
    print("[ERR] ligne V3 equity vol_calm=10 introuvable")
    sys.exit(1)
indent1 = lines[idx1][:len(lines[idx1]) - len(lines[idx1].lstrip())]
print("[ANCHOR-1] L" + str(idx1 + 1) + ":", lines[idx1].rstrip())
lines[idx1] = indent1 + new1
print("[PATCH-1]  L" + str(idx1 + 1) + ":", lines[idx1].rstrip())

# ===== Patch 2: vix_proxy_calm 12 -> 15 =====
old2 = "elif vix_proxy <= 12.0: n_calm += 1  " + MARKER_V3
new2 = "elif vix_proxy <= 15.0: n_calm += 1  " + MARKER_V4
idx2 = -1
for i, ln in enumerate(lines):
    if ln.strip() == old2:
        idx2 = i
        break
if idx2 < 0:
    print("[ERR] ligne V3 vix_proxy<=12 introuvable")
    sys.exit(1)
indent2 = lines[idx2][:len(lines[idx2]) - len(lines[idx2].lstrip())]
print("[ANCHOR-2] L" + str(idx2 + 1) + ":", lines[idx2].rstrip())
lines[idx2] = indent2 + new2
print("[PATCH-2]  L" + str(idx2 + 1) + ":", lines[idx2].rstrip())

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

print("[OK] marker:", MARKER_V4)
print()
print("Etat final des seuils:")
print("  EQUITY:")
print("    vol_stress=25, vol_calm=15 (V0 restaure)")
print("    dd_stress=-5, dd_calm=-2")
print("    vix_proxy_stress=25, vix_proxy_calm=15 (V0 restaure)")
print("  CRYPTO:")
print("    vol_stress=45, vol_calm=15 (V2 conserve)")
print("    dd_5j_stress=-8, dd_5j_calm=-3")
print("    dd_20j_stress=-15, dd_20j_calm=-3 (V1 conserve)")
print()
print("Attendu Equity Only 12 mois:")
print("  retour aux chiffres V0: CALM 211 / NORM 40 / STR 0")
print("  Delta Sharpe +0.30, Delta Max DD -2.13%")
print("Attendu Crypto Only 12 mois:")
print("  inchange vs V2: CALM 117 / NORM 216 / STR 33")
