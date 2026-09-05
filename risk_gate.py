#!/usr/bin/env python3
# risk_gate.py
# [RISK_GATE_V1]
"""Risk Gate v1 — contrôle déterministe portefeuille et pré-trade THESIUM.

Pipeline
--------
consensus_v2 -> decision_gate_v2 -> sizing.py (futur) -> RISK GATE -> startup_ramp.py

Ce module ne crée ni ordre, ni fill, ni écriture SQLite. Il évalue une proposition
contre risk_policy_v1.json et produit une décision entièrement explicable :

  RISK_APPROVED        proposition conforme, taille intacte
  RISK_REDUCED         proposition réduite à une taille sûre
  RISK_REVIEW_REQUIRED donnée critique inconnue ou validation humaine nécessaire
  RISK_REJECTED        règle dure violée, impossible à corriger par réduction

Principes
---------
- Fail closed : absence de donnée critique => REVIEW ou REJECT, jamais APPROVED.
- Les règles dures sont en code et dans la politique versionnée, jamais dans un LLM.
- Une vente qui réduit un risque reste possible même lorsque les achats sont bloqués.
- Toute réduction est calculée puis exposée : jamais silencieuse.
- Le module n'exécute AUCUN ordre et ne contacte AUCUN broker.

Usage
-----
    from risk_gate import RiskGate, load_policy

    policy = load_policy("risk_policy_v1.json")
    gate = RiskGate(policy)
    outcome = gate.evaluate(proposal, portfolio, instrument, market)
    print(outcome.to_dict())

Autotest
--------
    py -3.13 risk_gate.py --selftest
    py -3.13 risk_gate.py --demo
    py -3.13 risk_gate.py --validate-policy risk_policy_v1.json
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# ==========================================================================
# ERREURS ET ENUMS
# ==========================================================================

class PolicyError(ValueError):
    """Politique absente, invalide ou incohérente."""


class RiskStatus(str, Enum):
    RISK_APPROVED = "RISK_APPROVED"
    RISK_REDUCED = "RISK_REDUCED"
    RISK_REVIEW_REQUIRED = "RISK_REVIEW_REQUIRED"
    RISK_REJECTED = "RISK_REJECTED"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


# ==========================================================================
# STRUCTURES PUBLIQUES
# ==========================================================================

@dataclass(frozen=True)
class TradeProposal:
    """Proposition issue du futur sizing, jamais un ordre broker."""
    ticker: str
    side: str
    requested_notional_eur: float
    decision_gate_status: str = "READY_FOR_SIZING"
    cycle_id: str = ""
    rationale: str = ""
    source: str = ""


@dataclass(frozen=True)
class Instrument:
    """Métadonnées déterministes de l'instrument candidat."""
    ticker: str
    asset_class: str
    sector: str = "UNKNOWN"
    instrument_role: str = "DIRECTIONAL"
    universe_state: str = "ELIGIBLE"
    is_halted: bool = False
    is_tradable: bool = True


@dataclass(frozen=True)
class MarketSnapshot:
    """Données de marché nécessaires aux règles pré-trade."""
    price_eur: Optional[float]
    price_age_hours: Optional[float]
    history_observations: Optional[int]
    adv_eur: Optional[float]
    bid_ask_spread_bps: Optional[float] = None
    annualized_vol_pct: Optional[float] = None
    last_price_move_pct: Optional[float] = None
    market_open: bool = True
    quote_currency: str = "EUR"
    fx_rate_to_eur: Optional[float] = 1.0


