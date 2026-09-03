# -*- coding: utf-8 -*-
"""
nextones-shadow-nav-engine-v2.py
=================================
JALON 9 - Phase 9.7 - CORRECTIF NAV SHADOW

PROBLEME CORRIGE
----------------
shadow_engine.py (Phase 9.2) inserait des placeholders figes :
    NAV_PLACEHOLDER  = 1000000.0
    CASH_PLACEHOLDER = 1000000.0
    n_positions = 0, invested_pct = 0.0
    notes = "mvp_phase92_no_fills"

Consequence : shadow_perf_rolling_j30 cumulait les fills sur un capital
fictif jamais borne. La NAV a derive jusqu'a -1 881 445 USD au 2026-09-02,
avec un max_dd de -432.7% (mathematiquement impossible), et le systeme
continuait a promouvoir variant 2 en "champion" parce qu'elle etait
MOINS negative que "prod".

CE MODULE
---------
Recalcule un etat de portefeuille shadow REEL, propage cycle par cycle :

    nav_t = cash_t + SUM(qty_i * close_i(day_t))

Avec contraintes physiques dures :
  - cash ne peut jamais devenir negatif  -> BUY tronque ou rejete
  - qty ne peut jamais devenir negative  -> SELL borne a la position
  - nav <= 0 -> cycle marque INVALID, propagation stoppee
  - max_dd non calcule si peak <= 0

USAGE
-----
    py -3.13 nextones-shadow-nav-engine-v2.py --self-test
    py -3.13 nextones-shadow-nav-engine-v2.py --db thesium.db --dry-run
    py -3.13 nextones-shadow-nav-engine-v2.py --db thesium.db --apply

Ce module est IMPORTABLE : nextones-shadow-perf-rolling-v2.py l'utilise.

AUTEUR : audit Perplexity - 2026-09-03
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# ----------------------------------------------------------------------------
# CONSTANTES
# ----------------------------------------------------------------------------

MARKER = "SHADOW_NAV_V2"

# Capital initial du book shadow. Doit correspondre au K_init prod pour que
# la comparaison variant vs prod ait un sens.
K_INIT = 1_000_000.0

# Frais et slippage appliques aux fills shadow (bps du notional).
FEES_BPS = 1.0
SLIPPAGE_BPS = 5.0

# Garde-fous de plausibilite. Toute metrique hors bornes -> ligne INVALID.
MAX_ABS_RETURN_PCT = 500.0     # +/-500% sur une fenetre = anomalie
MIN_NAV = 1.0                  # NAV <= 1 USD = book detruit, on stoppe
MAX_DD_FLOOR_PCT = -100.0      # un DD < -100% est impossible

# Nombre minimum de cycles avant d'autoriser une recommandation.
MIN_CYCLES_FOR_RECO = 60

# Taux sans risque annuel pour le Sharpe (0.0 = Sharpe brut).
RISK_FREE_ANNUAL = 0.0

TRADING_DAYS = 252


# ----------------------------------------------------------------------------
# STRUCTURES
# ----------------------------------------------------------------------------

@dataclass
class Position:
    """Position shadow sur un ticker."""
    ticker: str
    qty: float = 0.0
    avg_cost: float = 0.0

    def market_value(self, price: float) -> float:
        return self.qty * price


@dataclass
class BookState:
    """Etat du book shadow a un instant t."""
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    valid: bool = True
    invalid_reason: Optional[str] = None

    def nav(self, prices: Dict[str, float]) -> float:
        mv = 0.0
        for tkr, pos in self.positions.items():
            px = prices.get(tkr)
            if px is None or px <= 0:
                continue
            mv += pos.market_value(px)
        return self.cash + mv

    def n_positions(self) -> int:
        return sum(1 for p in self.positions.values() if abs(p.qty) > 1e-9)

    def invested_pct(self, prices: Dict[str, float]) -> float:
        nav = self.nav(prices)
        if nav <= 0:
            return 0.0
        mv = nav - self.cash
        return 100.0 * mv / nav

    def clone(self) -> "BookState":
        return BookState(
            cash=self.cash,
            positions={k: Position(v.ticker, v.qty, v.avg_cost)
                       for k, v in self.positions.items()},
            valid=self.valid,
            invalid_reason=self.invalid_reason,
        )


@dataclass
class FillResult:
    """Resultat d'une tentative de fill shadow."""
    ticker: str
    side: str
    requested_qty: float
    filled_qty: float
    fill_price: float
    notional: float
    fees: float
    status: str                      # filled | partial | rejected
    rejection_reason: Optional[str] = None


