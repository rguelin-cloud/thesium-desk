# -*- coding: utf-8 -*-
# nextones-fix-sell-overshoot-cap-v1.py
# Marker : [SELL_OVERSHOOT_CAP_V1]
#
# Etape D : Cap qty SELL <= position detenue.
# - Si side == "sell" et held <= 0 : refus dur (no_position)
# - Si side == "sell" et quantity > held : on cappe a held (warning)
# - Le patch est insere DANS create_and_execute_order L1174, juste apres
#   la resolution du ticker via _rv2_ticker_row (L1196-1199), avant le
#   bloc RISK_V2.
#
# Ce patch utilise le helper get_position_qty() deja defini L1156.

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
EE = os.path.join(PROD, "execution_engine.py")
MARKER = "[SELL_OVERSHOOT_CAP_V1]"

print()
print("=" * 72)
print("PATCH : Cap qty SELL <= position detenue")
print("-" * 72)

with open(EE, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if MARKER in content:
    print("  [SKIP] Marker deja present")
    sys.exit(0)

lines = content.split("\n")

# ----------------------------------------------------------------------
# On cherche le premier "if _rv2_ticker:" apres "def create_and_execute_order"
# et on insere le bloc cap juste APRES la ligne de resolution
# (_rv2_ticker = ...) mais AVANT "if _rv2_ticker:".
# ----------------------------------------------------------------------
fn_start = None
for i, ln in enumerate(lines):
    if "def create_and_execute_order(" in ln:
        fn_start = i
        break

if fn_start is None:
    print("  [KO] create_and_execute_order introuvable")
    sys.exit(2)

print("  create_and_execute_order trouve L%d" % (fn_start + 1))

# Trouver la ligne "_rv2_ticker = _rv2_ticker_row[0] if _rv2_ticker_row else None"
target_line = None
for i in range(fn_start, min(fn_start + 120, len(lines))):
    if "_rv2_ticker =" in lines[i] and "_rv2_ticker_row" in lines[i] and "[0]" in lines[i]:
        target_line = i
        break

if target_line is None:
    print("  [KO] ligne resolution _rv2_ticker introuvable")
    sys.exit(3)

print("  Resolution _rv2_ticker trouvee L%d" % (target_line + 1))
print("    >> %s" % lines[target_line].strip()[:160])

# Determiner l indentation (celle de la ligne courante)
indent = lines[target_line][:len(lines[target_line]) - len(lines[target_line].lstrip())]
print("  Indentation utilisee : %d espaces" % len(indent))

# Bloc patch a inserer apres target_line
patch_block = [
    "",
    indent + "# " + MARKER,
    indent + "# Cap qty SELL <= position detenue (anti-overshoot construction)",
    indent + "if side and side.lower() == \"sell\" and _rv2_ticker:",
    indent + "    _cap_held = get_position_qty(conn, _rv2_ticker)",
    indent + "    if _cap_held <= 0:",
    indent + "        # Refus dur : pas de position a vendre",
    indent + "        if isinstance(risk_result, dict):",
    indent + "            risk_result[\"approved\"] = False",
    indent + "            risk_result[\"action\"] = \"rejected_no_position\"",
    indent + "            risk_result.setdefault(\"reasons\", []).append(",
    indent + "                \"[CAP_SELL] no position to sell (held=0)\"",
    indent + "            )",
    indent + "        quantity = 0",
    indent + "    elif quantity > _cap_held:",
    indent + "        _cap_original = quantity",
    indent + "        quantity = _cap_held",
    indent + "        if isinstance(risk_result, dict):",
    indent + "            risk_result.setdefault(\"warnings\", []).append({",
    indent + "                \"source\": \"[CAP_SELL]\",",
    indent + "                \"code\": \"sell_overshoot_capped\",",
    indent + "                \"details\": {",
    indent + "                    \"original_qty\": _cap_original,",
    indent + "                    \"held\": _cap_held,",
    indent + "                    \"capped_to\": _cap_held,",
    indent + "                },",
    indent + "            })",
    "",
]

# Inserer apres target_line
for k, entry in enumerate(patch_block):
    lines.insert(target_line + 1 + k, entry)

print("  Patch insere apres L%d (%d lignes)" % (target_line + 1, len(patch_block)))

new_content = "\n".join(lines)

# ----------------------------------------------------------------------
# Validation AST + py_compile
# ----------------------------------------------------------------------
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s (L%s)" % (e, getattr(e, "lineno", "?")))
    err_l = getattr(e, "lineno", None)
    if err_l:
        nl = new_content.split("\n")
        for k in range(max(0, err_l - 5), min(len(nl), err_l + 5)):
            print("    L%d: %s" % (k + 1, nl[k][:180].rstrip()))
    sys.exit(4)

ts = time.strftime("%Y%m%d_%H%M%S")
bak = EE + ".bak." + ts
shutil.copy2(EE, bak)
print("  Backup : %s" % os.path.basename(bak))

with open(EE, "w", encoding="utf-8", newline="") as fh:
    fh.write(new_content)

try:
    py_compile.compile(EE, doraise=True)
    print("  py_compile OK")
except py_compile.PyCompileError as e:
    shutil.copy2(bak, EE)
    print("  [KO] py_compile : %s -- restore" % e)
    sys.exit(5)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  - SELL avec held=0 : refus dur (rejected_no_position)")
print("  - SELL avec qty > held : capped a held + warning [CAP_SELL]")
print("  - Le ticker est resolu via _rv2_ticker (deja present pour RISK_V2)")
print("  - Helper get_position_qty(conn, ticker) deja defini L1156")
print()
print("  Validation :")
print("    1. Restart API (uvicorn port 8000)")
print("    2. Cycle reel et observer les orders SELL ZEC")
print("    3. py -3.13 .\\nextones-validate-sell-cap-v1.py")
print("=" * 72)
