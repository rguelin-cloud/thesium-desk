#!/usr/bin/env python3
# startup_ramp.py
# [STARTUP_RAMP_V1.0.1]
"""Startup Ramp v1 — montée progressive déterministe du portefeuille THESIUM.

Position dans le pipeline
-------------------------
consensus_v2 -> decision_gate_v2 -> sizing.py -> risk_gate.py -> STARTUP RAMP
                                                               -> revue humaine
                                                               -> paper trading futur

Le Risk Gate décide si une proposition est sûre au regard des limites portefeuille.
Le Startup Ramp décide si le portefeuille est autorisé à déployer CE montant CE cycle,
compte tenu de son stade de démarrage, de son niveau d'investissement et de sa santé.

Ce module ne crée ni ordre, ni fill, ni écriture SQLite, ni appel broker.

Principes
---------
- Le Risk Gate est une précondition : seuls RISK_APPROVED/RISK_REDUCED entrent.
- La limite la plus conservatrice gagne toujours.
- Une vente qui réduit le risque contourne la limite de ramp, mais reste soumise au Risk Gate.
- Une phase ne progresse jamais automatiquement.
- Santé, réconciliation ou métriques manquantes => fail closed, RAMP_REVIEW_REQUIRED.
- PAUSED et DE_RISK interdisent tout nouvel achat.

Usage
-----
    from startup_ramp import StartupRamp, load_startup_policy

    ramp = StartupRamp.from_file("startup_policy_v1.json")
    outcome = ramp.evaluate(proposal, portfolio, health)
    print(outcome.to_dict())

Autotest
--------
    py -3.13 startup_ramp.py --validate-policy startup_policy_v1.json
    py -3.13 startup_ramp.py --selftest
    py -3.13 startup_ramp.py --demo
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
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


class StartupPolicyError(ValueError):
    pass


class RampStatus(str, Enum):
    RAMP_APPROVED = "RAMP_APPROVED"
    RAMP_REDUCED = "RAMP_REDUCED"
    RAMP_PAUSED = "RAMP_PAUSED"
    RAMP_REVIEW_REQUIRED = "RAMP_REVIEW_REQUIRED"
    RAMP_REJECTED = "RAMP_REJECTED"


@dataclass(frozen=True)
class RiskApprovedProposal:
    ticker: str
    side: str
    risk_status: str
    risk_approved_notional_eur: float
    asset_class: str
    is_new_position: bool
    decision_gate_status: str = "READY_FOR_SIZING"
    cycle_id: str = ""


@dataclass(frozen=True)
class RampPortfolio:
    nav_eur: float
    invested_eur: float
    strategic_target_invested_eur: float
    phase: str = "BOOTSTRAP"
    regime: str = "RISK_ON"
    cycle_net_buys_eur: float = 0.0
    cycle_asset_class_net_buys_eur: float = 0.0
    cycle_new_positions: int = 0
    completed_open_cycles_in_phase: int = 0
    phase_human_approved: bool = False


@dataclass(frozen=True)
class RampHealth:
    paper_fills_reconciled: Optional[bool]
    unreconciled_paper_fills: Optional[int]
    open_critical_incidents: Optional[int]
    consecutive_failed_cycles: Optional[int]
    data_staleness_hours: Optional[float]
    agent_call_success_rate_pct: Optional[float]
    router_p95_latency_seconds: Optional[float]
    unresolved_review_items: Optional[int]
    drawdown_pct: Optional[float]
    phase_change_human_approved: Optional[bool] = None


@dataclass
class RampCheck:
    rule_id: str
    status: str
    severity: str
    message: str
    actual: Optional[float] = None
    limit: Optional[float] = None
    unit: str = ""
    reducible: bool = False


@dataclass
class RampOutcome:
    ticker: str
    side: str
    status: RampStatus
    reason: str
    requested_notional_eur: float
    approved_notional_eur: float
    reduction_eur: float
    max_deployable_notional_eur: float
    policy_id: str
    policy_version: str
    phase: str
    effective_regime: str
    cycle_id: str = ""
    checks: List[RampCheck] = field(default_factory=list)
    rejection_codes: List[str] = field(default_factory=list)
    review_codes: List[str] = field(default_factory=list)
    pause_codes: List[str] = field(default_factory=list)
    reductions: List[Dict[str, Any]] = field(default_factory=list)
    input_snapshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def compact(self) -> str:
        codes = self.rejection_codes + self.review_codes + self.pause_codes
        return ("%-8s %-4s %-22s req=%9.2f€ appr=%9.2f€ %s" % (
            self.ticker, self.side, self.status.value,
            self.requested_notional_eur, self.approved_notional_eur,
            ",".join(codes) or "OK"))


@dataclass
class PromotionEligibility:
    current_phase: str
    next_phase: Optional[str]
    eligible: bool
    reason: str
    checks: List[RampCheck] = field(default_factory=list)
    blocking_codes: List[str] = field(default_factory=list)


_REQUIRED_TOP = {
    "policy_id", "version", "status", "scope", "phase_order", "initial_phase",
    "special_phases", "phases", "health_gates_for_promotion",
    "automatic_safety_actions", "interaction_with_risk_policy",
    "promotion_protocol", "change_control", "audit",
}

_REQUIRED_PHASE = {
    "min_completed_open_cycles", "max_deployed_pct_of_strategic_target",
    "max_total_invested_pct_nav", "max_net_buy_pct_nav_per_cycle",
    "max_new_position_pct_nav_per_cycle", "max_existing_position_increase_pct_nav_per_cycle",
    "max_asset_class_net_buy_pct_nav_per_cycle", "max_new_positions_per_cycle",
    "max_deployable_notional_eur_per_cycle", "allow_new_longs",
}


def load_startup_policy(path: str = "startup_policy_v1.json") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise StartupPolicyError("Politique introuvable : %s" % path)
    try:
        with open(path, encoding="utf-8") as f:
            policy = json.load(f)
    except json.JSONDecodeError as e:
        raise StartupPolicyError("JSON invalide : %s" % e) from e
    validate_startup_policy(policy)
    return policy


def validate_startup_policy(policy: Mapping[str, Any]) -> None:
    missing = sorted(_REQUIRED_TOP - set(policy))
    if missing:
        raise StartupPolicyError("Clés obligatoires absentes : %s" % ", ".join(missing))
    if policy.get("scope", {}).get("broker_execution_enabled") is not False:
        raise StartupPolicyError("Startup Ramp v1 refuse broker_execution_enabled=true")
    if policy.get("change_control", {}).get("allow_automatic_phase_promotion") is not False:
        raise StartupPolicyError("La promotion automatique est interdite")
    if policy.get("change_control", {}).get("risk_gate_must_approve_before_ramp") is not True:
        raise StartupPolicyError("Risk Gate doit être une précondition")

    phases = policy["phases"]
    declared = list(policy["phase_order"]) + list(policy["special_phases"])
    missing_phase = [x for x in declared if x not in phases]
    if missing_phase:
        raise StartupPolicyError("Phases absentes : %s" % ", ".join(missing_phase))
    if policy["initial_phase"] not in policy["phase_order"]:
        raise StartupPolicyError("initial_phase doit appartenir à phase_order")

    for name, phase in phases.items():
        keys = _REQUIRED_PHASE - set(phase)
        if keys:
            raise StartupPolicyError("Phase %s : clés absentes %s" % (name, ", ".join(sorted(keys))))
        for key in _REQUIRED_PHASE - {"allow_new_longs"}:
            value = phase[key]
            if not isinstance(value, (int, float)) or not math.isfinite(float(value)) or float(value) < 0:
                raise StartupPolicyError("Phase %s : valeur invalide %s=%r" % (name, key, value))
        if not isinstance(phase["allow_new_longs"], bool):
            raise StartupPolicyError("Phase %s : allow_new_longs doit être bool" % name)
        if float(phase["max_total_invested_pct_nav"]) > 100:
            raise StartupPolicyError("Phase %s : invested max >100" % name)
        if float(phase["max_deployed_pct_of_strategic_target"]) > 100:
            raise StartupPolicyError("Phase %s : deployed target >100" % name)


def policy_fingerprint(policy: Mapping[str, Any]) -> str:
    raw = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _input_hash(proposal: RiskApprovedProposal, portfolio: RampPortfolio,
                health: RampHealth) -> str:
    raw = json.dumps({"proposal": asdict(proposal), "portfolio": asdict(portfolio),
                      "health": asdict(health)}, sort_keys=True, ensure_ascii=False,
                     default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class StartupRamp:
    """Garde de vitesse de déploiement, pur et déterministe."""

    def __init__(self, policy: Mapping[str, Any]):
        validate_startup_policy(policy)
        self.policy = copy.deepcopy(dict(policy))
        self.policy_hash = policy_fingerprint(self.policy)

    @classmethod
    def from_file(cls, path: str = "startup_policy_v1.json") -> "StartupRamp":
        return cls(load_startup_policy(path))

    def evaluate(self, proposal: RiskApprovedProposal, portfolio: RampPortfolio,
                 health: RampHealth) -> RampOutcome:
        """Borne un montant déjà autorisé par Risk Gate selon phase et santé.

        Priorité des résultats :
        1. entrée/Risk Gate invalide => RAMP_REJECTED
        2. vente réductrice Risk Gate approuvée => RAMP_APPROVED
        3. phase/régime/santé bloquants => RAMP_PAUSED
        4. donnée nécessaire absente ou autorisation humaine absente => REVIEW_REQUIRED
        5. plafonds économiques => APPROVED ou REDUCED

        Le classement des pauses avant les plafonds est volontaire : PAUSED ne veut
        pas dire que le budget est épuisé, mais que tout nouvel achat est interdit.
        """
        policy = self.policy
        side = _upper(proposal.side)
        phase, phase_is_known = self._phase(portfolio.phase)
        regime = _upper(portfolio.regime)
        requested = _finite(proposal.risk_approved_notional_eur)
        nav = _finite(portfolio.nav_eur)
        invested = _finite(portfolio.invested_eur)
        strategic = _finite(portfolio.strategic_target_invested_eur)
        req_safe = max(0.0, requested or 0.0)

        out = RampOutcome(
            ticker=str(proposal.ticker).upper().strip() or "UNKNOWN",
            side=side,
            status=RampStatus.RAMP_REJECTED,
            reason="",
            requested_notional_eur=req_safe,
            approved_notional_eur=0.0,
            reduction_eur=req_safe,
            max_deployable_notional_eur=0.0,
            policy_id=str(policy["policy_id"]),
            policy_version=str(policy["version"]),
            phase=phase,
            effective_regime=regime,
            cycle_id=proposal.cycle_id,
            input_snapshot_hash=_input_hash(proposal, portfolio, health),
        )
        hard: List[str] = []
        review: List[str] = []
        paused: List[str] = []
        ceilings: List[Tuple[str, float, str]] = []

        def add_check(rule_id: str, passed: bool, message: str,
                      actual: Optional[float] = None, limit: Optional[float] = None,
                      unit: str = "", severity: str = "HARD") -> None:
            status = "PASS" if passed else ("WARN" if severity == "REVIEW" else "FAIL")
            out.checks.append(RampCheck(rule_id, status, severity, message, actual, limit, unit))
            if not passed:
                if severity == "REVIEW":
                    review.append(rule_id)
                elif severity == "PAUSE":
                    paused.append(rule_id)
                else:
                    hard.append(rule_id)

        def add_ceiling(rule_id: str, value: Optional[float], detail: str) -> None:
            if value is None or not math.isfinite(value):
                review.append(rule_id + "_DATA_MISSING")
                out.checks.append(RampCheck(rule_id + "_DATA_MISSING", "WARN", "REVIEW",
                                             "Donnée nécessaire au plafond absente", None, None, "EUR"))
            else:
                ceilings.append((rule_id, max(0.0, value), detail))

        # 1. Entrées et précondition Risk Gate.
        add_check("INPUT_TICKER", out.ticker != "UNKNOWN", "Ticker renseigné")
        add_check("INPUT_SIDE", side in ("BUY", "SELL"), "Sens autorisé : BUY ou SELL")
        add_check("RISK_GATE_APPROVED", proposal.risk_status in ("RISK_APPROVED", "RISK_REDUCED"),
                  "Risk Gate doit avoir approuvé ou réduit la proposition")
        add_check("INPUT_NOTIONAL", requested is not None and requested > 0,
                  "Notionnel Risk Gate strictement positif", requested, 0.0, "EUR")
        add_check("PORTFOLIO_NAV", nav is not None and nav > 0,
                  "NAV présente et positive", nav, 0.0, "EUR")
        add_check("PORTFOLIO_INVESTED", invested is not None and invested >= 0,
                  "Montant investi présent", invested, 0.0, "EUR")
        add_check("STRATEGIC_TARGET_PRESENT", strategic is not None and strategic >= 0,
                  "Cible stratégique investie présente", strategic, 0.0, "EUR")
        if hard:
            return self._finish(out, hard, review, paused, ceilings)

        # 2. Vente réductrice : jamais ralentie par le ramp, sous réserve Risk Gate.
        if side == "SELL":
            out.status = RampStatus.RAMP_APPROVED
            out.approved_notional_eur = round(req_safe, 2)
            out.reduction_eur = 0.0
            out.max_deployable_notional_eur = round(req_safe, 2)
            out.reason = "Ramp approuvé : vente réductrice non limitée par la montée en charge"
            out.checks.append(RampCheck("RISK_REDUCING_SELL_BYPASS", "PASS", "INFO",
                                        "Vente réductrice autorisée, sous réserve du Risk Gate"))
            return out

        # 3. Pauses dures avant tout calcul économique.
        phase_policy = policy["phases"][phase]
        add_check("PHASE_RECOGNIZED", phase_is_known,
                  "Phase portefeuille reconnue", severity="PAUSE")
        add_check("PHASE_ALLOWS_LONGS", bool(phase_policy["allow_new_longs"]),
                  "La phase active autorise les nouveaux LONG", severity="PAUSE")
        add_check("REGIME_ALLOWS_LONGS", regime not in ("RISK_OFF", "UNKNOWN"),
                  "Régime compatible avec nouveaux achats", severity="PAUSE")
        self._health_checks(out, health, review, paused)
        if paused:
            return self._finish(out, hard, review, paused, ceilings)

        # 4. Revue humaine et données nécessaires aux plafonds.
        if bool(phase_policy.get("require_human_approval_for_new_position", False)) and proposal.is_new_position:
            add_check("NEW_POSITION_HUMAN_APPROVAL", bool(portfolio.phase_human_approved),
                      "Nouvelle position requiert approbation humaine de phase", severity="REVIEW")

        # 5. Plafonds économiques de la phase.
        target_deployed = strategic * float(phase_policy["max_deployed_pct_of_strategic_target"]) / 100.0
        add_ceiling("STRATEGIC_DEPLOYMENT_CAP", target_deployed - invested,
                    "%.2f%% de la cible stratégique" % float(phase_policy["max_deployed_pct_of_strategic_target"]))

        total_cap = nav * float(phase_policy["max_total_invested_pct_nav"]) / 100.0
        add_ceiling("TOTAL_INVESTED_CAP", total_cap - invested,
                    "%.2f%% NAV investi maximum" % float(phase_policy["max_total_invested_pct_nav"]))

        cycle_cap = nav * float(phase_policy["max_net_buy_pct_nav_per_cycle"]) / 100.0
        cycle_buys = _finite(portfolio.cycle_net_buys_eur)
        if cycle_buys is None or cycle_buys < 0:
            review.append("CYCLE_NET_BUYS_DATA_MISSING")
            out.checks.append(RampCheck("CYCLE_NET_BUYS_DATA_MISSING", "WARN", "REVIEW",
                                        "Achats nets du cycle absents ou invalides", cycle_buys, cycle_cap, "EUR"))
        else:
            add_ceiling("CYCLE_NET_BUY_CAP", cycle_cap - cycle_buys,
                        "%.2f%% NAV d'achats nets par cycle" % float(phase_policy["max_net_buy_pct_nav_per_cycle"]))

        if proposal.is_new_position:
            ticker_cap = nav * float(phase_policy["max_new_position_pct_nav_per_cycle"]) / 100.0
            add_ceiling("NEW_POSITION_RAMP_CAP", ticker_cap,
                        "%.2f%% NAV pour une nouvelle ligne" % float(phase_policy["max_new_position_pct_nav_per_cycle"]))
            new_count = _finite(portfolio.cycle_new_positions)
            max_new = float(phase_policy["max_new_positions_per_cycle"])
            add_check("NEW_POSITION_COUNT", new_count is not None and new_count < max_new,
                      "Quota de nouvelles positions de la phase", new_count, max_new, "positions")
        else:
            ticker_cap = nav * float(phase_policy["max_existing_position_increase_pct_nav_per_cycle"]) / 100.0
            add_ceiling("EXISTING_POSITION_RAMP_CAP", ticker_cap,
                        "%.2f%% NAV d'augmentation sur ligne existante" %
                        float(phase_policy["max_existing_position_increase_pct_nav_per_cycle"]))

        class_cap = nav * float(phase_policy["max_asset_class_net_buy_pct_nav_per_cycle"]) / 100.0
        class_buys = _finite(portfolio.cycle_asset_class_net_buys_eur)
        if class_buys is None or class_buys < 0:
            review.append("ASSET_CLASS_CYCLE_BUYS_DATA_MISSING")
            out.checks.append(RampCheck("ASSET_CLASS_CYCLE_BUYS_DATA_MISSING", "WARN", "REVIEW",
                                        "Achats nets de classe absents ou invalides", class_buys, class_cap, "EUR"))
        else:
            add_ceiling("ASSET_CLASS_CYCLE_BUY_CAP", class_cap - class_buys,
                        "%.2f%% NAV par classe et cycle" %
                        float(phase_policy["max_asset_class_net_buy_pct_nav_per_cycle"]))

        add_ceiling("PHASE_EUR_DEPLOYMENT_CAP", float(phase_policy["max_deployable_notional_eur_per_cycle"]),
                    "Cap EUR de déploiement de phase")
        return self._finish(out, hard, review, paused, ceilings)

    def _health_checks(self, out: RampOutcome, health: RampHealth,
                       review: List[str], paused: List[str]) -> None:
        gates = self.policy["health_gates_for_promotion"]

        def value(name: str) -> Optional[float]:
            return _finite(getattr(health, name))

        def add(rule: str, passed: bool, message: str, actual: Optional[float],
                limit: Optional[float], unit: str, action: str = "REVIEW") -> None:
            if actual is None:
                out.checks.append(RampCheck(rule + "_MISSING", "WARN", "REVIEW",
                                            message + " : donnée absente", None, limit, unit))
                review.append(rule + "_MISSING")
            elif passed:
                out.checks.append(RampCheck(rule, "PASS", "INFO", message, actual, limit, unit))
            elif action == "PAUSE":
                out.checks.append(RampCheck(rule, "FAIL", "PAUSE", message, actual, limit, unit))
                paused.append(rule)
            else:
                out.checks.append(RampCheck(rule, "WARN", "REVIEW", message, actual, limit, unit))
                review.append(rule)

        fills_ok = health.paper_fills_reconciled
        if fills_ok is None:
            out.checks.append(RampCheck("PAPER_FILLS_RECONCILED_MISSING", "WARN", "REVIEW",
                                        "État de réconciliation paper fills absent"))
            review.append("PAPER_FILLS_RECONCILED_MISSING")
        elif fills_ok is False:
            out.checks.append(RampCheck("PAPER_FILLS_RECONCILED", "FAIL", "PAUSE",
                                        "Fills paper non réconciliés"))
            paused.append("PAPER_FILLS_RECONCILED")
        else:
            out.checks.append(RampCheck("PAPER_FILLS_RECONCILED", "PASS", "INFO",
                                        "Fills paper réconciliés"))

        unrec = value("unreconciled_paper_fills")
        incidents = value("open_critical_incidents")
        failed = value("consecutive_failed_cycles")
        stale = value("data_staleness_hours")
        success = value("agent_call_success_rate_pct")
        p95 = value("router_p95_latency_seconds")
        unresolved = value("unresolved_review_items")
        add("UNRECONCILED_PAPER_FILLS", unrec is not None and unrec <= float(gates["max_unreconciled_paper_fills"]),
            "Fills paper non réconciliés sous limite", unrec, float(gates["max_unreconciled_paper_fills"]), "fills", "PAUSE")
        add("OPEN_CRITICAL_INCIDENTS", incidents is not None and incidents <= float(gates["max_open_critical_incidents"]),
            "Incidents critiques ouverts sous limite", incidents, float(gates["max_open_critical_incidents"]), "incidents", "PAUSE")
        add("CONSECUTIVE_FAILED_CYCLES", failed is not None and failed <= float(gates["max_consecutive_failed_cycles"]),
            "Cycles échoués consécutifs sous limite", failed, float(gates["max_consecutive_failed_cycles"]), "cycles", "PAUSE")
        add("DATA_STALENESS", stale is not None and stale <= float(gates["max_recent_data_staleness_hours"]),
            "Fraîcheur des données sous limite", stale, float(gates["max_recent_data_staleness_hours"]), "h", "PAUSE")
        add("AGENT_SUCCESS_RATE", success is not None and success >= float(gates["min_agent_call_success_rate_pct"]),
            "Taux de succès agents suffisant", success, float(gates["min_agent_call_success_rate_pct"]), "%")
        add("ROUTER_P95", p95 is not None and p95 <= float(gates["max_router_p95_latency_seconds"]),
            "p95 router sous limite", p95, float(gates["max_router_p95_latency_seconds"]), "s")
        add("UNRESOLVED_REVIEW_ITEMS", unresolved is not None and unresolved <= float(gates["max_unresolved_review_items"]),
            "Éléments en revue résolus", unresolved, float(gates["max_unresolved_review_items"]), "items")

        dd = value("drawdown_pct")
        if dd is None:
            out.checks.append(RampCheck("DRAWDOWN_MISSING", "WARN", "REVIEW", "Drawdown absent"))
            review.append("DRAWDOWN_MISSING")
        elif dd >= 12.0:
            out.checks.append(RampCheck("DRAWDOWN_HALT", "FAIL", "PAUSE",
                                        "Drawdown au seuil halt", dd, 12.0, "%"))
            paused.append("DRAWDOWN_HALT")
        elif dd >= 8.0:
            out.checks.append(RampCheck("DRAWDOWN_CRITICAL", "FAIL", "PAUSE",
                                        "Drawdown au seuil critique", dd, 8.0, "%"))
            paused.append("DRAWDOWN_CRITICAL")
        else:
            out.checks.append(RampCheck("DRAWDOWN_HEALTH", "PASS", "INFO",
                                        "Drawdown sous seuil critique", dd, 8.0, "%"))

    def promotion_eligibility(self, portfolio: RampPortfolio,
                              health: RampHealth) -> PromotionEligibility:
        policy = self.policy
        current, known = self._phase(portfolio.phase)
        order = list(policy["phase_order"])
        if not known or current not in order:
            return PromotionEligibility(current, None, False,
                "Phase spéciale ou inconnue : aucune promotion autorisée",
                blocking_codes=["PHASE_NOT_PROMOTABLE"])
        index = order.index(current)
        if index >= len(order) - 1:
            return PromotionEligibility(current, None, False,
                "STEADY_STATE est la phase terminale", blocking_codes=["ALREADY_TERMINAL_PHASE"])
        next_phase = order[index + 1]
        checks: List[RampCheck] = []
        blocked: List[str] = []

        def ck(rule: str, condition: bool, message: str, actual: Optional[float] = None,
               limit: Optional[float] = None, unit: str = "") -> None:
            checks.append(RampCheck(rule, "PASS" if condition else "FAIL", "HARD", message,
                                    actual, limit, unit))
            if not condition:
                blocked.append(rule)

        min_cycles = float(policy["phases"][current]["min_completed_open_cycles"])
        cycles = _finite(portfolio.completed_open_cycles_in_phase)
        ck("PHASE_MIN_CYCLES", cycles is not None and cycles >= min_cycles,
           "Nombre minimal de cycles dans la phase", cycles, min_cycles, "cycles")
        ck("PHASE_HUMAN_APPROVAL", bool(health.phase_change_human_approved),
           "Approbation humaine explicite de progression")
        allowed_regimes = set(policy["health_gates_for_promotion"]["regimes_allowed_for_promotion"])
        ck("PROMOTION_REGIME", _upper(portfolio.regime) in allowed_regimes,
           "Régime compatible avec progression")

        temp = RampOutcome("PROMOTION", "BUY", RampStatus.RAMP_REJECTED, "", 0, 0, 0, 0,
                           policy["policy_id"], policy["version"], current, _upper(portfolio.regime))
        review: List[str] = []
        paused: List[str] = []
        self._health_checks(temp, health, review, paused)
        checks.extend(temp.checks)
        blocked.extend(review + paused)
        eligible = not blocked
        reason = ("Promotion vers %s éligible mais jamais automatique" % next_phase if eligible
                  else "Promotion bloquée : " + ", ".join(sorted(set(blocked))))
        return PromotionEligibility(current, next_phase, eligible, reason, checks,
                                    sorted(set(blocked)))

    def _finish(self, out: RampOutcome, hard: Sequence[str], review: Sequence[str],
                paused: Sequence[str], ceilings: Sequence[Tuple[str, float, str]]) -> RampOutcome:
        out.rejection_codes = sorted(set(hard))
        out.review_codes = sorted(set(review))
        out.pause_codes = sorted(set(paused))
        if out.rejection_codes:
            out.status = RampStatus.RAMP_REJECTED
            out.reason = self._reason(out)
            return out
        if out.pause_codes:
            out.status = RampStatus.RAMP_PAUSED
            out.reason = self._reason(out)
            return out
        if out.review_codes:
            out.status = RampStatus.RAMP_REVIEW_REQUIRED
            out.reason = self._reason(out)
            return out
        if not ceilings:
            out.status = RampStatus.RAMP_REVIEW_REQUIRED
            out.review_codes = ["NO_RAMP_CEILINGS"]
            out.reason = self._reason(out)
            return out

        safe = min(value for _, value, _ in ceilings)
        out.max_deployable_notional_eur = round(max(0.0, safe), 2)
        approved = min(out.requested_notional_eur, out.max_deployable_notional_eur)
        if approved <= 1e-9:
            out.status = RampStatus.RAMP_PAUSED
            out.pause_codes = ["RAMP_CAP_EXHAUSTED"]
            out.reason = self._reason(out)
            return out
        out.approved_notional_eur = round(approved, 2)
        out.reduction_eur = round(max(0.0, out.requested_notional_eur - approved), 2)
        active = [(rule, value, detail) for rule, value, detail in ceilings if abs(value - safe) < 1e-7]
        if approved + 1e-9 < out.requested_notional_eur:
            out.status = RampStatus.RAMP_REDUCED
            out.reductions = [{"rule_id": rule, "safe_notional_eur": round(value, 2), "detail": detail}
                              for rule, value, detail in active]
        else:
            out.status = RampStatus.RAMP_APPROVED
        out.reason = self._reason(out)
        return out

    @staticmethod
    def _reason(out: RampOutcome) -> str:
        labels = {
            "INPUT_TICKER": "ticker absent",
            "INPUT_SIDE": "sens invalide",
            "RISK_GATE_APPROVED": "Risk Gate non approuvé",
            "INPUT_NOTIONAL": "notionnel Risk Gate invalide",
            "PORTFOLIO_NAV": "NAV absente ou invalide",
            "PORTFOLIO_INVESTED": "investi absent ou invalide",
            "STRATEGIC_TARGET_PRESENT": "cible stratégique absente",
            "PHASE_RECOGNIZED": "phase portefeuille inconnue",
            "PHASE_ALLOWS_LONGS": "phase active : nouveaux achats suspendus",
            "REGIME_ALLOWS_LONGS": "régime défensif ou inconnu",
            "PAPER_FILLS_RECONCILED": "fills paper non réconciliés",
            "PAPER_FILLS_RECONCILED_MISSING": "réconciliation paper inconnue",
            "UNRECONCILED_PAPER_FILLS": "fills non réconciliés",
            "OPEN_CRITICAL_INCIDENTS": "incident critique ouvert",
            "CONSECUTIVE_FAILED_CYCLES": "cycle échoué récent",
            "DATA_STALENESS": "données trop anciennes",
            "AGENT_SUCCESS_RATE": "taux de succès agents insuffisant",
            "ROUTER_P95": "latence p95 excessive",
            "UNRESOLVED_REVIEW_ITEMS": "éléments en revue non résolus",
            "DRAWDOWN_MISSING": "drawdown absent",
            "DRAWDOWN_CRITICAL": "drawdown critique",
            "DRAWDOWN_HALT": "drawdown au seuil d'arrêt",
            "NEW_POSITION_HUMAN_APPROVAL": "approbation humaine requise pour nouvelle position",
            "NEW_POSITION_COUNT": "quota de nouvelles positions atteint",
            "CYCLE_NET_BUYS_DATA_MISSING": "budget achats cycle inconnu",
            "ASSET_CLASS_CYCLE_BUYS_DATA_MISSING": "budget achats de classe inconnu",
            "NO_RAMP_CEILINGS": "plafonds de ramp non calculables",
            "RAMP_CAP_EXHAUSTED": "budget de montée en charge épuisé",
        }
        codes = out.rejection_codes + out.review_codes + out.pause_codes
        if out.status == RampStatus.RAMP_APPROVED:
            return "Ramp approuvé : montant conforme à la phase %s" % out.phase
        if out.status == RampStatus.RAMP_REDUCED:
            rules = ", ".join(item["rule_id"] for item in out.reductions)
            return "Ramp réduit : %.2f€ -> %.2f€ (%s)" % (
                out.requested_notional_eur, out.approved_notional_eur, rules)
        if out.status == RampStatus.RAMP_PAUSED:
            return "Ramp suspendu : " + "; ".join(labels.get(code, code) for code in codes)
        if out.status == RampStatus.RAMP_REVIEW_REQUIRED:
            return "Ramp en revue : " + "; ".join(labels.get(code, code) for code in codes)
        return "Ramp rejeté : " + "; ".join(labels.get(code, code) for code in codes)

    def _phase(self, raw: str) -> Tuple[str, bool]:
        phase = _upper(raw)
        if phase in self.policy["phases"]:
            return phase, True
        return "PAUSED", False


class StartupRampJournal:
    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def append(self, outcome: RampOutcome, source: str = "live") -> None:
        row = {"kind": "startup_ramp_v1_outcome",
               "timestamp": datetime.now(timezone.utc).isoformat(),
               "source": source, **outcome.to_dict()}
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def Q(ticker="AAPL", side="BUY", risk_status="RISK_APPROVED", amount=5000.0,
      asset_class="EQUITY", new=True) -> RiskApprovedProposal:
    return RiskApprovedProposal(ticker=ticker, side=side, risk_status=risk_status,
                                risk_approved_notional_eur=amount,
                                asset_class=asset_class, is_new_position=new,
                                decision_gate_status="READY_FOR_SIZING", cycle_id="selftest")


def P(nav=1_000_000.0, invested=0.0, target=600_000.0, phase="BOOTSTRAP",
      regime="RISK_ON", cycle_buys=0.0, class_buys=0.0, new_count=0,
      cycles=5, approved=True) -> RampPortfolio:
    return RampPortfolio(nav_eur=nav, invested_eur=invested,
                         strategic_target_invested_eur=target, phase=phase,
                         regime=regime, cycle_net_buys_eur=cycle_buys,
                         cycle_asset_class_net_buys_eur=class_buys,
                         cycle_new_positions=new_count,
                         completed_open_cycles_in_phase=cycles,
                         phase_human_approved=approved)


def H(reconciled=True, unrec=0, incidents=0, failed=0, stale=1.0,
      success=100.0, p95=10.0, reviews=0, dd=0.0, promote=True) -> RampHealth:
    return RampHealth(paper_fills_reconciled=reconciled,
                      unreconciled_paper_fills=unrec,
                      open_critical_incidents=incidents,
                      consecutive_failed_cycles=failed,
                      data_staleness_hours=stale,
                      agent_call_success_rate_pct=success,
                      router_p95_latency_seconds=p95,
                      unresolved_review_items=reviews,
                      drawdown_pct=dd,
                      phase_change_human_approved=promote)


def selftest() -> int:
    print("=" * 84)
    print("[STARTUP_RAMP_V1.0.1] autotest — montée progressive après Risk Gate")
    print("=" * 84)
    try:
        ramp = StartupRamp.from_file()
    except Exception as error:
        print("ERREUR politique : %r" % error)
        print("Placez startup_policy_v1.json dans le même dossier.")
        return 1
    failed: List[str] = []

    def ck(name: str, condition: bool, detail: str = "") -> None:
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC",
                                ("  " + detail) if detail and not condition else ""))
        if not condition:
            failed.append(name)

    ck("politique chargée et fingerprint stable", len(ramp.policy_hash) == 64)
    try:
        bad = copy.deepcopy(ramp.policy)
        bad["scope"]["broker_execution_enabled"] = True
        StartupRamp(bad)
        broker_rejected = False
    except StartupPolicyError:
        broker_rejected = True
    ck("politique broker=true refusée", broker_rejected)
    ck("Risk Gate REVIEW ne progresse pas", ramp.evaluate(Q(risk_status="RISK_REVIEW_REQUIRED"), P(), H()).status == RampStatus.RAMP_REJECTED)
    ck("Risk Gate REJECTED ne progresse pas", ramp.evaluate(Q(risk_status="RISK_REJECTED"), P(), H()).status == RampStatus.RAMP_REJECTED)
    ck("chemin nominal BOOTSTRAP approuvé", ramp.evaluate(Q(amount=5000), P(), H()).status == RampStatus.RAMP_APPROVED)

    outcome = ramp.evaluate(Q(amount=12000), P(), H())
    ck("BOOTSTRAP nouvelle ligne plafonnée à .5% NAV", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 5000) < .01, str(outcome.to_dict()))
    outcome = ramp.evaluate(Q(amount=25000, new=False), P(), H())
    ck("BOOTSTRAP ligne existante plafonnée à .5% NAV", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 5000) < .01)
    outcome = ramp.evaluate(Q(amount=5000), P(invested=89_000, target=600_000), H())
    ck("cap stratégique BOOTSTRAP 15% cible réduit à 1k", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 1000) < .01)
    # Ici la cible stratégique est volontairement supérieure au plafond absolu de 15% NAV.
    # Cela isole TOTAL_INVESTED_CAP sans que STRATEGIC_DEPLOYMENT_CAP ne soit le limitant.
    outcome = ramp.evaluate(Q(amount=5000), P(invested=149_000, target=2_000_000), H())
    ck("cap total investi BOOTSTRAP 15% NAV réduit à 1k", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 1000) < .01)
    outcome = ramp.evaluate(Q(amount=5000), P(cycle_buys=19_000), H())
    ck("budget achats cycle BOOTSTRAP réduit à 1k", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 1000) < .01)
    outcome = ramp.evaluate(Q(amount=5000), P(class_buys=9_500), H())
    ck("budget classe BOOTSTRAP réduit à .5k", outcome.status == RampStatus.RAMP_REDUCED and abs(outcome.approved_notional_eur - 500) < .01)

    ck("PAUSED bloque les achats", ramp.evaluate(Q(), P(phase="PAUSED"), H()).status == RampStatus.RAMP_PAUSED)
    ck("DE_RISK bloque les achats", ramp.evaluate(Q(), P(phase="DE_RISK"), H()).status == RampStatus.RAMP_PAUSED)
    ck("RISK_OFF bloque les achats", ramp.evaluate(Q(), P(regime="RISK_OFF"), H()).status == RampStatus.RAMP_PAUSED)
    ck("fill non réconcilié suspend", ramp.evaluate(Q(), P(), H(reconciled=False, unrec=1)).status == RampStatus.RAMP_PAUSED)
    ck("incident critique suspend", ramp.evaluate(Q(), P(), H(incidents=1)).status == RampStatus.RAMP_PAUSED)
    ck("données trop anciennes suspend", ramp.evaluate(Q(), P(), H(stale=25)).status == RampStatus.RAMP_PAUSED)
    ck("santé manquante -> revue fail closed", ramp.evaluate(Q(), P(), H(stale=None)).status == RampStatus.RAMP_REVIEW_REQUIRED)

    ck("nouvelle position sans approbation -> revue", ramp.evaluate(Q(), P(approved=False), H()).status == RampStatus.RAMP_REVIEW_REQUIRED)
    outcome = ramp.evaluate(Q(new=True), P(new_count=2), H())
    ck("quota nouvelles positions BOOTSTRAP atteint", outcome.status == RampStatus.RAMP_REJECTED and "NEW_POSITION_COUNT" in outcome.rejection_codes)
    ck("vente réductrice bypass ramp", ramp.evaluate(Q(side="SELL", amount=5000), P(phase="PAUSED"), H(reconciled=False, unrec=1)).status == RampStatus.RAMP_APPROVED)
    ck("montant Risk Gate nul rejeté", ramp.evaluate(Q(amount=0), P(), H()).status == RampStatus.RAMP_REJECTED)
    ck("phase inconnue devient PAUSED", ramp.evaluate(Q(), P(phase="mystery"), H()).status == RampStatus.RAMP_PAUSED)
    first = ramp.evaluate(Q(), P(), H()).to_dict()
    second = ramp.evaluate(Q(), P(), H()).to_dict()
    ck("décision Ramp déterministe", first == second)

    eligibility = ramp.promotion_eligibility(P(phase="BOOTSTRAP", cycles=5), H(promote=True))
    ck("BOOTSTRAP -> OBSERVE éligible avec santé saine", eligibility.eligible and eligibility.next_phase == "OBSERVE")
    eligibility = ramp.promotion_eligibility(P(phase="BOOTSTRAP", cycles=4), H(promote=True))
    ck("promotion bloquée si cycles insuffisants", not eligibility.eligible and "PHASE_MIN_CYCLES" in eligibility.blocking_codes)
    eligibility = ramp.promotion_eligibility(P(phase="BOOTSTRAP", cycles=5), H(promote=False))
    ck("promotion exige approbation humaine", not eligibility.eligible and "PHASE_HUMAN_APPROVAL" in eligibility.blocking_codes)
    eligibility = ramp.promotion_eligibility(P(phase="BOOTSTRAP", cycles=5, regime="RISK_OFF"), H(promote=True))
    ck("promotion interdite en RISK_OFF", not eligibility.eligible and "PROMOTION_REGIME" in eligibility.blocking_codes)
    eligibility = ramp.promotion_eligibility(P(phase="STEADY_STATE", cycles=30), H())
    ck("STEADY_STATE non promouvable", not eligibility.eligible and "ALREADY_TERMINAL_PHASE" in eligibility.blocking_codes)
    path = "startup_ramp_v1_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        StartupRampJournal(path).append(ramp.evaluate(Q(), P(), H()), source="selftest")
        with open(path, encoding="utf-8") as handle:
            row = json.loads(handle.readline())
        ck("journal JSONL relisible", row["kind"] == "startup_ramp_v1_outcome" and row["phase"] == "BOOTSTRAP")
    finally:
        if os.path.exists(path):
            os.remove(path)

    print()
    print("-" * 84)
    if failed:
        print("ÉCHECS : %d/30" % len(failed))
        for name in failed:
            print("  - %s" % name)
        return 1
    print("30/30 contrôles passent. Startup Ramp v1.0.1 prêt avant startup_phase_manager.py.")
    return 0


def demo() -> int:
    try:
        ramp = StartupRamp.from_file()
    except Exception as error:
        print("ERREUR politique : %r" % error)
        return 1
    print("=" * 84)
    print("[STARTUP_RAMP_V1.0.1] démonstration")
    print("=" * 84)
    cases = [
        ("Bootstrap nouveau AAPL", Q("AAPL", amount=5000, new=True), P(), H()),
        ("Bootstrap AAPL 12k", Q("AAPL", amount=12000, new=True), P(), H()),
        ("Budget cycle presque consommé", Q("JPM", amount=5000), P(cycle_buys=19_000), H()),
        ("Cible stratégique presque atteinte", Q("MS", amount=5000), P(invested=89_000, target=600_000), H()),
        ("Phase PAUSED", Q("AAPL", amount=5000), P(phase="PAUSED"), H()),
        ("Vente sous PAUSED", Q("AAPL", side="SELL", amount=5000, new=False), P(phase="PAUSED"), H(reconciled=False, unrec=1)),
        ("Santé inconnue", Q("AAPL", amount=5000), P(), H(p95=None)),
    ]
    for label, proposal, portfolio, health in cases:
        outcome = ramp.evaluate(proposal, portfolio, health)
        print("\n  %-32s %s" % (label, outcome.compact()))
        print("     " + outcome.reason)
        for reduction in outcome.reductions:
            print("     réduction : %(rule_id)s -> %(safe_notional_eur).2f€" % reduction)
    print("\n  --- éligibilité de promotion ---")
    for phase, cycles, approved in [("BOOTSTRAP", 5, True), ("OBSERVE", 10, True), ("RAMP_1", 14, True), ("STEADY_STATE", 25, True)]:
        eligibility = ramp.promotion_eligibility(P(phase=phase, cycles=cycles), H(promote=approved))
        print("  %-12s -> %-13s %-5s %s" % (
            eligibility.current_phase, eligibility.next_phase or "-",
            "OK" if eligibility.eligible else "BLOQUÉ", eligibility.reason))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Startup Ramp v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-policy", metavar="PATH")
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.validate_policy:
        try:
            policy = load_startup_policy(args.validate_policy)
            print("Politique valide : %s v%s" % (policy["policy_id"], policy["version"]))
            print("Fingerprint SHA-256 : %s" % policy_fingerprint(policy))
            return 0
        except StartupPolicyError as error:
            print("Politique invalide : %s" % error)
            return 1
    return selftest() if args.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