@dataclass(frozen=True)
class Position:
    ticker: str
    quantity: float
    price_eur: float
    asset_class: str
    sector: str = "UNKNOWN"
    instrument_role: str = "DIRECTIONAL"
    annualized_vol_pct: Optional[float] = None

    @property
    def market_value_eur(self) -> float:
        return max(0.0, float(self.quantity)) * max(0.0, float(self.price_eur))


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Instantané cohérent du portefeuille, fourni par portfolio_state.py futur."""
    nav_eur: float
    cash_eur: float
    positions: Tuple[Position, ...] = ()
    regime: str = "UNKNOWN"
    drawdown_pct: float = 0.0
    pending_tickers: Tuple[str, ...] = ()


@dataclass
class RuleCheck:
    rule_id: str
    status: str                   # PASS / FAIL / WARN / INFO
    severity: str                 # HARD / REVIEW / INFO
    message: str
    actual: Optional[float] = None
    limit: Optional[float] = None
    unit: str = ""
    reducible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskOutcome:
    ticker: str
    side: str
    status: RiskStatus
    reason: str
    requested_notional_eur: float
    approved_notional_eur: float
    reduction_eur: float
    requested_weight_pct: float
    approved_weight_pct: float
    max_safe_notional_eur: float
    policy_id: str
    policy_version: str
    effective_regime: str
    cycle_id: str = ""
    checks: List[RuleCheck] = field(default_factory=list)
    rejection_codes: List[str] = field(default_factory=list)
    review_codes: List[str] = field(default_factory=list)
    reductions: List[Dict[str, Any]] = field(default_factory=list)
    input_snapshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def compact(self) -> str:
        return ("%-8s %-4s %-22s req=%9.2f€ appr=%9.2f€ %s"
                % (self.ticker, self.side, self.status.value,
                   self.requested_notional_eur, self.approved_notional_eur,
                   ",".join(self.rejection_codes + self.review_codes) or "OK"))


# ==========================================================================
# CHARGEMENT ET VALIDATION DE POLITIQUE
# ==========================================================================

_REQUIRED_TOP_LEVEL = {
    "policy_id", "version", "status", "scope", "portfolio", "regime_overrides",
    "asset_class_caps_pct", "position_caps_pct", "sector_caps_pct", "liquidity",
    "market_data", "volatility", "drawdown", "concentration", "trade_controls",
    "decision_gate_requirements", "rune_controls", "universe_admission_interface",
    "audit",
}


def load_policy(path: str = "risk_policy_v1.json") -> Dict[str, Any]:
    """Charge et valide une politique JSON. Échoue fermé si invalide."""
    if not os.path.exists(path):
        raise PolicyError("Politique introuvable : %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            policy = json.load(f)
    except json.JSONDecodeError as e:
        raise PolicyError("JSON invalide dans %s : %s" % (path, e)) from e
    validate_policy(policy)
    return policy


def validate_policy(p: Mapping[str, Any]) -> None:
    """Validation sans dépendance JSONSchema pour garder le déploiement léger."""
    missing = sorted(_REQUIRED_TOP_LEVEL - set(p))
    if missing:
        raise PolicyError("Clés obligatoires absentes : %s" % ", ".join(missing))
    if not str(p["policy_id"]).strip() or not str(p["version"]).strip():
        raise PolicyError("policy_id et version doivent être renseignés")
    if p.get("scope", {}).get("broker_execution_enabled") is not False:
        raise PolicyError("Risk Gate v1 refuse une politique activant le broker")
    if p.get("scope", {}).get("long_only") is not True:
        raise PolicyError("Risk Gate v1 requiert long_only=true")
    if p.get("scope", {}).get("short_selling_allowed") is not False:
        raise PolicyError("Risk Gate v1 requiert short_selling_allowed=false")
    if p.get("change_control", {}).get("fail_closed_on_missing_critical_data") is not True:
        raise PolicyError("La politique doit imposer fail_closed_on_missing_critical_data=true")

    pct_paths = [
        ("portfolio.min_cash_pct", p["portfolio"].get("min_cash_pct")),
        ("portfolio.max_gross_exposure_pct", p["portfolio"].get("max_gross_exposure_pct")),
        ("trade_controls.max_order_notional_pct_nav", p["trade_controls"].get("max_order_notional_pct_nav")),
        ("trade_controls.max_single_ticker_weight_change_pct", p["trade_controls"].get("max_single_ticker_weight_change_pct")),
        ("trade_controls.max_initial_ticker_weight_pct", p["trade_controls"].get("max_initial_ticker_weight_pct")),
        ("rune_controls.block_long_if_short_conviction_gte", p["rune_controls"].get("block_long_if_short_conviction_gte")),
    ]
    for name, value in pct_paths:
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
            raise PolicyError("Valeur invalide : %s=%r" % (name, value))
    if float(p["portfolio"]["min_cash_pct"]) > 100:
        raise PolicyError("min_cash_pct ne peut pas dépasser 100")
    if float(p["portfolio"]["max_gross_exposure_pct"]) > 100:
        raise PolicyError("max_gross_exposure_pct ne peut pas dépasser 100 en long-only")
    if float(p["trade_controls"]["max_initial_ticker_weight_pct"]) > float(p["position_caps_pct"]["default"]):
        raise PolicyError("Le cap initial ne peut pas dépasser le cap position par défaut")
    for name, override in p["regime_overrides"].items():
        if not isinstance(override, Mapping):
            raise PolicyError("Régime invalide : %s" % name)
        for key in ("max_gross_exposure_pct", "min_cash_pct", "new_longs_allowed"):
            if key not in override:
                raise PolicyError("Régime %s : clé absente %s" % (name, key))
        if not 0 <= float(override["min_cash_pct"]) <= 100:
            raise PolicyError("Régime %s : min_cash_pct invalide" % name)
        if not 0 <= float(override["max_gross_exposure_pct"]) <= 100:
            raise PolicyError("Régime %s : max_gross_exposure_pct invalide" % name)


def policy_fingerprint(p: Mapping[str, Any]) -> str:
    raw = json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ==========================================================================
# UTILITAIRES
# ==========================================================================

def _finite(value: Any) -> Optional[float]:
    try:
        x = float(value)
    except (ValueError, TypeError):
        return None
    return x if math.isfinite(x) else None


def _safe_pct(value: float, base: float) -> float:
    return 0.0 if base <= 0 else 100.0 * value / base


def _upper(x: Any, default: str = "UNKNOWN") -> str:
    return str(x or default).strip().upper() or default


def _snapshot_hash(proposal: TradeProposal, portfolio: PortfolioSnapshot,
                   instrument: Instrument, market: MarketSnapshot) -> str:
    blob = {
        "proposal": asdict(proposal), "portfolio": asdict(portfolio),
        "instrument": asdict(instrument), "market": asdict(market),
    }
    raw = json.dumps(blob, sort_keys=True, default=str, ensure_ascii=False,
                     separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ==========================================================================
# RISK GATE
# ==========================================================================

class RiskGate:
    """Évalue une proposition de façon déterministe contre la politique v1."""

    def __init__(self, policy: Mapping[str, Any]):
        validate_policy(policy)
        self.policy: Dict[str, Any] = copy.deepcopy(dict(policy))
        self.policy_hash = policy_fingerprint(self.policy)

    @classmethod
    def from_file(cls, path: str = "risk_policy_v1.json") -> "RiskGate":
        return cls(load_policy(path))

    # ------------------------------------------------------------------
    # Interface principale
    # ------------------------------------------------------------------

    def evaluate(self, proposal: TradeProposal, portfolio: PortfolioSnapshot,
                 instrument: Instrument, market: MarketSnapshot) -> RiskOutcome:
        """Évalue un achat ou une vente sans effet de bord.

        Les contrôles sont exécutés dans un ordre stable. Les blocages irréductibles
        gagnent sur toute réduction. Les contrôles réductibles produisent un plafond
        consolidé, puis la décision finale est calculée une seule fois.
        """
        p = self.policy
        side = _upper(proposal.side)
        ticker = str(proposal.ticker).upper().strip()
        req = _finite(proposal.requested_notional_eur)
        nav = _finite(portfolio.nav_eur)
        cash = _finite(portfolio.cash_eur)

        # Valeurs sûres : l'outcome doit exister même pour entrée invalide.
        req_safe = max(0.0, req or 0.0)
        nav_safe = max(0.0, nav or 0.0)
        outcome = RiskOutcome(
            ticker=ticker or "UNKNOWN",
            side=side,
            status=RiskStatus.RISK_REJECTED,
            reason="",
            requested_notional_eur=req_safe,
            approved_notional_eur=0.0,
            reduction_eur=req_safe,
            requested_weight_pct=_safe_pct(req_safe, nav_safe),
            approved_weight_pct=0.0,
            max_safe_notional_eur=0.0,
            policy_id=str(p["policy_id"]),
            policy_version=str(p["version"]),
            effective_regime=self._effective_regime(portfolio.regime),
            cycle_id=proposal.cycle_id,
            input_snapshot_hash=_snapshot_hash(proposal, portfolio, instrument, market),
        )

        checks = outcome.checks
        hard_fail: List[str] = []
        review: List[str] = []
        ceilings: List[Tuple[str, float, str]] = []

        def check(rule_id: str, passed: bool, message: str, actual: Optional[float] = None,
                  limit: Optional[float] = None, unit: str = "", severity: str = "HARD",
                  reducible: bool = False) -> None:
            status = "PASS" if passed else ("WARN" if severity == "REVIEW" else "FAIL")
            checks.append(RuleCheck(rule_id, status, severity, message, actual, limit, unit, reducible))
            if not passed:
                (review if severity == "REVIEW" else hard_fail).append(rule_id)

        def ceiling(rule_id: str, amount: Optional[float], detail: str) -> None:
            if amount is None or not math.isfinite(amount):
                review.append(rule_id + "_DATA_MISSING")
                checks.append(RuleCheck(rule_id + "_DATA_MISSING", "WARN", "REVIEW",
                                        "Donnée nécessaire au plafond absente", None, None, "EUR", False))
                return
            ceilings.append((rule_id, max(0.0, amount), detail))

        # ==============================================================
        # A. Préconditions et entrées
        # ==============================================================
        check("INPUT_TICKER", bool(ticker), "Ticker renseigné")
        check("INPUT_SIDE", side in (Side.BUY.value, Side.SELL.value),
              "Sens autorisé : BUY ou SELL")
        check("INPUT_NOTIONAL", req is not None and req > 0,
              "Notionnel demandé strictement positif", req, 0.0, "EUR")
        check("PORTFOLIO_NAV", nav is not None and nav >= float(p["portfolio"]["min_nav_eur"]),
              "NAV présente et supérieure au minimum de politique", nav,
              float(p["portfolio"]["min_nav_eur"]), "EUR")
        check("PORTFOLIO_CASH", cash is not None and cash >= 0.0,
              "Cash présent et non négatif", cash, 0.0, "EUR")

        if hard_fail:
            return self._finish(outcome, hard_fail, review, ceilings)

        # ==============================================================
        # B. Entrée de pipeline et univers
        # ==============================================================
        required_statuses = set(p["decision_gate_requirements"]["allowed_input_statuses"])
        check("DECISION_GATE_STATUS", proposal.decision_gate_status in required_statuses,
              "Decision Gate doit autoriser le sizing")

        asset_class = _upper(instrument.asset_class)
        role = _upper(instrument.instrument_role, "DIRECTIONAL")
        universe_state = _upper(instrument.universe_state)
        allowed_classes = set(p["scope"]["allowed_asset_classes"])
        excluded_roles = set(p["scope"]["excluded_instrument_roles"])
        eligible_states = set(p["universe_admission_interface"]["eligible_instrument_states"])

        check("ASSET_CLASS_ALLOWED", asset_class in allowed_classes,
              "Classe d'actif autorisée", severity="HARD")
        check("INSTRUMENT_ROLE_ALLOWED", role not in excluded_roles,
              "Rôle d'instrument compatible avec le pipeline directionnel", severity="HARD")
        check("UNIVERSE_ELIGIBLE", universe_state in eligible_states,
              "Instrument admis et éligible dans l'univers", severity="HARD")
        check("INSTRUMENT_TRADABLE", bool(instrument.is_tradable),
              "Instrument tradable", severity="HARD")
        check("INSTRUMENT_NOT_HALTED", not bool(instrument.is_halted),
              "Instrument non suspendu", severity="HARD")

        # ==============================================================
        # C. Données de marché — fail closed
        # ==============================================================
        price = _finite(market.price_eur)
        age = _finite(market.price_age_hours)
        hist = _finite(market.history_observations)
        adv = _finite(market.adv_eur)
        spread = _finite(market.bid_ask_spread_bps)
        last_move = _finite(market.last_price_move_pct)

        md = p["market_data"]
        liq = p["liquidity"]
        check("PRICE_PRESENT", price is not None and price > 0.0,
              "Prix présent et positif", price, 0.0, "EUR")
        check("PRICE_FRESH", age is not None and age <= float(liq["price_max_age_hours"]),
              "Prix suffisamment récent", age, float(liq["price_max_age_hours"]), "h")
        check("HISTORY_MINIMUM", hist is not None and hist >= float(liq["history_min_observations"]),
              "Historique minimal disponible", hist, float(liq["history_min_observations"]), "observations")
        check("MARKET_OPEN", bool(market.market_open), "Marché ouvert", severity="HARD")
        if last_move is None:
            check("PRICE_MOVE_SANITY", False, "Variation de prix récente absente", severity="REVIEW")
        else:
            check("PRICE_MOVE_SANITY", abs(last_move) <= float(md["max_close_to_last_price_move_pct"]),
                  "Variation de prix dans la plage de cohérence", abs(last_move),
                  float(md["max_close_to_last_price_move_pct"]), "%")

        if market.quote_currency.upper() != p["portfolio"]["base_currency"].upper():
            fx = _finite(market.fx_rate_to_eur)
            check("FX_RATE_PRESENT", fx is not None and fx > 0.0,
                  "Taux FX présent pour une cotation hors devise de base", fx, 0.0, "FX")
        else:
            checks.append(RuleCheck("FX_RATE_PRESENT", "INFO", "INFO",
                                    "Cotation déjà dans la devise de base"))

        min_adv = self._min_adv(asset_class)
        check("ADV_PRESENT", adv is not None and adv > 0.0,
              "ADV présent et positif", adv, min_adv, "EUR")
        if adv is not None:
            check("ADV_MINIMUM", adv >= min_adv, "Liquidité ADV minimum respectée",
                  adv, min_adv, "EUR")
        if spread is None:
            check("SPREAD_PRESENT", False, "Bid-ask spread absent", severity="REVIEW")
        else:
            check("SPREAD_MAX", spread <= float(liq["max_bid_ask_spread_bps"]),
                  "Spread dans la limite", spread, float(liq["max_bid_ask_spread_bps"]), "bps")

        # ==============================================================
        # D. Régime, drawdown et blocages d'achats
        # ==============================================================
        regime = outcome.effective_regime
        regime_policy = p["regime_overrides"][regime]
        dd = _finite(portfolio.drawdown_pct)
        check("DRAWDOWN_PRESENT", dd is not None and dd >= 0.0,
              "Drawdown présent et non négatif", dd, 0.0, "%")
        if dd is not None:
            if dd >= float(p["drawdown"]["halt_pct"]):
                if side == Side.BUY.value:
                    check("DRAWDOWN_HALT_BUY", False, "Drawdown au seuil halt : nouveaux achats interdits",
                          dd, float(p["drawdown"]["halt_pct"]), "%")
                else:
                    checks.append(RuleCheck("DRAWDOWN_HALT_SELL", "PASS", "INFO",
                                            "Vente réductrice autorisée pendant halt", dd,
                                            float(p["drawdown"]["halt_pct"]), "%"))
            elif dd >= float(p["drawdown"]["critical_pct"]) and side == Side.BUY.value:
                check("DRAWDOWN_CRITICAL_BUY", False, "Drawdown critique : nouveaux achats interdits",
                      dd, float(p["drawdown"]["critical_pct"]), "%")
            elif dd >= float(p["drawdown"]["warning_pct"]) and side == Side.BUY.value:
                checks.append(RuleCheck("DRAWDOWN_WARNING", "WARN", "INFO",
                                        "Drawdown warning : plafond achat réduit", dd,
                                        float(p["drawdown"]["warning_pct"]), "%"))

        if side == Side.BUY.value:
            check("REGIME_NEW_LONGS", bool(regime_policy["new_longs_allowed"]),
                  "Nouveaux achats autorisés dans le régime effectif")

        # ==============================================================
        # E. Ventes : disponibilité et principe réduction de risque
        # ==============================================================
        current_pos = self._position(portfolio, ticker)
        current_value = current_pos.market_value_eur if current_pos else 0.0
        current_qty = current_pos.quantity if current_pos else 0.0

        if side == Side.SELL.value:
            check("SELL_POSITION_EXISTS", current_pos is not None and current_qty > 0.0,
                  "Vente possible uniquement sur une position détenue", current_qty, 0.0, "qty")
            if current_pos:
                ceiling("SELL_POSITION_VALUE", current_value,
                        "Vente plafonnée à la valeur de position détenue")

        # ==============================================================
        # F. Plafonds réductibles : position, classe, secteur, cash,
        #    exposition, ADV, ordre, vitesse et volatilité.
        # ==============================================================
        if side == Side.BUY.value:
            # Position par ticker.
            pos_cap_pct = self._position_cap(asset_class)
            pos_cap_eur = nav_safe * pos_cap_pct / 100.0
            ceiling("POSITION_CAP", pos_cap_eur - current_value,
                    "Cap position %s = %.2f%%" % (ticker, pos_cap_pct))

            # Nouvelle position : cap d'entrée initiale, complémentaire au cap position.
            if current_value <= 1e-9:
                init_pct = float(p["trade_controls"]["max_initial_ticker_weight_pct"])
                ceiling("INITIAL_POSITION_CAP", nav_safe * init_pct / 100.0,
                        "Cap initial nouvelle ligne = %.2f%% NAV" % init_pct)

            # Classe d'actifs.
            class_current = self._class_exposure(portfolio, asset_class)
            class_cap_pct = float(p["asset_class_caps_pct"].get(asset_class, 0.0))
            ceiling("ASSET_CLASS_CAP", nav_safe * class_cap_pct / 100.0 - class_current,
                    "Cap classe %s = %.2f%%" % (asset_class, class_cap_pct))

            # Secteur. UNKNOWN est un cap 0 par politique.
            sector = instrument.sector or "UNKNOWN"
            sector_cap_pct = self._sector_cap(sector)
            sector_current = self._sector_exposure(portfolio, sector)
            ceiling("SECTOR_CAP", nav_safe * sector_cap_pct / 100.0 - sector_current,
                    "Cap secteur %s = %.2f%%" % (sector, sector_cap_pct))

            # Cash résiduel et exposition brute, renforcés par le régime.
            min_cash_pct = max(float(p["portfolio"]["min_cash_pct"]),
                               float(regime_policy["min_cash_pct"]))
            min_cash_eur = nav_safe * min_cash_pct / 100.0
            ceiling("CASH_RESERVE", cash - min_cash_eur,
                    "Cash résiduel minimum = %.2f%% NAV" % min_cash_pct)

            max_gross_pct = min(float(p["portfolio"]["max_gross_exposure_pct"]),
                                float(regime_policy["max_gross_exposure_pct"]))
            gross_current = self._gross_exposure(portfolio)
            ceiling("GROSS_EXPOSURE_CAP", nav_safe * max_gross_pct / 100.0 - gross_current,
                    "Exposition brute maximale = %.2f%% NAV" % max_gross_pct)

            # Budget d'achat par cycle et limite d'ordre.
            max_order_by_nav = nav_safe * float(p["trade_controls"]["max_order_notional_pct_nav"]) / 100.0
            max_order_absolute = float(p["trade_controls"]["max_order_notional_eur"])
            ceiling("ORDER_NOTIONAL_CAP", min(max_order_by_nav, max_order_absolute),
                    "Plafond notionnel par ordre")
            buy_budget = nav_safe * float(p["portfolio"]["max_buy_notional_pct_per_cycle"]) / 100.0
            buy_budget *= float(regime_policy.get("buy_notional_multiplier", 1.0))
            if dd is not None and dd >= float(p["drawdown"]["warning_pct"]):
                buy_budget *= float(p["drawdown"]["warning_buy_multiplier"])
            ceiling("CYCLE_BUY_BUDGET", buy_budget,
                    "Budget d'achat du cycle après régime/drawdown")

            # Vitesse de variation par ticker.
            move_cap = nav_safe * float(p["trade_controls"]["max_single_ticker_weight_change_pct"]) / 100.0
            ceiling("TICKER_MOVE_CAP", move_cap,
                    "Variation maximale par ticker et cycle")

            # Nouveaux tickers déjà ouverts dans ce cycle.
            if current_value <= 1e-9:
                n_new = self._new_positions_count(portfolio, ticker)
                max_new = int(regime_policy["max_new_positions_per_cycle"])
                check("NEW_POSITION_COUNT", n_new < max_new,
                      "Nombre maximal de nouvelles positions dans le cycle",
                      float(n_new), float(max_new), "positions")

            # Liquidité : ADV et spread sont déjà validés comme données critiques.
            if adv is not None:
                ceiling("ORDER_ADV_CAP", adv * float(liq["max_order_pct_adv"]) / 100.0,
                        "Part maximale ADV par ordre")
                ceiling("POSITION_ADV_CAP", adv * float(liq["max_position_pct_adv"]) / 100.0 - current_value,
                        "Part maximale ADV par position")

            # Volatilité : interdit l'excès, puis plafonne via contribution simple.
            vol = _finite(market.annualized_vol_pct)
            if vol is None:
                review.append("VOLATILITY_DATA_MISSING")
                checks.append(RuleCheck("VOLATILITY_DATA_MISSING", "WARN", "REVIEW",
                                        "Volatilité absente : revue requise", None, None, "%"))
            else:
                max_vol = min(float(p["volatility"]["max_annualized_vol_pct_for_new_long"]),
                              float(p["volatility"]["max_annualized_vol_pct_by_asset_class"].get(asset_class, 0.0)))
                check("VOLATILITY_MAX", vol <= max_vol,
                      "Volatilité compatible avec l'actif", vol, max_vol, "%")
                if bool(p["volatility"]["volatility_scaling_enabled"]) and vol > 0:
                    # Contribution simple : weight * vol. Exemple .75% de contribution avec
                    # vol 25% permet 3% de poids (0.75 / 25 * 100).
                    max_rc = float(p["volatility"]["max_risk_contribution_pct"])
                    max_weight_pct = 100.0 * max_rc / vol
                    total_position_room = nav_safe * max_weight_pct / 100.0 - current_value
                    ceiling("VOLATILITY_RISK_CONTRIBUTION", total_position_room,
                            "Contribution risque max %.2f%%, vol %.2f%%" % (max_rc, vol))

            # Corrélation : manque = revue selon politique, corrélation élevée = revue.
            # La mesure complète sera alimentée par portfolio_state/correlation engine.
            # On ne l'invente jamais dans ce gate.

        else:  # SELL
            max_order_by_nav = nav_safe * float(p["trade_controls"]["max_order_notional_pct_nav"]) / 100.0
            max_order_absolute = float(p["trade_controls"]["max_order_notional_eur"])
            ceiling("ORDER_NOTIONAL_CAP", min(max_order_by_nav, max_order_absolute),
                    "Plafond notionnel par ordre")
            sell_budget = nav_safe * float(p["portfolio"]["max_sell_notional_pct_per_cycle"]) / 100.0
            ceiling("CYCLE_SELL_BUDGET", sell_budget, "Budget de vente par cycle")
            move_cap = nav_safe * float(p["trade_controls"]["max_single_ticker_weight_change_pct"]) / 100.0
            ceiling("TICKER_MOVE_CAP", move_cap, "Variation maximale par ticker et cycle")
            if adv is not None:
                ceiling("ORDER_ADV_CAP", adv * float(liq["max_order_pct_adv"]) / 100.0,
                        "Part maximale ADV par ordre")

        # Les hard fails irréductibles prévalent sur tout plafond.
        return self._finish(outcome, hard_fail, review, ceilings)

    # ------------------------------------------------------------------
    # Finalisation et plafonds
    # ------------------------------------------------------------------

    def _finish(self, out: RiskOutcome, hard_fail: Sequence[str], review: Sequence[str],
                ceilings: Sequence[Tuple[str, float, str]]) -> RiskOutcome:
        """Consolide les plafonds et attribue un statut, sans effet de bord."""
        out.rejection_codes = sorted(set(hard_fail))
        out.review_codes = sorted(set(review))

        if out.rejection_codes:
            out.status = RiskStatus.RISK_REJECTED
            out.approved_notional_eur = 0.0
            out.reduction_eur = out.requested_notional_eur
            out.max_safe_notional_eur = 0.0
            out.reason = self._reason(out)
            return out

        # Toute revue est un fail closed : pas de montant approuvé.
        if out.review_codes:
            out.status = RiskStatus.RISK_REVIEW_REQUIRED
            out.approved_notional_eur = 0.0
            out.reduction_eur = out.requested_notional_eur
            out.max_safe_notional_eur = 0.0
            out.reason = self._reason(out)
            return out

        if not ceilings:
            # Situation défensive : aucune limite calculable ne signifie pas approbation.
            out.status = RiskStatus.RISK_REVIEW_REQUIRED
            out.review_codes = ["NO_SAFE_CEILING"]
            out.reason = self._reason(out)
            return out

        safe = min(a for _, a, _ in ceilings)
        out.max_safe_notional_eur = max(0.0, safe)
        approved = min(out.requested_notional_eur, out.max_safe_notional_eur)

        # Le notionnel résultant trop petit ne devient jamais un ordre microscopique.
        min_order = float(self.policy["trade_controls"]["min_order_notional_eur"])
        if approved + 1e-9 < min_order:
            out.status = RiskStatus.RISK_REJECTED
            out.rejection_codes = ["SAFE_NOTIONAL_BELOW_MIN_ORDER"]
            out.approved_notional_eur = 0.0
            out.reduction_eur = out.requested_notional_eur
            out.reason = self._reason(out)
            return out

        out.approved_notional_eur = round(approved, 2)
        out.reduction_eur = round(max(0.0, out.requested_notional_eur - approved), 2)
        nav = out.requested_notional_eur / (out.requested_weight_pct / 100.0) \
            if out.requested_weight_pct > 0 else 0.0
        out.approved_weight_pct = round(_safe_pct(approved, nav), 6)

        active_limits = [(rule, cap, detail) for rule, cap, detail in ceilings
                         if abs(cap - safe) < 1e-7]
        if approved + 1e-9 < out.requested_notional_eur:
            out.status = RiskStatus.RISK_REDUCED
            out.reductions = [{"rule_id": rule, "safe_notional_eur": round(cap, 2),
                               "detail": detail}
                              for rule, cap, detail in active_limits]
        else:
            out.status = RiskStatus.RISK_APPROVED
        out.reason = self._reason(out)
        return out

    def _reason(self, out: RiskOutcome) -> str:
        labels = {
            "INPUT_TICKER": "ticker absent",
            "INPUT_SIDE": "sens d'opération invalide",
            "INPUT_NOTIONAL": "notionnel invalide",
            "PORTFOLIO_NAV": "NAV invalide ou insuffisante",
            "PORTFOLIO_CASH": "cash invalide",
            "DECISION_GATE_STATUS": "Decision Gate non autorisé",
            "ASSET_CLASS_ALLOWED": "classe d'actif interdite",
            "INSTRUMENT_ROLE_ALLOWED": "rôle d'instrument exclu",
            "UNIVERSE_ELIGIBLE": "instrument non éligible dans l'univers",
            "INSTRUMENT_TRADABLE": "instrument non tradable",
            "INSTRUMENT_NOT_HALTED": "instrument suspendu",
            "PRICE_PRESENT": "prix absent ou invalide",
            "PRICE_FRESH": "prix périmé",
            "HISTORY_MINIMUM": "historique insuffisant",
            "MARKET_OPEN": "marché fermé",
            "PRICE_MOVE_SANITY": "variation de prix aberrante",
            "FX_RATE_PRESENT": "taux de change absent",
            "ADV_PRESENT": "ADV absent",
            "ADV_MINIMUM": "ADV insuffisant",
            "SPREAD_MAX": "spread excessif",
            "DRAWDOWN_PRESENT": "drawdown absent ou invalide",
            "DRAWDOWN_HALT_BUY": "drawdown au seuil d'arrêt",
            "DRAWDOWN_CRITICAL_BUY": "drawdown critique",
            "REGIME_NEW_LONGS": "achats interdits par le régime",
            "SELL_POSITION_EXISTS": "position insuffisante pour vendre",
            "NEW_POSITION_COUNT": "quota de nouvelles positions atteint",
            "VOLATILITY_MAX": "volatilité excessive",
            "SAFE_NOTIONAL_BELOW_MIN_ORDER": "notionnel sûr inférieur au minimum d'ordre",
            "VOLATILITY_DATA_MISSING": "volatilité absente",
            "PRICE_MOVE_SANITY": "variation de prix absente ou aberrante",
            "SPREAD_PRESENT": "spread absent",
            "NO_SAFE_CEILING": "plafond sûr non calculable",
        }
        codes = out.rejection_codes + out.review_codes
        if out.status == RiskStatus.RISK_APPROVED:
            return "Risque approuvé : toutes les limites sont respectées"
        if out.status == RiskStatus.RISK_REDUCED:
            limits = ", ".join(x["rule_id"] for x in out.reductions)
            return "Risque réduit : %.2f€ -> %.2f€ (%s)" % (
                out.requested_notional_eur, out.approved_notional_eur, limits)
        if out.status == RiskStatus.RISK_REVIEW_REQUIRED:
            return "Revue risque requise : " + "; ".join(labels.get(x, x) for x in codes)
        return "Risque rejeté : " + "; ".join(labels.get(x, x) for x in codes)

    # ------------------------------------------------------------------
    # Lecture de politique et métriques portefeuille
    # ------------------------------------------------------------------

    def _effective_regime(self, raw: str) -> str:
        r = _upper(raw)
        return r if r in self.policy["regime_overrides"] else "UNKNOWN"

    def _min_adv(self, asset_class: str) -> float:
        liq = self.policy["liquidity"]
        return float({
            "EQUITY": liq["equity_etf_min_adv_eur"],
            "ETF": liq["equity_etf_min_adv_eur"],
            "REIT": liq["reit_min_adv_eur"],
            "CRYPTO_DIRECTIONAL": liq["crypto_min_adv_eur"],
        }.get(asset_class, float("inf")))

    def _position_cap(self, asset_class: str) -> float:
        caps = self.policy["position_caps_pct"]
        return float(caps.get(asset_class, caps["default"]))

    def _sector_cap(self, sector: str) -> float:
        caps = self.policy["sector_caps_pct"]
        return float(caps.get(sector, caps.get("default", 0.0)))

    @staticmethod
    def _position(portfolio: PortfolioSnapshot, ticker: str) -> Optional[Position]:
        for pos in portfolio.positions:
            if pos.ticker.upper() == ticker.upper():
                return pos
        return None

    @staticmethod
    def _class_exposure(portfolio: PortfolioSnapshot, asset_class: str) -> float:
        return sum(pos.market_value_eur for pos in portfolio.positions
                   if _upper(pos.asset_class) == asset_class)

    @staticmethod
    def _sector_exposure(portfolio: PortfolioSnapshot, sector: str) -> float:
        return sum(pos.market_value_eur for pos in portfolio.positions
                   if str(pos.sector or "UNKNOWN") == str(sector or "UNKNOWN"))

    @staticmethod
    def _gross_exposure(portfolio: PortfolioSnapshot) -> float:
        return sum(pos.market_value_eur for pos in portfolio.positions)

    @staticmethod
    def _new_positions_count(portfolio: PortfolioSnapshot, ticker: str) -> int:
        # pending_tickers est l'interface temporaire jusqu'à cycle_orchestrator.py.
        # Le ticker courant est exclu pour ne pas compter sa propre proposition deux fois.
        return len({x.upper() for x in portfolio.pending_tickers if x.upper() != ticker.upper()})


# ==========================================================================
# JOURNAL JSONL
# ==========================================================================

class RiskJournal:
    """Journal append-only de décisions; intégration SQLite ultérieure."""

    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def append(self, outcome: RiskOutcome, source: str = "live") -> None:
        rec = {
            "kind": "risk_gate_v1_outcome",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            **outcome.to_dict(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")


# ==========================================================================
# FABRIQUES DE TEST
# ==========================================================================

def _test_policy() -> Dict[str, Any]:
    """Charge la politique locale ou fournit une erreur explicite à l'autotest."""
    return load_policy("risk_policy_v1.json")


