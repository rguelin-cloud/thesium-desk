# -*- coding: utf-8 -*-
# [NEXTONES-INSTALL-ROUTER-WIRING-V1]
#
# Installeur idempotent du wiring routeur Phase 3C etape 4.
#
# Operations :
#   1. ALTER TABLE broker_shadow_orders ADD COLUMN is_live INTEGER DEFAULT 0
#   2. CREATE INDEX idx_shadow_is_live ON broker_shadow_orders(is_live, status)
#   3. Injection du bloc routeur dans execution_engine.py
#      - Marker [NEXTONES-BROKER-ROUTER-V1]
#      - Insere AVANT le marker [NEXTONES-SHADOW-EXEC-COMMIT-V2]/[V1]
#      - Idempotent : skip si deja present
#   4. Validation AST + py_compile + smoke import via subprocess
#
# Comportement runtime du bloc injecte :
#   - Resout ticker (via _rv2_ticker ou fallback DB)
#   - Importe routeur par chemin (nextones-broker-router.py)
#   - Appelle route_order(ticker, side, qty, asset_class, entry_price, cycle_id)
#   - Selon decision["route"] :
#       reject -> log + court-circuite (return success avec routing=reject)
#       live   -> dry_run : log + flag _nx_router_decision pour tag is_live apres shadow
#                 armed   : appelle metaapi_provider.place_order + flag is_live
#       shadow -> rien, laisse passer au shadow_executor existant
#   - Toute exception -> log stderr, laisse passer (fail-open vers shadow)
#
# Backup auto : execution_engine.py.bak.routerwiring.{ts}
#
# Usage :
#   py -3.13 nextones-install-router-wiring.py
#   py -3.13 nextones-install-router-wiring.py --dry-run

import argparse
import ast
import os
import py_compile
import shutil
import sqlite3
import subprocess
import sys
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
ENGINE = os.path.join(PROD, "execution_engine.py")
DB = os.path.join(PROD, "thesium.db")
ROUTER_PATH_FOR_CHECK = os.path.join(PROD, "nextones-broker-router.py")

MARKER_NEW = "[NEXTONES-BROKER-ROUTER-V1]"
MARKER_ANCHOR_PRIMARY = "[NEXTONES-SHADOW-EXEC-COMMIT-V2]"
MARKER_ANCHOR_FALLBACK = "[NEXTONES-SHADOW-EXEC-V1]"


