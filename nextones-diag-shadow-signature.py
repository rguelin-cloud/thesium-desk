# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-SIGNATURE-V1]
# Charge nextones-broker-shadow-executor.py par chemin de fichier
# (meme pattern que _nx_broker_check_load) et affiche les signatures
# exactes de execute_shadow et snapshot_pnl.
#
# Usage : py -3.13 nextones-diag-shadow-signature.py

import importlib.util
import inspect
import os
import sys

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGETS = [
    ("nextones-broker-shadow-executor.py", ["execute_shadow", "snapshot_pnl"]),
    ("nextones-risk-broker-check.py", ["check_broker_mapping"]),
    ("nextones-broker-resolver.py", ["resolve"]),
    ("nextones-order-translator.py", ["translate"]),
]


def load_by_path(filename, modname):
    p = os.path.join(PROD_DIR, filename)
    if not os.path.exists(p):
        return None, f"fichier absent: {p}"
    try:
        spec = importlib.util.spec_from_file_location(modname, p)
        if spec is None or spec.loader is None:
            return None, "spec invalide"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, None
    except Exception as e:
        return None, f"exec_module: {e}"


def show(filename, attrs):
    print("=" * 72)
    print(f"FICHIER: {filename}")
    print("-" * 72)
    modname = "_diag_" + filename.replace(".py", "").replace("-", "_")
    mod, err = load_by_path(filename, modname)
    if err:
        print(f"  [ERR] {err}")
        return
    print(f"  [OK] charge depuis {getattr(mod, '__file__', '?')}")
    for a in attrs:
        f = getattr(mod, a, None)
        if f is None:
            print(f"  [ERR] attribut absent : {a}")
            continue
        try:
            sig = inspect.signature(f)
            print(f"  {a}{sig}")
            doc = inspect.getdoc(f)
            if doc:
                head = doc.split("\n\n", 1)[0]
                print(f"    docstring (1er para) : {head[:300]}")
        except (ValueError, TypeError) as e:
            print(f"  {a} : signature inaccessible ({e})")
    # Liste aussi toutes les fonctions top-level pour reference
    print("  -- toutes les callables top-level :")
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if callable(obj):
            try:
                sig = inspect.signature(obj)
                print(f"    {name}{sig}")
            except (ValueError, TypeError):
                print(f"    {name}(?)")
    print()


def main():
    print(f"PROD_DIR : {PROD_DIR}")
    print()
    for filename, attrs in TARGETS:
        show(filename, attrs)


if __name__ == "__main__":
    main()
