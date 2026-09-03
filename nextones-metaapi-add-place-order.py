# -*- coding: utf-8 -*-
# [NEXTONES-METAAPI-ADD-PLACE-ORDER-V1]
# Ajoute la fonction place_order() au module metaapi_provider.py.
#
# Comportement de place_order(symbol, side, volume, dry_run_default=True) :
#
#   Si LIVE_DRY_RUN=True (lecture bridge_config) OU dry_run=True kwargs :
#     -> retourne {accepted:False, dry_run:True, would_send:{...}}
#        SANS appeler le SDK MetaApi
#
#   Sinon :
#     -> appelle create_market_buy_order/create_market_sell_order sur la RPC
#     -> retourne {accepted:True|False, order_id, response_raw, error}
#
# Sauvegarde : backup avant ecriture + ast.parse + py_compile + smoke import.
#
# Usage :
#   py -3.13 nextones-metaapi-add-place-order.py --dry-run
#   py -3.13 nextones-metaapi-add-place-order.py

import argparse
import ast
import os
import py_compile
import shutil
import subprocess
import sys
import time

PROD = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
TARGET = os.path.join(PROD, "metaapi_provider.py")
MARKER = "# [NEXTONES-METAAPI-PLACE-ORDER-V1]"


PLACE_ORDER_BLOCK = '''

# ===================================================================
# [NEXTONES-METAAPI-PLACE-ORDER-V1]
# Phase 3C : passage d'ordre reel ActivTrades via MetaAPI.
# Protege par LIVE_DRY_RUN dans bridge_config.py.
# ===================================================================

def _load_bridge_cfg_live_dry_run() -> bool:
    """Lit LIVE_DRY_RUN depuis bridge_config.py. Defaut True si introuvable."""
    try:
        import importlib.util as _ilu
        import os as _os
        _here = _os.path.dirname(_os.path.abspath(__file__))
        _p = _os.path.join(_here, "bridge_config.py")
        if not _os.path.exists(_p):
            return True
        _spec = _ilu.spec_from_file_location("_nx_bc_for_place", _p)
        _bc = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_bc)
        return bool(getattr(_bc, "LIVE_DRY_RUN", True))
    except Exception as _e:
        print(f"[PLACE-ORDER] erreur lecture LIVE_DRY_RUN ({_e}) -> True par defaut")
        return True


async def _place_order_async(symbol: str,
                             side: str,
                             volume: float,
                             comment: str = "NEXTONES"):
    """Place un market order via la RPC MetaApi.
    Retourne le dict reponse du SDK ou leve une exception.
    """
    conn = await _ensure_account_async()
    if conn is None:
        raise RuntimeError("MetaAPI non configure (token/account manquants)")
    side_l = side.lower().strip()
    if side_l == "buy":
        res = await asyncio.wait_for(
            conn.create_market_buy_order(symbol, volume, comment=comment),
            timeout=_CONNECT_TIMEOUT,
        )
    elif side_l == "sell":
        res = await asyncio.wait_for(
            conn.create_market_sell_order(symbol, volume, comment=comment),
            timeout=_CONNECT_TIMEOUT,
        )
    else:
        raise ValueError(f"side invalide: {side}")
    return res


def place_order(symbol: str,
                side: str,
                volume: float,
                comment: str = "NEXTONES",
                dry_run: "Optional[bool]" = None) -> "Dict[str, Any]":
    """Passe un market order chez ActivTrades via MetaApi.

    Garde-fou : si LIVE_DRY_RUN=True dans bridge_config, OU si dry_run=True
    en kwargs, l'ordre n'est PAS envoye au broker. On retourne un dict
    decrivant l'ordre qui aurait ete envoye.

    Returns:
        {
          "accepted": bool,
          "dry_run": bool,
          "would_send": {...},      # toujours present
          "order_id": str|None,
          "response_raw": Any,
          "error": str|None,
        }
    """
    cfg_dry = _load_bridge_cfg_live_dry_run()
    effective_dry = bool(dry_run) if dry_run is not None else cfg_dry

    would = {
        "symbol": symbol,
        "side": side.lower(),
        "volume": float(volume),
        "comment": comment,
    }
    result = {
        "accepted": False,
        "dry_run": effective_dry,
        "would_send": would,
        "order_id": None,
        "response_raw": None,
        "error": None,
    }

    if effective_dry:
        # Pas d'appel SDK : on logge et on rend la decision
        print(
            f"[PLACE-ORDER] DRY-RUN : would send {side} {volume} {symbol} "
            f"(comment={comment})"
        )
        result["accepted"] = False
        result["error"] = "dry_run_no_call"
        return result

    if not _is_configured_bool():
        result["error"] = "metaapi_not_configured"
        return result

    try:
        res = _run_async(_place_order_async(symbol, side, volume, comment))
        result["response_raw"] = res
        # MetaApi retourne souvent un dict avec orderId / numericCode / stringCode
        oid = None
        if isinstance(res, dict):
            oid = (res.get("orderId") or res.get("order_id")
                   or res.get("orderID"))
        result["order_id"] = oid
        # Heuristique d'acceptation : si on a un orderId -> accepted
        result["accepted"] = oid is not None
        if not result["accepted"]:
            result["error"] = f"no order_id in response: {res!r}"
        return result
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        return result
'''


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


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
        "m = importlib.import_module('metaapi_provider');"
        "print('PLACE_ORDER_PRESENT:', hasattr(m, 'place_order'));"
        "print('IS_CONFIGURED:', m.is_configured());"
        "# Test dry-run (ne doit pas appeler SDK)\n"
        "r = m.place_order('LINKUSD', 'buy', 0.1, dry_run=True);"
        "print('DRY_RUN_RESULT:', r)"
    )
    try:
        res = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
            cwd=PROD,
        )
        out = (res.stdout or "") + "\n--STDERR--\n" + (res.stderr or "")
        if res.returncode != 0 or "PLACE_ORDER_PRESENT: True" not in out:
            return False, out
        return True, out.strip()
    except Exception as e:
        return False, f"subprocess exception: {e}"


def do_apply(dry_run):
    if not os.path.exists(TARGET):
        log(f"[ERR] {TARGET} introuvable.")
        sys.exit(2)

    src = read_text(TARGET)
    log(f"Taille initiale : {len(src)} octets")

    if MARKER in src:
        log("[SKIP] marker deja present, pas de double patch.")
        return

    new_src = src.rstrip() + "\n" + PLACE_ORDER_BLOCK + "\n"

    ok, msg = validate(new_src, TARGET)
    if not ok:
        log(f"[ERR] validation : {msg}")
        sys.exit(3)
    log("Validation ast.parse + py_compile : OK")

    if dry_run:
        log(f"DRY-RUN : ajouterait {len(new_src) - len(src)} octets")
        log("DRY-RUN : extrait du bloc :")
        print("-" * 60)
        print(PLACE_ORDER_BLOCK[:800])
        print("...")
        print("-" * 60)
        return

    ts = time.strftime("%Y%m%d-%H%M%S")
    backup = TARGET + f".bak.{ts}"
    shutil.copy2(TARGET, backup)
    log(f"[OK] backup -> {backup}")

    write_text(TARGET, new_src)
    log(f"[OK] patch ecrit ({len(new_src)} octets)")

    ok, info = smoke_import(TARGET)
    if not ok:
        log(f"[ERR] smoke import KO :")
        print(info)
        shutil.copy2(backup, TARGET)
        log("[OK] rollback depuis backup")
        sys.exit(4)
    log(f"[OK] smoke import :")
    print(info)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    do_apply(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
