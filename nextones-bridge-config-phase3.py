# -*- coding: utf-8 -*-
# [NEXTONES-BRIDGE-CONFIG-PHASE3-V2]
# Cree (ou patche) bridge_config.py pour Phase 3 :
#   - BROKER_SHADOW_ENABLED  : True  (Phase 2.5+ : shadow executor actif)
#   - BROKER_LIVE_ENABLED    : False (Phase 3C activera plus tard)
#   - MAX_LIVE_NAV           : 100000.0 (palier valide par user)
#   - BROKER_LIVE_ACCOUNT    : "ACTIVTRADES"
#
# Comportement :
#   - Si bridge_config.py absent  -> creation propre
#   - Si bridge_config.py present -> ajout des flags manquants en fin de fichier
#                                    (idempotent : ne reecrit pas un flag deja present)
#
# Garde-fous :
#   - backup .bak.{ts} avant ecriture si fichier existant
#   - ast.parse + py_compile sur le resultat
#   - rollback auto si validation echoue
#
# Usage :
#   py -3.13 nextones-bridge-config-phase3.py --dry-run
#   py -3.13 nextones-bridge-config-phase3.py
#   py -3.13 nextones-bridge-config-phase3.py --rollback

import argparse
import ast
import os
import py_compile
import re
import shutil
import sys
import time

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\bridge_config.py"
MARKER = "# [NEXTONES-BRIDGE-CONFIG-PHASE3-V2]"

FLAGS = [
    ("BROKER_SHADOW_ENABLED", "True",
     "Phase 2.5+ : shadow executor en parallele de PineConnector"),
    ("BROKER_LIVE_ENABLED", "False",
     "Phase 3C : bascule live (False = simu uniquement)"),
    ("MAX_LIVE_NAV", "100000.0",
     "Palier max NAV en mode live (EUR, valide user 2026-05-30)"),
    ("BROKER_LIVE_ACCOUNT", '"ACTIVTRADES"',
     "Broker live cible (FTMO desactive)"),
]

HEADER_NEW = '''# -*- coding: utf-8 -*-
"""
bridge_config.py
NEXTONES <-> ActivTrades bridge configuration.
Cree par nextones-bridge-config-phase3.py
"""
'''


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, content):
    # ecrit en utf-8 SANS BOM
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def has_flag(src, name):
    # detecte une assignation top-level NAME = ...
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=", re.MULTILINE)
    return bool(pattern.search(src))


def build_flag_block():
    lines = ["", MARKER, "# Phase 3 broker flags"]
    for name, value, comment in FLAGS:
        lines.append(f"{name} = {value}  # {comment}")
    lines.append("")
    return "\n".join(lines)


def build_initial_file():
    return HEADER_NEW + build_flag_block()


def validate(src, path_hint):
    # ast.parse sur le contenu
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"ast.parse: {e}"
    # py_compile sur fichier temporaire si pas encore ecrit
    tmp = path_hint + ".tmp_validate"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(src)
        py_compile.compile(tmp, doraise=True)
    except Exception as e:
        return False, f"py_compile: {e}"
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    return True, "OK"


def smoke_import(path):
    # Import via subprocess pour eviter de polluer ce process
    import subprocess
    target_dir = os.path.dirname(path) or "."
    code = (
        "import sys, importlib;"
        f"sys.path.insert(0, r'{target_dir}');"
        "m = importlib.import_module('bridge_config');"
        "vals = {k: getattr(m, k, '<MISSING>') for k in "
        "['BROKER_SHADOW_ENABLED','BROKER_LIVE_ENABLED','MAX_LIVE_NAV','BROKER_LIVE_ACCOUNT']};"
        "print('SMOKE_IMPORT_OK', vals)"
    )
    try:
        res = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=15,
        )
        if res.returncode != 0 or "SMOKE_IMPORT_OK" not in res.stdout:
            return False, (res.stdout or "") + (res.stderr or "")
        return True, res.stdout.strip()
    except Exception as e:
        return False, f"subprocess exception: {e}"


