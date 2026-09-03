# -*- coding: utf-8 -*-
# nextones-fix-broker-os-undefined-v3.py
# Marker : [BROKER_OS_UNDEFINED_FIX_V3]
#
# v3 : approche ligne-par-ligne. On lit toutes les lignes, on remplace
# '_os.environ' par 'os.environ' uniquement sur les lignes concernees,
# on dump avant/apres pour visibilite.

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RPT = os.path.join(PROD, "risk_pretrade.py")
MARKER = "[BROKER_OS_UNDEFINED_FIX_V3]"

print()
print("=" * 72)
print("[PATCH v3] risk_pretrade.py : fix _os undefined (ligne par ligne)")
print("-" * 72)

if not os.path.exists(RPT):
    print("  [KO] Fichier absent")
    sys.exit(1)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    lines = fh.readlines()

print("  Lignes lues : %d" % len(lines))

# Verif marker
joined = "".join(lines)
if MARKER in joined:
    print("  [SKIP] Marker %s deja present" % MARKER)
    sys.exit(0)

# Trouver les lignes a patcher : celles contenant '_os.environ'
hits = [(i, l) for i, l in enumerate(lines) if "_os.environ" in l]
print("  Lignes contenant '_os.environ' : %d" % len(hits))
if not hits:
    # Verif _os tout court
    hits_loose = [(i, l) for i, l in enumerate(lines) if "_os." in l and i > 380]
    print("  Lignes contenant '_os.' apres L380 : %d" % len(hits_loose))
    for idx, l in hits_loose[:10]:
        print("    L%d : %s" % (idx + 1, l.rstrip()[:120]))
    sys.exit(0)

for idx, l in hits:
    print("  AVANT L%d : %s" % (idx + 1, l.rstrip()[:160]))

# Patch ligne par ligne
new_lines = list(lines)
for idx, l in hits:
    new_lines[idx] = l.replace("_os.environ", "os.environ")

for idx, _ in hits:
    print("  APRES L%d : %s" % (idx + 1, new_lines[idx].rstrip()[:160]))

# Ajouter marker en commentaire au-dessus du bloc broker (chercher ligne avec _dt.now)
marker_inserted = False
for i, l in enumerate(new_lines):
    if "_dt.now(_tz.utc)" in l and not marker_inserted:
        indent = l[:len(l) - len(l.lstrip())]
        new_lines.insert(i, indent + "# " + MARKER + " - _os.environ -> os.environ (os deja importe)\n")
        marker_inserted = True
        break
if not marker_inserted:
    # Fallback : avant la def _nx_broker_precheck
    for i, l in enumerate(new_lines):
        if l.startswith("def _nx_broker_precheck"):
            new_lines.insert(i, "# " + MARKER + " applique\n")
            marker_inserted = True
            break

new_content = "".join(new_lines)

# AST + py_compile avant ecriture
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST parse erreur : %s" % e)
    sys.exit(2)

# Backup + ecriture
ts = time.strftime("%Y%m%d_%H%M%S")
bak = RPT + ".bak." + ts
shutil.copy2(RPT, bak)
print("  Backup : %s" % os.path.basename(bak))

with open(RPT, "w", encoding="utf-8", newline="") as fh:
    fh.write(new_content)

# py_compile
try:
    py_compile.compile(RPT, doraise=True)
    print("  py_compile OK")
except py_compile.PyCompileError as e:
    print("  [KO] py_compile erreur : %s" % e)
    shutil.copy2(bak, RPT)
    print("  [RESTORE] fichier restaure depuis backup")
    sys.exit(3)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  %d ligne(s) patchee(s)" % len(hits))
print("  Marker %s ajoute en commentaire" % MARKER)
print()
print("  Validation :")
print("    py -3.13 .\\nextones-test-convergence-block-suite.py")
print("=" * 72)
