# -*- coding: utf-8 -*-
# [NEXTONES-BRIDGE-CONFIG-PHASE3C-V1]
# Extension Phase 3C de bridge_config.py.
#
# Ajoute (ou met a jour) les flags suivants :
#   LIVE_DRY_RUN                 = True       # par defaut : route 'live' loggee mais
#                                              # pas d'ordre reel envoye
#   MAX_LIVE_NOTIONAL_PER_ORDER  = 100.0      # EUR, plafond par ordre
#   LIVE_INSTRUMENTS             = set()      # whitelist de thesium_ticker
#   MAX_LIVE_NAV                 = 300.0      # DOWNGRADE de 100000.0 -> 300.0
#                                              # (compte test 800 EUR)
#
# Strategie :
#   - Detecte presence de chaque flag dans le fichier existant
#   - Pour les flags manquants : append en fin de fichier
#   - Pour MAX_LIVE_NAV : si valeur != 300.0 -> remplace via regex
#   - Pour les autres flags presents : laisse en l'etat (idempotent)
#
# Garde-fous :
#   - backup avant toute ecriture
#   - ast.parse + py_compile + smoke import sur resultat
#   - rollback auto si validation echoue
#
# Usage :
#   py -3.13 nextones-bridge-config-phase3c.py --dry-run
#   py -3.13 nextones-bridge-config-phase3c.py

import argparse
import ast
import os
import py_compile
import re
import shutil
import subprocess
import sys
import time

TARGET = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\bridge_config.py"
MARKER = "# [NEXTONES-BRIDGE-CONFIG-PHASE3C-V1]"

# nom -> (valeur_str, commentaire)
NEW_FLAGS = {
    "LIVE_DRY_RUN": (
        "True",
        "Phase 3C: True=route 'live' loggee mais ordre PAS envoye au broker",
    ),
    "MAX_LIVE_NOTIONAL_PER_ORDER": (
        "100.0",
        "Phase 3C: plafond notional par ordre en EUR",
    ),
    "LIVE_INSTRUMENTS": (
        "set()",
        "Phase 3C: whitelist thesium_ticker autorises en live (vide=tous shadow)",
    ),
}

# Flag a downgrader (de 100000.0 -> 300.0)
DOWNGRADE_FLAG = "MAX_LIVE_NAV"
DOWNGRADE_NEW_VALUE = "300.0"
DOWNGRADE_COMMENT = (
    "Phase 3C: downgrade de 100000.0 a 300.0 (compte test 800 EUR)"
)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def has_flag(src, name):
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=", re.MULTILINE)
    return bool(pattern.search(src))


def current_value(src, name):
    pattern = re.compile(
        rf"^\s*{re.escape(name)}\s*=\s*([^\n#]+)",
        re.MULTILINE,
    )
    m = pattern.search(src)
    if m:
        return m.group(1).strip()
    return None


def replace_flag_value(src, name, new_value_str, comment=None):
    """Remplace la ligne NAME = ... par NAME = new_value (preserve indent)."""
    pattern = re.compile(
        rf"^(\s*){re.escape(name)}\s*=[^\n]*$",
        re.MULTILINE,
    )
    comment_suffix = f"  # {comment}" if comment else ""
    return pattern.sub(
        lambda m: f"{m.group(1)}{name} = {new_value_str}{comment_suffix}",
        src,
        count=1,
    )


