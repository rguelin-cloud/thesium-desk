# -*- coding: utf-8 -*-
# nextones-fix-stop-loss-block-v1.py
# Patch [STOP_LOSS_BLOCK_V1] : ajoute check_stop_loss dans risk_pretrade.py
# Bloque les ordres BUY sur position avec PnL <= -8%
# Insertion : nouvelle fonction apres check_convergence_forced_exit
#             appel dans run_pretrade_checks apres convergence
# Pattern : 100% ASCII pur, AST validation, idempotent

import ast
import os
import sys
import time
import shutil
import py_compile

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\risk_pretrade.py"
MARKER = "[STOP_LOSS_BLOCK_V1]"
STOP_LOSS_PCT = -8.0

NEW_FUNC = '''

# ================================================================
# [STOP_LOSS_BLOCK_V1] check_stop_loss
# Bloque BUY si position existante avec PnL <= -8%
# SELL toujours autorise (laisse sortir)
# ================================================================
STOP_LOSS_PCT_THRESHOLD = -8.0

def check_stop_loss(c, ticker, side):
    """Stop-loss bloquant : refuse BUY si position en perte >= 8%.

    Returns (ok: bool, details: dict)
    """
    try:
        if str(side).lower() != "buy":
            return True, {"verdict": "pass", "reason": "sell_skip"}

        row = c.execute(
            """
            SELECT pp.avg_cost, pp.current_price, pp.quantity, pp.unrealized_pnl
            FROM portfolio_positions pp
            JOIN instruments i ON i.id = pp.instrument_id
            WHERE i.ticker = ?
            """,
            (ticker,),
        ).fetchone()

        if not row:
            return True, {"verdict": "pass", "reason": "no_position"}

        avg_cost = float(row[0] or 0.0)
        current_price = float(row[1] or 0.0)
        qty = float(row[2] or 0.0)

        if qty <= 0 or avg_cost <= 0 or current_price <= 0:
            return True, {"verdict": "pass", "reason": "invalid_data"}

        pnl_pct = (current_price - avg_cost) / avg_cost * 100.0

        if pnl_pct <= STOP_LOSS_PCT_THRESHOLD:
            return False, {
                "verdict": "block_stop_loss",
                "reason": "position_loss_exceeds_threshold",
                "pnl_pct": round(pnl_pct, 2),
                "threshold_pct": STOP_LOSS_PCT_THRESHOLD,
                "avg_cost": round(avg_cost, 6),
                "current_price": round(current_price, 6),
                "qty": qty,
            }

        return True, {
            "verdict": "pass",
            "reason": "pnl_above_threshold",
            "pnl_pct": round(pnl_pct, 2),
        }
    except Exception as e:
        # Failsafe : ne pas bloquer en cas d'erreur
        return True, {"verdict": "pass", "reason": "error", "error": str(e)[:200]}
# ================================================================
# [STOP_LOSS_BLOCK_V1] END
# ================================================================

'''


def is_ascii_pure(s):
    return all(ord(ch) < 128 for ch in s)