def P(ticker="AAPL", side="BUY", notional=1000.0, status="READY_FOR_SIZING") -> TradeProposal:
    return TradeProposal(ticker=ticker, side=side, requested_notional_eur=notional,
                         decision_gate_status=status, cycle_id="selftest")


def I(ticker="AAPL", cls="EQUITY", sector="Technology", state="ELIGIBLE",
      role="DIRECTIONAL", halted=False, tradable=True) -> Instrument:
    return Instrument(ticker=ticker, asset_class=cls, sector=sector,
                      universe_state=state, instrument_role=role,
                      is_halted=halted, is_tradable=tradable)


def M(price=100.0, age=1.0, hist=252, adv=20_000_000.0, spread=10.0,
      vol=20.0, move=1.0, open_=True) -> MarketSnapshot:
    return MarketSnapshot(price_eur=price, price_age_hours=age,
                          history_observations=hist, adv_eur=adv,
                          bid_ask_spread_bps=spread, annualized_vol_pct=vol,
                          last_price_move_pct=move, market_open=open_)


def S(nav=1_000_000.0, cash=900_000.0, positions=(), regime="RISK_ON",
      dd=0.0, pending=()) -> PortfolioSnapshot:
    return PortfolioSnapshot(nav_eur=nav, cash_eur=cash, positions=tuple(positions),
                             regime=regime, drawdown_pct=dd,
                             pending_tickers=tuple(pending))


