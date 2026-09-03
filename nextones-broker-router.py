# -*- coding: utf-8 -*-
# [NEXTONES-BROKER-ROUTER-V1]
# Routeur Phase 3C : decide pour chaque ordre s'il part en LIVE, en SHADOW,
# ou est REJET (Regle A strict).
#
# Decision arbre (top->down) :
#
#   1. bridge_config.BROKER_LIVE_ENABLED ?
#        False -> route = 'shadow'
#
#   2. thesium_ticker in bridge_config.LIVE_INSTRUMENTS ?
#        non   -> route = 'shadow'
#
#   3. notional estime > MAX_LIVE_NOTIONAL_PER_ORDER ?
#        oui   -> route = 'reject' reason='live_notional_per_order_exceeded'
#
#   4. live_nav_courant + notional > MAX_LIVE_NAV ?
#        oui   -> route = 'reject' reason='live_nav_cap_exceeded'
#
#   5. market_guard.is_us_market_open() (sauf crypto 24/7) ?
#        ferme -> route = 'reject' reason='market_closed'
#
#   6. -> route = 'live'
#
# API publique :
#
#   route_order(thesium_ticker, side, qty, asset_class=None,
#               entry_price=None, cycle_id=None, db_path=None)
#       -> dict {
#            'route': 'live'|'shadow'|'reject',
#            'reason': str,
#            'broker_symbol': str|None,
#            'volume_lots': float|None,
#            'est_notional_eur': float|None,
#            'live_nav_eur': float,
#            'config_snapshot': {...},
#          }
#
# Le routeur NE PASSE PAS l'ordre lui-meme. Il rend une decision.
# L'engine appelle ensuite execute_shadow() ou metaapi_provider.place_order()
# selon la decision.

from __future__ import annotations

import importlib.util as _ilu
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ===================================================================
# Chemins et helpers d'import
# ===================================================================

PROD_DIR = r"C:\Users\RichardGUELIN\Prod\ThesiumDesk"
DB_PATH = os.path.join(PROD_DIR, "thesium.db")

RESOLVER_PATH = os.path.join(PROD_DIR, "nextones-broker-resolver.py")
TRANSLATOR_PATH = os.path.join(PROD_DIR, "nextones-order-translator.py")
MARKET_CAL_PATH = os.path.join(PROD_DIR, "nextones-market-calendar.py")

# EUR/USD fallback si pas de quote dispo (entry_price suppose USD pour crypto/equity)
EURUSD_FALLBACK = 1.08


def _load_module(name: str, path: str):
    if not os.path.exists(path):
        return None
    try:
        spec = _ilu.spec_from_file_location(name, path)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"[ROUTER] erreur import {name}: {e}")
        return None


