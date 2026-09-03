# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-BROKER-MODULES-V1]
# Renomme les scripts livres en modules Python importables.
#
# Source -> Destination :
#   nextones-broker-shadow-executor.py -> broker_shadow_executor.py
#   nextones-risk-broker-check.py      -> risk_broker_check.py
#   nextones-broker-resolver.py        -> broker_resolver.py
#   nextones-order-translator.py       -> order_translator.py
#
# Garde-fous :
#   - precheck : les 4 sources existent et compilent (ast.parse)
#   - precheck : les 4 destinations N'EXISTENT PAS (sinon refus, --force pour overrider)
#   - operation : os.rename (atomique sur Windows si meme volume)
#   - postcheck : import dans subprocess pour chaque module + attributs cles
#   - rollback auto si un import postcheck echoue
#
# Modes :
#   py -3.13 nextones-install-broker-modules.py --dry-run
#   py -3.13 nextones-install-broker-modules.py
#   py -3.13 nextones-install-broker-modules.py --force          (ecrase destinations)
#   py -3.13 nextones-install-broker-modules.py --rollback       (defait le rename)

import argparse
import ast
import os
import shutil
import subprocess
import sys
import time

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"

RENAMES = [
    ("nextones-broker-shadow-executor.py", "broker_shadow_executor.py",
     ["execute_shadow", "snapshot_pnl"]),
    ("nextones-risk-broker-check.py", "risk_broker_check.py",
     ["check_broker_mapping"]),
    ("nextones-broker-resolver.py", "broker_resolver.py",
     ["resolve"]),
    ("nextones-order-translator.py", "order_translator.py",
     ["translate"]),
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def src_path(name):
    return os.path.join(PROD_DIR, name)


def precheck_sources():
    log("=== Precheck sources ===")
    bad = []
    for src, dst, attrs in RENAMES:
        p = src_path(src)
        if not os.path.exists(p):
            log(f"  [ERR] source absente : {src}")
            bad.append(src)
            continue
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                code = f.read()
            ast.parse(code)
            log(f"  [OK]  {src} ({len(code)} bytes)")
        except SyntaxError as e:
            log(f"  [ERR] ast.parse {src} : {e}")
            bad.append(src)
    if bad:
        log(f"Echec precheck sources : {bad}")
        sys.exit(2)


def precheck_destinations(force):
    log("=== Precheck destinations ===")
    conflicts = []
    for src, dst, attrs in RENAMES:
        p = src_path(dst)
        if os.path.exists(p):
            conflicts.append(dst)
            log(f"  [WARN] destination existe : {dst}")
        else:
            log(f"  [OK]   {dst} libre")
    if conflicts and not force:
        log(f"Conflits : {conflicts}. Relancer avec --force pour overrider.")
        sys.exit(3)
    if conflicts and force:
        log("  --force actif : les destinations existantes seront sauvegardees")


def smoke_import_one(module_name, attrs):
    code = (
        "import sys, importlib\n"
        f"sys.path.insert(0, r'{PROD_DIR}')\n"
        f"m = importlib.import_module('{module_name}')\n"
        "missing = []\n"
        f"for a in {attrs!r}:\n"
        "    if not hasattr(m, a):\n"
        "        missing.append(a)\n"
        "if missing:\n"
        "    print('SMOKE_FAIL missing=' + ','.join(missing))\n"
        "    raise SystemExit(1)\n"
        "print('SMOKE_OK ' + str([a for a in " + repr(attrs) + " if hasattr(m,a)]))\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, timeout=30,
    )
    return res.returncode == 0, (res.stdout + res.stderr).strip()


def do_install(dry_run, force):
    precheck_sources()
    precheck_destinations(force)

    if dry_run:
        log("=== DRY-RUN : actions qui seraient effectuees ===")
        for src, dst, attrs in RENAMES:
            log(f"  RENAME {src} -> {dst} (attrs: {attrs})")
        log("DRY-RUN termine, aucune ecriture.")
        return

    log("=== Renommage ===")
    rename_done = []  # (src, dst, backup_of_existing_dst)
    try:
        ts = time.strftime("%Y%m%d-%H%M%S")
        for src, dst, attrs in RENAMES:
            sp = src_path(src)
            dp = src_path(dst)
            backup_dst = None
            if os.path.exists(dp):
                backup_dst = dp + f".bak.{ts}"
                shutil.copy2(dp, backup_dst)
                os.remove(dp)
                log(f"  backup destination existante -> {backup_dst}")
            os.rename(sp, dp)
            log(f"  [OK] {src} -> {dst}")
            rename_done.append((src, dst, backup_dst))
    except Exception as e:
        log(f"ERREUR rename : {e}")
        # rollback partiel
        for src, dst, backup_dst in rename_done:
            try:
                os.rename(src_path(dst), src_path(src))
                if backup_dst:
                    shutil.copy2(backup_dst, src_path(dst))
                log(f"  rollback {dst} -> {src}")
            except Exception as e2:
                log(f"  [WARN] rollback partiel {dst} : {e2}")
        sys.exit(4)

    log("=== Smoke import par module ===")
    failed = []
    for src, dst, attrs in RENAMES:
        mod_name = dst[:-3]  # strip .py
        ok, out = smoke_import_one(mod_name, attrs)
        if ok:
            log(f"  [OK] {mod_name} -> {out}")
        else:
            log(f"  [ERR] {mod_name} -> {out}")
            failed.append(mod_name)

    if failed:
        log(f"=== Rollback complet : {failed} ===")
        for src, dst, backup_dst in rename_done:
            try:
                if os.path.exists(src_path(dst)):
                    os.rename(src_path(dst), src_path(src))
                    log(f"  rollback {dst} -> {src}")
                if backup_dst and os.path.exists(backup_dst):
                    shutil.copy2(backup_dst, src_path(dst))
                    log(f"  restore destination originale depuis {backup_dst}")
            except Exception as e:
                log(f"  [WARN] rollback {dst} : {e}")
        sys.exit(5)

    log("=" * 60)
    log("INSTALL TERMINE - 4 modules importables")
    log("=" * 60)


def do_rollback():
    """
    Defait le rename : recopie chaque destination vers son nom source d'origine.
    """
    log("=== Rollback : restaure les noms nextones-*.py ===")
    for src, dst, attrs in RENAMES:
        sp = src_path(src)
        dp = src_path(dst)
        if os.path.exists(sp):
            log(f"  {src} existe deja, skip {dst}")
            continue
        if not os.path.exists(dp):
            log(f"  {dst} absent, skip")
            continue
        os.rename(dp, sp)
        log(f"  [OK] {dst} -> {src}")
    log("Rollback termine.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="ecrase les destinations existantes (avec backup)")
    ap.add_argument("--rollback", action="store_true",
                    help="restaure les noms nextones-*.py")
    args = ap.parse_args()
    log(f"PROD_DIR : {PROD_DIR}")
    if args.rollback:
        do_rollback()
    else:
        do_install(dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    main()
