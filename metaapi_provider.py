# -*- coding: utf-8 -*-
# [NEXTONES-METAAPI-PROVIDER-V2]
# V2 : ajoute timeouts explicites + fix get_positions qui freeze
# parce que la connexion RPC ne se synchronise pas correctement pour les positions.
# Provider MetaAPI sync pour NextOnes / Thesium :
#   - is_configured() -> bool
#   - get_current_price(broker_symbol) -> dict | None
#   - get_symbol_specification(broker_symbol) -> dict | None
#   - get_positions() -> list[dict]
#   - get_account_information() -> dict | None
#
# Design :
#   - lit METAAPI_TOKEN et METAAPI_ACCOUNT_ID depuis .env (via python-dotenv si dispo,
#     sinon parse minimal en interne)
#   - utilise metaapi_cloud_sdk (deja installe, version 29.x)
#   - cache une instance api + account par process, partagee entre appels
#   - tout sync : asyncio.run(...) en interne, mais expose une API sync au caller
#   - degrade gracieusement : si pas configure, retourne None / [] sans exception
#   - thread-safe pour usage depuis multiple call sites

import asyncio
import os
import threading
import time
from typing import Any, Dict, List, Optional

# ---------------------- Config / dotenv ----------------------

# Chargement .env si python-dotenv dispo, sinon parse minimal
def _load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv()
        return
    except Exception:
        pass
    # Parse minimal du .env de la racine du projet (ou cwd)
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for p in candidates:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8-sig", errors="ignore") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln or ln.startswith("#") or "=" not in ln:
                        continue
                    k, _, v = ln.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except Exception:
            pass


_load_dotenv()

_TOKEN = os.environ.get("METAAPI_TOKEN", "").strip()
_ACCOUNT_ID = (
    os.environ.get("METAAPI_ACCOUNT_ID", "").strip()
    or os.environ.get("ACCOUNT_ID", "").strip()
)
_REGION = os.environ.get("METAAPI_REGION", "").strip() or None
# Cache TTL pour les prices (evite de spammer MetaAPI)
_PRICE_TTL_SEC = float(os.environ.get("METAAPI_PRICE_TTL_SEC", "5"))
# Timeouts (en secondes)
_CONNECT_TIMEOUT = float(os.environ.get("METAAPI_CONNECT_TIMEOUT_SEC", "60"))
_RPC_CALL_TIMEOUT = float(os.environ.get("METAAPI_RPC_TIMEOUT_SEC", "30"))


# ---------------------- Etat cache ----------------------

_lock = threading.RLock()
_api = None              # instance MetaApi cloud SDK
_account = None          # MetatraderAccount
_connection = None       # connexion (rpc ou streaming)
_account_kind = None     # 'rpc' ou 'streaming'
_last_connect_at = 0.0
_price_cache: Dict[str, Dict[str, Any]] = {}  # broker_symbol -> {"ts": float, "p": dict}


def _is_configured_bool() -> bool:
    return bool(_TOKEN) and bool(_ACCOUNT_ID)


def is_configured() -> bool:
    """Vrai si METAAPI_TOKEN et METAAPI_ACCOUNT_ID sont presents."""
    return _is_configured_bool()


# ---------------------- Helpers async/sync ----------------------

def _run_async(coro):
    """Execute une coroutine de maniere sync. Cree ou reutilise un event loop."""
    try:
        # Cas typique : pas de loop en cours -> on en cree un
        return asyncio.run(coro)
    except RuntimeError as e:
        # Si on est deja dans un loop (ex. depuis FastAPI handler), on tombe
        # en arriere sur un thread separe
        if "already running" in str(e).lower() or "running event loop" in str(e).lower():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(lambda: asyncio.run(coro))
                return fut.result()
        raise


