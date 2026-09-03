# -*- coding: utf-8 -*-
"""
Phase 2-bis : injecte les multiplicateurs market_regime (equity/crypto) dans
apply_regime_to_proposals() de execution_engine.py.

Strategie :
  1. Enrichir le cache positions avec asset_class (JOIN instruments deja present)
  2. Construire un cache ticker -> asset_class pour les BUY (proposals hors positions)
  3. Lire market_info = regime_info.get("market") (injecte par Phase 1)
  4. Appliquer mult sur max_sell_ratio (SELL) et max_overshoot (BUY) par asset_class
  5. Logger les compteurs dans le dict retourne

Marker idempotent : [PATCH_MARKET_REGIME_CAPS_V1]
Kill-switch : env NEXTONES_MARKET_REGIME_CAPS_DISABLE=1

Strict :
  - ASCII pur dans le code injecte
  - utf-8-sig en lecture, utf-8 sans BOM en ecriture
  - ast.parse + py_compile avant ecriture
  - Backup .bak.<timestamp>
"""
import ast
import os
import py_compile
import re
import shutil
import sys
import time

ROOT = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(ROOT, "execution_engine.py")
MARKER = "[PATCH_MARKET_REGIME_CAPS_V1]"

# ----------------------------------------------------------------------
# Lecture
# ----------------------------------------------------------------------
if not os.path.isfile(EE):
    print(f"[ERR] {EE} introuvable")
    sys.exit(1)

with open(EE, "r", encoding="utf-8-sig") as f:
    src = f.read()

if MARKER in src:
    print(f"[SKIP] Marker {MARKER} deja present, patch deja applique. Rien a faire.")
    sys.exit(0)

# ----------------------------------------------------------------------
# Localisation des points d'injection
# ----------------------------------------------------------------------
lines = src.splitlines(keepends=True)

# 1) Trouver la ligne avec max_overshoot = MAX_OVERSHOOT_TARGET_MULT.get(...)
#    On injecte JUSTE APRES cette ligne :
#    - lecture market_info
#    - calculs market_buy_mult / market_sell_mult par asset_class
idx_overshoot = None
for i, line in enumerate(lines):
    if "max_overshoot = MAX_OVERSHOOT_TARGET_MULT.get(regime" in line:
        idx_overshoot = i
        break
if idx_overshoot is None:
    print("[ERR] Point d'injection 'max_overshoot = MAX_OVERSHOOT_TARGET_MULT' introuvable")
    sys.exit(2)

# 2) Trouver le SELECT i.ticker, p.quantity, p.current_price (cache positions)
#    On va remplacer pour ajouter i.asset_class
idx_select_positions = None
for i, line in enumerate(lines):
    if "SELECT i.ticker, p.quantity, p.current_price" in line:
        idx_select_positions = i
        break
if idx_select_positions is None:
    print("[ERR] Cache positions SELECT introuvable")
    sys.exit(3)

# 3) Trouver le dict-comp positions = {r["ticker"]: (float(r["quantity"]...)
idx_positions_dict = None
for i, line in enumerate(lines):
    if "positions = {r[\"ticker\"]: (float(r[\"quantity\"]" in line:
        idx_positions_dict = i
        break
if idx_positions_dict is None:
    print("[ERR] Construction dict positions introuvable")
    sys.exit(4)

# 4) Ligne du if SELL : if sell_ratio > max_sell_ratio:
idx_sell_check = None
for i, line in enumerate(lines):
    if "if sell_ratio > max_sell_ratio:" in line:
        idx_sell_check = i
        break
if idx_sell_check is None:
    print("[ERR] Branche SELL plafonnement introuvable")
    sys.exit(5)

# 5) new_qpct = held_pct_of_nav * max_sell_ratio
idx_sell_qpct = None
for i, line in enumerate(lines):
    if "new_qpct = held_pct_of_nav * max_sell_ratio" in line:
        idx_sell_qpct = i
        break
if idx_sell_qpct is None:
    print("[ERR] Ligne SELL new_qpct introuvable")
    sys.exit(6)

# 6) ceiling_w = target_w * max_overshoot
idx_buy_ceiling = None
for i, line in enumerate(lines):
    if "ceiling_w = target_w * max_overshoot" in line:
        idx_buy_ceiling = i
        break
if idx_buy_ceiling is None:
    print("[ERR] Ligne BUY ceiling_w introuvable")
    sys.exit(7)

# 7) capped_qty = max(1, int(held_qty * max_sell_ratio))
idx_capped_qty = None
for i, line in enumerate(lines):
    if "capped_qty = max(1, int(held_qty * max_sell_ratio))" in line:
        idx_capped_qty = i
        break
if idx_capped_qty is None:
    print("[ERR] Ligne capped_qty introuvable")
    sys.exit(8)

