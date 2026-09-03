# -*- coding: utf-8 -*-
# nextones-fix-broker-os-import-v4.py
# Marker : [BROKER_OS_IMPORT_FIX_V4]
#
# Probleme final : _nx_broker_precheck fait des imports locaux (import sys as _sys,
# import json as _json, import sqlite3 as _sql) mais oublie 'os'. Le 'os' global
# n'est pas visible dans ce scope (probablement masque). Solution : ajouter
# 'import os as _os' local + revert os.environ -> _os.environ.

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RPT = os.path.join(PROD, "risk_pretrade.py")
MARKER = "[BROKER_OS_IMPORT_FIX_V4]"

print()
print("=" * 72)
print("[PATCH v4] risk_pretrade.py : ajout import os local + revert _os.environ")
print("-" * 72)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    lines = fh.readlines()

joined = "".join(lines)
if MARKER in joined:
    print("  [SKIP] Marker deja present")
    sys.exit(0)

# Etape 1 : revert os.environ -> _os.environ (pour coherence avec import os as _os)
hits_revert = [(i, l) for i, l in enumerate(lines) if "os.environ" in l and "_os.environ" not in l]
print("  Lignes a revert os.environ -> _os.environ : %d" % len(hits_revert))
for idx, l in hits_revert:
    print("    L%d AVANT : %s" % (idx + 1, l.rstrip()[:160]))
    lines[idx] = l.replace("os.environ", "_os.environ")
    print("    L%d APRES : %s" % (idx + 1, lines[idx].rstrip()[:160]))

# Etape 2 : ajouter 'import os as _os' juste apres 'import sqlite3 as _sql'
# dans _nx_broker_precheck. Ancre : ligne contenant 'import sqlite3 as _sql'
anchor_found = False
for i, l in enumerate(lines):
    if "import sqlite3 as _sql" in l and not anchor_found:
        indent = l[:len(l) - len(l.lstrip())]
        # Verifier si 'import os as _os' deja present dans les 5 lignes suivantes
        already = False
        for j in range(max(0, i - 5), min(len(lines), i + 5)):
            if "import os as _os" in lines[j]:
                already = True
                break
        if already:
            print("  'import os as _os' deja present pres de L%d, skip insert" % (i + 1))
        else:
            lines.insert(i + 1, indent + "import os as _os  # " + MARKER + "\n")
            print("  Insertion 'import os as _os' apres L%d" % (i + 1))
        anchor_found = True
        break

if not anchor_found:
    print("  [KO] Ancre 'import sqlite3 as _sql' introuvable")
    sys.exit(2)

new_content = "".join(lines)

# Validation AST
try:
    ast.parse(new_content)
    print("  AST OK")
except SyntaxError as e:
    print("  [KO] AST : %s" % e)
    sys.exit(3)

# Backup + ecriture
ts = time.strftime("%Y%m%d_%H%M%S")
bak = RPT + ".bak." + ts
shutil.copy2(RPT, bak)
print("  Backup : %s" % os.path.basename(bak))

with open(RPT, "w", encoding="utf-8", newline="") as fh:
    fh.write(new_content)

try:
    py_compile.compile(RPT, doraise=True)
    print("  py_compile OK")
except py_compile.PyCompileError as e:
    shutil.copy2(bak, RPT)
    print("  [KO] py_compile : %s -- restore" % e)
    sys.exit(4)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Revert os.environ -> _os.environ : %d ligne(s)" % len(hits_revert))
print("  Ajout 'import os as _os' local dans _nx_broker_precheck")
print()
print("  Validation : py -3.13 .\\nextones-test-convergence-block-suite.py")
print("=" * 72)
