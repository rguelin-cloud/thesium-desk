#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch V3 backtest_engine.py - Resserre seuils CALM equity.

Probleme: vol_calm=15% trop haut pour SPY (qui tourne 10-14% en bull normal)
-> 211 jours CALM / 251 -> overlay plafonne l'upside.

Fix:
  equity vol_calm: 15 -> 10 (vrai calme rare)
  equity vix_proxy_calm: 15 -> 12 (coherent)
  Garde vol_stress=25, dd inchanges.

Marker: # [PATCH_BACKTEST_ENGINE_EQUITY_THRESHOLDS_V3]
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
MARKER_V3 = "# [PATCH_BACKTEST_ENGINE_EQUITY_THRESHOLDS_V3]"

print("=" * 70)
print("PATCH V3 backtest_engine.py - seuils CALM equity resserres")
print("=" * 70)

if not os.path.isfile(TARGET):
    print("[ERR] introuvable:", TARGET)
    sys.exit(1)

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER_V1 not in src:
    print("[ERR] V1 non applique, abort")
    sys.exit(1)

if MARKER_V3 in src:
    print("[SKIP] V3 deja applique, idempotent")
    sys.exit(0)

ts = time.strftime("%Y%m%d-%H%M%S")
bak = TARGET + ".bak." + ts
shutil.copy2(TARGET, bak)
print("[BACKUP]", bak)

lines = src.split("\n")

# ===== Patch 1: equity vol_stress, vol_calm = 25.0, 15.0  ->  25.0, 10.0 =====
old1 = "vol_stress, vol_calm = 25.0, 15.0"
new1 = "vol_stress, vol_calm = 25.0, 10.0  " + MARKER_V3
idx1 = -1
for i, ln in enumerate(lines):
    if ln.strip() == old1:
        idx1 = i
        break
if idx1 < 0:
    print("[ERR] ligne equity vol_calm=15 introuvable")
    sys.exit(1)
indent1 = lines[idx1][:len(lines[idx1]) - len(lines[idx1].lstrip())]
print("[ANCHOR-1] L" + str(idx1 + 1) + ":", lines[idx1].rstrip())
lines[idx1] = indent1 + new1
print("[PATCH-1]  L" + str(idx1 + 1) + ":", lines[idx1].rstrip())

# ===== Patch 2: vix_proxy seuil calm =====
# Ligne actuelle: "elif vix_proxy <= 15.0: n_calm += 1"
# Nouvelle:       "elif vix_proxy <= 12.0: n_calm += 1  # [...V3]"
old2 = "elif vix_proxy <= 15.0: n_calm += 1"
new2 = "elif vix_proxy <= 12.0: n_calm += 1  " + MARKER_V3
idx2 = -1
for i, ln in enumerate(lines):
    if ln.strip() == old2:
        idx2 = i
        break
if idx2 < 0:
    print("[ERR] ligne vix_proxy calm=15 introuvable")
    sys.exit(1)
indent2 = lines[idx2][:len(lines[idx2]) - len(lines[idx2].lstrip())]
print("[ANCHOR-2] L" + str(idx2 + 1) + ":", lines[idx2].rstrip())
lines[idx2] = indent2 + new2
print("[PATCH-2]  L" + str(idx2 + 1) + ":", lines[idx2].rstrip())

# ===== Note: vix_proxy = max(20d vol, 15.0) reste a 15 =====
# C'est un PLANCHER, pas un seuil de classification. On le laisse car
# si vol=8% (calme), vix_proxy=max(8,15)=15. Avec new seuil vix_calm=12,
# vix_proxy=15 NE declenche PAS calm signal. Donc seul vol_pct<=10
# pourra trigger calm (1 seul signal sur 3 -> NORMAL).
# Pour avoir CALM il faut: vol<=10 ET dd>=-2 (2 signaux sur 3 sans vix)
# C'est exactement ce qu'on veut: vrai calme rare.

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

print("[OK] marker:", MARKER_V3)
print()
print("Changements:")
print("  equity vol_calm:        15 -> 10")
print("  equity vix_proxy_calm:  15 -> 12")
print("  (vix_proxy floor=15 inchange, donc vix ne triggere plus jamais calm:")
print("   seul vol<=10 + dd>=-2 peut classer CALM -> exigeant)")
print()
print("Attendu sur Equity Only 12 mois:")
print("  CALM: 211 -> ~60-90")
print("  NORMAL: 40 -> ~160-190")
print("  STRESS: 0 -> 0 (pas de stress sur SPY 2025-2026)")
print("  Delta Sharpe: +0.30 -> +0.10 a +0.20 (moins de plafonnement)")
print("  Delta Max DD: -2.13% -> reste negatif (DD regime plus petit)")