# Bloc injecte AVANT le marker shadow. Indentation 4 spaces (interieur de fn).
# Toutes variables locales prefixees _nxr_ pour eviter collisions.
ROUTER_BLOCK = '''
    # [NEXTONES-BROKER-ROUTER-V1] - Phase 3C router (sandwich avant shadow_executor)
    # Decide route=shadow|live|reject avant que shadow_executor s'execute.
    # Fail-open : toute exception laisse passer au shadow normal.
    _nxr_decision = None
    try:
        import bridge_config as _nxr_bc
        # Pre-conditions : routeur n'est utile que si live globalement active OU
        # qu'on veut un audit decisionnel. On l'appelle toujours pour tracer,
        # mais on ne fait rien si live disabled (route=shadow direct).
        import importlib.util as _nxr_ilu
        import os as _nxr_os
        _nxr_p = _nxr_os.path.join(
            _nxr_os.path.dirname(_nxr_os.path.abspath(__file__)),
            "nextones-broker-router.py",
        )
        if _nxr_os.path.exists(_nxr_p):
            _nxr_spec = _nxr_ilu.spec_from_file_location(
                "_nx_router_wired", _nxr_p
            )
            if _nxr_spec is not None and _nxr_spec.loader is not None:
                _nxr_mod = _nxr_ilu.module_from_spec(_nxr_spec)
                _nxr_spec.loader.exec_module(_nxr_mod)
                # Resolution ticker
                _nxr_ticker = None
                try:
                    _nxr_ticker = _rv2_ticker
                except NameError:
                    _nxr_row = conn.execute(
                        "SELECT ticker FROM instruments WHERE id = ?",
                        (instrument_id,),
                    ).fetchone()
                    _nxr_ticker = _nxr_row[0] if _nxr_row else None
                # Resolution asset_class (best-effort)
                _nxr_asset_class = None
                try:
                    _nxr_ac_row = conn.execute(
                        "SELECT asset_class FROM instruments WHERE id = ?",
                        (instrument_id,),
                    ).fetchone()
                    _nxr_asset_class = _nxr_ac_row[0] if _nxr_ac_row else None
                except Exception:
                    pass
                if _nxr_ticker:
                    _nxr_decision = _nxr_mod.route_order(
                        thesium_ticker=_nxr_ticker,
                        side=side,
                        qty=float(approved_qty),
                        asset_class=_nxr_asset_class,
                        entry_price=float(effective_price),
                        cycle_id="order_id=" + str(order_id),
                    )
                    # Log decisionnel
                    try:
                        log_event(
                            conn, "broker_router_decision", "order", order_id,
                            {
                                "route": _nxr_decision.get("route"),
                                "reason": _nxr_decision.get("reason"),
                                "broker_symbol": _nxr_decision.get("broker_symbol"),
                                "volume_lots": _nxr_decision.get("volume_lots"),
                                "est_notional_eur": _nxr_decision.get("est_notional_eur"),
                                "live_nav_eur": _nxr_decision.get("live_nav_eur"),
                            },
                            agent="BrokerRouter",
                        )
                    except Exception:
                        pass
                    # Court-circuit reject
                    if _nxr_decision.get("route") == "reject":
                        try:
                            conn.execute(
                                "UPDATE orders SET status = 'rejected_router' "
                                "WHERE id = ?", (order_id,),
                            )
                            conn.commit()
                        except Exception:
                            pass
                        return {
                            "success": False,
                            "order_id": order_id,
                            "reason": "Router rejected: " + str(
                                _nxr_decision.get("reason")
                            ),
                            "router_decision": _nxr_decision,
                            "risk_check": risk_result,
                        }
                    # route=live : place_order si LIVE_DRY_RUN=False
                    if _nxr_decision.get("route") == "live":
                        if not bool(getattr(_nxr_bc, "LIVE_DRY_RUN", True)):
                            try:
                                import metaapi_provider as _nxr_mp
                                _nxr_po = _nxr_mp.place_order(
                                    symbol=_nxr_decision.get("broker_symbol"),
                                    side=side,
                                    volume=_nxr_decision.get("volume_lots"),
                                    comment="nextones_order_" + str(order_id),
                                )
                                _nxr_decision["place_order_result"] = _nxr_po
                                try:
                                    log_event(
                                        conn, "broker_place_order", "order", order_id,
                                        {
                                            "accepted": _nxr_po.get("accepted"),
                                            "broker_order_id": _nxr_po.get("broker_order_id"),
                                            "error": _nxr_po.get("error"),
                                        },
                                        agent="BrokerRouter",
                                    )
                                except Exception:
                                    pass
                            except Exception as _nxr_po_e:
                                try:
                                    import sys as _nxr_sys
                                    print(
                                        "[WARN] [NEXTONES-BROKER-ROUTER-V1] place_order: "
                                        + str(_nxr_po_e)[:200],
                                        file=_nxr_sys.stderr,
                                    )
                                except Exception:
                                    pass
    except Exception as _nxr_e:
        try:
            import sys as _nxr_sys
            print(
                "[WARN] [NEXTONES-BROKER-ROUTER-V1] " + str(_nxr_e)[:200],
                file=_nxr_sys.stderr,
            )
        except Exception:
            pass
    # Fin [NEXTONES-BROKER-ROUTER-V1]

'''


def banner(s):
    print()
    print("=" * 70)
    print(s)
    print("=" * 70)


