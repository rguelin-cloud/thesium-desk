# -*- coding: utf-8 -*-
# [NEXTONES-DIAG-SHADOW-IMPORTS-V1]
# Verifie que les modules Phase 2/2.5 sont importables avant de wirer Phase 3A.
# Usage : py -3.13 nextones-diag-shadow-imports.py

import os
import sys
import traceback

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
sys.path.insert(0, PROD_DIR)


def check(modname, expected_attrs):
    print("-" * 60)
    print(f"Module: {modname}")
    try:
        m = __import__(modname)
    except Exception as e:
        print(f"  [ERR] import: {e}")
        traceback.print_exc(limit=3)
        return False
    print(f"  [OK] import (file={getattr(m, '__file__', '?')})")
    for a in expected_attrs:
        if hasattr(m, a):
            obj = getattr(m, a)
            print(f"  [OK] {a} -> {type(obj).__name__}")
        else:
            print(f"  [ERR] attribut manquant : {a}")
            return False
    return True


def show_signature(modname, funcname):
    try:
        import inspect
        m = __import__(modname)
        f = getattr(m, funcname, None)
        if f is None:
            print(f"  {modname}.{funcname} : ABSENT")
            return
        sig = inspect.signature(f)
        print(f"  {modname}.{funcname}{sig}")
    except Exception as e:
        print(f"  {modname}.{funcname} : ERR {e}")


def main():
    print(f"sys.path[0] = {sys.path[0]}")
    print()
    print("=" * 60)
    print("CHECK MODULES PHASE 2 / 2.5 / 3")
    print("=" * 60)

    ok1 = check("broker_shadow_executor", ["execute_shadow", "snapshot_pnl"])
    ok2 = check("risk_broker_check", ["check_broker_mapping"])
    ok3 = check("bridge_config", [
        "BROKER_SHADOW_ENABLED",
        "BROKER_LIVE_ENABLED",
        "MAX_LIVE_NAV",
        "BROKER_LIVE_ACCOUNT",
    ])
    ok4 = check("broker_resolver", ["resolve"])
    ok5 = check("order_translator", ["translate"])
    ok6 = check("risk_pretrade", ["run_pretrade_checks"])

    print()
    print("=" * 60)
    print("SIGNATURES DETAILLEES")
    print("=" * 60)
    show_signature("broker_shadow_executor", "execute_shadow")
    show_signature("broker_shadow_executor", "snapshot_pnl")
    show_signature("risk_broker_check", "check_broker_mapping")
    show_signature("broker_resolver", "resolve")
    show_signature("order_translator", "translate")

    print()
    print("=" * 60)
    print("VALEURS bridge_config")
    print("=" * 60)
    try:
        import bridge_config as bc
        for k in ("BROKER_SHADOW_ENABLED", "BROKER_LIVE_ENABLED",
                  "MAX_LIVE_NAV", "BROKER_LIVE_ACCOUNT"):
            print(f"  {k} = {getattr(bc, k, '<MISSING>')!r}")
    except Exception as e:
        print(f"  [ERR] {e}")

    print()
    print("=" * 60)
    verdict = all([ok1, ok2, ok3, ok4, ok5, ok6])
    print(f"VERDICT : {'PASS' if verdict else 'FAIL'} - "
          f"{'pret pour wiring Phase 3A' if verdict else 'corriger les imports avant patch'}")
    print("=" * 60)
    sys.exit(0 if verdict else 1)


if __name__ == "__main__":
    main()
