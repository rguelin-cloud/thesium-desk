# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-SHADOW-WIRING-V1]
# Phase 3A : cable execute_shadow() en parallele de l'insertion d'ordre
# dans execution_engine.create_and_execute_order().
#
# Point d'insertion :
#   - Ancre : la ligne contenant
#         conn.execute("UPDATE orders SET quantity = ? WHERE id = ?",
#                      (approved_qty, order_id))
#   - Bloc shadow injecte JUSTE APRES (entre UPDATE et le return final)
#
# A ce point :
#   - risk_result["approved"] == True (verifie L1247-L1252)
#   - approved_qty defini (L1254)
#   - order_id defini (L1232)
#   - _rv2_ticker defini si la branche RISK_V2 L1198 a tourne (sinon None)
#   - effective_price defini (L1187)
#
# Comportement :
#   - GARDE bridge_config.BROKER_SHADOW_ENABLED
#   - Charge nextones-broker-shadow-executor.py par chemin de fichier
#     (meme pattern que _nx_broker_check_load dans risk_pretrade.py)
#   - Appelle execute_shadow(thesium_ticker, side, qty, entry_price=..., cycle_id=order_id_str)
#   - FIRE-AND-FORGET : tout est dans un try/except, jamais d'exception remontee
#   - Trace warning stderr en cas d'echec
#
# Garde-fous :
#   - Backup .bak.{ts} de execution_engine.py
#   - Idempotent : refuse si marker [NEXTONES-SHADOW-EXEC-V1] deja present
#   - ast.parse + py_compile sur le resultat
#   - Smoke import via subprocess (import execution_engine)
#   - Rollback auto si l'une de ces validations echoue
#
# Modes :
#   py -3.13 nextones-install-shadow-wiring.py --dry-run
#   py -3.13 nextones-install-shadow-wiring.py
#   py -3.13 nextones-install-shadow-wiring.py --rollback

import argparse
import ast
import os
import py_compile
import re
import shutil
import subprocess
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD_DIR, "execution_engine.py")
MARKER = "[NEXTONES-SHADOW-EXEC-V1]"

# Ancre : ligne UPDATE orders SET quantity
# (regex tolerant aux espaces et au formatage)
ANCHOR_RE = re.compile(
    r'conn\.execute\(\s*"UPDATE\s+orders\s+SET\s+quantity\s*=\s*\?\s+WHERE\s+id\s*=\s*\?"',
    re.IGNORECASE,
)