# ----------------------------------------------------------------------------
# MOTEUR DE FILLS BORNE
# ----------------------------------------------------------------------------

def apply_fill(
    book: BookState,
    ticker: str,
    side: str,
    target_qty: float,
    ref_price: float,
) -> FillResult:
    """
    Applique un fill shadow AVEC contraintes physiques.

    C'est ici que se trouvait le bug : l'ancien moteur ne verifiait ni le
    cash disponible ni la quantite detenue, ce qui laissait la NAV plonger
    en negatif sans limite.

    Regles :
      BUY  -> notional <= cash disponible, sinon troncature (partial)
      SELL -> qty <= qty detenue, sinon troncature (partial)
      Aucune vente a decouvert, aucun levier.
    """
    side = side.upper()

    if ref_price is None or ref_price <= 0:
        return FillResult(ticker, side, target_qty, 0.0, 0.0, 0.0, 0.0,
                          "rejected", "invalid_price")

    if target_qty <= 0:
        return FillResult(ticker, side, target_qty, 0.0, ref_price, 0.0, 0.0,
                          "rejected", "qty_zero_or_negative")

    slip = SLIPPAGE_BPS / 10_000.0
    pos = book.positions.setdefault(ticker, Position(ticker))

    if side == "BUY":
        fill_price = ref_price * (1.0 + slip)
        fee_rate = FEES_BPS / 10_000.0

        # Cash maximum mobilisable, frais inclus.
        max_notional = book.cash / (1.0 + fee_rate)
        if max_notional <= 0:
            return FillResult(ticker, side, target_qty, 0.0, fill_price,
                              0.0, 0.0, "rejected", "no_cash_available")

        max_qty = max_notional / fill_price
        filled_qty = min(target_qty, max_qty)

        if filled_qty <= 0:
            return FillResult(ticker, side, target_qty, 0.0, fill_price,
                              0.0, 0.0, "rejected", "cash_insufficient")

        notional = filled_qty * fill_price
        fees = notional * fee_rate
        total_cost = notional + fees

        # Garde-fou dur : jamais de cash negatif.
        if total_cost > book.cash + 1e-6:
            return FillResult(ticker, side, target_qty, 0.0, fill_price,
                              0.0, 0.0, "rejected", "cash_guard_triggered")

        prev_qty = pos.qty
        prev_cost = pos.avg_cost
        new_qty = prev_qty + filled_qty
        if new_qty > 0:
            pos.avg_cost = ((prev_qty * prev_cost) + notional) / new_qty
        pos.qty = new_qty
        book.cash -= total_cost

        status = "filled" if abs(filled_qty - target_qty) < 1e-9 else "partial"
        reason = None if status == "filled" else "cash_truncated"
        return FillResult(ticker, side, target_qty, filled_qty, fill_price,
                          notional, fees, status, reason)

    # ---- SELL ----
    fill_price = ref_price * (1.0 - slip)
    fee_rate = FEES_BPS / 10_000.0

    available = max(0.0, pos.qty)
    if available <= 0:
        return FillResult(ticker, side, target_qty, 0.0, fill_price,
                          0.0, 0.0, "rejected", "no_position_to_sell")

    filled_qty = min(target_qty, available)
    notional = filled_qty * fill_price
    fees = notional * fee_rate

    pos.qty = available - filled_qty
    if pos.qty <= 1e-9:
        pos.qty = 0.0
        pos.avg_cost = 0.0
    book.cash += (notional - fees)

    status = "filled" if abs(filled_qty - target_qty) < 1e-9 else "partial"
    reason = None if status == "filled" else "position_truncated"
    return FillResult(ticker, side, target_qty, filled_qty, fill_price,
                      notional, fees, status, reason)


# ----------------------------------------------------------------------------
# ACCES DONNEES
# ----------------------------------------------------------------------------

