# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-RECONCILER-V2-FIX]
# Corrige resolve_via_resolver() dans nextones-broker-reconciler.py :
# le resolver renvoie un dataclass BrokerMatch, pas un dict.
# On ajoute la branche dataclass + getattr().
#
# Validation stricte : ast.parse + py_compile + smoke --help + backup auto.
#
# Usage : py -3.13 nextones-broker-reconciler-v2-fix.py [--dry-run]

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

OLD_BLOCK = '''    if res is None:
        return None
    # res est attendu sous forme dict avec broker_symbol/specs ou un tuple
    if isinstance(res, dict):
        bs = res.get("broker_symbol")
        if not bs:
            return None
        specs = res.get("specs") or res.get("diagnostics", {}).get("specs") or {}
        return {
            "broker_symbol": bs,
            "contract_size": float(specs.get("contract_size", 1.0)),
            "lot_step": float(specs.get("lot_step", 0.01)),
            "source": res.get("source") or res.get("resolver_source") or "resolver",
            "asset_class": res.get("asset_class")
            or res.get("diagnostics", {}).get("asset_class"),
        }
    return None'''

NEW_BLOCK = '''    if res is None:
        return None
    # Cas 1 : dataclass BrokerMatch (cas reel du resolver)
    bs = getattr(res, "broker_symbol", None)
    if bs is not None or hasattr(res, "thesium_ticker"):
        if not bs:
            return None
        return {
            "broker_symbol": bs,
            "contract_size": float(getattr(res, "contract_size", None) or 1.0),
            "lot_step": float(getattr(res, "lot_step", None) or 0.01),
            "source": getattr(res, "source", None) or "resolver",
            "asset_class": getattr(res, "asset_class", None),
            "tradable": getattr(res, "tradable", True),
        }
    # Cas 2 : dict (anciennes API)
    if isinstance(res, dict):
        bs = res.get("broker_symbol")
        if not bs:
            return None
        specs = res.get("specs") or res.get("diagnostics", {}).get("specs") or {}
        return {
            "broker_symbol": bs,
            "contract_size": float(specs.get("contract_size", 1.0)),
            "lot_step": float(specs.get("lot_step", 0.01)),
            "source": res.get("source") or res.get("resolver_source") or "resolver",
            "asset_class": res.get("asset_class")
            or res.get("diagnostics", {}).get("asset_class"),
        }
    return None'''


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
    print(f"  taille : {len(src)} octets")

    if "Cas 1 : dataclass BrokerMatch" in src:
        print("  [SKIP] fix dataclass deja applique")
        return

    if OLD_BLOCK not in src:
        print("[FAIL] bloc cible introuvable.")
        print("  Cherchez dans le fichier : 'res est attendu sous forme dict'")
        # diag : montre les premieres lignes du bloc resolve_via_resolver
        idx = src.find("def resolve_via_resolver")
        if idx >= 0:
            print("  Contexte autour de resolve_via_resolver :")
            print(src[idx:idx + 1500])
        sys.exit(1)

    banner("[2] Substitution")
    src2 = src.replace(OLD_BLOCK, NEW_BLOCK, 1)
    print(f"  taille apres : {len(src2)} octets")
    if src2 == src:
        print("[FAIL] aucune substitution effectuee")
        sys.exit(1)

    banner("[3] Validation ast.parse + py_compile")
    ast.parse(src2)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(src2)
        tmpname = tf.name
    try:
        py_compile.compile(tmpname, doraise=True)
        print("  [OK] py_compile")
    finally:
        try:
            os.unlink(tmpname)
        except Exception:
            pass

    banner("[4] Smoke --help")
    tmp_target = TARGET + ".tmpfix"
    with open(tmp_target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(src2)
    try:
        r = subprocess.run(
            ["py", "-3.13", tmp_target, "--help"],
            capture_output=True, text=True, timeout=30, cwd=PROD,
        )
        if r.returncode != 0:
            print(f"[FAIL] smoke rc={r.returncode}")
            print("STDERR:", r.stderr[-500:])
            sys.exit(1)
        print("  [OK] smoke --help rc=0")
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