# ==========================================================================
# AUTOTEST
# ==========================================================================

def selftest() -> int:
    print("=" * 82)
    print("[RISK_GATE_V1] autotest — politique déterministe pré-trade")
    print("=" * 82)
    try:
        policy = _test_policy()
    except PolicyError as e:
        print("ERREUR politique : %s" % e)
        print("Placez risk_policy_v1.json dans le même dossier.")
        return 1
    gate = RiskGate(policy)
    failed: List[str] = []

    def ck(name: str, condition: bool, detail: str = "") -> None:
        print("  %-64s %s%s" % (name, "OK" if condition else "ECHEC",
                                ("  " + detail) if detail and not condition else ""))
        if not condition:
            failed.append(name)

    # 1–4 : politique et fail-closed.
    ck("politique chargée et fingerprint stable", len(gate.policy_hash) == 64)
    ck("broker interdit par politique", policy["scope"]["broker_execution_enabled"] is False)
    try:
        bad = copy.deepcopy(policy)
        bad["scope"]["broker_execution_enabled"] = True
        RiskGate(bad)
        broker_rejected = False
    except PolicyError:
        broker_rejected = True
    ck("politique broker=true refusée", broker_rejected)
    ck("entrée Decision Gate REVIEW refusée", gate.evaluate(P(status="REVIEW_REQUIRED"), S(), I(), M()).status == RiskStatus.RISK_REJECTED)

    # 5–9 : données marché et univers.
    ck("chemin nominal BUY approuvé", gate.evaluate(P(notional=1000), S(), I(), M()).status == RiskStatus.RISK_APPROVED)
    ck("ticker PENDING rejeté", gate.evaluate(P(), S(), I(state="PENDING"), M()).status == RiskStatus.RISK_REJECTED)
    ck("stable reserve rejetée", gate.evaluate(P(), S(), I(role="STABLE_RESERVE"), M()).status == RiskStatus.RISK_REJECTED)
    ck("prix périmé rejeté", gate.evaluate(P(), S(), I(), M(age=25)).status == RiskStatus.RISK_REJECTED)
    ck("ADV absente rejetée", gate.evaluate(P(), S(), I(), M(adv=None)).status == RiskStatus.RISK_REJECTED)

    # 10–14 : régime et drawdown.
    ck("RISK_OFF bloque les achats", gate.evaluate(P(), S(regime="RISK_OFF"), I(), M()).status == RiskStatus.RISK_REJECTED)
    ck("régime inconnu bloque les achats", gate.evaluate(P(), S(regime="inconnu"), I(), M()).status == RiskStatus.RISK_REJECTED)
    ck("drawdown critique bloque BUY", gate.evaluate(P(), S(dd=8.0), I(), M()).status == RiskStatus.RISK_REJECTED)
    ck("drawdown halt autorise SELL réducteur", gate.evaluate(P(ticker="AAPL", side="SELL", notional=1000), S(cash=800000, dd=13, positions=[Position("AAPL", 100, 100, "EQUITY", "Technology")]), I(), M()).status in (RiskStatus.RISK_APPROVED, RiskStatus.RISK_REDUCED))
    ck("marché fermé rejeté", gate.evaluate(P(), S(), I(), M(open_=False)).status == RiskStatus.RISK_REJECTED)

    # 15–20 : plafonds réductibles.
    o = gate.evaluate(P(notional=10_000), S(), I(), M())
    ck("nouvelle position réduite au cap initial .5%", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 5000) < .01, str(o.to_dict()))
    o = gate.evaluate(P(notional=5000), S(cash=51000), I(), M())
    ck("cash reserve réduit la proposition", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 1000) < .01, str(o.to_dict()))
    pos = Position("AAPL", 28_000, 1, "EQUITY", "Technology")
    o = gate.evaluate(P(notional=5000), S(cash=900000, positions=[pos]), I(), M())
    ck("cap ticker 3% réduit à la marge", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 2000) < .01, str(o.to_dict()))
    tech = Position("MSFT", 195_000, 1, "EQUITY", "Technology")
    o = gate.evaluate(P(notional=10_000), S(cash=700000, positions=[tech]), I(), M())
    ck("cap secteur 20% réduit à la marge", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 5000) < .01, str(o.to_dict()))
    many_eq = Position("SPY", 595_000, 1, "EQUITY", "Financials")
    o = gate.evaluate(P(notional=10_000), S(cash=400000, positions=[many_eq]), I(), M())
    ck("cap classe equity 60% réduit à la marge", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 5000) < .01, str(o.to_dict()))
    o = gate.evaluate(P(notional=2_000_000), S(), I(), M())
    ck("ordre gigantesque plafonné", o.status == RiskStatus.RISK_REDUCED and o.approved_notional_eur <= 5000.01)

    # 21–25 : liquidité, volatilité, ventes.
    o = gate.evaluate(P(notional=2_000_000), S(), I(), M(adv=50_000))
    ck("ADV faible rejetée", o.status == RiskStatus.RISK_REJECTED)
    ck("spread absent -> revue fail closed", gate.evaluate(P(), S(), I(), M(spread=None)).status == RiskStatus.RISK_REVIEW_REQUIRED)
    ck("volatilité absente -> revue fail closed", gate.evaluate(P(), S(), I(), M(vol=None)).status == RiskStatus.RISK_REVIEW_REQUIRED)
    ck("vol equity >60% rejetée", gate.evaluate(P(), S(), I(), M(vol=61)).status == RiskStatus.RISK_REJECTED)
    ck("vente sans position rejetée", gate.evaluate(P(side="SELL"), S(), I(), M()).status == RiskStatus.RISK_REJECTED)

    # 26–30 : quantité de position, quota, journal et déterminisme.
    held = Position("AAPL", 20, 100, "EQUITY", "Technology")
    o = gate.evaluate(P(side="SELL", notional=5000), S(cash=800000, positions=[held]), I(), M())
    ck("vente réduite à valeur détenue", o.status == RiskStatus.RISK_REDUCED and abs(o.approved_notional_eur - 2000) < .01)
    o = gate.evaluate(P(ticker="NEW", notional=1000), S(pending=("X", "Y", "Z")), I(ticker="NEW"), M())
    ck("quota nouvelles positions atteint", o.status == RiskStatus.RISK_REJECTED and "NEW_POSITION_COUNT" in o.rejection_codes)
    a = gate.evaluate(P(), S(), I(), M()).to_dict()
    b = gate.evaluate(P(), S(), I(), M()).to_dict()
    ck("décision déterministe", a == b)
    path = "risk_gate_v1_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        RiskJournal(path).append(gate.evaluate(P(), S(), I(), M()), source="selftest")
        with open(path, encoding="utf-8") as f:
            row = json.loads(f.readline())
        ck("journal JSONL relisible", row["kind"] == "risk_gate_v1_outcome" and row["policy_id"] == "RISK_POLICY_V1")
    finally:
        if os.path.exists(path):
            os.remove(path)
    o = gate.evaluate(P(notional=1000), S(), I(), M())
    ck("outcome contient toutes les règles", len(o.checks) >= 15)

    print()
    print("-" * 82)
    if failed:
        print("ÉCHECS : %d/30" % len(failed))
        for x in failed:
            print("  - %s" % x)
        return 1
    print("30/30 contrôles passent. Risk Gate v1 prêt avant sizing.py.")
    return 0


