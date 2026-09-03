# -*- coding: utf-8 -*-
# nextones-fix-memo-verdict-reason-v5b.py
# Marker : [MEMO_VERDICT_REASON_FIX_V5]
#
# v5b : version 100 percent ASCII (pas d apostrophe francaise, pas d accent)
# car v5 a casse sur Windows cp1252 (SyntaxError L87 : unterminated string).
#
# Logique :
#   - risk_v2.details est un dict vide
#   - risk_v2.details_json est une string JSON contenant le vrai motif
#   - On lit details_json en priorite, puis details en fallback
#   - Comme details_json est une STRING, on la parse en json avant humanize

import os
import sys
import ast
import json
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(PROD, "memo_generator.py")
MARKER = "[MEMO_VERDICT_REASON_FIX_V5]"

print()
print("=" * 72)
print("PATCH v5b : motif humain - lire details_json (string) + parse JSON")
print("-" * 72)

with open(MG, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if MARKER in content:
    print("  [SKIP] Marker v5 deja present")
    sys.exit(0)

lines = content.split("\n")

# --- Patch 1 : remplacer la ligne _details_for_humanize
# Comportement : prendre details_json en priorite (string JSON), parser,
# sinon fallback sur details (dict).
patch1_done = False
for i, line in enumerate(lines):
    if "_details_for_humanize" in line and "v2.get(" in line:
        indent = line[:len(line) - len(line.lstrip())]
        # On construit un bloc multi-lignes robuste
        block = [
            indent + "# " + MARKER,
            indent + "_raw_details_json = v2.get(\"details_json\") if isinstance(v2, dict) else None",
            indent + "_raw_details = v2.get(\"details\") if isinstance(v2, dict) else None",
            indent + "_details_for_humanize = {}",
            indent + "if _raw_details_json:",
            indent + "    try:",
            indent + "        _parsed = json.loads(_raw_details_json) if isinstance(_raw_details_json, str) else _raw_details_json",
            indent + "        if isinstance(_parsed, dict):",
            indent + "            _details_for_humanize = _parsed",
            indent + "    except Exception:",
            indent + "        _details_for_humanize = {}",
            indent + "if not _details_for_humanize and isinstance(_raw_details, dict):",
            indent + "    _details_for_humanize = _raw_details",
        ]
        print("  Patch 1 L%d AVANT : %s" % (i + 1, line.strip()[:180]))
        # Remplacer la ligne par le bloc
        lines[i:i+1] = block
        print("  Patch 1 : bloc multi-lignes insere (%d lignes)" % len(block))
        patch1_done = True
        break

if not patch1_done:
    print("  [KO] Patch 1 : ligne _details_for_humanize introuvable")
    sys.exit(2)

# --- S assurer que json est importe en haut du fichier
has_json_import = False
for ln in lines[:40]:
    if ln.strip() == "import json" or ln.strip().startswith("import json"):
        has_json_import = True
        break

if not has_json_import:
    # Inserer apres la 1ere ligne d import existante
    for i, ln in enumerate(lines):
        if ln.startswith("import ") or ln.startswith("from "):
            lines.insert(i, "import json  # " + MARKER)
            print("  Patch 1b : import json ajoute L%d" % (i + 1))
            break

# --- Patch 2 : enrichir _humanize_block_reason avec entrees forced_exit
patch2_done = False
for i, line in enumerate(lines):
    if "\"market_closed\"" in line and "Marche ferme" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_entries = [
            indent + "\"convergence_forced_exit\":       (\"Convergence forced exit\",",
            indent + "                                  \"Le moteur convergence a force la sortie sur ce ticker\"),",
            indent + "\"block_forced_exit\":             (\"Convergence forced exit\",",
            indent + "                                  \"Verdict V2 : forced_exit detecte par le moteur convergence\"),",
        ]
        end_market = i
        for j in range(i, min(len(lines), i + 5)):
            if "Hors plage" in lines[j] or "ferie NYSE" in lines[j]:
                end_market = j
                break
        for k, entry in enumerate(new_entries):
            lines.insert(end_market + 1 + k, entry)
        print("  Patch 2 : %d entrees ajoutees au dict HUMAN apres L%d" % (len(new_entries), end_market + 1))
        patch2_done = True
        break

if not patch2_done:
    print("  [WARN] Patch 2 : entree market_closed non trouvee (skip)")

new_content = "\n".join(lines)

# --- AST + py_compile
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s (L%s)" % (e, getattr(e, "lineno", "?")))
    err_l = getattr(e, "lineno", None)
    if err_l:
        new_lines_dump = new_content.split("\n")
        for k in range(max(0, err_l - 5), min(len(new_lines_dump), err_l + 5)):
            print("    L%d: %s" % (k + 1, new_lines_dump[k][:180].rstrip()))
    sys.exit(3)

ts = time.strftime("%Y%m%d_%H%M%S")
bak = MG + ".bak." + ts
shutil.copy2(MG, bak)
print("  Backup : %s" % os.path.basename(bak))

with open(MG, "w", encoding="utf-8", newline="") as fh:
    fh.write(new_content)

try:
    py_compile.compile(MG, doraise=True)
    print("  py_compile OK")
except py_compile.PyCompileError as e:
    shutil.copy2(bak, MG)
    print("  [KO] py_compile : %s -- restore" % e)
    sys.exit(4)

print()
print("=" * 72)
print("RECAP v5b")
print("-" * 72)
print("  - _details_for_humanize lit details_json (string) puis parse JSON")
print("  - Fallback sur details (dict) si details_json vide")
print("  - HUMAN dict enrichi : convergence_forced_exit + block_forced_exit")
print("  - import json garanti present")
print()
print("  Validation :")
print("    1. Restart API (uvicorn sur port 8000)")
print("    2. POST /api/orders/execute-cycle (cycle reel)")
print("    3. py -3.13 .\\nextones-check-memo-risk-section-v1.py")
print("       attendu : 'BLOCK - Non tradable (regle A)'")
print("=" * 72)
