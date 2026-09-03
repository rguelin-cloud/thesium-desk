#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch backtest_engine.py - Recalibre seuils crypto dans _compute_regime_overlay()

Changements:
  1. crypto vol_stress 30->45, vol_calm 20->25
  2. ajoute 3eme signal crypto: drawdown long 20j (dd_long_stress=-15, dd_long_calm=-3)
  3. _rolling_metrics() retourne aussi dd_20j
  4. _classify() crypto consomme dd_long si fourni

Marker: # [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V1]
Idempotent + backup .bak.<timestamp>
ASCII pur, validation AST+py_compile avant ecriture.
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
MARKER = "# [PATCH_BACKTEST_ENGINE_CRYPTO_THRESHOLDS_V1]"

print("=" * 70)
print("PATCH backtest_engine.py - SEUILS CRYPTO V1")
print("=" * 70)

if not os.path.isfile(TARGET):
    print("[ERR] introuvable:", TARGET)
    sys.exit(1)

with io.open(TARGET, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print("[SKIP] marker deja present, idempotent")
    sys.exit(0)

# Backup
ts = time.strftime("%Y%m%d-%H%M%S")
bak = TARGET + ".bak." + ts
shutil.copy2(TARGET, bak)
print("[BACKUP]", bak)

lines = src.split("\n")

# ===== ANCRE 1: _classify signature + crypto thresholds =====
# Cherche la ligne exacte "def _classify(vol_pct, dd_pct, vix_proxy, asset_class):"
idx_classify = -1
for i, ln in enumerate(lines):
    if ln.strip() == "def _classify(vol_pct, dd_pct, vix_proxy, asset_class):":
        idx_classify = i
        break

if idx_classify < 0:
    print("[ERR] _classify introuvable")
    sys.exit(1)
print("[ANCHOR-1] _classify L" + str(idx_classify + 1))

# Cherche les 2 lignes thresholds crypto dans les ~6 lignes suivantes
idx_vol_crypto = -1
idx_dd_crypto = -1
for j in range(idx_classify + 1, min(idx_classify + 15, len(lines))):
    s = lines[j].strip()
    if s == "vol_stress, vol_calm = 30.0, 20.0":
        idx_vol_crypto = j
    if s == "dd_stress, dd_calm = -8.0, -3.0":
        idx_dd_crypto = j

if idx_vol_crypto < 0 or idx_dd_crypto < 0:
    print("[ERR] thresholds crypto introuvables")
    print("  idx_vol_crypto =", idx_vol_crypto)
    print("  idx_dd_crypto =", idx_dd_crypto)
    sys.exit(1)
print("[ANCHOR-2] vol_crypto L" + str(idx_vol_crypto + 1))
print("[ANCHOR-3] dd_crypto L" + str(idx_dd_crypto + 1))

# ===== ANCRE 2: _classify signature - on ajoute parametre dd_long_pct =====
# On modifie:
#   def _classify(vol_pct, dd_pct, vix_proxy, asset_class):
# en:
#   def _classify(vol_pct, dd_pct, vix_proxy, asset_class, dd_long_pct=None):
new_classify_sig = "    def _classify(vol_pct, dd_pct, vix_proxy, asset_class, dd_long_pct=None):"
# Detecte indentation reelle
indent = lines[idx_classify][:len(lines[idx_classify]) - len(lines[idx_classify].lstrip())]
new_classify_sig = indent + "def _classify(vol_pct, dd_pct, vix_proxy, asset_class, dd_long_pct=None):"

# ===== Reconstruction =====
# 1. Remplace signature _classify
# 2. Remplace thresholds crypto vol et dd
# 3. Apres le bloc crypto thresholds, on injecte le 3eme signal (dd_long)
# 4. Apres "elif dd_pct >= dd_calm: n_calm += 1" du bloc crypto, ajouter check dd_long

# Trouve l'indentation des thresholds (interieur _classify, niveau 2 = 8 espaces typiquement)
ind_thr = lines[idx_vol_crypto][:len(lines[idx_vol_crypto]) - len(lines[idx_vol_crypto].lstrip())]

# Nouvelles lignes pour crypto thresholds (juste apres le if asset_class == 'crypto':)
new_vol_crypto = ind_thr + "vol_stress, vol_calm = 45.0, 25.0  " + MARKER
new_dd_crypto = ind_thr + "dd_stress, dd_calm = -8.0, -3.0"
new_dd_long_crypto = ind_thr + "dd_long_stress, dd_long_calm = -15.0, -3.0"

# Pour equity (sinon branche), on ajoute aussi dd_long = None par defaut (pas utilise pour equity)
# Trouve la ligne equity correspondante
idx_vol_equity = -1
for j in range(idx_dd_crypto + 1, min(idx_dd_crypto + 8, len(lines))):
    if lines[j].strip() == "vol_stress, vol_calm = 25.0, 15.0":
        idx_vol_equity = j
        break
if idx_vol_equity < 0:
    print("[ERR] vol equity introuvable")
    sys.exit(1)
print("[ANCHOR-4] vol_equity L" + str(idx_vol_equity + 1))

# Trouve la ligne "elif dd_pct >= dd_calm: n_calm += 1" (pour inserer le 3eme signal apres)
idx_dd_check_end = -1
for j in range(idx_vol_equity, min(idx_vol_equity + 30, len(lines))):
    if lines[j].strip().startswith("elif dd_pct >= dd_calm"):
        idx_dd_check_end = j
        break
if idx_dd_check_end < 0:
    print("[ERR] dd_check_end introuvable")
    sys.exit(1)
print("[ANCHOR-5] dd_check_end L" + str(idx_dd_check_end + 1))

# Indent interieur du if asset_class != 'crypto' / vix block (bloc vix proxy)
# On veut inserer notre check dd_long juste apres "elif dd_pct >= dd_calm: n_calm += 1"
# Au meme niveau d'indentation que "if vol_pct is not None"
idx_vix_block = -1
for j in range(idx_dd_check_end + 1, min(idx_dd_check_end + 10, len(lines))):
    if "asset_class != 'crypto'" in lines[j]:
        idx_vix_block = j
        break
if idx_vix_block < 0:
    print("[ERR] vix_block introuvable")
    sys.exit(1)
print("[ANCHOR-6] vix_block L" + str(idx_vix_block + 1))

ind_check = lines[idx_vix_block][:len(lines[idx_vix_block]) - len(lines[idx_vix_block].lstrip())]
ind_inner = ind_check + "    "

# Bloc dd_long a inserer JUSTE APRES idx_dd_check_end (avant idx_vix_block)
dd_long_block_lines = [
    ind_check + "if asset_class == 'crypto' and dd_long_pct is not None:  " + MARKER,
    ind_inner + "if dd_long_pct <= dd_long_stress: n_stress += 1",
    ind_inner + "elif dd_long_pct >= dd_long_calm: n_calm += 1",
]

# ===== ANCRE 3: _rolling_metrics - retourner aussi dd_20j =====
# Cherche "def _rolling_metrics"
idx_rm = -1
for i, ln in enumerate(lines):
    if "def _rolling_metrics" in ln:
        idx_rm = i
        break
if idx_rm < 0:
    print("[ERR] _rolling_metrics introuvable")
    sys.exit(1)
print("[ANCHOR-7] _rolling_metrics L" + str(idx_rm + 1))

# Cherche la ligne "return vol_ann, dd" dans _rolling_metrics
idx_rm_return = -1
for j in range(idx_rm, min(idx_rm + 40, len(lines))):
    if lines[j].strip() == "return vol_ann, dd":
        idx_rm_return = j
        break
if idx_rm_return < 0:
    print("[ERR] return vol_ann, dd introuvable")
    sys.exit(1)
print("[ANCHOR-8] return L" + str(idx_rm_return + 1))

# Avant ce return, on insere calcul dd_20j
# Indent du return
ind_rm_ret = lines[idx_rm_return][:len(lines[idx_rm_return]) - len(lines[idx_rm_return].lstrip())]
dd_long_calc_lines = [
    ind_rm_ret + "# dd long 20j (pour signal crypto)  " + MARKER,
    ind_rm_ret + "dd_long_window = prices_list[-min(21, len(prices_list)):]",
    ind_rm_ret + "peak_long = max(dd_long_window) if dd_long_window else 0.0",
    ind_rm_ret + "last_long = dd_long_window[-1] if dd_long_window else 0.0",
    ind_rm_ret + "dd_long = ((last_long - peak_long) / peak_long) * 100.0 if peak_long > 0 else 0.0",
]
new_rm_return = ind_rm_ret + "return vol_ann, dd, dd_long"

# ===== ANCRE 4: appels a _rolling_metrics + _classify dans la boucle principale =====
# Cherche "vol_c, dd_c = _rolling_metrics(cr_prices"
idx_call_cr = -1
for i, ln in enumerate(lines):
    if "vol_c, dd_c = _rolling_metrics(cr_prices" in ln:
        idx_call_cr = i
        break
if idx_call_cr < 0:
    print("[ERR] appel _rolling_metrics crypto introuvable")
    sys.exit(1)
print("[ANCHOR-9] appel cr L" + str(idx_call_cr + 1))

idx_call_eq = -1
for i, ln in enumerate(lines):
    if "vol_e, dd_e = _rolling_metrics(eq_prices" in ln:
        idx_call_eq = i
        break
if idx_call_eq < 0:
    print("[ERR] appel _rolling_metrics equity introuvable")
    sys.exit(1)
print("[ANCHOR-10] appel eq L" + str(idx_call_eq + 1))

# Cherche les appels a _classify
idx_classify_eq = -1
idx_classify_cr = -1
for i, ln in enumerate(lines):
    if "eq_reg = _classify(vol_e, dd_e, vix_proxy, 'equity')" in ln:
        idx_classify_eq = i
    if "cr_reg = _classify(vol_c, dd_c, None, 'crypto')" in ln:
        idx_classify_cr = i
if idx_classify_eq < 0 or idx_classify_cr < 0:
    print("[ERR] appels _classify introuvables")
    sys.exit(1)
print("[ANCHOR-11] _classify eq L" + str(idx_classify_eq + 1))
print("[ANCHOR-12] _classify cr L" + str(idx_classify_cr + 1))

# Indents
ind_eq = lines[idx_call_eq][:len(lines[idx_call_eq]) - len(lines[idx_call_eq].lstrip())]
ind_cr = lines[idx_call_cr][:len(lines[idx_call_cr]) - len(lines[idx_call_cr].lstrip())]
ind_cls_eq = lines[idx_classify_eq][:len(lines[idx_classify_eq]) - len(lines[idx_classify_eq].lstrip())]
ind_cls_cr = lines[idx_classify_cr][:len(lines[idx_classify_cr]) - len(lines[idx_classify_cr].lstrip())]

new_call_eq = ind_eq + "vol_e, dd_e, dd_e_long = _rolling_metrics(eq_prices[:i + 1], 20, 5)"
new_call_cr = ind_cr + "vol_c, dd_c, dd_c_long = _rolling_metrics(cr_prices[:i + 1], 20, 5)"
new_classify_eq = ind_cls_eq + "eq_reg = _classify(vol_e, dd_e, vix_proxy, 'equity')"
new_classify_cr = ind_cls_cr + "cr_reg = _classify(vol_c, dd_c, None, 'crypto', dd_long_pct=dd_c_long)"

# ===== Construction de la nouvelle source - en ordre decroissant =====
# Pour eviter de decaler les indices, on patche les indices du plus grand au plus petit

# 1. Remplace appels _classify (lignes seules)
lines[idx_classify_cr] = new_classify_cr
lines[idx_classify_eq] = new_classify_eq

# 2. Remplace appels _rolling_metrics
lines[idx_call_cr] = new_call_cr
lines[idx_call_eq] = new_call_eq

# 3. _rolling_metrics: remplace return, insere calcul dd_20j AVANT
lines[idx_rm_return] = new_rm_return
# Insertion avant idx_rm_return
for k, blk_line in enumerate(dd_long_calc_lines):
    lines.insert(idx_rm_return + k, blk_line)
# (idx_rm_return n'est plus correct apres insertion, mais on l'utilise plus)

# 4. _classify - inserer bloc dd_long apres idx_dd_check_end (idx pas encore decale car en amont)
# WARNING: dd_long_calc_lines a deja decale les indices, mais idx_dd_check_end < idx_rm_return ?
# Verifions: _classify est avant _rolling_metrics ? 
# Diag montre: _classify L448 et _rolling_metrics L468 -> oui, _classify avant
# Donc nos insertions dans _rolling_metrics (apres L468) ne decalent PAS idx_dd_check_end
# OK, on continue

# Insere bloc dd_long apres idx_dd_check_end
for k, blk_line in enumerate(dd_long_block_lines):
    lines.insert(idx_dd_check_end + 1 + k, blk_line)

# 5. Remplace les thresholds crypto (idx pas decale car en amont du point 4 d'insertion qui est apres)
# Re-verif: idx_dd_check_end > idx_dd_crypto donc insertion en aval, OK
lines[idx_dd_crypto] = new_dd_crypto
lines[idx_vol_crypto] = new_vol_crypto

# 6. Insertion 3eme threshold crypto (dd_long_stress/calm) JUSTE APRES dd_crypto
lines.insert(idx_dd_crypto + 1, new_dd_long_crypto)

# 7. Remplace signature _classify
lines[idx_classify] = new_classify_sig

# ===== Validation AST + py_compile =====
new_src = "\n".join(lines)

try:
    ast.parse(new_src)
    print("[VALIDATE] ast.parse: OK")
except SyntaxError as e:
    print("[ERR] AST:", e)
    sys.exit(1)

# Ecriture
with io.open(TARGET, "w", encoding="utf-8", newline="\n") as f:
    f.write(new_src)

try:
    py_compile.compile(TARGET, doraise=True)
    print("[VALIDATE] py_compile: OK")
except py_compile.PyCompileError as e:
    print("[ERR] py_compile:", e)
    print("[ROLLBACK] restoring backup...")
    shutil.copy2(bak, TARGET)
    sys.exit(1)

if MARKER in new_src:
    print("[OK] marker ecrit:", MARKER)
print("[WRITE]", TARGET, "(lignes:", len(lines), ")")
print()
print("Recap modifs:")
print("  - crypto vol_stress/calm: 30/20 -> 45/25")
print("  - crypto dd_stress/calm: -8/-3 (inchange)")
print("  - crypto NOUVEAU signal dd_long 20j: stress=-15, calm=-3")
print("  - _rolling_metrics retourne (vol_ann, dd_5j, dd_20j)")
print("  - _classify accepte dd_long_pct optionnel, utilise pour crypto uniquement")
print("  - equity: AUCUN changement")
