# -*- coding: utf-8 -*-
# nextones-fix-broker-os-undefined-v2.py
# Marker : [BROKER_OS_UNDEFINED_FIX_V2]
#
# v2 : remplacement strict de '_os.environ' -> 'os.environ' SANS commentaire inline
# (le commentaire inline cassait l'expression multi-lignes _sql.connect(...))
#
# Le marker est ajoute SEULEMENT en commentaire de ligne complete, juste au-dessus
# du bloc patche.

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RPT = os.path.join(PROD, "risk_pretrade.py")
MARKER = "[BROKER_OS_UNDEFINED_FIX_V2]"

def backup_and_write(path, new_content):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    print("  Backup : %s" % os.path.basename(bak))
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print("  [KO] AST parse erreur : %s" % e)
        return False
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_content)
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        print("  [KO] py_compile erreur : %s" % e)
        shutil.copy2(bak, path)
        print("  [RESTORE] %s restaure" % os.path.basename(path))
        return False
    print("  Ecriture OK + py_compile OK")
    return True

print()
print("=" * 72)
print("[PATCH v2] risk_pretrade.py : fix _os undefined (sans commentaire inline)")
print("-" * 72)

if not os.path.exists(RPT):
    print("  [KO] Fichier absent")
    sys.exit(1)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    txt = fh.read()

if MARKER in txt:
    print("  [SKIP] Marker deja present (idempotent)")
    sys.exit(0)

# Verif presence du symptome
if "_os.environ" not in txt:
    print("  [SKIP] Pattern '_os.environ' non present (deja fixe ?)")
    sys.exit(0)

n_before = txt.count("_os.environ")
print("  Occurrences '_os.environ' avant : %d" % n_before)

# Remplacement strict (pas de commentaire inline)
txt2 = txt.replace("_os.environ", "os.environ")

# Ajout d'une ligne de marker en commentaire au tout debut du bloc broker
# pour tracabilite. On trouve le commentaire suivant et on insere une ligne au-dessus.
ANCHOR_BLOCK = "    ts = _dt.now(_tz.utc).isoformat(timespec=\"seconds\")\n"
if ANCHOR_BLOCK in txt2:
    NEW_BLOCK = "    # " + MARKER + " - _os.environ -> os.environ (os deja importe au top du module)\n" + ANCHOR_BLOCK
    txt2 = txt2.replace(ANCHOR_BLOCK, NEW_BLOCK, 1)
else:
    print("  [WARN] Anchor pour marker non trouve, on ajoute en tete de _nx_broker_precheck")
    # Fallback: marker comme commentaire avant la def
    ANCHOR2 = "def _nx_broker_precheck(ticker"
    if ANCHOR2 in txt2:
        txt2 = txt2.replace(ANCHOR2, "# " + MARKER + " applique\n" + ANCHOR2, 1)

n_after = txt2.count("_os.environ")
print("  Occurrences '_os.environ' apres : %d" % n_after)
if n_after != 0:
    print("  [KO] Remplacement incomplet, abandon")
    sys.exit(2)

if not backup_and_write(RPT, txt2):
    sys.exit(3)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Pattern '_os.environ' remplace par 'os.environ' (%d -> 0)" % n_before)
print("  Marker %s ajoute en commentaire de ligne separee" % MARKER)
print()
print("  Validation :")
print("    py -3.13 .\\nextones-test-convergence-block-suite.py")
print("    -> verifier disparition du warning '_os is not defined'")
print("=" * 72)
