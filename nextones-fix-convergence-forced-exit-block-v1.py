# -*- coding: utf-8 -*-
# nextones-fix-convergence-forced-exit-block-v1.py
# Marker : [CONVERGENCE_FORCED_EXIT_BLOCK_V1]
#
# Probleme :
#   convergence_snapshots marque SOL forced_exit=1 (cycle 20260609-091332)
#   mais order #266 SOL BUY 51 a quand meme passe. Cause : apply_convergence_sizing
#   n'a pas correctement ramene target_weight a 0, et risk_pretrade ne lit
#   pas convergence -> aucune barriere de defense.
#
# Fix :
#   Ajouter un nouveau check check_convergence_forced_exit(c, ticker, side)
#   appele AVANT concentration/var/correlation dans run_pretrade_checks.
#   - BLOCK si side='buy' AND dernier snapshot forced_exit=1
#   - PASS sinon (sell autorise, forced_exit=0 autorise)
#
# Strategie :
#   - lit dernier snapshot par created_at DESC (peu importe cycle_id frais ou J-1)
#   - failsafe : table absente / requete echoue -> log warn + return ok
#   - idempotent (skip si marker present)
#   - backup .bak.<ts>
#   - validation AST + py_compile

import os
import sys
import ast
import py_compile
import shutil
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
MARKER = "[CONVERGENCE_FORCED_EXIT_BLOCK_V1]"
RPT = os.path.join(PROD, "risk_pretrade.py")

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
        print("  [RESTORE] %s restaure depuis backup" % os.path.basename(path))
        return False
    print("  Ecriture OK + py_compile OK")
    return True

print()
print("=" * 72)
print("[PATCH] risk_pretrade.py : ajout check_convergence_forced_exit")
print("-" * 72)

if not os.path.exists(RPT):
    print("  [KO] Fichier absent : %s" % RPT)
    sys.exit(1)

with open(RPT, "r", encoding="utf-8-sig") as fh:
    txt = fh.read()

if MARKER in txt:
    print("  [SKIP] Marker %s deja present (idempotent)" % MARKER)
    sys.exit(0)

# -----------------------------------------------------------------
# Etape 1 : Inserer la fonction check_convergence_forced_exit
# juste avant `def run_pretrade_checks(`
# -----------------------------------------------------------------
CONV_FN = '''
# ''' + MARKER + '''
def check_convergence_forced_exit(c, ticker, side):
    """Bloque les BUY sur tickers marques forced_exit=1 dans convergence_snapshots.

    Lit le snapshot le plus recent (par created_at DESC) pour ce ticker.
    Failsafe : si table absente ou requete echoue, retourne (True, details) -> pas de block.

    Returns
    -------
    (ok: bool, details: dict)
        ok=True  -> pas de raison de bloquer (ou failsafe)
        ok=False -> BLOCK (BUY sur ticker en forced_exit)
    """
    details = {"check": "convergence_forced_exit", "ticker": ticker, "side": side}
    try:
        # SELL toujours autorise (on doit pouvoir sortir)
        if str(side).lower() != "buy":
            details["verdict"] = "skip_non_buy"
            return True, details
        row = c.execute(
            "SELECT cycle_id, forced_exit, sizing_multiplier, direction_consensus, created_at "
            "FROM convergence_snapshots "
            "WHERE ticker = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (ticker,)
        ).fetchone()
        if row is None:
            details["verdict"] = "no_snapshot"
            return True, details
        # sqlite3.Row -> dict-like
        forced = int(row["forced_exit"] or 0)
        details["snapshot"] = {
            "cycle_id": row["cycle_id"],
            "forced_exit": forced,
            "sizing_multiplier": float(row["sizing_multiplier"] or 0),
            "direction_consensus": row["direction_consensus"],
            "created_at": row["created_at"],
        }
        if forced == 1:
            details["verdict"] = "block_forced_exit"
            return False, details
        details["verdict"] = "pass"
        return True, details
    except Exception as _e:
        # Failsafe : table absente, schema decale, etc. -> ne bloque pas
        details["verdict"] = "failsafe"
        details["error"] = str(_e)[:160]
        return True, details


'''