def validate(src, path_hint):
    try:
        ast.parse(src)
    except SyntaxError as e:
        return False, f"ast.parse: {e}"
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
    target_dir = os.path.dirname(path) or "."
    code = (
        "import sys, importlib;"
        f"sys.path.insert(0, r'{target_dir}');"
        "m = importlib.import_module('bridge_config');"
        "vals = {k: getattr(m, k, '<MISSING>') for k in "
        "['BROKER_SHADOW_ENABLED','BROKER_LIVE_ENABLED','MAX_LIVE_NAV',"
        "'BROKER_LIVE_ACCOUNT','LIVE_DRY_RUN','MAX_LIVE_NOTIONAL_PER_ORDER',"
        "'LIVE_INSTRUMENTS']};"
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
    if not os.path.exists(TARGET):
        log(f"[ERR] {TARGET} introuvable.")
        log("Lance d'abord : py -3.13 nextones-bridge-config-phase3.py")
        sys.exit(2)

    log(f"Cible : {TARGET}")
    original = read_text(TARGET)
    log(f"Taille initiale : {len(original)} octets")

    # === 1. Detection des flags existants
    summary = []
    for name in list(NEW_FLAGS.keys()) + [DOWNGRADE_FLAG]:
        cv = current_value(original, name)
        summary.append((name, cv))
        log(f"  {name:35s} = {cv}")

    # === 2. Construction nouveau src
    src = original

    # Downgrade MAX_LIVE_NAV si besoin
    cv_nav = current_value(src, DOWNGRADE_FLAG)
    if cv_nav and cv_nav.split("#")[0].strip() != DOWNGRADE_NEW_VALUE:
        log(f"  -> downgrade {DOWNGRADE_FLAG} {cv_nav} -> {DOWNGRADE_NEW_VALUE}")
        src = replace_flag_value(src, DOWNGRADE_FLAG, DOWNGRADE_NEW_VALUE,
                                 comment=DOWNGRADE_COMMENT)
    elif cv_nav:
        log(f"  -> {DOWNGRADE_FLAG} deja a {DOWNGRADE_NEW_VALUE}, skip")
    else:
        # MAX_LIVE_NAV absent : on l'ajoutera comme nouveau flag
        log(f"  -> {DOWNGRADE_FLAG} absent, sera ajoute")
        NEW_FLAGS[DOWNGRADE_FLAG] = (DOWNGRADE_NEW_VALUE, DOWNGRADE_COMMENT)

    # Ajout des flags manquants
    missing = []
    for name, (value, comment) in NEW_FLAGS.items():
        if not has_flag(src, name):
            missing.append((name, value, comment))

    if missing:
        log(f"  -> a ajouter : {[m[0] for m in missing]}")
        block_lines = ["", MARKER, "# Phase 3C live router flags"]
        for name, value, comment in missing:
            block_lines.append(f"{name} = {value}  # {comment}")
        block_lines.append("")
        block = "\n".join(block_lines)
        src = src.rstrip() + "\n" + block
    else:
        log("  -> tous les flags Phase 3C deja presents")

    # === 3. Si rien n'a change
    if src == original:
        log("Aucune modification a appliquer.")
        return

    # === 4. Validation
    ok, msg = validate(src, TARGET)
    if not ok:
        log(f"[ERR] validation post-patch : {msg}")
        sys.exit(3)
    log("Validation post-patch : OK")

    # === 5. Dry-run preview
    if dry_run:
        log("DRY-RUN : diff (lignes ajoutees ou modifiees) :")
        print("-" * 60)
        # diff simple : lignes nouvelles ou modifiees
        old_lines = original.splitlines()
        new_lines = src.splitlines()
        for i, ln in enumerate(new_lines):
            if i >= len(old_lines) or old_lines[i] != ln:
                print(f"L{i+1}+ {ln}")
        print("-" * 60)
        log("DRY-RUN termine, aucune ecriture.")
        return

    # === 6. Backup + ecriture
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak.{ts}"
    shutil.copy2(TARGET, backup)
    log(f"[OK] backup -> {backup}")

    write_text(TARGET, src)
    log(f"[OK] patch ecrit ({len(src)} octets)")

    # === 7. Smoke import
    ok, info = smoke_import(TARGET)
    if not ok:
        log(f"[ERR] smoke import echec : {info}")
        shutil.copy2(backup, TARGET)
        log("[OK] rollback depuis backup")
        sys.exit(4)
    log(f"[OK] smoke import : {info}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    do_apply(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