def load_prices_for_day(conn: sqlite3.Connection, day: str) -> Dict[str, float]:
    """
    Retourne {ticker: close} pour la date donnee (YYYY-MM-DD).
    Si pas de cours ce jour-la, prend le dernier close <= day (forward fill).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.ticker, p.close
        FROM prices p
        JOIN instruments i ON i.id = p.instrument_id
        WHERE p.date = ?
        """,
        (day,),
    )
    prices = {r[0]: float(r[1]) for r in cur.fetchall()
              if r[1] is not None and float(r[1]) > 0}

    # Forward fill pour les tickers absents ce jour.
    cur.execute(
        """
        SELECT i.ticker, p.close, MAX(p.date) AS d
        FROM prices p
        JOIN instruments i ON i.id = p.instrument_id
        WHERE p.date <= ?
        GROUP BY i.ticker
        """,
        (day,),
    )
    for tkr, close, _d in cur.fetchall():
        if tkr not in prices and close is not None and float(close) > 0:
            prices[tkr] = float(close)

    return prices


def load_shadow_cycles(conn: sqlite3.Connection) -> List[Tuple[str, str]]:
    """Retourne [(cycle_id, day_t)] trie chronologiquement."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT cycle_id, day_t
        FROM shadow_cycle_snapshots
        ORDER BY day_t ASC, cycle_id ASC
        """
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