def do_apply(dry_run):
    exists = os.path.exists(TARGET)
    log(f"Cible : {TARGET}")
    log(f"Etat  : {'EXISTE' if exists else 'ABSENT (creation)'}")

    if not exists:
        new_src = build_initial_file()
        ok, msg = validate(new_src, TARGET)
        if not ok:
            log(f"[ERR] validation contenu genere -> {msg}")
            sys.exit(3)
        log("Validation contenu genere: OK")
        if dry_run:
            log("DRY-RUN : fichier qui serait cree :")
            print("-" * 60)
            print(new_src)
            print("-" * 60)
            log("DRY-RUN termine, aucune ecriture.")
            return
        write_text(TARGET, new_src)
        log(f"[OK] fichier cree : {TARGET}")
        ok, info = smoke_import(TARGET)
        if not ok:
            log(f"[ERR] smoke import echec : {info}")
            try:
                os.remove(TARGET)
                log("Fichier supprime (rollback creation).")
            except Exception:
                pass
            sys.exit(4)
        log(f"[OK] smoke import : {info}")
        return

    # fichier existant : ajout idempotent des flags manquants
    original = read_text(TARGET)
    missing = [f for f in FLAGS if not has_flag(original, f[0])]
    present = [f[0] for f in FLAGS if has_flag(original, f[0])]
    if present:
        log(f"Deja presents : {present}")
    if not missing:
        log("Tous les flags Phase 3 sont deja presents -> rien a faire.")
        return

    log(f"A ajouter : {[f[0] for f in missing]}")

    # construire le bloc uniquement avec les flags manquants
    block_lines = ["", MARKER, "# Phase 3 broker flags (ajout incremental)"]
    for name, value, comment in missing:
        block_lines.append(f"{name} = {value}  # {comment}")
    block_lines.append("")
    block = "\n".join(block_lines)

    new_src = original.rstrip() + "\n" + block
    ok, msg = validate(new_src, TARGET)
    if not ok:
        log(f"[ERR] validation post-patch -> {msg}")
        sys.exit(5)
    log("Validation post-patch : OK")

    if dry_run:
        log("DRY-RUN : bloc qui serait ajoute :")
        print("-" * 60)
        print(block)
        print("-" * 60)
        log("DRY-RUN termine, aucune ecriture.")
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak.{ts}"
    shutil.copy2(TARGET, backup)
    log(f"[OK] backup -> {backup}")

    write_text(TARGET, new_src)
    log("[OK] patch applique")

    ok, info = smoke_import(TARGET)
    if not ok:
        log(f"[ERR] smoke import echec : {info}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback effectue depuis backup")
        sys.exit(6)
    log(f"[OK] smoke import : {info}")


def do_rollback():
    # Cherche le backup le plus recent
    d = os.path.dirname(TARGET)
    base = os.path.basename(TARGET)
    candidates = sorted(
        [f for f in os.listdir(d) if f.startswith(base + ".bak.")],
        reverse=True,
    )
    if candidates:
        backup = os.path.join(d, candidates[0])
        shutil.copy2(backup, TARGET)
        log(f"[OK] rollback depuis {backup}")
        return
    # Pas de backup -> si le fichier ne contient QUE notre creation, on le supprime
    if not os.path.exists(TARGET):
        log("bridge_config.py absent et aucun backup -> rien a faire.")
        return
    src = read_text(TARGET)
    if MARKER in src and "Cree par nextones-bridge-config-phase3.py" in src:
        os.remove(TARGET)
        log(f"[OK] fichier cree par ce script supprime : {TARGET}")
    else:
        log(
            "[ERR] aucun backup trouve et le fichier ne semble pas avoir "
            "ete cree par ce script -> rollback impossible."
        )
        sys.exit(7)


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