def main():
    if not is_ascii_pure(NEW_FUNC):
        print("[FATAL] NEW_FUNC contient des caracteres non-ASCII")
        sys.exit(2)

    if not os.path.exists(TARGET):
        print("[FATAL] Fichier introuvable: " + TARGET)
        sys.exit(2)

    # Read utf-8-sig
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        src = f.read()

    # Idempotence
    if MARKER in src:
        print("[SKIP] Marker " + MARKER + " deja present, aucun changement.")
        return

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    backup = TARGET + ".bak." + ts
    shutil.copy2(TARGET, backup)
    print("[BACKUP] " + backup)

    # Localiser run_pretrade_checks
    anchor_func = "def run_pretrade_checks("
    idx_func = src.find(anchor_func)
    if idx_func < 0:
        print("[FATAL] run_pretrade_checks introuvable")
        sys.exit(2)

    # Inserer la nouvelle fonction JUSTE AVANT def run_pretrade_checks
    # Remonter au debut de la ligne
    line_start = src.rfind("\n", 0, idx_func) + 1
    new_src = src[:line_start] + NEW_FUNC + src[line_start:]

    # Localiser l'appel convergence dans run_pretrade_checks pour ajouter sl_ok juste apres
    anchor_call = "conv_ok, conv_d = check_convergence_forced_exit(c, ticker, side)"
    idx_call = new_src.find(anchor_call)
    if idx_call < 0:
        print("[FATAL] Ancre convergence call introuvable")
        sys.exit(2)

    # Trouver la fin de cette ligne
    line_end = new_src.find("\n", idx_call)
    if line_end < 0:
        print("[FATAL] Fin de ligne convergence introuvable")
        sys.exit(2)

    # Calculer l'indentation
    line_begin = new_src.rfind("\n", 0, idx_call) + 1
    indent_str = ""
    for ch in new_src[line_begin:idx_call]:
        if ch in " \t":
            indent_str += ch
        else:
            break

    insertion = "\n" + indent_str + "sl_ok, sl_d = check_stop_loss(c, ticker, side)"
    new_src = new_src[:line_end] + insertion + new_src[line_end:]

    # Localiser la chaine blocked_by pour ajouter elif not sl_ok
    # Pattern attendu : elif not conv_ok: blocked_by = "convergence_forced_exit"
    anchor_conv_block = 'elif not conv_ok:'
    idx_conv_block = new_src.find(anchor_conv_block)
    if idx_conv_block < 0:
        # Fallback : chercher autre forme
        anchor_conv_block_alt = "not conv_ok"
        idx_conv_block = new_src.find(anchor_conv_block_alt, idx_call + 100)
        if idx_conv_block < 0:
            print("[FATAL] Bloc blocked_by convergence introuvable")
            sys.exit(2)

    # Trouver la ligne complete de blocked_by = "convergence..."
    # On veut inserer APRES le bloc convergence complet (2 lignes : elif + body)
    # Cherche "blocked_by = \"convergence" apres idx_conv_block
    bb_idx = new_src.find('blocked_by', idx_conv_block)
    if bb_idx < 0:
        print("[FATAL] blocked_by convergence body introuvable")
        sys.exit(2)
    bb_line_end = new_src.find("\n", bb_idx)
    if bb_line_end < 0:
        print("[FATAL] Fin ligne blocked_by convergence introuvable")
        sys.exit(2)

    # Calculer l'indentation du elif
    elif_line_begin = new_src.rfind("\n", 0, idx_conv_block) + 1
    elif_indent = ""
    for ch in new_src[elif_line_begin:idx_conv_block]:
        if ch in " \t":
            elif_indent += ch
        else:
            break

    # Indentation du body (4 espaces de plus en general, mais on detecte)
    body_line_begin = new_src.rfind("\n", 0, bb_idx) + 1
    body_indent = ""
    for ch in new_src[body_line_begin:bb_idx]:
        if ch in " \t":
            body_indent += ch
        else:
            break

    sl_insertion = (
        "\n" + elif_indent + "elif not sl_ok:"
        + "\n" + body_indent + 'blocked_by = "stop_loss"'
    )
    new_src = new_src[:bb_line_end] + sl_insertion + new_src[bb_line_end:]

    # Ajouter "stop_loss": sl_d dans le dict details
    # Cherche "convergence_forced_exit": conv_d
    anchor_details = '"convergence_forced_exit": conv_d'
    idx_details = new_src.find(anchor_details)
    if idx_details < 0:
        # Fallback : essayer sans guillemets exacts
        anchor_details = "convergence_forced_exit"
        idx_details = new_src.find(anchor_details, idx_call + 200)
        if idx_details < 0:
            print("[WARN] Cle convergence_forced_exit dans details introuvable, on continue sans")
        else:
            # Trouver fin de ligne
            det_line_end = new_src.find("\n", idx_details)
            # Indentation
            det_line_begin = new_src.rfind("\n", 0, idx_details) + 1
            det_indent = ""
            for ch in new_src[det_line_begin:idx_details]:
                if ch in " \t":
                    det_indent += ch
                else:
                    break
            det_insertion = "\n" + det_indent + '"stop_loss": sl_d,'
            new_src = new_src[:det_line_end] + det_insertion + new_src[det_line_end:]
    else:
        det_line_end = new_src.find("\n", idx_details)
        det_line_begin = new_src.rfind("\n", 0, idx_details) + 1
        det_indent = ""
        for ch in new_src[det_line_begin:idx_details]:
            if ch in " \t":
                det_indent += ch
            else:
                break
        det_insertion = "\n" + det_indent + '"stop_loss": sl_d,'
        new_src = new_src[:det_line_end] + det_insertion + new_src[det_line_end:]

    # Validation AST
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print("[FATAL] AST parse failed: " + str(e))
        # Dump pour debug
        lines = new_src.split("\n")
        ln = e.lineno or 0
        for i in range(max(0, ln - 5), min(len(lines), ln + 5)):
            print(("  >> " if (i + 1) == ln else "     ") + str(i + 1) + ": " + lines[i])
        sys.exit(3)

    # Write utf-8 sans BOM
    with open(TARGET, "w", encoding="utf-8", newline="") as f:
        f.write(new_src)

    # py_compile final
    try:
        py_compile.compile(TARGET, doraise=True)
    except py_compile.PyCompileError as e:
        print("[FATAL] py_compile failed: " + str(e))
        # Restore
        shutil.copy2(backup, TARGET)
        print("[ROLLBACK] " + TARGET + " restaure depuis " + backup)
        sys.exit(4)

    print("[OK] Patch " + MARKER + " applique avec succes.")
    print("[OK] Fonction check_stop_loss inseree avant run_pretrade_checks.")
    print("[OK] Appel sl_ok/sl_d ajoute apres convergence.")
    print("[OK] Bloc elif not sl_ok ajoute apres convergence_forced_exit.")
    print("[OK] Cle stop_loss ajoutee au dict details.")
    print("[OK] Seuil : PnL <= " + str(STOP_LOSS_PCT) + "% bloque BUY.")


if __name__ == "__main__":
    main()