def load_shadow_orders(
    conn: sqlite3.Connection, cycle_id: str, variant_id: int
) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ticker, side, qty, target_weight_pct, sizing_multiplier,
               decision, convergence_pct, forced_exit
        FROM shadow_orders
        WHERE cycle_id = ? AND variant_id = ? AND decision != 'filter'
        ORDER BY ticker
        """,
        (cycle_id, variant_id),
    )
    return cur.fetchall()


def load_variants(conn: sqlite3.Connection) -> List[sqlite3.Row]:
    cur = conn.cursor()
    cur.execute(
        "SELECT variant_id, name, description, settings_json "
        "FROM shadow_variants WHERE active = 1 ORDER BY variant_id"
    )
    return cur.fetchall()


# ----------------------------------------------------------------------------
# PROPAGATION NAV
# ----------------------------------------------------------------------------

def qty_from_target_weight(
    nav: float, target_weight_pct: float, price: float
) -> float:
    """
    Convertit un poids cible en quantite, sur la base de la NAV COURANTE.

    L'ancien moteur utilisait NAV_PLACEHOLDER = 1_000_000 en dur, ce qui
    dimensionnait chaque ordre sur un capital fictif independant des
    pertes accumulees. C'est le coeur du bug.
    """
    if price is None or price <= 0 or nav <= 0:
        return 0.0
    notional = nav * (target_weight_pct / 100.0)
    if notional <= 0:
        return 0.0
    return notional / price


def rebuild_variant_nav_series(
    conn: sqlite3.Connection,
    variant_id: int,
    k_init: float = K_INIT,
    verbose: bool = False,
) -> List[dict]:
    """
    Reconstruit la serie NAV d'un variant, cycle par cycle, avec contraintes.

    Retourne une liste de dicts :
      cycle_id, day_t, nav, cash, n_positions, invested_pct,
      n_orders, n_filled, n_partial, n_rejected, valid, invalid_reason
    """
    cycles = load_shadow_cycles(conn)
    book = BookState(cash=k_init)
    series: List[dict] = []
    price_cache: Dict[str, Dict[str, float]] = {}

    for cycle_id, day_t in cycles:
        if day_t not in price_cache:
            price_cache[day_t] = load_prices_for_day(conn, day_t)
        prices = price_cache[day_t]

        nav_open = book.nav(prices)

        # Book detruit : on arrete la propagation plutot que de deriver.
        if nav_open < MIN_NAV:
            book.valid = False
            book.invalid_reason = f"nav_below_min({nav_open:.2f})"
            series.append({
                "cycle_id": cycle_id, "day_t": day_t,
                "nav": nav_open, "cash": book.cash,
                "n_positions": book.n_positions(),
                "invested_pct": 0.0,
                "n_orders": 0, "n_filled": 0,
                "n_partial": 0, "n_rejected": 0,
                "valid": 0, "invalid_reason": book.invalid_reason,
            })
            continue

        orders = load_shadow_orders(conn, cycle_id, variant_id)
        n_filled = n_partial = n_rejected = 0

        # SELL d'abord : libere du cash avant les achats du meme cycle.
        def order_key(o: sqlite3.Row) -> int:
            dec = (o["decision"] or "").lower()
            side = (o["side"] or "").upper()
            if dec == "exit" or side == "SELL":
                return 0
            return 1

        for o in sorted(orders, key=order_key):
            tkr = o["ticker"]
            px = prices.get(tkr)
            if px is None or px <= 0:
                n_rejected += 1
                continue

            decision = (o["decision"] or "").lower()
            target_w = float(o["target_weight_pct"] or 0.0)
            pos = book.positions.get(tkr, Position(tkr))
            cur_qty = pos.qty

            if decision == "exit":
                side = "SELL"
                qty = cur_qty
            else:
                desired_qty = qty_from_target_weight(nav_open, target_w, px)
                delta = desired_qty - cur_qty
                if abs(delta) * px < 0.01 * nav_open / 100.0:
                    continue          # delta negligeable
                side = "BUY" if delta > 0 else "SELL"
                qty = abs(delta)

            if qty <= 0:
                n_rejected += 1
                continue

            res = apply_fill(book, tkr, side, qty, px)
            if res.status == "filled":
                n_filled += 1
            elif res.status == "partial":
                n_partial += 1
            else:
                n_rejected += 1

        nav_close = book.nav(prices)

        # Invariants durs.
        valid = 1
        reason = None
        if book.cash < -1e-6:
            valid = 0
            reason = f"negative_cash({book.cash:.2f})"
        elif nav_close <= 0:
            valid = 0
            reason = f"nav_non_positive({nav_close:.2f})"
        elif any(p.qty < -1e-9 for p in book.positions.values()):
            valid = 0
            reason = "negative_position"

        if valid == 0:
            book.valid = False
            book.invalid_reason = reason

        row = {
            "cycle_id": cycle_id,
            "day_t": day_t,
            "nav": nav_close,
            "cash": book.cash,
            "n_positions": book.n_positions(),
            "invested_pct": book.invested_pct(prices),
            "n_orders": len(orders),
            "n_filled": n_filled,
            "n_partial": n_partial,
            "n_rejected": n_rejected,
            "valid": valid,
            "invalid_reason": reason,
        }
        series.append(row)

        if verbose:
            print(f"  {day_t}  {cycle_id[:20]:20s}  "
                  f"NAV={nav_close:12,.0f}  cash={book.cash:11,.0f}  "
                  f"pos={row['n_positions']:2d}  "
                  f"inv={row['invested_pct']:5.1f}%  "
                  f"F/P/R={n_filled}/{n_partial}/{n_rejected}  "
                  f"{'OK' if valid else 'INVALID:' + str(reason)}")

    return series


# ----------------------------------------------------------------------------
# METRIQUES ROBUSTES
# ----------------------------------------------------------------------------

def compute_metrics(nav_series: List[float]) -> dict:
    """
    Sharpe, Sortino, max drawdown, avec garde-fous.

    L'ancien calcul produisait max_dd = -432% parce que le pic de reference
    etait devenu negatif. Ici tout pic <= 0 invalide la metrique.
    """
    out = {
        "n_obs": len(nav_series),
        "total_return_pct": None,
        "ann_return_pct": None,
        "vol_ann_pct": None,
        "sharpe": None,
        "sortino": None,
        "max_dd_pct": None,
        "calmar": None,
        "valid": False,
        "invalid_reason": None,
    }

    clean = [v for v in nav_series if v is not None]
    if len(clean) < 3:
        out["invalid_reason"] = "insufficient_observations"
        return out

    if any(v <= 0 for v in clean):
        out["invalid_reason"] = "non_positive_nav_in_series"
        return out

    rets: List[float] = []
    for i in range(1, len(clean)):
        prev = clean[i - 1]
        if prev <= 0:
            out["invalid_reason"] = "non_positive_denominator"
            return out
        rets.append(clean[i] / prev - 1.0)

    if not rets:
        out["invalid_reason"] = "no_returns"
        return out

    total_ret = clean[-1] / clean[0] - 1.0
    out["total_return_pct"] = 100.0 * total_ret

    if abs(out["total_return_pct"]) > MAX_ABS_RETURN_PCT:
        out["invalid_reason"] = f"return_out_of_bounds({out['total_return_pct']:.1f}%)"
        return out

    n = len(rets)
    mean_r = sum(rets) / n
    var = sum((r - mean_r) ** 2 for r in rets) / (n - 1) if n > 1 else 0.0
    std = math.sqrt(var)

    ann_ret = (1.0 + total_ret) ** (TRADING_DAYS / n) - 1.0 if n > 0 else 0.0
    out["ann_return_pct"] = 100.0 * ann_ret
    out["vol_ann_pct"] = 100.0 * std * math.sqrt(TRADING_DAYS)

    if std > 1e-12:
        rf_daily = RISK_FREE_ANNUAL / TRADING_DAYS
        out["sharpe"] = ((mean_r - rf_daily) * TRADING_DAYS) / (std * math.sqrt(TRADING_DAYS))

    downside = [r for r in rets if r < 0]
    if len(downside) > 1:
        d_mean = sum(downside) / len(downside)
        d_var = sum((r - d_mean) ** 2 for r in downside) / (len(downside) - 1)
        d_std = math.sqrt(d_var)
        if d_std > 1e-12:
            out["sortino"] = (mean_r * TRADING_DAYS) / (d_std * math.sqrt(TRADING_DAYS))

    # Max drawdown avec pic strictement positif.
    peak = clean[0]
    max_dd = 0.0
    for v in clean:
        if v > peak:
            peak = v
        if peak <= 0:
            out["invalid_reason"] = "non_positive_peak"
            return out
        dd = (v - peak) / peak
        if dd < max_dd:
            max_dd = dd
    max_dd_pct = 100.0 * max_dd

    if max_dd_pct < MAX_DD_FLOOR_PCT:
        out["invalid_reason"] = f"max_dd_impossible({max_dd_pct:.1f}%)"
        return out

    out["max_dd_pct"] = max_dd_pct
    if abs(max_dd_pct) > 1e-9 and out["ann_return_pct"] is not None:
        out["calmar"] = out["ann_return_pct"] / abs(max_dd_pct)

    out["valid"] = True
    return out


# ----------------------------------------------------------------------------
# PERSISTANCE
# ----------------------------------------------------------------------------

SCHEMA_V2 = [
    """
    CREATE TABLE IF NOT EXISTS shadow_nav_series_v2 (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        variant_id      INTEGER NOT NULL,
        cycle_id        TEXT    NOT NULL,
        day_t           TEXT    NOT NULL,
        nav             REAL    NOT NULL,
        cash            REAL    NOT NULL,
        n_positions     INTEGER NOT NULL DEFAULT 0,
        invested_pct    REAL    NOT NULL DEFAULT 0,
        n_orders        INTEGER NOT NULL DEFAULT 0,
        n_filled        INTEGER NOT NULL DEFAULT 0,
        n_partial       INTEGER NOT NULL DEFAULT 0,
        n_rejected      INTEGER NOT NULL DEFAULT 0,
        valid           INTEGER NOT NULL DEFAULT 1,
        invalid_reason  TEXT,
        engine_version  TEXT    NOT NULL DEFAULT 'SHADOW_NAV_V2',
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(variant_id, cycle_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_shadow_nav_v2_variant_day
        ON shadow_nav_series_v2(variant_id, day_t)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_shadow_nav_v2_valid
        ON shadow_nav_series_v2(valid, day_t)
    """,
]


def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for sql in SCHEMA_V2:
        cur.execute(sql)


def persist_series(
    conn: sqlite3.Connection, variant_id: int, series: List[dict]
) -> int:
    cur = conn.cursor()
    cur.execute("DELETE FROM shadow_nav_series_v2 WHERE variant_id = ?",
                (variant_id,))
    n = 0
    for r in series:
        cur.execute(
            """
            INSERT INTO shadow_nav_series_v2
              (variant_id, cycle_id, day_t, nav, cash, n_positions,
               invested_pct, n_orders, n_filled, n_partial, n_rejected,
               valid, invalid_reason, engine_version)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (variant_id, r["cycle_id"], r["day_t"], r["nav"], r["cash"],
             r["n_positions"], r["invested_pct"], r["n_orders"],
             r["n_filled"], r["n_partial"], r["n_rejected"],
             r["valid"], r["invalid_reason"], MARKER),
        )
        n += 1
    return n


# ----------------------------------------------------------------------------
# SELF-TEST
# ----------------------------------------------------------------------------

def self_test() -> bool:
    """Valide les invariants sans toucher a la base."""
    print("=" * 74)
    print("SELF-TEST  nextones-shadow-nav-engine-v2")
    print("=" * 74)
    ok = True

    def check(label: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        status = "PASS" if cond else "FAIL"
        if not cond:
            ok = False
        print(f"  [{status}] {label}{('  ' + detail) if detail else ''}")

    # 1. BUY borne par le cash
    b = BookState(cash=1000.0)
    r = apply_fill(b, "AAA", "BUY", 1000.0, 10.0)  # veut 10 000 USD
    check("BUY tronque par le cash", r.status == "partial",
          f"filled={r.filled_qty:.2f} cash={b.cash:.2f}")
    check("cash jamais negatif apres BUY", b.cash >= -1e-6,
          f"cash={b.cash:.6f}")

    # 2. BUY sans cash
    b2 = BookState(cash=0.0)
    r2 = apply_fill(b2, "AAA", "BUY", 10.0, 10.0)
    check("BUY rejete si cash nul", r2.status == "rejected",
          str(r2.rejection_reason))

    # 3. SELL borne par la position
    b3 = BookState(cash=0.0, positions={"AAA": Position("AAA", 5.0, 10.0)})
    r3 = apply_fill(b3, "AAA", "SELL", 100.0, 10.0)
    check("SELL tronque a la position", r3.filled_qty == 5.0,
          f"filled={r3.filled_qty}")
    check("pas de position negative", b3.positions["AAA"].qty >= 0.0,
          f"qty={b3.positions['AAA'].qty}")

    # 4. SELL sans position
    b4 = BookState(cash=100.0)
    r4 = apply_fill(b4, "BBB", "SELL", 1.0, 10.0)
    check("SELL rejete sans position", r4.status == "rejected",
          str(r4.rejection_reason))

    # 5. NAV conservee sur un aller-retour
    b5 = BookState(cash=10_000.0)
    apply_fill(b5, "AAA", "BUY", 100.0, 50.0)
    nav5 = b5.nav({"AAA": 50.0})
    check("NAV coherente apres BUY", 9_000.0 < nav5 <= 10_000.0,
          f"nav={nav5:.2f}")

    # 6. Sizing sur NAV courante, pas sur placeholder
    q_small = qty_from_target_weight(500_000.0, 10.0, 100.0)
    q_big = qty_from_target_weight(1_000_000.0, 10.0, 100.0)
    check("sizing proportionnel a la NAV", abs(q_big - 2 * q_small) < 1e-6,
          f"{q_small:.1f} vs {q_big:.1f}")

    # 7. Metriques : serie saine
    m = compute_metrics([100.0, 102.0, 101.0, 105.0, 103.0, 108.0])
    check("metriques valides sur serie saine", m["valid"] is True)
    check("max_dd dans [-100, 0]", m["max_dd_pct"] is not None
          and -100.0 <= m["max_dd_pct"] <= 0.0, f"dd={m['max_dd_pct']:.2f}%")

    # 8. Metriques : NAV negative rejetee (le bug d'origine)
    m2 = compute_metrics([1_000_000.0, 500_000.0, -1_881_445.0])
    check("NAV negative rejetee", m2["valid"] is False,
          str(m2["invalid_reason"]))
    check("aucun max_dd publie si invalide", m2["max_dd_pct"] is None)

    # 9. Metriques : rendement absurde rejete
    m3 = compute_metrics([1.0, 1000.0, 100_000.0])
    check("rendement hors bornes rejete", m3["valid"] is False,
          str(m3["invalid_reason"]))

    # 10. Serie trop courte
    m4 = compute_metrics([100.0])
    check("serie trop courte rejetee", m4["valid"] is False,
          str(m4["invalid_reason"]))

    print("=" * 74)
    print("RESULTAT :", "TOUS LES TESTS PASSENT" if ok else "ECHEC")
    print("=" * 74)
    return ok


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(
        description="Recalcul NAV shadow avec contraintes physiques (V2)"
    )
    p.add_argument("--db", default="thesium.db", help="chemin de la base")
    p.add_argument("--apply", action="store_true", help="persiste les resultats")
    p.add_argument("--dry-run", action="store_true", help="calcule sans ecrire")
    p.add_argument("--self-test", action="store_true", help="tests unitaires")
    p.add_argument("--variant-id", type=int, default=None)
    p.add_argument("--k-init", type=float, default=K_INIT)
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    if not os.path.exists(args.db):
        print(f"ERREUR : base introuvable : {os.path.abspath(args.db)}")
        return 1

    if not args.apply and not args.dry_run:
        args.dry_run = True

    mode = "APPLY" if args.apply else "DRY-RUN"
    print("=" * 74)
    print("SHADOW NAV ENGINE V2 - recalcul avec contraintes physiques")
    print(f"DB      : {os.path.abspath(args.db)}")
    print(f"K_init  : {args.k_init:,.0f}")
    print(f"Mode    : {mode}")
    print("=" * 74)

    conn = sqlite3.connect(args.db, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")

    try:
        if args.apply:
            ensure_schema(conn)

        variants = load_variants(conn)
        if args.variant_id is not None:
            variants = [v for v in variants
                        if v["variant_id"] == args.variant_id]
        if not variants:
            print("Aucun variant actif trouve.")
            return 1

        results = []
        for v in variants:
            vid, vname = v["variant_id"], v["name"]
            print(f"\n--- variant {vid} : {vname} ---")

            series = rebuild_variant_nav_series(
                conn, vid, k_init=args.k_init, verbose=args.verbose
            )
            if not series:
                print("  aucun cycle shadow trouve")
                continue

            valid_navs = [r["nav"] for r in series if r["valid"] == 1]
            metrics = compute_metrics(valid_navs)
            n_invalid = sum(1 for r in series if r["valid"] == 0)

            print(f"  cycles          : {len(series)}")
            print(f"  cycles invalides: {n_invalid}")
            print(f"  NAV finale      : {series[-1]['nav']:,.2f}")
            print(f"  cash final      : {series[-1]['cash']:,.2f}")
            print(f"  positions       : {series[-1]['n_positions']}")
            print(f"  investi         : {series[-1]['invested_pct']:.1f}%")

            if metrics["valid"]:
                print(f"  rendement total : {metrics['total_return_pct']:+.2f}%")
                print(f"  annualise       : {metrics['ann_return_pct']:+.2f}%")
                print(f"  vol annualisee  : {metrics['vol_ann_pct']:.2f}%")
                sh = metrics["sharpe"]
                so = metrics["sortino"]
                print(f"  Sharpe          : {sh:.3f}" if sh is not None else "  Sharpe          : n/a")
                print(f"  Sortino         : {so:.3f}" if so is not None else "  Sortino         : n/a")
                print(f"  max drawdown    : {metrics['max_dd_pct']:.2f}%")
            else:
                print(f"  METRIQUES INVALIDES : {metrics['invalid_reason']}")

            if args.apply:
                n = persist_series(conn, vid, series)
                print(f"  persiste        : {n} lignes -> shadow_nav_series_v2")

            results.append((vid, vname, series, metrics))

        if args.apply:
            conn.commit()
            print("\nCOMMIT effectue.")
        else:
            conn.rollback()
            print("\nDRY-RUN : aucune ecriture.")

        # Tableau comparatif
        print("\n" + "=" * 74)
        print("COMPARATIF VARIANTS (NAV recalculee V2)")
        print("=" * 74)
        print(f"{'ID':>3} {'variant':<20} {'NAV finale':>14} "
              f"{'ret%':>9} {'Sharpe':>8} {'maxDD%':>9} {'statut':>10}")
        print("-" * 74)
        for vid, vname, series, m in results:
            nav_f = series[-1]["nav"] if series else 0.0
            ret = f"{m['total_return_pct']:+.2f}" if m["valid"] else "n/a"
            shp = f"{m['sharpe']:.3f}" if m["valid"] and m["sharpe"] is not None else "n/a"
            ddv = f"{m['max_dd_pct']:.2f}" if m["valid"] else "n/a"
            st = "VALID" if m["valid"] else "INVALID"
            print(f"{vid:>3} {vname[:20]:<20} {nav_f:>14,.0f} "
                  f"{ret:>9} {shp:>8} {ddv:>9} {st:>10}")
        print("=" * 74)
        print("\nEtape suivante :")
        print("  py -3.13 nextones-shadow-perf-rolling-v2.py --db thesium.db --apply")
        return 0

    except Exception as exc:
        conn.rollback()
        print(f"\nERREUR : {exc}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
