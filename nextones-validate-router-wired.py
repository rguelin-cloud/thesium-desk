# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-ROUTER-WIRED-V1]
#
# Validator runtime du wiring routeur dans execution_engine.py.
#
# Verifie :
#   [1] Le marker [NEXTONES-BROKER-ROUTER-V1] est present dans engine
#   [2] Le code injecte est syntaxiquement valide (re-AST)
#   [3] La colonne is_live existe dans broker_shadow_orders
#   [4] L'index idx_shadow_is_live existe
#   [5] Le routeur est importable et expose route_order
#   [6] Un appel route_order direct avec config prod retourne shadow (live disabled)
#   [7] log_event est bien defini dans execution_engine (necessaire au bloc)
#   [8] Le bloc routeur est positionne AVANT le bloc shadow_executor
#
# Aucun cycle reel n'est lance. Test passif sur l'etat installe.
#
# Usage : py -3.13 nextones-validate-router-wired.py

import importlib.util as ilu
import os
import sqlite3
import sys

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
ENGINE = os.path.join(PROD, "execution_engine.py")
DB = os.path.join(PROD, "thesium.db")
ROUTER = os.path.join(PROD, "nextones-broker-router.py")

sys.path.insert(0, PROD)

PASS = 0
FAIL = 0
FAILED = []


def banner(t):
    print()
    print("=" * 60)
    print(t)
    print("=" * 60)


def check(label, cond, expected=None, got=None):
    global PASS, FAIL, FAILED
    if cond:
        print(f"  [OK]   {label}")
        PASS += 1
        return True
    ex = f" expected={expected}" if expected is not None else ""
    gt = f" got={got}" if got is not None else ""
    print(f"  [FAIL] {label}{ex}{gt}")
    FAIL += 1
    FAILED.append(label)
    return False


