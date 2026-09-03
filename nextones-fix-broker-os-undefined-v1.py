# -*- coding: utf-8 -*-
# nextones-fix-broker-os-undefined-v1.py
# Marker : [BROKER_OS_UNDEFINED_FIX_V1]
#
# Probleme : Dans risk_pretrade.py _nx_broker_precheck, le bloc d'insert
# broker_refuse utilise _os.environ.get(...) mais 'os as _os' n'est pas importe
# au scope de la fonction.
#
# Symptome : [WARN] [NEXTONES-BROKER-CHECK-V1] log insert: name '_os' is not defined
#
# Fix : remplacer _os.environ par os.environ (os est importe au top du module).

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
RPT = os.path.join(PROD, "risk_pretrade.py")
MARKER = "[BROKER_OS_UNDEFINED_FIX_V1]"

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
print("[PATCH] risk_pretrade.py : fix _os undefined dans _nx_broker_precheck")
print("-" * 72)

if not os.path.exists(RPT):
    print("  [KO] Fichier absent")
    sys.exit(1)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    txt = fh.read()

if MARKER in txt:
    print("  [SKIP] Marker deja present (idempotent)")
    sys.exit(0)

# L463 du dump initial :
#   _c = _sql.connect(db_path or _os.environ.get("THESIUM_DB",
#                                                r"C:\Users\..."))
OLD = '_c = _sql.connect(db_path or _os.environ.get("THESIUM_DB",'
NEW = '_c = _sql.connect(db_path or os.environ.get("THESIUM_DB",  # ' + MARKER + '\n                                                     '

# Verif presence
if "_os.environ" not in txt:
    print("  [SKIP] Pattern '_os.environ' non present (deja fixe ?)")
    # On verifie quand meme si pas deja un import _os
    sys.exit(0)

# Comptage des occurrences pour confirmer la portee
n = txt.count("_os.environ")
print("  Occurrences '_os.environ' : %d" % n)

# Remplacement simple : _os.environ -> os.environ (os est importe au top du module)
txt2 = txt.replace("_os.environ", "os.environ  # " + MARKER, 1)
# Si autres occurrences sans le marker, replacer tout
txt2 = txt2.replace("_os.environ", "os.environ")

if not backup_and_write(RPT, txt2):
    sys.exit(2)

print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Pattern '_os.environ' remplace par 'os.environ' (%d occurrences)" % n)
print("  Marker %s ajoute en commentaire" % MARKER)
print()
print("  Validation :")
print("    py -3.13 .\\nextones-test-convergence-block-suite.py")
print("    -> Verifier disparition du warning '_os is not defined'")
print("=" * 72)