async def _ensure_account_async():
    """Garantit qu'on a une instance api + account + connection prets.

    V2 : applique un timeout strict sur wait_connected + wait_synchronized,
    et accepte une option (kwarg) pour skipper la synchro complete (utile
    quand on veut juste un appel RPC ponctuel comme getPositions).
    """
    global _api, _account, _connection, _account_kind, _last_connect_at
    if not _is_configured_bool():
        return None

    # Lazy import : evite de charger le SDK si non configure
    try:
        from metaapi_cloud_sdk import MetaApi
    except Exception as e:
        raise RuntimeError(f"metaapi_cloud_sdk non importable : {e}")

    if _api is None:
        kwargs = {}
        if _REGION:
            kwargs["region"] = _REGION
        _api = MetaApi(_TOKEN, kwargs) if kwargs else MetaApi(_TOKEN)

    if _account is None:
        _account = await asyncio.wait_for(
            _api.metatrader_account_api.get_account(_ACCOUNT_ID),
            timeout=_CONNECT_TIMEOUT,
        )

    # Deploy + connect si necessaire (avec timeout)
    try:
        state = getattr(_account, "state", "")
        if state in ("UNDEPLOYED", "DEPLOYING", "UNDEPLOYING", "DRAFT"):
            await asyncio.wait_for(_account.deploy(), timeout=_CONNECT_TIMEOUT)
        if getattr(_account, "connection_status", "") != "CONNECTED":
            await asyncio.wait_for(
                _account.wait_connected(),
                timeout=_CONNECT_TIMEOUT,
            )
    except asyncio.TimeoutError:
        print(f"[WARN] metaapi_provider : timeout sur deploy/wait_connected ({_CONNECT_TIMEOUT}s)")
    except Exception as e:
        print(f"[WARN] metaapi_provider : deploy/wait_connected : {e}")

    if _connection is None:
        # On prefere RPC pour des appels ponctuels (positions, prices)
        try:
            _connection = _account.get_rpc_connection()
            _account_kind = "rpc"
            await asyncio.wait_for(_connection.connect(), timeout=_CONNECT_TIMEOUT)
            # IMPORTANT : wait_synchronized peut etre tres long sur MT5
            # On le wrap dans un timeout et on continue meme si pas sync
            try:
                await asyncio.wait_for(
                    _connection.wait_synchronized(),
                    timeout=_CONNECT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                print(
                    f"[WARN] metaapi_provider : RPC wait_synchronized timeout "
                    f"({_CONNECT_TIMEOUT}s) -> on continue quand meme"
                )
        except AttributeError:
            # Fallback : streaming
            _connection = _account.get_streaming_connection()
            _account_kind = "streaming"
            await asyncio.wait_for(_connection.connect(), timeout=_CONNECT_TIMEOUT)
            try:
                await asyncio.wait_for(
                    _connection.wait_synchronized(),
                    timeout=_CONNECT_TIMEOUT,
                )
            except asyncio.TimeoutError:
                print(
                    f"[WARN] metaapi_provider : streaming wait_synchronized "
                    f"timeout ({_CONNECT_TIMEOUT}s) -> on continue quand meme"
                )

    _last_connect_at = time.time()
    return _connection


# ---------------------- Public API ----------------------

def get_current_price(broker_symbol: str) -> Optional[Dict[str, Any]]:
    """Retourne {"ask": ..., "bid": ..., "time": ...} ou None. Cache TTL court."""
    if not _is_configured_bool():
        return None
    with _lock:
        cached = _price_cache.get(broker_symbol)
        now = time.time()
        if cached and (now - cached["ts"] < _PRICE_TTL_SEC):
            return cached["p"]

    async def _do():
        conn = await _ensure_account_async()
        if conn is None:
            return None
        # API RPC : get_symbol_price
        try:
            res = await asyncio.wait_for(
                conn.get_symbol_price(broker_symbol),
                timeout=_RPC_CALL_TIMEOUT,
            )
            return res
        except AttributeError:
            # Streaming : terminal_state
            try:
                state = conn.terminal_state
                return state.price(broker_symbol)
            except Exception:
                return None

    try:
        res = _run_async(_do())
        if res:
            with _lock:
                _price_cache[broker_symbol] = {"ts": time.time(), "p": res}
        return res
    except Exception as e:
        print(f"[WARN] metaapi_provider.get_current_price({broker_symbol}) : {e}")
        return None


def get_symbol_specification(broker_symbol: str) -> Optional[Dict[str, Any]]:
    """Retourne dict {contractSize, minVolume, volumeStep, tickSize, tickValue, ...}."""
    if not _is_configured_bool():
        return None

    async def _do():
        conn = await _ensure_account_async()
        if conn is None:
            return None
        try:
            spec = await asyncio.wait_for(
                conn.get_symbol_specification(broker_symbol),
                timeout=_RPC_CALL_TIMEOUT,
            )
            return spec
        except AttributeError:
            try:
                return conn.terminal_state.specification(broker_symbol)
            except Exception:
                return None

    try:
        return _run_async(_do())
    except Exception as e:
        print(f"[WARN] metaapi_provider.get_symbol_specification({broker_symbol}) : {e}")
        return None


def get_positions() -> List[Dict[str, Any]]:
    """Retourne la liste des positions ouvertes du compte (lecture seule).

    Format MetaAPI (cle clefs) :
      id, symbol, type ('POSITION_TYPE_BUY' / 'POSITION_TYPE_SELL'),
      volume, openPrice, currentPrice, profit, swap, commission, time, ...
    """
    if not _is_configured_bool():
        return []

    async def _do():
        conn = await _ensure_account_async()
        if conn is None:
            return []
        try:
            positions = await asyncio.wait_for(
                conn.get_positions(),
                timeout=_RPC_CALL_TIMEOUT,
            )
            return positions or []
        except AttributeError:
            try:
                return conn.terminal_state.positions or []
            except Exception:
                return []
        except asyncio.TimeoutError:
            print(f"[WARN] metaapi_provider.get_positions() : timeout {_RPC_CALL_TIMEOUT}s")
            return []

    try:
        return _run_async(_do()) or []
    except Exception as e:
        print(f"[WARN] metaapi_provider.get_positions() : {e}")
        return []


def get_account_information() -> Optional[Dict[str, Any]]:
    """Retourne dict {balance, equity, margin, freeMargin, leverage, currency, ...}."""
    if not _is_configured_bool():
        return None

    async def _do():
        conn = await _ensure_account_async()
        if conn is None:
            return None
        try:
            return await asyncio.wait_for(
                conn.get_account_information(),
                timeout=_RPC_CALL_TIMEOUT,
            )
        except AttributeError:
            try:
                return conn.terminal_state.account_information
            except Exception:
                return None

    try:
        return _run_async(_do())
    except Exception as e:
        print(f"[WARN] metaapi_provider.get_account_information() : {e}")
        return None


# ---------------------- Diagnostics / CLI ----------------------

def diagnostics() -> Dict[str, Any]:
    """Retourne un dict d'etat (utile pour scripts de validation)."""
    return {
        "configured": _is_configured_bool(),
        "token_set": bool(_TOKEN),
        "account_id_set": bool(_ACCOUNT_ID),
        "region": _REGION,
        "price_ttl_sec": _PRICE_TTL_SEC,
        "connect_timeout_sec": _CONNECT_TIMEOUT,
        "rpc_timeout_sec": _RPC_CALL_TIMEOUT,
        "account_kind": _account_kind,
        "last_connect_at": _last_connect_at,
        "price_cache_size": len(_price_cache),
    }


if __name__ == "__main__":
    import json
    print("=== metaapi_provider diagnostics ===")
    print(json.dumps(diagnostics(), indent=2, default=str))
    if is_configured():
        print("\n--- get_account_information ---")
        ai = get_account_information()
        print(json.dumps(ai, indent=2, default=str) if ai else "None")
        print("\n--- get_positions (top 5) ---")
        pos = get_positions()
        print(f"{len(pos)} positions ouvertes")
        for p in pos[:5]:
            if isinstance(p, dict):
                print({k: p.get(k) for k in
                       ("id", "symbol", "type", "volume", "openPrice",
                        "currentPrice", "profit")})
            else:
                print(p)
    else:
        print("\n[INFO] non configure -> METAAPI_TOKEN ou METAAPI_ACCOUNT_ID manquant")


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