# 8) Lignes 'cap_reason = (f"SELL plafonne ...' et 'cap_reason = (f"BUY plafonne ...'
#    Pour les enrichir avec la mention du multiplicateur marche
idx_sell_cap_reason = None
idx_buy_cap_reason = None
for i, line in enumerate(lines):
    if 'cap_reason = (f"SELL plafonn' in line:
        idx_sell_cap_reason = i
    if 'cap_reason = (f"BUY plafonn' in line:
        idx_buy_cap_reason = i

# 9) Le return dict de la fonction (pour ajouter n_market_*)
#    Cherche return { puis "n_buy_capped"
idx_return_dict = None
for i, line in enumerate(lines):
    if '"n_buy_capped": n_buy_capped,' in line:
        idx_return_dict = i
        break
if idx_return_dict is None:
    print("[ERR] return dict introuvable")
    sys.exit(9)

print("[OK] Points d'injection identifies :")
print(f"  L{idx_select_positions+1}  SELECT positions")
print(f"  L{idx_positions_dict+1}  dict positions")
print(f"  L{idx_overshoot+1}  apres max_overshoot")
print(f"  L{idx_sell_check+1}  if sell_ratio > max_sell_ratio")
print(f"  L{idx_sell_qpct+1}  new_qpct SELL")
print(f"  L{idx_capped_qty+1}  capped_qty SELL")
print(f"  L{idx_buy_ceiling+1}  ceiling_w BUY")
print(f"  L{idx_return_dict+1}  return dict")
print()

# ----------------------------------------------------------------------
# Construction du nouveau source
# ----------------------------------------------------------------------
# Strategie : on modifie de la fin vers le debut pour ne pas casser les index.
new_lines = list(lines)

# (A) Ajouter compteurs au return dict (juste apres n_buy_capped)
return_line = new_lines[idx_return_dict]
indent_ret = return_line[: len(return_line) - len(return_line.lstrip())]
new_lines[idx_return_dict] = (
    return_line
    + indent_ret + f"# {MARKER} n_market_amplified / n_market_attenuated counters\n"
    + indent_ret + '"n_market_sell_amplified": n_market_sell_amplified,\n'
    + indent_ret + '"n_market_buy_attenuated": n_market_buy_attenuated,\n'
)

# (B) Remplacer ceiling_w pour multiplier par market_buy_mult par asset_class
old_buy_ceiling = new_lines[idx_buy_ceiling]
indent_buy = old_buy_ceiling[: len(old_buy_ceiling) - len(old_buy_ceiling.lstrip())]
new_lines[idx_buy_ceiling] = (
    indent_buy + f"# {MARKER} BUY market multiplier (equity vs crypto)\n"
    + indent_buy + "_ac_buy = _resolve_asset_class(ticker)\n"
    + indent_buy + "_mkt_buy_mult = _market_mult_for(_ac_buy, \"buy\")\n"
    + indent_buy + "ceiling_w = target_w * max_overshoot * _mkt_buy_mult\n"
    + indent_buy + "if abs(_mkt_buy_mult - 1.0) > 1e-9:\n"
    + indent_buy + "    n_market_buy_attenuated += 1\n"
)

# (C) Remplacer capped_qty pour utiliser max_sell_ratio * market_sell_mult
old_capped = new_lines[idx_capped_qty]
indent_cap = old_capped[: len(old_capped) - len(old_capped.lstrip())]
new_lines[idx_capped_qty] = (
    indent_cap + "capped_qty = max(1, int(held_qty * _eff_sell_ratio))\n"
)

# (D) Remplacer new_qpct = held_pct_of_nav * max_sell_ratio
old_new_qpct = new_lines[idx_sell_qpct]
indent_qpct = old_new_qpct[: len(old_new_qpct) - len(old_new_qpct.lstrip())]
new_lines[idx_sell_qpct] = (
    indent_qpct + "new_qpct = held_pct_of_nav * _eff_sell_ratio\n"
)

# (E) Avant le 'if sell_ratio > max_sell_ratio:' on calcule _eff_sell_ratio
old_sell_check = new_lines[idx_sell_check]
indent_sell_chk = old_sell_check[: len(old_sell_check) - len(old_sell_check.lstrip())]
new_lines[idx_sell_check] = (
    indent_sell_chk + f"# {MARKER} SELL market multiplier (equity vs crypto)\n"
    + indent_sell_chk + "_ac_sell = positions_ac.get(ticker) or _resolve_asset_class(ticker)\n"
    + indent_sell_chk + "_mkt_sell_mult = _market_mult_for(_ac_sell, \"sell\")\n"
    + indent_sell_chk + "_eff_sell_ratio = min(1.0, max_sell_ratio * _mkt_sell_mult)\n"
    + indent_sell_chk + "if abs(_mkt_sell_mult - 1.0) > 1e-9:\n"
    + indent_sell_chk + "    n_market_sell_amplified += 1\n"
    + indent_sell_chk + "if sell_ratio > _eff_sell_ratio:\n"
)