SHADOW_BLOCK = '''
    # [NEXTONES-SHADOW-EXEC-V1] - shadow executor en parallele (fire-and-forget)
    try:
        import bridge_config as _bc_sh
        if getattr(_bc_sh, "BROKER_SHADOW_ENABLED", False):
            import importlib.util as _ilu_sh
            import os as _os_sh
            _p_sh = _os_sh.path.join(
                _os_sh.path.dirname(_os_sh.path.abspath(__file__)),
                "nextones-broker-shadow-executor.py",
            )
            if _os_sh.path.exists(_p_sh):
                _spec_sh = _ilu_sh.spec_from_file_location(
                    "_nx_shadow_exec", _p_sh
                )
                if _spec_sh is not None and _spec_sh.loader is not None:
                    _mod_sh = _ilu_sh.module_from_spec(_spec_sh)
                    _spec_sh.loader.exec_module(_mod_sh)
                    _ticker_sh = None
                    try:
                        _ticker_sh = _rv2_ticker
                    except NameError:
                        _row_sh = conn.execute(
                            "SELECT ticker FROM instruments WHERE id = ?",
                            (instrument_id,),
                        ).fetchone()
                        _ticker_sh = _row_sh[0] if _row_sh else None
                    if _ticker_sh:
                        _mod_sh.execute_shadow(
                            thesium_ticker=_ticker_sh,
                            side=side,
                            qty=float(approved_qty),
                            cycle_id="order_id=" + str(order_id),
                            entry_price=float(effective_price),
                        )
    except Exception as _sh_e:
        try:
            import sys as _sh_sys
            print(
                "[WARN] [NEXTONES-SHADOW-EXEC-V1] " + str(_sh_e)[:200],
                file=_sh_sys.stderr,
            )
        except Exception:
            pass
'''


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_src():
    with open(TARGET, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_src(content):
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def find_insertion_point(src):
    """
    Retourne l'index char juste apres la ligne contenant l'ancre UPDATE.
    On va jusqu'a la fin du statement (parenthese fermante du conn.execute).
    """
    m = ANCHOR_RE.search(src)
    if not m:
        return None, "ancre UPDATE orders SET quantity introuvable"

    # Trouver la fin du statement : on cherche la fin de la ligne contenant
    # ").lastrowid" n'est PAS notre cas (c'est INSERT). Ici c'est juste
    # un conn.execute(...) sans .lastrowid. On suit les parentheses.
    start = m.start()
    # Compteur parentheses depuis le debut du match
    depth = 0
    i = start
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                # On est sur la parenthese fermante du conn.execute(...)
                # Aller jusqu'a la fin de la ligne (newline inclus)
                j = src.find("\n", i)
                if j == -1:
                    return n, None
                return j + 1, None
        i += 1
    return None, "parenthese fermante non trouvee"


def validate_python(src, label):
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"{label} ast.parse: {e}"
    return True, "OK"


def smoke_import():
    """Verifie que execution_engine s'importe sans erreur."""
    code = (
        "import sys\n"
        f"sys.path.insert(0, r'{PROD_DIR}')\n"
        "import execution_engine\n"
        "print('SMOKE_IMPORT_OK')\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=60,
    )
    ok = (res.returncode == 0) and ("SMOKE_IMPORT_OK" in res.stdout)
    return ok, (res.stdout + res.stderr).strip()


def do_apply(dry_run):
    if not os.path.exists(TARGET):
        log(f"[ERR] {TARGET} introuvable")
        sys.exit(2)
    src = read_src()
    log(f"Fichier cible : {TARGET} ({len(src)} bytes)")

    if MARKER in src:
        log(f"[OK] marker {MARKER} deja present -> rien a faire (idempotent)")
        return

    ip, err = find_insertion_point(src)
    if err:
        log(f"[ERR] {err}")
        sys.exit(3)
    # Compute ligne approximative
    line_no = src.count("\n", 0, ip) + 1
    log(f"Point d'insertion : char {ip} (apres L{line_no - 1})")

    new_src = src[:ip] + SHADOW_BLOCK + src[ip:]

    ok, msg = validate_python(new_src, "post-patch")
    if not ok:
        log(f"[ERR] {msg}")
        sys.exit(4)
    log("Validation ast.parse : OK")

    if dry_run:
        log("DRY-RUN : extrait du bloc qui serait insere :")
        print("-" * 60)
        # Affiche 20 lignes autour du point d'insertion (avant + bloc + apres)
        before = new_src[max(0, ip - 200):ip]
        block_end = ip + len(SHADOW_BLOCK)
        after = new_src[block_end:block_end + 200]
        print("...AVANT (200 derniers chars)...")
        print(before)
        print(">>> BLOC INSERE <<<")
        print(SHADOW_BLOCK)
        print("...APRES (200 premiers chars)...")
        print(after)
        print("-" * 60)
        log("DRY-RUN termine, aucune ecriture.")
        return

    # Backup + ecriture
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak.{ts}"
    shutil.copy2(TARGET, backup)
    log(f"[OK] backup -> {backup}")

    write_src(new_src)
    log("[OK] patch applique")

    # py_compile sur le fichier ecrit
    try:
        py_compile.compile(TARGET, doraise=True)
        log("[OK] py_compile")
    except Exception as e:
        log(f"[ERR] py_compile : {e}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback effectue")
        sys.exit(5)

    # Smoke import
    ok, info = smoke_import()
    if not ok:
        log(f"[ERR] smoke import : {info}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback effectue")
        sys.exit(6)
    log(f"[OK] smoke import : {info.splitlines()[-1]}")

    log("=" * 60)
    log("PHASE 3A SHADOW WIRING INSTALLE")
    log("=" * 60)
    log(f"Backup : {backup}")
    log(f"Marker : {MARKER}")
    log("")
    log("Etape suivante :")
    log("  py -3.13 nextones-validate-shadow-wired.py")


def do_rollback():
    """
    Restaure le backup le plus recent .bak.* de execution_engine.py.
    """
    d = os.path.dirname(TARGET)
    base = os.path.basename(TARGET)
    candidates = sorted(
        [f for f in os.listdir(d) if f.startswith(base + ".bak.")],
        reverse=True,
    )
    if not candidates:
        log("[ERR] aucun backup execution_engine.py.bak.* trouve")
        sys.exit(7)
    backup = os.path.join(d, candidates[0])
    shutil.copy2(backup, TARGET)
    log(f"[OK] rollback depuis {backup}")
    # Verif rapide
    ok, info = smoke_import()
    if ok:
        log("[OK] smoke import post-rollback")
    else:
        log(f"[WARN] smoke post-rollback : {info}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()
    if args.rollback:
        do_rollback()
    else:
        do_apply(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
