"""
justification_builder.py - Jalon 10
====================================

Construit une note structuree courte (~180 chars) qui justifie pourquoi
un ordre est BUY ou SELL et son amplitude, a partir des donnees deja
en base :

  - convergence_snapshots (via cycle_id + ticker) :
      direction_consensus, n_aligned, n_present, convergence_pct,
      forced_exit, sizing_multiplier, buckets_json (5 agents L1-L5)

  - market_regime_log (via cycle_id + asset_class) :
      regime (CALM/STRESS), buy_mult, sell_mult, convergence_thresh

  - portfolio_positions (via instrument_id) :
      quantity actuelle -> delta_qty

  - orders.risk_check_result (JSON deja stocke) :
      approved, order_value_usd, warnings

API principale :
    build_justification(conn, order_id) -> str

Contrat :
  - Ne leve JAMAIS d'exception : en cas de donnee manquante, renvoie
    un fallback lisible ("side qty ticker - context indisponible")
  - Idempotent : peut etre appele plusieurs fois sur le meme order_id
  - Aucun ecrit en base (pure query)

Utilise depuis :
  - execution_engine.py apres INSERT INTO orders (patch 3)
  - api_server_with_static.py endpoint memo (patch 4)
  - memo_generator.py section proposed changes (patch 5b)
"""
import json
import sqlite3
from typing import Optional


# ---------- helpers ----------

def _safe_json(s):
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        return {}


def _classify_asset(ticker: str, is_crypto_hint: Optional[int]) -> str:
    """Renvoie 'crypto' ou 'equity' pour matcher market_regime_log.asset_class."""
    if is_crypto_hint is not None:
        return "crypto" if is_crypto_hint else "equity"
    if not ticker:
        return "equity"
    # heuristique de repli : tickers crypto usuels
    t = ticker.upper()
    crypto_symbols = {"BTC", "ETH", "SOL", "XRP", "ADA", "DOT", "LINK",
                      "ZEC", "LTC", "BCH", "AVAX", "MATIC", "ATOM", "TRX",
                      "ETC", "XLM", "ALGO", "NEAR", "HYPE"}
    return "crypto" if t in crypto_symbols else "equity"


# ---------- main ----------

def build_justification(conn: sqlite3.Connection, order_id: int) -> str:
    """
    Construit la note structuree. Ne leve jamais d'exception.
    Retourne une string, garantie non-None.
    """
    try:
        return _build_impl(conn, order_id)
    except Exception as e:
        return f"[justification indisponible: {type(e).__name__}]"


