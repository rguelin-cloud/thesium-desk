# -*- coding: utf-8 -*-
# nextones-fix-broker-check-conn-v1.py
# Marker : [BROKER_CHECK_CONN_FIX_V1]
#
# Probleme : check_broker_mapping (dans nextones-risk-broker-check.py) ouvre une
# 2e connexion SQLite pour faire un INSERT dans broker_mapping_audit. Quand
# execution_engine detient une transaction BEGIN IMMEDIATE, l'audit attend
# 10s puis log "[WARN] risk_broker_check audit: database is locked".
#
# Fix :
# 1) nextones-risk-broker-check.py
#    - check_broker_mapping accepte un param `conn` optionnel
#    - si conn fourni, _audit utilise cette conn au lieu d'en ouvrir une nouvelle
# 2) risk_pretrade.py
#    - _nx_broker_precheck accepte et propage conn=
#    - run_pretrade_checks transmet conn= au precheck broker
#
# Strategie : backup .bak.<ts>, AST + py_compile avant ecriture, idempotent
# (skip si marker deja present).

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MARKER = "[BROKER_CHECK_CONN_FIX_V1]"

def backup_and_write(path, new_content):
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = path + ".bak." + ts
    shutil.copy2(path, bak)
    print("  Backup : %s" % os.path.basename(bak))
    # Validation AST avant ecriture
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        print("  [KO] AST parse erreur : %s" % e)
        return False
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_content)
    # py_compile post-ecriture
    try:
        py_compile.compile(path, doraise=True)
    except py_compile.PyCompileError as e:
        print("  [KO] py_compile erreur : %s" % e)
        # Restore
        shutil.copy2(bak, path)
        print("  [RESTORE] %s restaure depuis backup" % os.path.basename(path))
        return False
    print("  Ecriture OK + py_compile OK")
    return True

# =====================================================================
# PATCH 1 : nextones-risk-broker-check.py
# =====================================================================
print()
print("=" * 72)
print("[PATCH 1] nextones-risk-broker-check.py")
print("-" * 72)
RBC = os.path.join(PROD, "nextones-risk-broker-check.py")
if not os.path.exists(RBC):
    print("  [KO] Fichier absent : %s" % RBC)
    sys.exit(1)

with open(RBC, "r", encoding="utf-8-sig") as fh:
    rbc_txt = fh.read()

if MARKER in rbc_txt:
    print("  [SKIP] Marker %s deja present (idempotent)" % MARKER)
else:
    # Remplacement bloc check_broker_mapping (L103-L145 du dump)
    # On garde le contenu et on ajoute :
    #  - param conn=None dans la signature
    #  - bloc de selection conn vs ouverture interne
    OLD = (
        'def check_broker_mapping(proposal: Dict[str, Any],\n'
        '                         db_path: Optional[str] = None) -> Dict[str, Any]:\n'
    )
    NEW = (
        '# ' + MARKER + ' - accepte conn= partagee pour eviter db lock\n'
        'def check_broker_mapping(proposal: Dict[str, Any],\n'
        '                         db_path: Optional[str] = None,\n'
        '                         conn: "Optional[sqlite3.Connection]" = None) -> Dict[str, Any]:\n'
    )
    if OLD not in rbc_txt:
        print("  [KO] Signature attendue introuvable (fichier modifie ?)")
        print("       Cherchait :")
        print(OLD)
        sys.exit(2)
    rbc_txt2 = rbc_txt.replace(OLD, NEW, 1)

    # Remplacement bloc audit (L137-L143 du dump) :
    OLD_AUDIT = (
        '    path = db_path or DB_PATH\n'
        '    try:\n'
        '        con = _nx_open_db(path)\n'
        '        _audit(con, "accept" if result["ok"] else "reject", proposal, result)\n'
        '        con.close()\n'
        '    except Exception as e:\n'
        '        print("[WARN] check_broker_mapping audit: " + str(e))\n'
    )
    NEW_AUDIT = (
        '    # ' + MARKER + ' - reutilise conn partagee si fournie, sinon ouvre/ferme localement\n'
        '    path = db_path or DB_PATH\n'
        '    try:\n'
        '        if conn is not None:\n'
        '            _audit(conn, "accept" if result["ok"] else "reject", proposal, result)\n'
        '        else:\n'
        '            con = _nx_open_db(path)\n'
        '            try:\n'
        '                _audit(con, "accept" if result["ok"] else "reject", proposal, result)\n'
        '            finally:\n'
        '                con.close()\n'
        '    except Exception as e:\n'
        '        print("[WARN] check_broker_mapping audit: " + str(e))\n'
    )
    if OLD_AUDIT not in rbc_txt2:
        print("  [KO] Bloc audit attendu introuvable.")
        sys.exit(3)
    rbc_txt3 = rbc_txt2.replace(OLD_AUDIT, NEW_AUDIT, 1)

    if not backup_and_write(RBC, rbc_txt3):
        sys.exit(4)

