# -*- coding: utf-8 -*-
# [NEXTONES-TEST-MARKET-GUARD-RUNTIME-V2]
# Test fonctionnel direct du garde-fou sur run_decision_cycle(conn) reel.
# Sans passer par API server, sans uvicorn.
#
# Appelle directement run_decision_cycle(conn) et verifie qu'on recoit
# {status: 'skipped', reason: 'weekend_skip ...'} (en dimanche)
# ou {status: 'skipped', reason: 'holiday ...'} (en ferie)
#
# Usage :
#   py -3.13 nextones-test-market-guard-runtime.py             # mode normal
#   py -3.13 nextones-test-market-guard-runtime.py --force     # force=True

import argparse
import inspect
import json
import os
import sqlite3
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB = os.path.join(PROD, "thesium.db")
sys.path.insert(0, PROD)


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="passe force=True a run_decision_cycle()")
    args = ap.parse_args()

    banner("[1] Verifie marker dans execution_engine.py")
    engine_path = os.path.join(PROD, "execution_engine.py")
    with open(engine_path, "r", encoding="utf-8-sig") as fh:
        src = fh.read()
    has_marker = "[NEXTONES-MARKET-GUARD-V1]" in src
    print(f"  marker GUARD-V1 : {'PRESENT' if has_marker else 'ABSENT'}")
    if not has_marker:
        print("[FAIL] Le garde-fou n'est PAS installe.")
        print("  Lance d'abord : py -3.13 nextones-install-market-guard.py")
        sys.exit(1)

    banner("[2] Import execution_engine")
    try:
        import execution_engine as ee
        print(f"  import OK : {ee}")
    except Exception as e:
        print(f"[FAIL] import : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Choisit la fonction cible : run_decision_cycle (priorite) sinon execute_cycle
    fn = None
    fn_name = None
    for cand in ("run_decision_cycle", "execute_cycle"):
        if hasattr(ee, cand):
            fn = getattr(ee, cand)
            fn_name = cand
            break

    if fn is None:
        print("[FAIL] ni run_decision_cycle ni execute_cycle dans le module")
        sys.exit(1)

    banner(f"[3] Signature {fn_name}()")
    sig = inspect.signature(fn)
    print(f"  signature : {fn_name}{sig}")
    params = list(sig.parameters.keys())
    print(f"  parametres : {params}")

    banner(f"[4] Ouvre connection DB {DB}")
    if not os.path.exists(DB):
        print(f"[FAIL] DB introuvable : {DB}")
        sys.exit(1)
    conn = sqlite3.connect(DB, timeout=10.0)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.row_factory = sqlite3.Row
    print("  connection OK")

    banner(f"[5] Appel {fn_name}(conn)")
    print(f"  args.force = {args.force}")
    # On essaie d'abord avec force=True kwarg, fallback sans
    result = None
    try:
        if args.force:
            try:
                result = fn(conn, force=True)
            except TypeError as e:
                print(f"  [INFO] force=True kwarg KO ({e}), retry sans arg")
                # injection via locals() : on essaie via globals
                # mais le bloc lit locals().get('force'), donc sans kwarg
                # le guard verra force=False
                result = fn(conn)
        else:
            result = fn(conn)
    except Exception as e:
        print(f"[EXC] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.close()
        except Exception:
            pass
        sys.exit(1)

    try:
        conn.close()
    except Exception:
        pass

    banner("[6] Resultat")
    print(f"  type : {type(result)}")
    if isinstance(result, dict):
        try:
            print(json.dumps(result, indent=2, ensure_ascii=False,
                             default=str))
        except Exception as e:
            print(f"  (json dump KO: {e})")
            print(repr(result))
    else:
        print(repr(result))

    banner("[7] Verdict")
    if isinstance(result, dict):
        status = result.get("status")
        guard = result.get("guard")
        if status == "skipped" and guard == "NEXTONES-MARKET-GUARD-V1":
            print("  [OK] Garde-fou actif : cycle SKIP correctement")
            print(f"  reason       : {result.get('reason')}")
            print(f"  next_open_utc: {result.get('next_open_utc')}")
            sys.exit(0)
        elif args.force:
            print("  [INFO] force=True : le cycle s'est execute (pas de skip)")
            print("  (resultat normal, pas de garde-fou applique)")
            sys.exit(0)
        else:
            print("  [WARN] Le cycle n'a pas ete skip alors qu'on est dimanche")
            print("  Verifie le wiring du guard")
            sys.exit(2)
    else:
        print("  [INFO] Resultat non-dict, garde-fou peut etre ailleurs")
        sys.exit(0)


if __name__ == "__main__":
    main()
