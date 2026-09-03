# -*- coding: utf-8 -*-
# fill_simulator.py
# Jalon 8A - Fill simulator local pour backtest event-driven
# Execute les ordres au OPEN J+1 trading + slippage modele
# JAMAIS d'appel broker en replay.
#
# Modele slippage :
#   slippage_bps = min(SLIPPAGE_CAP_BPS, SLIPPAGE_FACTOR * |qty| / volume_J+1 * 10000)
#   - SLIPPAGE_CAP_BPS    = 5 bps (max absolu)
#   - SLIPPAGE_FACTOR     = 0.1  (impact base : 0.1 * qty/vol)
# Direction :
#   - BUY  : prix_filled = open_J1 * (1 + slippage)
#   - SELL : prix_filled = open_J1 * (1 - slippage)

import os
from typing import Dict, Any, Optional
from replay_adapters import MarketDataAdapter

SLIPPAGE_CAP_BPS = 5.0
SLIPPAGE_FACTOR = 0.1
MIN_VOLUME = 1.0  # garde-fou si volume nul ou manquant


class FillResult:
    def __init__(
        self,
        ticker: str,
        side: str,
        qty: float,
        day_decision: str,
        day_fill: Optional[str],
        open_j1: Optional[float],
        price_filled: Optional[float],
        slippage_bps: Optional[float],
        status: str,
        reason: Optional[str] = None,
    ):
        self.ticker = ticker
        self.side = side
        self.qty = qty
        self.day_decision = day_decision
        self.day_fill = day_fill
        self.open_j1 = open_j1
        self.price_filled = price_filled
        self.slippage_bps = slippage_bps
        self.status = status  # 'filled' | 'rejected'
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "side": self.side,
            "qty": self.qty,
            "day_decision": self.day_decision,
            "day_fill": self.day_fill,
            "open_j1": self.open_j1,
            "price_filled": self.price_filled,
            "slippage_bps": self.slippage_bps,
            "status": self.status,
            "reason": self.reason,
        }


def _ensure_replay_mode():
    mode = os.environ.get("NEXTONES_REPLAY_MODE", "0")
    if mode != "1":
        import sys
        print(
            "[WARN] fill_simulator hors mode replay (NEXTONES_REPLAY_MODE=%s)" % mode,
            file=sys.stderr,
        )


def compute_slippage_bps(qty: float, volume: float) -> float:
    """
    Slippage proportionnel a |qty|/volume, cape a SLIPPAGE_CAP_BPS.
    Garde-fou : si volume <= 0, applique le cap.
    """
    q = abs(qty)
    v = max(volume, MIN_VOLUME)
    raw_bps = SLIPPAGE_FACTOR * (q / v) * 10000.0
    if raw_bps != raw_bps:  # NaN
        return SLIPPAGE_CAP_BPS
    return min(SLIPPAGE_CAP_BPS, raw_bps)


def simulate_fill(
    adapter: MarketDataAdapter,
    ticker: str,
    side: str,
    qty: float,
    day_decision: str,
) -> FillResult:
    """
    Simule l'execution d'un ordre :
      1. Cherche l'open du premier jour trading APRES day_decision (J+1)
      2. Calcule slippage selon |qty|/volume_J+1
      3. Applique direction (BUY = +slip, SELL = -slip)

    Retourne FillResult avec status='filled' ou 'rejected' (pas de cours J+1).
    """
    _ensure_replay_mode()

    side_upper = (side or "").upper()
    if side_upper not in ("BUY", "SELL"):
        return FillResult(
            ticker, side_upper, qty, day_decision, None, None, None, None,
            "rejected", f"side invalide: {side}"
        )

    if qty == 0:
        return FillResult(
            ticker, side_upper, qty, day_decision, None, None, None, None,
            "rejected", "qty == 0"
        )

    bar = adapter.get_open_after(day_decision, ticker)
    if bar is None:
        return FillResult(
            ticker, side_upper, qty, day_decision, None, None, None, None,
            "rejected", "pas de cours J+1 (delisting / weekend final / data manquante)"
        )

    open_j1 = bar.get("open")
    vol_j1 = bar.get("volume") or MIN_VOLUME
    if open_j1 is None or open_j1 <= 0:
        return FillResult(
            ticker, side_upper, qty, day_decision, bar.get("date"), open_j1, None, None,
            "rejected", "open J+1 invalide"
        )

    slip_bps = compute_slippage_bps(qty, vol_j1)
    slip_frac = slip_bps / 10000.0
    if side_upper == "BUY":
        price_filled = open_j1 * (1.0 + slip_frac)
    else:
        price_filled = open_j1 * (1.0 - slip_frac)

    return FillResult(
        ticker=ticker,
        side=side_upper,
        qty=qty,
        day_decision=day_decision,
        day_fill=bar.get("date"),
        open_j1=open_j1,
        price_filled=price_filled,
        slippage_bps=slip_bps,
        status="filled",
        reason=None,
    )


__all__ = [
    "simulate_fill",
    "compute_slippage_bps",
    "FillResult",
    "SLIPPAGE_CAP_BPS",
    "SLIPPAGE_FACTOR",
]