# (F) Apres la ligne max_overshoot = ..., on injecte :
#     - lecture market_info + flag kill-switch
#     - helpers _resolve_asset_class et _market_mult_for
#     - compteurs n_market_sell_amplified / n_market_buy_attenuated
old_overshoot = new_lines[idx_overshoot]
indent_os = old_overshoot[: len(old_overshoot) - len(old_overshoot.lstrip())]
inject_overshoot = (
    indent_os + f"# {MARKER} Market regime multipliers (equity vs crypto)\n"
    + indent_os + "import os as _os_mr\n"
    + indent_os + "_market_caps_disabled = _os_mr.environ.get(\"NEXTONES_MARKET_REGIME_CAPS_DISABLE\") == \"1\"\n"
    + indent_os + "_market_info = regime_info.get(\"market\") if isinstance(regime_info, dict) else None\n"
    + indent_os + "_market_ac_cache = {}\n"
    + indent_os + "n_market_sell_amplified = 0\n"
    + indent_os + "n_market_buy_attenuated = 0\n"
    + indent_os + "def _resolve_asset_class(tk):\n"
    + indent_os + "    if not tk:\n"
    + indent_os + "        return None\n"
    + indent_os + "    if tk in _market_ac_cache:\n"
    + indent_os + "        return _market_ac_cache[tk]\n"
    + indent_os + "    try:\n"
    + indent_os + "        _row = conn.execute(\n"
    + indent_os + "            \"SELECT asset_class FROM instruments WHERE ticker = ?\",\n"
    + indent_os + "            (tk,),\n"
    + indent_os + "        ).fetchone()\n"
    + indent_os + "        _ac = _row[0] if _row else None\n"
    + indent_os + "    except Exception:\n"
    + indent_os + "        _ac = None\n"
    + indent_os + "    _market_ac_cache[tk] = _ac\n"
    + indent_os + "    return _ac\n"
    + indent_os + "def _market_mult_for(asset_class, side):\n"
    + indent_os + "    if _market_caps_disabled or not _market_info or not asset_class:\n"
    + indent_os + "        return 1.0\n"
    + indent_os + "    _ac = (asset_class or \"\").lower()\n"
    + indent_os + "    if _ac in (\"crypto\",):\n"
    + indent_os + "        _bucket = _market_info.get(\"crypto\") or {}\n"
    + indent_os + "    elif _ac in (\"equity\", \"etf\", \"stock\"):\n"
    + indent_os + "        _bucket = _market_info.get(\"equity\") or {}\n"
    + indent_os + "    else:\n"
    + indent_os + "        return 1.0\n"
    + indent_os + "    if side == \"buy\":\n"
    + indent_os + "        try:\n"
    + indent_os + "            return float(_bucket.get(\"buy_mult\", 1.0))\n"
    + indent_os + "        except Exception:\n"
    + indent_os + "            return 1.0\n"
    + indent_os + "    if side == \"sell\":\n"
    + indent_os + "        try:\n"
    + indent_os + "            return float(_bucket.get(\"sell_mult\", 1.0))\n"
    + indent_os + "        except Exception:\n"
    + indent_os + "            return 1.0\n"
    + indent_os + "    return 1.0\n"
)
new_lines[idx_overshoot] = old_overshoot + inject_overshoot

# (G) Modifier le SELECT positions pour inclure i.asset_class
old_select = new_lines[idx_select_positions]
new_lines[idx_select_positions] = old_select.replace(
    "SELECT i.ticker, p.quantity, p.current_price",
    "SELECT i.ticker, p.quantity, p.current_price, i.asset_class"
)

# (H) Modifier le dict positions pour ajouter positions_ac
#     Le bloc s'etend sur plusieurs lignes (L296-298). On insere apres la fermeture.
#     On detecte la ligne contenant "for r in pos_rows}"
idx_positions_close = None
for i in range(idx_positions_dict, min(idx_positions_dict + 6, len(new_lines))):
    if "for r in pos_rows}" in new_lines[i]:
        idx_positions_close = i
        break
if idx_positions_close is None:
    print("[ERR] Fermeture dict positions introuvable")
    sys.exit(10)