def _build_impl(conn: sqlite3.Connection, order_id: int) -> str:
    row_factory_backup = conn.row_factory
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # 1) Ordre + instrument
        ord_row = cur.execute("""
            SELECT o.id, o.side, o.quantity, o.instrument_id, o.cycle_id,
                   o.risk_check_result, o.status,
                   i.ticker, i.name
              FROM orders o
              JOIN instruments i ON i.id = o.instrument_id
             WHERE o.id = ?
        """, (order_id,)).fetchone()

        if not ord_row:
            return f"[order {order_id} introuvable]"

        side = (ord_row["side"] or "?").upper()
        qty = ord_row["quantity"] or 0
        ticker = ord_row["ticker"] or "?"
        cycle_id = ord_row["cycle_id"] or ""
        instrument_id = ord_row["instrument_id"]

        # 2) Convergence snapshot (cycle_id + ticker)
        conv = cur.execute("""
            SELECT direction_consensus, n_aligned, n_present, convergence_pct,
                   sizing_multiplier, forced_exit, is_crypto
              FROM convergence_snapshots
             WHERE cycle_id = ? AND ticker = ?
             ORDER BY id DESC LIMIT 1
        """, (cycle_id, ticker)).fetchone()

        # 3) Position actuelle (delta)
        pos = cur.execute("""
            SELECT quantity FROM portfolio_positions
             WHERE instrument_id = ?
        """, (instrument_id,)).fetchone()
        current_qty = float(pos["quantity"]) if pos and pos["quantity"] is not None else 0.0

        # delta = variation nette apportee par cet ordre
        delta_qty = float(qty) if side == "BUY" else -float(qty)

        # 4) Market regime (cycle_id + asset_class)
        is_crypto_hint = conv["is_crypto"] if conv is not None else None
        asset_class = _classify_asset(ticker, is_crypto_hint)
        regime = cur.execute("""
            SELECT regime, buy_mult, sell_mult, convergence_thresh
              FROM market_regime_log
             WHERE cycle_id = ? AND asset_class = ?
             ORDER BY id DESC LIMIT 1
        """, (cycle_id, asset_class)).fetchone()

        # 5) Risk check (deja JSON dans orders)
        risk = _safe_json(ord_row["risk_check_result"])
        risk_ok = bool(risk.get("approved"))
        warnings = risk.get("warnings") or []
        warn_codes = []
        for w in warnings:
            if isinstance(w, dict):
                c = w.get("code")
                if c:
                    warn_codes.append(c)

        # ---------- Composition de la phrase ----------
        parts = []

        # bloc 1 : action + delta
        parts.append(f"{side} {_fmt_qty(qty)} {ticker}")
        parts.append(
            f"(delta {_fmt_signed(delta_qty)} vs pos {_fmt_qty(current_qty)})"
        )

        # bloc 2 : convergence
        if conv is not None:
            conv_pct_num = float(conv["convergence_pct"] or 0) * 100
            n_aligned = conv["n_aligned"] or 0
            n_present = conv["n_present"] or 0
            direction = (conv["direction_consensus"] or "?").lower()
            forced_exit_flag = bool(conv["forced_exit"])
            sizing_mult = conv["sizing_multiplier"]

            parts.append(
                f"- conv {conv_pct_num:.0f}% ({n_aligned}/{n_present} agents {direction})"
            )
            if sizing_mult is not None and abs(float(sizing_mult) - 1.0) > 0.01:
                parts.append(f"sizing {float(sizing_mult):.2f}x")

            # Detecte l'incoherence side vs direction
            if forced_exit_flag:
                parts.append("[FORCED_EXIT]")
            elif direction == "long" and side == "SELL":
                parts.append("[SIZE_REDUCTION]")
            elif direction == "short" and side == "BUY":
                parts.append("[SHORT_COVER]")
        else:
            parts.append("- conv n/a")

        # bloc 3 : regime marche
        if regime is not None:
            reg_name = regime["regime"] or "?"
            mult_key = "buy_mult" if side == "BUY" else "sell_mult"
            mult_val = regime[mult_key]
            if mult_val is not None:
                parts.append(f"- regime {reg_name} ({mult_key} {float(mult_val):.2f}x)")
            else:
                parts.append(f"- regime {reg_name}")
        else:
            parts.append("- regime n/a")

        # bloc 4 : risk
        if risk_ok:
            if warn_codes:
                parts.append(f"- risk OK (warnings: {', '.join(warn_codes[:3])})")
            else:
                parts.append("- risk OK")
        else:
            reasons = risk.get("reasons") or []
            reason_str = "; ".join(str(x) for x in reasons[:2]) if reasons else "no-detail"
            parts.append(f"- risk BLOCK ({reason_str})")

        text = " ".join(parts)
        # tronque a 220 chars max (garde marge de securite pour DB TEXT)
        if len(text) > 220:
            text = text[:217] + "..."
        return text

    finally:
        conn.row_factory = row_factory_backup


# ---------- format helpers ----------

def _fmt_qty(q) -> str:
    try:
        f = float(q)
    except Exception:
        return str(q)
    if abs(f - int(f)) < 1e-9:
        return str(int(f))
    return f"{f:.4f}".rstrip("0").rstrip(".")


def _fmt_signed(f) -> str:
    try:
        v = float(f)
    except Exception:
        return str(f)
    sign = "+" if v >= 0 else ""
    if abs(v - int(v)) < 1e-9:
        return f"{sign}{int(v)}"
    return f"{sign}{v:.4f}".rstrip("0").rstrip(".")


# ---------- CLI test (utile pour verifier a la main) ----------

if __name__ == "__main__":
    import os
    import sys

    DB = os.environ.get("THESIUM_DB",
                        r"C:\Users\RichardGUELIN\Prod\ThesiumDesk\thesium.db")

    if len(sys.argv) > 1:
        target_ids = [int(x) for x in sys.argv[1:]]
    else:
        # par defaut : les 5 derniers ordres
        c0 = sqlite3.connect(DB, timeout=10.0)
        target_ids = [r[0] for r in c0.execute(
            "SELECT id FROM orders ORDER BY id DESC LIMIT 5").fetchall()]
        c0.close()

    conn = sqlite3.connect(DB, timeout=10.0)
    for oid in target_ids:
        j = build_justification(conn, oid)
        print(f"#{oid}: {j}")
    conn.close()