def main():
    print()
    print("=" * 60)
    print("VALIDATOR WIRING ROUTEUR Phase 3C etape 4")
    print(f"  PROD : {PROD}")
    print("=" * 60)

    banner("[1] Pre-conditions fichiers")
    check("execution_engine.py present", os.path.exists(ENGINE))
    check("routeur present", os.path.exists(ROUTER))
    check("DB present", os.path.exists(DB))

    if not os.path.exists(ENGINE):
        summary()
        sys.exit(2)

    with open(ENGINE, "r", encoding="utf-8-sig") as f:
        engine_src = f.read()

    banner("[2] Marker injecte")
    n_marker = engine_src.count("[NEXTONES-BROKER-ROUTER-V1]")
    check(f"marker [NEXTONES-BROKER-ROUTER-V1] present ({n_marker} occ)",
          n_marker >= 1, expected=">=1", got=n_marker)

    banner("[3] AST engine apres patch")
    try:
        import ast
        ast.parse(engine_src)
        check("execution_engine.py parse AST", True)
    except SyntaxError as e:
        check(f"AST parse failed: {e}", False)

    banner("[4] Schema broker_shadow_orders.is_live")
    if os.path.exists(DB):
        conn = sqlite3.connect(DB)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(broker_shadow_orders)")
            cols = {c[1]: c for c in cur.fetchall()}
            check("colonne is_live presente", "is_live" in cols)
            if "is_live" in cols:
                col = cols["is_live"]
                check("type is_live = INTEGER",
                      col[2].upper() == "INTEGER",
                      expected="INTEGER", got=col[2])
                check("default is_live = 0",
                      str(col[4]) == "0",
                      expected="0", got=col[4])

            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_shadow_is_live'"
            )
            idx_row = cur.fetchone()
            check("index idx_shadow_is_live existe", idx_row is not None)
        finally:
            conn.close()

    banner("[5] Routeur importable + route_order")
    try:
        spec = ilu.spec_from_file_location("_nx_router_test", ROUTER)
        mod = ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        check("import routeur", True)
        check("expose route_order", hasattr(mod, "route_order"))
    except Exception as e:
        check(f"import routeur exc: {e}", False)
        summary()
        sys.exit(1)

    banner("[6] Appel route_order avec config prod (live=OFF)")
    try:
        d = mod.route_order(
            "LINK", "buy", 0.1, asset_class="crypto", entry_price=12.0,
        )
        print(f"  route   : {d['route']}")
        print(f"  reason  : {d['reason']}")
        # Config prod = BROKER_LIVE_ENABLED=False -> shadow live_disabled
        check("route = shadow (config prod)", d["route"] == "shadow",
              expected="shadow", got=d["route"])
        check("reason = live_disabled",
              d["reason"] == "live_disabled",
              expected="live_disabled", got=d["reason"])
        check("config_snapshot.BROKER_LIVE_ENABLED == False",
              d.get("config_snapshot", {}).get("BROKER_LIVE_ENABLED") is False,
              expected=False,
              got=d.get("config_snapshot", {}).get("BROKER_LIVE_ENABLED"))
    except Exception as e:
        check(f"route_order exc: {e}", False)

    banner("[7] log_event est defini dans engine")
    has_log_event = "def log_event(" in engine_src
    check("def log_event(...) present", has_log_event)

    banner("[8] Position : bloc routeur AVANT shadow_executor")
    pos_router = engine_src.find("[NEXTONES-BROKER-ROUTER-V1]")
    pos_shadow_commit = engine_src.find("[NEXTONES-SHADOW-EXEC-COMMIT-V2]")
    pos_shadow_main = engine_src.find("[NEXTONES-SHADOW-EXEC-V1]")
    pos_shadow = pos_shadow_commit if pos_shadow_commit >= 0 else pos_shadow_main
    print(f"  pos router         : {pos_router}")
    print(f"  pos shadow (anchor): {pos_shadow}")
    check("bloc routeur AVANT bloc shadow",
          0 <= pos_router < pos_shadow,
          expected="router < shadow",
          got=f"router={pos_router} shadow={pos_shadow}")

    banner("[9] Fin: bloc routeur termine bien (pas d'indent issue)")
    # On verifie qu'apres l'injection on retrouve bien le bloc shadow intact
    n_shadow_commit = engine_src.count("[NEXTONES-SHADOW-EXEC-COMMIT-V2]")
    check(f"marker SHADOW-EXEC-COMMIT-V2 toujours present ({n_shadow_commit} occ)",
          n_shadow_commit >= 1, expected=">=1", got=n_shadow_commit)
    n_shadow_v1 = engine_src.count("[NEXTONES-SHADOW-EXEC-V1]")
    check(f"marker SHADOW-EXEC-V1 toujours present ({n_shadow_v1} occ)",
          n_shadow_v1 >= 1, expected=">=1", got=n_shadow_v1)

    banner("[10] Bridge config triple verrou actif")
    bridge_cfg = os.path.join(PROD, "bridge_config.py")
    with open(bridge_cfg, "r", encoding="utf-8-sig") as f:
        bc_src = f.read()
    # Verifie qu'au demarrage on est bien inerte
    has_live_off = ("BROKER_LIVE_ENABLED = False" in bc_src
                    or "BROKER_LIVE_ENABLED=False" in bc_src)
    has_dry_on = ("LIVE_DRY_RUN = True" in bc_src
                  or "LIVE_DRY_RUN=True" in bc_src)
    has_whitelist_empty = ("LIVE_INSTRUMENTS = set()" in bc_src
                           or "LIVE_INSTRUMENTS=set()" in bc_src)
    check("verrou 1: BROKER_LIVE_ENABLED = False", has_live_off)
    check("verrou 2: LIVE_DRY_RUN = True", has_dry_on)
    check("verrou 3: LIVE_INSTRUMENTS = set()", has_whitelist_empty)

    summary()


def summary():
    banner("RESUME")
    total = PASS + FAIL
    print(f"  PASS : {PASS} / {total}")
    print(f"  FAIL : {FAIL} / {total}")
    if FAIL == 0:
        print("  [OK] wiring routeur valide bout-en-bout")
        sys.exit(0)
    else:
        print(f"  [KO] {FAIL} echec(s) :")
        for lbl in FAILED:
            print(f"    - {lbl}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        print(f"\n[EXC] {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(2)
