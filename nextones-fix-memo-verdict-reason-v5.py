# -*- coding: utf-8 -*-
# nextones-fix-memo-verdict-reason-v5.py
# Marker : [MEMO_VERDICT_REASON_FIX_V5]
#
# Apres diag : pour les ordres bloques par le broker, risk_v2.details = {}
# mais risk_v2.details_json contient la string JSON avec le vrai motif :
#   { "broker_mapping_ok": { "reason": "not_tradable_strict_refusal", ... } }
#
# Le V4 lit details (dict) -> vide -> fallback. C'etait l'inverse.
# v5 : lire details_json (string) PRIORITAIREMENT, et tomber sur details si vide.
#
# Egalement : enrichir _humanize_block_reason pour gerer aussi
# "convergence_forced_exit" et "block_forced_exit".

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(PROD, "memo_generator.py")
MARKER = "[MEMO_VERDICT_REASON_FIX_V5]"

print()
print("=" * 72)
print("PATCH v5 : motif humain - lire details_json (string)")
print("-" * 72)

with open(MG, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if MARKER in content:
    print("  [SKIP] Marker v5 deja present")
    sys.exit(0)

lines = content.split("\n")

# --- Patch 1 : remplacer la ligne _details_for_humanize
# Comportement : prendre details_json (string) en priorite, sinon details (dict)
patch1_done = False
for i, line in enumerate(lines):
    if "_details_for_humanize" in line and "v2.get(" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_line = indent + '_details_for_humanize = (v2.get("details_json") if isinstance(v2, dict) else None) or (v2.get("details") if isinstance(v2, dict) else None) or {}  # ' + MARKER
        print("  Patch 1 L%d AVANT : %s" % (i + 1, line.strip()[:180]))
        lines[i] = new_line
        print("  Patch 1 L%d APRES : %s" % (i + 1, new_line.strip()[:180]))
        patch1_done = True
        break

if not patch1_done:
    print("  [KO] Patch 1 : ligne _details_for_humanize introuvable")
    sys.exit(2)

# --- Patch 2 : enrichir _humanize_block_reason avec :
#   - "convergence_forced_exit" -> "Convergence forced exit"
#   - "block_forced_exit" -> idem (variante du verdict)
#   - "not_tradable_strict_refusal" : on garde "Non tradable (regle A)"
# On ajoute les entrees au dict HUMAN.
patch2_done = False
for i, line in enumerate(lines):
    if '"market_closed"' in line and "Marche ferme" in line:
        # Insere apres cette ligne 2 nouvelles entrees
        indent = line[:len(line) - len(line.lstrip())]
        new_entries = [
            indent + '"convergence_forced_exit":       ("Convergence forced exit",',
            indent + '                                  "Le moteur convergence a force la sortie sur ce ticker"),',
            indent + '"block_forced_exit":             ("Convergence forced exit",',
            indent + '                                  "Verdict V2 : forced_exit detecte par le moteur convergence"),',
        ]
        # On insere apres la ligne (i + 1, donc i+1 = position d'insertion)
        # Mais ce dict a une structure {key: (a, b),} avec b sur la ligne suivante.
        # On cherche la fin de l'entree market_closed
        end_market = i
        for j in range(i, min(len(lines), i + 5)):
            if "Hors plage" in lines[j] or "ferie NYSE" in lines[j]:
                end_market = j
                break
        # Inserer apres end_market
        for k, entry in enumerate(new_entries):
            lines.insert(end_market + 1 + k, entry)
        print("  Patch 2 : %d entrees ajoutees au dict HUMAN apres L%d" % (len(new_entries), end_market + 1))
        for e in new_entries:
            print("    + %s" % e.strip()[:170])
        patch2_done = True
        break

if not patch2_done:
    print("  [WARN] Patch 2 : entree market_closed non trouvee (skip)")

# --- Marker en commentaire dans _humanize_block_reason
for i, line in enumerate(lines):
    if "def _humanize_block_reason" in line:
        for j in range(i + 1, min(len(lines), i + 8)):
            if '"""' in lines[j] and '"""' not in lines[j - 1]:
                # Inserer apres docstring close
                ind = "    "
                lines.insert(j + 1, ind + "# " + MARKER)
                break
        break

new_content = "\n".join(lines)

# --- AST + py_compile
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s (L%s)" % (e, getattr(e, "lineno", "?")))
    # dump 10 lignes autour
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
print("RECAP v5")
print("-" * 72)
print("  - _details_for_humanize lit MAINTENANT details_json (string) en priorite")
print("  - HUMAN dict enrichi : convergence_forced_exit + block_forced_exit")
print()
print("  Validation :")
print("    1. Restart API (uvicorn)")
print("    2. cycle reel pour generer un nouveau memo (qui aura des ordres BLOCKED)")
print("    3. py -3.13 .\\nextones-check-memo-risk-section-v1.py")
print("       -> doit afficher 'BLOCK - Non tradable (regle A)' ou 'Convergence forced exit'")
print("=" * 72)