ANCHOR_FN = "def run_pretrade_checks(\n"
if ANCHOR_FN not in txt:
    print("  [KO] Ancre 'def run_pretrade_checks(' introuvable.")
    sys.exit(2)

txt2 = txt.replace(ANCHOR_FN, CONV_FN + ANCHOR_FN, 1)

# -----------------------------------------------------------------
# Etape 2 : Inserer l'appel check_convergence_forced_exit dans
# run_pretrade_checks, juste avant check_concentration
# -----------------------------------------------------------------
OLD_CHECKS = (
    '        conc_ok, conc_d = check_concentration(c, ticker, qty, price, side, p)\n'
    '        var_ok, var_blocked, var_d = check_var_marginal(c, ticker, qty, price, side, p)\n'
    '        corr_ok, corr_d = check_correlation(c, ticker, side, p)\n'
    '\n'
    '        blocked_by: Optional[str] = None\n'
    '        if not conc_ok:\n'
    '            blocked_by = "concentration"\n'
    '        elif not var_ok:\n'
    '            blocked_by = var_blocked or "var"\n'
    '        elif not corr_ok:\n'
    '            blocked_by = "correlation"\n'
)
NEW_CHECKS = (
    '        # ' + MARKER + ' - garde-fou convergence/forced_exit AVANT autres checks\n'
    '        conv_ok, conv_d = check_convergence_forced_exit(c, ticker, side)\n'
    '        conc_ok, conc_d = check_concentration(c, ticker, qty, price, side, p)\n'
    '        var_ok, var_blocked, var_d = check_var_marginal(c, ticker, qty, price, side, p)\n'
    '        corr_ok, corr_d = check_correlation(c, ticker, side, p)\n'
    '\n'
    '        blocked_by: Optional[str] = None\n'
    '        if not conv_ok:\n'
    '            blocked_by = "convergence_forced_exit"\n'
    '        elif not conc_ok:\n'
    '            blocked_by = "concentration"\n'
    '        elif not var_ok:\n'
    '            blocked_by = var_blocked or "var"\n'
    '        elif not corr_ok:\n'
    '            blocked_by = "correlation"\n'
)
if OLD_CHECKS not in txt2:
    print("  [KO] Bloc checks (concentration/var/correlation) introuvable.")
    sys.exit(3)
txt3 = txt2.replace(OLD_CHECKS, NEW_CHECKS, 1)

# -----------------------------------------------------------------
# Etape 3 : Inserer conv_d dans le dict details
# -----------------------------------------------------------------
OLD_DETAILS = (
    '        details = {\n'
    '            "concentration": conc_d,\n'
    '            "var": var_d,\n'
    '            "correlation": corr_d,\n'
    '        }\n'
)
NEW_DETAILS = (
    '        details = {\n'
    '            "convergence_forced_exit": conv_d,  # ' + MARKER + '\n'
    '            "concentration": conc_d,\n'
    '            "var": var_d,\n'
    '            "correlation": corr_d,\n'
    '        }\n'
)
if OLD_DETAILS not in txt3:
    print("  [KO] Bloc details introuvable.")
    sys.exit(4)
txt4 = txt3.replace(OLD_DETAILS, NEW_DETAILS, 1)

# Ecriture
if not backup_and_write(RPT, txt4):
    sys.exit(5)

# -----------------------------------------------------------------
# Recap
# -----------------------------------------------------------------
print()
print("=" * 72)
print("RECAP")
print("-" * 72)
print("  Patch %s applique sur risk_pretrade.py" % MARKER)
print()
print("  Logique :")
print("    - SELL : toujours autorise (skip)")
print("    - BUY  : BLOCK si dernier snapshot convergence forced_exit=1")
print("    - Failsafe : table absente / requete KO -> pas de block")
print()
print("  Validation : ")
print("    py -3.13 .\\nextones-test-risk-v2-direct.py")
print("    -> Test [4] sur SOL BUY doit retourner passed=False")
print("       blocked_by='convergence_forced_exit'")
print("=" * 72)
