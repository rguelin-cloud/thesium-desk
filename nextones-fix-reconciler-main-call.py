# -*- coding: utf-8 -*-
# [NEXTONES-FIX-RECONCILER-MAIN-CALL]
# Corrige l'appel main() du reconciler V2 :
#   AVANT : fetch_mappings(con)
#   APRES : fetch_mappings(con, thesium_tickers=list(thesium_positions.keys()))
#
# Le diag a montre que thesium_positions est un dict (cf. fetch_thesium_positions
# qui retourne {ticker: {qty, last_price, ...}}), donc .keys() suffit.
#
# Validation : ast.parse + py_compile + smoke --help + backup auto.

import argparse
import ast
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "nextones-broker-reconciler.py")

OLD = "mapping_by_broker, mapping_by_thesium = fetch_mappings(con)"
NEW = ("mapping_by_broker, mapping_by_thesium = fetch_mappings("
       "con, thesium_tickers=list(thesium_positions.keys()))")


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    banner("[1] Lecture target")
    with open(TARGET, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    print(f"  taille initiale : {len(src)} octets")
    n_old = src.count(OLD)
    n_new = src.count("thesium_tickers=list(thesium_positions.keys())")
    print(f"  occurrences OLD : {n_old}")
    print(f"  occurrences NEW : {n_new}")

    if n_new > 0 and n_old == 0:
        print("  [SKIP] deja patche")
        return

    if n_old != 1:
        print(f"[FAIL] attendu 1 occurrence OLD, trouve {n_old}")
        # diag
        if "fetch_mappings(" in src:
            for i, ln in enumerate(src.splitlines(), 1):
                if "fetch_mappings(" in ln:
                    print(f"  L{i}: {ln.strip()}")
        sys.exit(1)

    banner("[2] Substitution")
    src2 = src.replace(OLD, NEW, 1)
    print(f"  taille apres : {len(src2)} octets")

    banner("[3] ast.parse + py_compile")
    ast.parse(src2)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(src2)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmpname)
        except Exception:
            pass

    banner("[4] Smoke --help")
    tmp_target = TARGET + ".tmpfix2"
    with open(tmp_target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src2)
    try:
        r = subprocess.run(
            ["py", "-3.13", tmp_target, "--help"],
            capture_output=True, text=True, timeout=30, cwd=PROD,
        )
        if r.returncode != 0:
            print(f"[FAIL] smoke rc={r.returncode}")
            print(r.stderr[-500:])
            sys.exit(1)
        print("  [OK]")
    finally:
        try:
            os.unlink(tmp_target)
        except Exception:
            pass

    if args.dry_run:
        banner("[5] DRY-RUN : pas d'ecriture")
    else:
        banner("[5] Backup + ecriture")
        bak = TARGET + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(TARGET, bak)
        print(f"  backup : {bak}")
        with open(TARGET, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(src2)
        print(f"  ecrit  : {TARGET}")

    banner("[6] DONE")
    print("  py -3.13 nextones-broker-reconciler.py --no-broker --verbose")


if __name__ == "__main__":
    main()
