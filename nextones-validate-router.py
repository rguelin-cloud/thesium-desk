# -*- coding: utf-8 -*-
# [NEXTONES-VALIDATE-ROUTER-V1]
#
# Validator du routeur Phase 3C.
# Teste les 6 scenarios cles via manipulation temporaire de bridge_config :
#
#   [1] BROKER_LIVE_ENABLED=False -> tout va en shadow (live_disabled)
#   [2] Live enabled + ticker hors whitelist -> shadow (not_in_live_whitelist)
#   [3] Live enabled + ticker whitelist + LIVE_DRY_RUN=True -> live (dry_run)
#   [4] Live enabled + notional > MAX_LIVE_NOTIONAL_PER_ORDER -> reject
#   [5] Live enabled + (NAV + notional) > MAX_LIVE_NAV -> reject
#   [6] Live enabled + asset_class='equity' + samedi -> reject (market_closed)
#       Live enabled + asset_class='crypto' + samedi -> live (24/7)
#
# Methode : on backup bridge_config.py + on cree un overlay temporaire
# en memoire via module patching, on tient le routeur en self-test.
# Pour eviter de toucher au prod bridge_config, on appelle directement
# les fonctions internes du routeur en injectant les valeurs.
#
# Strategie de test :
#   - Backup bridge_config.py vers .bak.test.{ts}
#   - Pour chaque scenario : reecrit bridge_config.py avec les valeurs cibles
#   - Appelle nextones-broker-router.route_order()
#   - Verifie le dict retourne
#   - Restaure bridge_config.py original a la fin
#
# Exit codes :
#   0 = all pass
#   1 = au moins un FAIL
#   2 = pre-conditions KO
#
# Usage :
#   py -3.13 nextones-validate-router.py

import importlib
import importlib.util as ilu
import os
import shutil
import sys
import time
import traceback

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
BRIDGE_CFG = os.path.join(PROD, "bridge_config.py")
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


def check(label, cond, expected=None, got=None, fatal=False):
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
    if fatal:
        print("[FATAL] arret immediat")
        summary()
        sys.exit(2)
    return False


def _load_router_fresh():
    """Force un reimport du routeur pour qu'il relise bridge_config."""
    # Le routeur charge bridge_config a chaque appel route_order() via
    # _load_bridge_config() qui re-execute le module. Donc pas besoin
    # de purger un cache. On charge le routeur lui-meme une seule fois.
    spec = ilu.spec_from_file_location("_nx_router", ROUTER)
    mod = ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_bridge_cfg(content):
    with open(BRIDGE_CFG, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    # Force mtime a now pour invalider tout cache filesystem
    # (Windows + NTFS peut mettre en cache si mtime < 1s).
    os.utime(BRIDGE_CFG, None)
    # Invalide __pycache__ Python (importlib bytecode cache).
    importlib.invalidate_caches()
    # Purge sys.modules au cas ou bridge_config y serait reste
    sys.modules.pop("bridge_config", None)
    # Supprime le .pyc s'il existe (defensive contre PYTHONDONTWRITEBYTECODE off)
    cache_dir = os.path.join(PROD, "__pycache__")
    if os.path.isdir(cache_dir):
        for fn in os.listdir(cache_dir):
            if fn.startswith("bridge_config.") and fn.endswith(".pyc"):
                try:
                    os.remove(os.path.join(cache_dir, fn))
                except OSError:
                    pass
    # Granularite mtime
    time.sleep(0.02)


def _read_bridge_cfg():
    with open(BRIDGE_CFG, "r", encoding="utf-8-sig") as f:
        return f.read()


def _make_cfg(**overrides):
    """Genere un bridge_config.py minimal mais complet."""
    defaults = {
        "BROKER_SHADOW_ENABLED": True,
        "BROKER_LIVE_ENABLED": False,
        "BROKER_LIVE_ACCOUNT": '"ACTIVTRADES"',
        "MAX_LIVE_NAV": 300.0,
        "LIVE_DRY_RUN": True,
        "MAX_LIVE_NOTIONAL_PER_ORDER": 100.0,
        "LIVE_INSTRUMENTS": "set()",
    }
    for k, v in overrides.items():
        defaults[k] = v

    lines = [
        "# -*- coding: utf-8 -*-",
        '"""',
        "bridge_config.py (genere temporairement par nextones-validate-router)",
        '"""',
        "",
    ]
    for k, v in defaults.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {v}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k} = {v}")
        elif isinstance(v, str):
            # Pour LIVE_INSTRUMENTS et BROKER_LIVE_ACCOUNT, v est deja
            # une expression Python valide
            lines.append(f"{k} = {v}")
        else:
            lines.append(f"{k} = {v!r}")
    lines.append("")
    return "\n".join(lines)


