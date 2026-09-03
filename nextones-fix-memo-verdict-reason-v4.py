# -*- coding: utf-8 -*-
# nextones-fix-memo-verdict-reason-v4.py
# Marker : [MEMO_VERDICT_REASON_FIX_V4]
#
# Cause : dans memo_generator.py, _build_risk_v2_section lit v2.get("details_json")
# pour humaniser le motif. Mais le verdict V2 stocke les details dans v2["details"]
# (dict parse), pas dans v2["details_json"]. Resultat : raw_reason fallback sur
# blocked_by = "broker_mapping_ok" -> affiche "Mapping broker OK" (mensonger).
#
# Fix :
#  1) L299 : v2.get("details_json") -> v2.get("details") or {}
#  2) Renommer "Mapping broker OK" en "Refus broker (motif non extrait)" pour
#     que le fallback ne mente pas si jamais la lecture echoue.
#  3) Backup .bak.<timestamp>, AST + py_compile, idempotent (marker).

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MG = os.path.join(PROD, "memo_generator.py")
MARKER = "[MEMO_VERDICT_REASON_FIX_V4]"

print()
print("=" * 72)
print("PATCH : memo_generator _build_risk_v2_section motif humain")
print("-" * 72)

with open(MG, "r", encoding="utf-8-sig") as fh:
    content = fh.read()

if MARKER in content:
    print("  [SKIP] Marker deja present")
    sys.exit(0)

lines = content.split("\n")

# --- Patch 1 : remplacer v2.get("details_json") par v2.get("details") or {}
patch1_done = False
for i, line in enumerate(lines):
    if "_details_for_humanize" in line and "v2.get(" in line and "details_json" in line:
        # ligne exacte : _details_for_humanize = v2.get("details_json") if isinstance(v2, dict) else None
        indent = line[:len(line) - len(line.lstrip())]
        new_line = indent + '_details_for_humanize = (v2.get("details") if isinstance(v2, dict) else None) or {}  # ' + MARKER
        print("  Patch 1 L%d AVANT : %s" % (i + 1, line.strip()[:160]))
        lines[i] = new_line
        print("  Patch 1 L%d APRES : %s" % (i + 1, new_line.strip()[:160]))
        patch1_done = True
        break

if not patch1_done:
    print("  [KO] Patch 1 : ligne _details_for_humanize introuvable")
    sys.exit(2)

# --- Patch 2 : renommer 'Mapping broker OK' en 'Refus broker (motif non extrait)'
# Ancre : la ligne "broker_mapping_ok" du dict HUMAN (L249)
patch2_done = False
for i, line in enumerate(lines):
    s = line.strip()
    if s.startswith('"broker_mapping_ok"') and '("Mapping broker OK"' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_line = indent + '"broker_mapping_ok":             ("Refus broker (motif non extrait)",'
        print("  Patch 2 L%d AVANT : %s" % (i + 1, line.strip()[:160]))
        lines[i] = new_line
        print("  Patch 2 L%d APRES : %s" % (i + 1, new_line.strip()[:160]))
        # La ligne suivante doit aussi etre changee (le long label)
        if i + 1 < len(lines) and "Verification du mapping broker reussie" in lines[i + 1]:
            ind2 = lines[i + 1][:len(lines[i + 1]) - len(lines[i + 1].lstrip())]
            lines[i + 1] = ind2 + '                                  "Le broker a refuse - details indisponibles"),'
            print("  Patch 2 L%d (cont) : %s" % (i + 2, lines[i + 1].strip()[:160]))
        patch2_done = True
        break

if not patch2_done:
    print("  [WARN] Patch 2 : entree broker_mapping_ok non modifiee (cosmetique)")

# --- Marker en commentaire dans la fonction _humanize_block_reason
# Pour pouvoir verifier facilement la presence
inject_marker_done = False
for i, line in enumerate(lines):
    if "def _humanize_block_reason" in line:
        # insertion d'un commentaire marker juste apres la def
        # on cherche la ligne """Returns ... """ + on insere apres
        for j in range(i + 1, min(len(lines), i + 5)):
            if '"""' in lines[j]:
                # Inserer apres
                ind = lines[j + 1][:len(lines[j + 1]) - len(lines[j + 1].lstrip())] if j + 1 < len(lines) else "    "
                lines.insert(j + 1, ind + "# " + MARKER)
                inject_marker_done = True
                break
        break

if inject_marker_done:
    print("  Marker injecte dans _humanize_block_reason")
else:
    print("  [WARN] Marker non injecte (cosmetique)")

new_content = "\n".join(lines)

# --- AST + py_compile
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s (L%s)" % (e, getattr(e, "lineno", "?")))
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
print("RECAP")
print("-" * 72)
print("  - Patch 1 : _details_for_humanize lit maintenant v2.get('details') (dict)")
print("  - Patch 2 : fallback 'broker_mapping_ok' renomme en 'Refus broker (motif non extrait)'")
print()
print("  Validation :")
print("    1. Restart API (uvicorn)")
print("    2. powershell -ExecutionPolicy Bypass -File .\\nextones-run-execute-cycle-auth.ps1")
print("    3. Recuperer un memo avec un ZEC/HYPE BUY :")
print("       GET /api/memos/<id>/markdown")
print("       -> doit afficher 'BLOCK - Non tradable (regle A)' au lieu de 'BLOCK - Mapping broker OK'")
print("=" * 72)