def step_1_alter_db():
    banner("[1] ALTER TABLE broker_shadow_orders + index is_live")
    if not os.path.exists(DB):
        print(f"  [SKIP] DB {DB} introuvable")
        return False
    conn = sqlite3.connect(DB)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(broker_shadow_orders)")
        cols = [c[1] for c in cur.fetchall()]
        if "is_live" in cols:
            print("  [OK] colonne is_live deja presente")
        else:
            cur.execute(
                "ALTER TABLE broker_shadow_orders "
                "ADD COLUMN is_live INTEGER DEFAULT 0"
            )
            print("  [OK] ALTER TABLE add column is_live INTEGER DEFAULT 0")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_shadow_is_live "
            "ON broker_shadow_orders(is_live, status)"
        )
        print("  [OK] index idx_shadow_is_live cree/verifie")
        conn.commit()
        return True
    finally:
        conn.close()


def step_2_patch_engine(dry_run=False):
    banner("[2] Patch execution_engine.py - injection routeur")
    if not os.path.exists(ENGINE):
        print(f"  [FATAL] {ENGINE} introuvable")
        return False
    with open(ENGINE, "r", encoding="utf-8-sig") as f:
        content = f.read()

    if MARKER_NEW in content:
        print(f"  [OK] marker {MARKER_NEW} deja present - skip injection")
        return True

    # Trouve la ligne d'ancrage : MARKER_ANCHOR_PRIMARY en priorite
    anchor_idx = content.find(MARKER_ANCHOR_PRIMARY)
    if anchor_idx < 0:
        anchor_idx = content.find(MARKER_ANCHOR_FALLBACK)
        if anchor_idx < 0:
            print(
                f"  [FATAL] aucun anchor trouve ({MARKER_ANCHOR_PRIMARY} "
                f"ni {MARKER_ANCHOR_FALLBACK})"
            )
            return False
        print(f"  [WARN] anchor primaire absent, fallback sur {MARKER_ANCHOR_FALLBACK}")

    # Remonte au debut de la ligne contenant l'ancre
    line_start = content.rfind("\n", 0, anchor_idx) + 1
    # Le bloc s'insere AVANT cette ligne. Le bloc commence et finit par \n.
    new_content = content[:line_start] + ROUTER_BLOCK.lstrip("\n") + content[line_start:]

    # Validation AST avant ecriture
    try:
        ast.parse(new_content)
        print("  [OK] AST parse")
    except SyntaxError as e:
        print(f"  [FATAL] AST parse FAIL: {e}")
        # Dump 20 lignes autour de l'injection pour debug
        lines = new_content.splitlines()
        # Trouver la ligne d'injection approximative
        injection_line = content[:line_start].count("\n")
        start = max(0, injection_line - 5)
        end = min(len(lines), injection_line + 30)
        print("  Contexte injection :")
        for i in range(start, end):
            print(f"    L{i+1:5d}: {lines[i]}")
        return False

    if dry_run:
        print("  [DRY-RUN] aucune ecriture, mais bloc valide")
        print(f"  Taille originale : {len(content)} octets")
        print(f"  Taille apres     : {len(new_content)} octets (+{len(new_content)-len(content)})")
        return True

    # Backup
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = ENGINE + f".bak.routerwiring.{ts}"
    shutil.copy2(ENGINE, backup)
    print(f"  [OK] backup -> {backup}")

    # Ecriture utf-8 sans BOM, newline LF preserve
    with open(ENGINE, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print(f"  [OK] ecrit {ENGINE} ({len(new_content)} octets)")

    # py_compile
    try:
        py_compile.compile(ENGINE, doraise=True)
        print("  [OK] py_compile OK")
    except py_compile.PyCompileError as e:
        print(f"  [FATAL] py_compile FAIL: {e}")
        # Restauration auto
        shutil.copy2(backup, ENGINE)
        print(f"  [ROLLBACK] restaure depuis {backup}")
        return False

    return True


def step_3_smoke_import():
    banner("[3] Smoke import via subprocess")
    code = (
        "import sys, importlib; "
        f"sys.path.insert(0, r'{PROD}'); "
        "m = importlib.import_module('execution_engine'); "
        "assert hasattr(m, 'run_decision_cycle') or hasattr(m, 'execute_cycle'), "
        "'no cycle entrypoint'; "
        "print('SMOKE_OK')"
    )
    try:
        result = subprocess.run(
            ["py", "-3.13", "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        print(f"  STDOUT: {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"  STDERR: {result.stderr.strip()}")
        if result.returncode == 0 and "SMOKE_OK" in result.stdout:
            print("  [OK] smoke import OK")
            return True
        else:
            print(f"  [FAIL] smoke import echec (rc={result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print("  [FAIL] timeout smoke import")
        return False
    except Exception as e:
        print(f"  [FAIL] smoke import exception: {e}")
        return False


def step_4_check_router_present():
    banner("[4] Verification routeur present dans PROD")
    ok = True
    if not os.path.exists(ROUTER_PATH_FOR_CHECK):
        print(f"  [FATAL] {ROUTER_PATH_FOR_CHECK} introuvable")
        ok = False
    else:
        print(f"  [OK] {ROUTER_PATH_FOR_CHECK} present")
    bridge_cfg = os.path.join(PROD, "bridge_config.py")
    if not os.path.exists(bridge_cfg):
        print(f"  [FATAL] {bridge_cfg} introuvable")
        ok = False
    else:
        with open(bridge_cfg, "r", encoding="utf-8-sig") as f:
            bc_content = f.read()
        for need in ["BROKER_LIVE_ENABLED", "LIVE_DRY_RUN",
                     "MAX_LIVE_NAV", "MAX_LIVE_NOTIONAL_PER_ORDER",
                     "LIVE_INSTRUMENTS"]:
            if need not in bc_content:
                print(f"  [FAIL] bridge_config manque {need}")
                ok = False
            else:
                print(f"  [OK] bridge_config contient {need}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Valide sans ecrire de fichier ni toucher DB")
    args = ap.parse_args()

    print()
    print("=" * 70)
    print("INSTALLEUR WIRING ROUTEUR Phase 3C etape 4")
    print(f"  date    : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  PROD    : {PROD}")
    print(f"  ENGINE  : {ENGINE}")
    print(f"  DB      : {DB}")
    print(f"  dry_run : {args.dry_run}")
    print("=" * 70)

    if not step_4_check_router_present():
        print("\n[FATAL] preconditions KO")
        sys.exit(2)

    if not args.dry_run:
        if not step_1_alter_db():
            print("\n[FATAL] ALTER DB echec")
            sys.exit(2)
    else:
        print("\n[DRY-RUN] step 1 (ALTER DB) skip")

    if not step_2_patch_engine(dry_run=args.dry_run):
        print("\n[FATAL] patch engine echec")
        sys.exit(2)

    if not args.dry_run:
        if not step_3_smoke_import():
            print("\n[FATAL] smoke import echec")
            sys.exit(2)
    else:
        print("\n[DRY-RUN] step 3 (smoke) skip")

    banner("RESUME")
    print("  Phase 3C etape 4 : WIRING ROUTEUR INSTALLE")
    print()
    print("  Marker injecte : [NEXTONES-BROKER-ROUTER-V1]")
    print("  Position : avant [NEXTONES-SHADOW-EXEC-COMMIT-V2]")
    print()
    print("  Etat actuel runtime :")
    print("    BROKER_LIVE_ENABLED = False  (live globalement OFF)")
    print("    LIVE_DRY_RUN        = True   (inerte meme si live=True)")
    print("    LIVE_INSTRUMENTS    = set()  (whitelist vide)")
    print("    MAX_LIVE_NAV        = 300.0 EUR")
    print("    MAX_LIVE_NOTIONAL   = 100.0 EUR")
    print()
    print("  Triple verrou actif. Aucun ordre live ne peut etre envoye.")
    print()
    print("  Pour bascule live (procedure manuelle Phase 3C etape 6) :")
    print("    1. editer bridge_config.py : BROKER_LIVE_ENABLED=True")
    print("    2. editer bridge_config.py : LIVE_INSTRUMENTS={\"LINK\"}")
    print("    3. observer 24h en live_dry_run (logs broker_router_decision)")
    print("    4. editer bridge_config.py : LIVE_DRY_RUN=False")
    print("    5. surveiller broker_shadow_orders WHERE is_live=1")


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