# ==========================================================================
# DÉMONSTRATION
# ==========================================================================

def demo() -> int:
    try:
        gate = RiskGate.from_file()
    except PolicyError as e:
        print("ERREUR politique : %s" % e)
        return 1
    print("=" * 82)
    print("[RISK_GATE_V1] démonstration")
    print("=" * 82)
    scenarios = [
        ("AAPL approuvé", P("AAPL", "BUY", 1000), S(), I("AAPL"), M()),
        ("AAPL cap initial", P("AAPL", "BUY", 12000), S(), I("AAPL"), M()),
        ("JNJ manque données", P("JNJ", "BUY", 1000), S(), I("JNJ", "EQUITY", "Health Care"), M(vol=None)),
        ("BTC risque volatil", P("BTC", "BUY", 1000), S(), I("BTC", "CRYPTO_DIRECTIONAL", "Crypto"), M(vol=101, adv=50_000_000)),
        ("SELL réduction", P("AAPL", "SELL", 5000), S(cash=850000, positions=[Position("AAPL", 20, 100, "EQUITY", "Technology")]), I("AAPL"), M()),
        ("RISK_OFF achat", P("AAPL", "BUY", 1000), S(regime="RISK_OFF"), I("AAPL"), M()),
    ]
    for label, prop, port, inst, market in scenarios:
        out = gate.evaluate(prop, port, inst, market)
        print("\n  %-24s %s" % (label, out.compact()))
        print("     " + out.reason)
        for r in out.reductions:
            print("     réduction : %(rule_id)s -> %(safe_notional_eur).2f€" % r)
    return 0


# ==========================================================================
# CLI
# ==========================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Risk Gate v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    group.add_argument("--validate-policy", metavar="PATH")
    args = parser.parse_args()

    if args.validate_policy:
        try:
            p = load_policy(args.validate_policy)
            print("Politique valide : %s v%s" % (p["policy_id"], p["version"]))
            print("Fingerprint SHA-256 : %s" % policy_fingerprint(p))
            return 0
        except PolicyError as e:
            print("Politique invalide : %s" % e)
            return 1
    return selftest() if args.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