# =====================================================================
# PATCH 2 : risk_pretrade.py
# =====================================================================
print()
print("=" * 72)
print("[PATCH 2] risk_pretrade.py - _nx_broker_precheck + run_pretrade_checks")
print("-" * 72)
RPT = os.path.join(PROD, "risk_pretrade.py")
if not os.path.exists(RPT):
    print("  [KO] Fichier absent : %s" % RPT)
    sys.exit(5)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    rpt_txt = fh.read()

if MARKER in rpt_txt:
    print("  [SKIP] Marker %s deja present (idempotent)" % MARKER)
else:
    # 1. Signature _nx_broker_precheck : ajouter conn=None
    OLD_SIG_PRE = (
        'def _nx_broker_precheck(ticker, qty, price, side, db_path):\n'
    )
    NEW_SIG_PRE = (
        '# ' + MARKER + ' - propage conn= au broker_check pour eviter db lock\n'
        'def _nx_broker_precheck(ticker, qty, price, side, db_path, conn=None):\n'
    )
    if OLD_SIG_PRE not in rpt_txt:
        print("  [KO] Signature _nx_broker_precheck introuvable.")
        sys.exit(6)
    rpt_txt2 = rpt_txt.replace(OLD_SIG_PRE, NEW_SIG_PRE, 1)

    # 2. Appel check_broker_mapping : ajouter conn=conn
    OLD_CALL = (
        '        result = _NX_BROKER_CHECK.check_broker_mapping({\n'
        '            "thesium_ticker": ticker,\n'
        '            "side": side,\n'
        '            "qty": qty,\n'
        '        })\n'
    )
    NEW_CALL = (
        '        # ' + MARKER + ' - passe conn partagee si dispo\n'
        '        result = _NX_BROKER_CHECK.check_broker_mapping({\n'
        '            "thesium_ticker": ticker,\n'
        '            "side": side,\n'
        '            "qty": qty,\n'
        '        }, conn=conn)\n'
    )
    if OLD_CALL not in rpt_txt2:
        print("  [KO] Appel check_broker_mapping introuvable.")
        sys.exit(7)
    rpt_txt3 = rpt_txt2.replace(OLD_CALL, NEW_CALL, 1)

    # 3. Appel _nx_broker_precheck dans run_pretrade_checks : ajouter conn=conn
    OLD_PRE_CALL = (
        '    # [NEXTONES-BROKER-CHECK-V1] - 5e controle broker_mapping_ok EN PREMIER\n'
        '    _nx_pre = _nx_broker_precheck(ticker, qty, price, side, db_path)\n'
    )
    NEW_PRE_CALL = (
        '    # [NEXTONES-BROKER-CHECK-V1] - 5e controle broker_mapping_ok EN PREMIER\n'
        '    # ' + MARKER + ' - propage conn partagee\n'
        '    _nx_pre = _nx_broker_precheck(ticker, qty, price, side, db_path, conn=conn)\n'
    )
    if OLD_PRE_CALL not in rpt_txt3:
        print("  [KO] Appel _nx_broker_precheck dans run_pretrade_checks introuvable.")
        sys.exit(8)
    rpt_txt4 = rpt_txt3.replace(OLD_PRE_CALL, NEW_PRE_CALL, 1)

    if not backup_and_write(RPT, rpt_txt4):
        sys.exit(9)

# =====================================================================
# RECAP
# =====================================================================
print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Patch %s applique" % MARKER)
print("  Fichiers modifies :")
print("    - nextones-risk-broker-check.py : check_broker_mapping(.., conn=None)")
print("    - risk_pretrade.py              : _nx_broker_precheck(.., conn=None) + propagation")
print()
print("  Validation : ")
print("    py -3.13 .\\nextones-test-risk-v2-direct.py")
print("    -> Test [4] doit passer SANS warning broker_check et en <100ms")
print("=" * 72)