def main():
    print()
    print("=" * 60)
    print("VALIDATOR PHASE 3C ROUTER")
    print(f"  date  : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  PROD  : {PROD}")
    print("=" * 60)

    banner("[0] Pre-conditions")
    check(f"router present : {ROUTER}",
          os.path.exists(ROUTER), fatal=True)
    check(f"bridge_config present : {BRIDGE_CFG}",
          os.path.exists(BRIDGE_CFG), fatal=True)

    # Backup original
    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = BRIDGE_CFG + f".bak.validate-router.{ts}"
    shutil.copy2(BRIDGE_CFG, backup)
    print(f"  backup original -> {backup}")

    original_cfg = _read_bridge_cfg()

    # Charge routeur (sera reinstancie a chaque test via re-exec)
    try:
        router_mod = _load_router_fresh()
        check("import routeur par chemin", True)
    except Exception as e:
        check(f"import routeur : {e}", False, fatal=True)
        return

    try:
        # ============================================================
        # [1] live disabled -> shadow
        # ============================================================
        banner("[1] BROKER_LIVE_ENABLED=False -> shadow (live_disabled)")
        _write_bridge_cfg(_make_cfg(BROKER_LIVE_ENABLED=False))
        router_mod = _load_router_fresh()
        d = router_mod.route_order(
            "LINK", "buy", 1.0, asset_class="crypto", entry_price=12.0,
        )
        print(f"  reason: {d['reason']}")
        check("route = shadow", d["route"] == "shadow",
              expected="shadow", got=d["route"])
        check("reason = live_disabled", d["reason"] == "live_disabled",
              expected="live_disabled", got=d["reason"])

        # ============================================================
        # [2] live enabled + ticker non whiteliste
        # ============================================================
        banner("[2] Live + ticker non whitelist -> shadow")
        _write_bridge_cfg(_make_cfg(
            BROKER_LIVE_ENABLED=True,
            LIVE_INSTRUMENTS='{"BTC"}',  # LINK pas dans la whitelist
        ))
        router_mod = _load_router_fresh()
        d = router_mod.route_order(
            "LINK", "buy", 1.0, asset_class="crypto", entry_price=12.0,
        )
        print(f"  reason: {d['reason']}")
        check("route = shadow", d["route"] == "shadow",
              expected="shadow", got=d["route"])
        check("reason = not_in_live_whitelist",
              d["reason"] == "not_in_live_whitelist",
              expected="not_in_live_whitelist", got=d["reason"])

        # ============================================================
        # [3] live enabled + whiteliste + DRY_RUN
        # ============================================================
        banner("[3] Live + whitelist + DRY_RUN -> live (live_dry_run)")
        _write_bridge_cfg(_make_cfg(
            BROKER_LIVE_ENABLED=True,
            LIVE_DRY_RUN=True,
            LIVE_INSTRUMENTS='{"LINK"}',
        ))
        router_mod = _load_router_fresh()
        d = router_mod.route_order(
            "LINK", "buy", 0.1, asset_class="crypto", entry_price=12.0,
        )
        print(f"  reason: {d['reason']}")
        print(f"  est_notional_eur: {d.get('est_notional_eur')}")
        print(f"  volume_lots: {d.get('volume_lots')}")
        print(f"  broker_symbol: {d.get('broker_symbol')}")
        check("route = live", d["route"] == "live",
              expected="live", got=d["route"])
        check("reason = live_dry_run", d["reason"] == "live_dry_run",
              expected="live_dry_run", got=d["reason"])
        check("broker_symbol = LINKUSD",
              d.get("broker_symbol") == "LINKUSD",
              expected="LINKUSD", got=d.get("broker_symbol"))

        # ============================================================
        # [4] notional > MAX_LIVE_NOTIONAL_PER_ORDER
        # ============================================================
        banner("[4] notional > cap par ordre -> reject")
        _write_bridge_cfg(_make_cfg(
            BROKER_LIVE_ENABLED=True,
            LIVE_DRY_RUN=True,
            LIVE_INSTRUMENTS='{"LINK"}',
            MAX_LIVE_NOTIONAL_PER_ORDER=10.0,  # tres bas pour declencher
        ))
        router_mod = _load_router_fresh()
        # 1 lot * contract_size LINK * 12 USD / 1.08 EUR ~= 10 USD = 9.26 EUR
        # On force qty=10 pour bien depasser 10 EUR
        d = router_mod.route_order(
            "LINK", "buy", 10.0, asset_class="crypto", entry_price=12.0,
        )
        print(f"  reason: {d['reason']}")
        print(f"  est_notional_eur: {d.get('est_notional_eur')}")
        check("route = reject", d["route"] == "reject",
              expected="reject", got=d["route"])
        check("reason contient 'live_notional_per_order_exceeded'",
              "live_notional_per_order_exceeded" in d["reason"],
              expected="contains live_notional_per_order_exceeded",
              got=d["reason"])

        # ============================================================
        # [5] NAV cap exceeded
        # ============================================================
        banner("[5] NAV total + notional > MAX_LIVE_NAV -> reject")
        _write_bridge_cfg(_make_cfg(
            BROKER_LIVE_ENABLED=True,
            LIVE_DRY_RUN=True,
            LIVE_INSTRUMENTS='{"LINK"}',
            MAX_LIVE_NAV=5.0,  # tres bas, n'importe quel ordre passe au-dessus
            MAX_LIVE_NOTIONAL_PER_ORDER=1000.0,  # haut pour ne pas trigger [4]
        ))
        router_mod = _load_router_fresh()
        # qty=1 * 12 USD / 1.08 ~= 11 EUR > 5 EUR de cap
        d = router_mod.route_order(
            "LINK", "buy", 1.0, asset_class="crypto", entry_price=12.0,
        )
        print(f"  reason: {d['reason']}")
        print(f"  live_nav_eur: {d.get('live_nav_eur')}")
        print(f"  est_notional_eur: {d.get('est_notional_eur')}")
        check("route = reject", d["route"] == "reject",
              expected="reject", got=d["route"])
        check("reason contient 'live_nav_cap_exceeded'",
              "live_nav_cap_exceeded" in d["reason"],
              expected="contains live_nav_cap_exceeded",
              got=d["reason"])

        # ============================================================
        # [6] market closed pour equity vs crypto 24/7
        # ============================================================
        banner("[6] Equity dimanche -> reject / Crypto dimanche -> live")
        _write_bridge_cfg(_make_cfg(
            BROKER_LIVE_ENABLED=True,
            LIVE_DRY_RUN=True,
            LIVE_INSTRUMENTS='{"AAPL", "LINK"}',
            MAX_LIVE_NAV=10000.0,
            MAX_LIVE_NOTIONAL_PER_ORDER=10000.0,
        ))
        router_mod = _load_router_fresh()

        # equity un dimanche -> market_closed (sauf si test lance un jour ouvre)
        # Pour rendre le test reproductible on detecte le contexte courant
        import importlib.util as _ilu
        mc_path = os.path.join(PROD, "nextones-market-calendar.py")
        spec_mc = _ilu.spec_from_file_location("_nx_mc_for_test", mc_path)
        mc = _ilu.module_from_spec(spec_mc)
        spec_mc.loader.exec_module(mc)
        market_open_now = mc.is_us_market_open()
        print(f"  marche US ouvert maintenant : {market_open_now}")

        d_eq = router_mod.route_order(
            "AAPL", "buy", 0.1, asset_class="equity", entry_price=180.0,
        )
        print(f"  equity AAPL reason: {d_eq['reason']}")
        if not market_open_now:
            check("equity AAPL -> reject market_closed",
                  d_eq["route"] == "reject"
                  and d_eq["reason"] == "market_closed",
                  expected="reject market_closed",
                  got=f"{d_eq['route']} {d_eq['reason']}")
        else:
            check("equity AAPL -> live (marche ouvert)",
                  d_eq["route"] == "live",
                  expected="live", got=d_eq["route"])

        # crypto LINK -> live (24/7) peu importe le jour
        d_cr = router_mod.route_order(
            "LINK", "buy", 0.1, asset_class="crypto", entry_price=12.0,
        )
        print(f"  crypto LINK reason: {d_cr['reason']}")
        check("crypto LINK -> live (24/7)",
              d_cr["route"] == "live",
              expected="live", got=d_cr["route"])

        # ============================================================
        # Bonus : config_snapshot integre
        # ============================================================
        banner("[7] config_snapshot dans la decision")
        snap = d_cr.get("config_snapshot", {})
        check("snapshot contient BROKER_LIVE_ENABLED",
              "BROKER_LIVE_ENABLED" in snap)
        check("snapshot contient MAX_LIVE_NAV",
              "MAX_LIVE_NAV" in snap)
        check("snapshot.BROKER_LIVE_ENABLED == True",
              snap.get("BROKER_LIVE_ENABLED") is True,
              expected=True, got=snap.get("BROKER_LIVE_ENABLED"))

    finally:
        # Restauration ABSOLUE du bridge_config original
        banner("[CLEANUP] Restauration bridge_config.py original")
        try:
            _write_bridge_cfg(original_cfg)
            print(f"  [OK] bridge_config restaure ({len(original_cfg)} octets)")
        except Exception as e:
            print(f"  [FATAL] echec restauration : {e}")
            print(f"  Restaure manuellement depuis : {backup}")

    summary()


def summary():
    banner("RESUME")
    total = PASS + FAIL
    print(f"  PASS : {PASS} / {total}")
    print(f"  FAIL : {FAIL} / {total}")
    if FAIL == 0:
        print("  [OK] tous les tests passent")
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
        print(f"\n[EXC] {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(2)