close_line = new_lines[idx_positions_close]
# IMPORTANT : prendre l'indentation de la ligne 'positions = {' (debut du dict),
# pas celle de la ligne de fermeture qui est sur-indentee (alignee sur l'ouverture).
first_pos_line = new_lines[idx_positions_dict]
indent_pos = first_pos_line[: len(first_pos_line) - len(first_pos_line.lstrip())]
# Construction d'un dict ticker -> asset_class (best-effort)
new_lines[idx_positions_close] = (
    close_line
    + indent_pos + f"# {MARKER} positions_ac : ticker -> asset_class (best-effort)\n"
    + indent_pos + "positions_ac = {}\n"
    + indent_pos + "for r in pos_rows:\n"
    + indent_pos + "    try:\n"
    + indent_pos + "        positions_ac[r[\"ticker\"]] = r[\"asset_class\"]\n"
    + indent_pos + "    except Exception:\n"
    + indent_pos + "        pass\n"
)

# (I) Enrichir cap_reason SELL pour mentionner le multiplicateur si != 1
if idx_sell_cap_reason is not None:
    # On reecrit le calcul : on cherche la ligne avec max_sell_ratio*100 dans le f-string
    # et on remplace par _eff_sell_ratio*100 + on rajoute le mult dans le message
    old = new_lines[idx_sell_cap_reason]
    new_lines[idx_sell_cap_reason] = old.replace(
        "f\"SELL plafonn\\u00e9 a {max_sell_ratio*100:.0f} %\"",
        "f\"SELL plafonn\\u00e9 a {_eff_sell_ratio*100:.0f} %\""
    ).replace(
        "f\"SELL plafonn\xe9 \xe0 {max_sell_ratio*100:.0f} %\"",
        "f\"SELL plafonn\xe9 \xe0 {_eff_sell_ratio*100:.0f} %\""
    )

# (J) Enrichir cap_reason BUY pour utiliser le ceiling reel
if idx_buy_cap_reason is not None:
    old = new_lines[idx_buy_cap_reason]
    new_lines[idx_buy_cap_reason] = old.replace(
        "{max_overshoot:.2f}",
        "{max_overshoot*_mkt_buy_mult:.2f}"
    )

# ----------------------------------------------------------------------
# Concat + validation
# ----------------------------------------------------------------------
new_src = "".join(new_lines)

# Verif ASCII des INJECTIONS uniquement (le fichier hote peut contenir non-ASCII)
def _check_ascii(snippet, label):
    for i, ch in enumerate(snippet):
        if ord(ch) > 127:
            print(f"[ERR] Non-ASCII char dans {label} at pos {i}: U+{ord(ch):04X} ({ch!r})")
            sys.exit(20)

_check_ascii(inject_overshoot, "inject_overshoot")

# AST + py_compile
try:
    ast.parse(new_src)
    print("[OK] ast.parse passed")
except SyntaxError as e:
    print(f"[ERR] SyntaxError: {e}")
    # Dump du contexte autour
    err_lines = new_src.splitlines()
    a = max(0, (e.lineno or 1) - 5)
    b = min(len(err_lines), (e.lineno or 1) + 5)
    for k in range(a, b):
        print(f"  L{k+1:5} | {err_lines[k][:160]}")
    sys.exit(11)

# Backup + ecriture + py_compile
ts = time.strftime("%Y%m%d-%H%M%S")
backup = EE + f".bak.{ts}"
shutil.copyfile(EE, backup)
print(f"[OK] Backup -> {backup}")

with open(EE, "w", encoding="utf-8", newline="") as f:
    f.write(new_src)
print(f"[OK] {EE} reecrit ({len(new_src)} chars, {new_src.count(chr(10))} lignes)")

try:
    py_compile.compile(EE, doraise=True)
    print("[OK] py_compile passed")
except py_compile.PyCompileError as e:
    print(f"[ERR] py_compile failed: {e}")
    # rollback
    shutil.copyfile(backup, EE)
    print(f"[ROLLBACK] {EE} restaure depuis {backup}")
    sys.exit(12)

# ----------------------------------------------------------------------
# Verifs post-patch
# ----------------------------------------------------------------------
with open(EE, "r", encoding="utf-8-sig") as f:
    final = f.read()
n_marker = final.count(MARKER)
print(f"[OK] Marker {MARKER} present x{n_marker}")

print()
print("=" * 70)
print("PATCH PHASE 2-bis APPLIQUE")
print("=" * 70)
print(f"Marker         : {MARKER}")
print(f"Kill-switch    : NEXTONES_MARKET_REGIME_CAPS_DISABLE=1")
print(f"Backup         : {backup}")
print()
print("Effet :")
print("  BUY  : ceiling_w = target_w * max_overshoot * market_buy_mult")
print("         (CALM equity=0.7, NORMAL=1.0, STRESS=1.8 par asset_class)")
print("  SELL : eff_sell_ratio = min(1.0, max_sell_ratio * market_sell_mult)")
print("         (CALM=1.5, NORMAL=1.0, STRESS=0.5 par asset_class)")
print()
print("Compteurs ajoutes au return : n_market_sell_amplified, n_market_buy_attenuated")
print()
print("Prochaine etape : restart API + run cycle + verifier compteurs dans regime_log")