def _load_bridge_config():
    """Charge bridge_config.py depuis PROD_DIR (pas par chemin direct car
    nom de fichier normal sans tiret)."""
    bc_path = os.path.join(PROD_DIR, "bridge_config.py")
    if not os.path.exists(bc_path):
        return None
    spec = _ilu.spec_from_file_location("bridge_config", bc_path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _get_config():
    """Retourne (config_obj, snapshot_dict). config_obj peut etre None."""
    bc = _load_bridge_config()
    snap = {
        "BROKER_LIVE_ENABLED": False,
        "LIVE_DRY_RUN": True,
        "MAX_LIVE_NAV": 0.0,
        "MAX_LIVE_NOTIONAL_PER_ORDER": 0.0,
        "LIVE_INSTRUMENTS": [],
    }
    if bc is None:
        return None, snap
    snap["BROKER_LIVE_ENABLED"] = bool(getattr(bc, "BROKER_LIVE_ENABLED",
                                              False))
    snap["LIVE_DRY_RUN"] = bool(getattr(bc, "LIVE_DRY_RUN", True))
    snap["MAX_LIVE_NAV"] = float(getattr(bc, "MAX_LIVE_NAV", 0.0))
    snap["MAX_LIVE_NOTIONAL_PER_ORDER"] = float(
        getattr(bc, "MAX_LIVE_NOTIONAL_PER_ORDER", 0.0)
    )
    li = getattr(bc, "LIVE_INSTRUMENTS", set())
    snap["LIVE_INSTRUMENTS"] = sorted(list(li))
    return bc, snap


# ===================================================================
# NAV live courant
# ===================================================================

def _current_live_nav_eur(db_path: str = None) -> float:
    """Somme des notional des ordres broker_shadow_orders.is_live=1 ouverts.
    Si la colonne is_live n'existe pas (pas encore migree), retourne 0.0.
    """
    path = db_path or DB_PATH
    try:
        con = sqlite3.connect(path, timeout=10.0)
        con.execute("PRAGMA busy_timeout=10000")
        # check colonne is_live
        cols = [r[1] for r in con.execute(
            "PRAGMA table_info(broker_shadow_orders)"
        ).fetchall()]
        if "is_live" not in cols:
            con.close()
            return 0.0
        row = con.execute(
            "SELECT COALESCE(SUM(est_notional), 0.0) AS nav "
            "FROM broker_shadow_orders "
            "WHERE is_live = 1 AND status IN ('open','filled')"
        ).fetchone()
        con.close()
        nav_quote = float(row[0]) if row and row[0] is not None else 0.0
        # nav_quote est en quote_ccy (souvent USD). Conversion EUR approx.
        # Pour le compte 800 EUR / ActivTrades EUR, on convertit USD -> EUR
        # via fallback. Si EURUSD passe a 1.10, le cap est legerement
        # conservateur (USD/1.10 < USD/1.08).
        return nav_quote / EURUSD_FALLBACK
    except Exception as e:
        print(f"[ROUTER] _current_live_nav_eur erreur : {e}")
        return 0.0


# ===================================================================
# Notional estime EUR
# ===================================================================

def _estimate_notional_eur(broker_symbol: str,
                          volume_lots: float,
                          contract_size: float,
                          entry_price: Optional[float]) -> Optional[float]:
    """Estime le notional d'un ordre en EUR.
    Retourne None si pas de prix.
    """
    if entry_price is None or entry_price <= 0:
        return None
    notional_quote = volume_lots * contract_size * entry_price
    # On suppose quote = USD pour CFD US et crypto (vrai 99% du temps
    # ActivTrades). EUR/EUR direct si quote='EUR'.
    # Heuristique : si broker_symbol finit par '.US' ou commence par
    # 'BTC|ETH|LINK|SOL|...USD' -> USD. Sinon EUR.
    is_usd = (broker_symbol.endswith(".US")
              or broker_symbol.endswith("USD")
              or broker_symbol.endswith("USDT"))
    if is_usd:
        return notional_quote / EURUSD_FALLBACK
    return notional_quote


# ===================================================================
# Marche US ouvert ? (sauf crypto 24/7)
# ===================================================================

def _is_market_open_for_asset(asset_class: Optional[str]) -> bool:
    """Crypto -> 24/7 -> True. Equity/ETF -> consulte nextones-market-calendar."""
    ac = (asset_class or "").lower()
    if ac in ("crypto", "cryptocurrency", "coin"):
        return True
    mc = _load_module("_nx_router_market_cal", MARKET_CAL_PATH)
    if mc is None:
        # fail open : si pas de market calendar, on considere ouvert
        return True
    try:
        return bool(mc.is_us_market_open())
    except Exception as e:
        print(f"[ROUTER] market_calendar erreur : {e}")
        return True


# ===================================================================
# API publique
# ===================================================================

def route_order(thesium_ticker: str,
                side: str,
                qty: float,
                asset_class: Optional[str] = None,
                entry_price: Optional[float] = None,
                cycle_id: Optional[str] = None,
                db_path: Optional[str] = None) -> Dict[str, Any]:
    """Decide la route pour un ordre. Voir docstring du module."""
    db = db_path or DB_PATH
    bc, snap = _get_config()

    result = {
        "route": "shadow",
        "reason": "default",
        "broker_symbol": None,
        "volume_lots": None,
        "est_notional_eur": None,
        "live_nav_eur": 0.0,
        "config_snapshot": snap,
        "cycle_id": cycle_id,
        "thesium_ticker": thesium_ticker,
        "side": side,
        "qty": qty,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # === 1. Live globalement desactive
    if not snap["BROKER_LIVE_ENABLED"]:
        result["route"] = "shadow"
        result["reason"] = "live_disabled"
        return result

    # === 2. Ticker pas dans whitelist
    if thesium_ticker not in (set(snap["LIVE_INSTRUMENTS"])):
        result["route"] = "shadow"
        result["reason"] = "not_in_live_whitelist"
        return result

    # === 2bis. Early market_closed check si asset_class connu et non-crypto
    # On evite ainsi de traduire un ordre voue a etre rejete pour marche ferme.
    # Pour les crypto (24/7) et les cas asset_class=None, on differe le check
    # apres la traduction (qui peut renseigner asset_class via diagnostics).
    if asset_class and str(asset_class).lower() not in ("crypto", "cryptocurrency"):
        if not _is_market_open_for_asset(asset_class):
            result["route"] = "reject"
            result["reason"] = "market_closed"
            return result

    # === 3. Traduction via translator pour avoir volume_lots + broker_symbol
    # Le translator expose translate() au niveau module (pas de classe).
    # Il utilise son resolver interne qui lit broker_universe_activtrades.
    translator_mod = _load_module("_nx_router_translator", TRANSLATOR_PATH)
    if translator_mod is None:
        result["route"] = "reject"
        result["reason"] = "translator_unavailable"
        return result

    if not hasattr(translator_mod, "translate"):
        result["route"] = "reject"
        result["reason"] = "translator_missing_translate_fn"
        return result

    try:
        tr = translator_mod.translate(
            thesium_ticker, qty, side, asset_class=asset_class,
        )
    except Exception as e:
        result["route"] = "reject"
        result["reason"] = f"translator_error: {type(e).__name__}: {e}"
        return result

    if not tr.accepted:
        result["route"] = "reject"
        result["reason"] = f"translator_reject: {tr.reason}"
        result["broker_symbol"] = tr.broker_symbol
        return result

    result["broker_symbol"] = tr.broker_symbol
    result["volume_lots"] = tr.volume_lots

    # === 4. Notional estime
    specs = (tr.diagnostics or {}).get("specs") or {}
    contract_size = float(specs.get("contract_size", 1.0))
    notional_eur = _estimate_notional_eur(
        tr.broker_symbol, tr.volume_lots, contract_size, entry_price,
    )
    result["est_notional_eur"] = notional_eur

    if notional_eur is None:
        # Pas de prix -> on ne peut pas garantir le cap -> reject prudent
        result["route"] = "reject"
        result["reason"] = "no_entry_price_for_cap_check"
        return result

    if notional_eur > snap["MAX_LIVE_NOTIONAL_PER_ORDER"]:
        result["route"] = "reject"
        result["reason"] = (
            f"live_notional_per_order_exceeded "
            f"({notional_eur:.2f} > {snap['MAX_LIVE_NOTIONAL_PER_ORDER']:.2f})"
        )
        return result

    # === 5. NAV courant
    live_nav = _current_live_nav_eur(db)
    result["live_nav_eur"] = live_nav

    if (live_nav + notional_eur) > snap["MAX_LIVE_NAV"]:
        result["route"] = "reject"
        result["reason"] = (
            f"live_nav_cap_exceeded "
            f"({live_nav:.2f} + {notional_eur:.2f} > "
            f"{snap['MAX_LIVE_NAV']:.2f})"
        )
        return result

    # === 6. Marche ouvert ?
    market_ok = _is_market_open_for_asset(
        asset_class or (tr.diagnostics or {}).get("asset_class")
    )
    if not market_ok:
        result["route"] = "reject"
        result["reason"] = "market_closed"
        return result

    # === 7. Tout va bien
    result["route"] = "live"
    if snap["LIVE_DRY_RUN"]:
        result["reason"] = "live_dry_run"
    else:
        result["reason"] = "live_armed"
    return result


# ===================================================================
# CLI diag
# ===================================================================

def _print_decision(d: Dict[str, Any]):
    print(json.dumps(d, indent=2, ensure_ascii=False, default=str))


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True, help="thesium_ticker")
    ap.add_argument("--side", required=True, choices=["buy", "sell"])
    ap.add_argument("--qty", required=True, type=float)
    ap.add_argument("--asset-class", default=None,
                    help="crypto|equity|etf|forex")
    ap.add_argument("--entry-price", type=float, default=None)
    args = ap.parse_args()

    d = route_order(
        args.ticker, args.side, args.qty,
        asset_class=args.asset_class,
        entry_price=args.entry_price,
    )
    _print_decision(d)


if __name__ == "__main__":
    main()
