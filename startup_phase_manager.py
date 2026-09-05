#!/usr/bin/env python3
# startup_phase_manager.py
# [STARTUP_PHASE_MANAGER_V1.0.1]
"""Gestionnaire de phases de démarrage THESIUM.

Rôle
----
Analyse l'état réel du portefeuille et recommande un palier de montée en charge.
Il ne crée pas d'ordre, ne modifie pas une phase persistée et ne fait aucun appel broker.

Pipeline
--------
portfolio_state / cycle_history / health
    -> startup_phase_manager (recommandation, éligibilité, motifs)
    -> approbation humaine explicite et persistée (composant ultérieur)
    -> startup_ramp (application des plafonds de la phase persistée)

Convention de cycle
-------------------
Un cycle correspond à UNE séance de marché validée et réconciliée, pas à 24 h.
Les week-ends, jours fériés, jours incomplets, jours avec données périmées,
incidents critiques ou fills non réconciliés ne sont jamais comptabilisés.

Usage
-----
    from startup_phase_manager import StartupPhaseManager

    manager = StartupPhaseManager.from_file("startup_policy_v1.json")
    assessment = manager.assess(portfolio, health, cycle_history)
    print(assessment.to_dict())

CLI
---
    py -3.13 startup_phase_manager.py --validate-policy startup_policy_v1.json
    py -3.13 startup_phase_manager.py --selftest
    py -3.13 startup_phase_manager.py --demo
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

try:
    from startup_ramp import RampHealth, StartupRamp, StartupPolicyError, load_startup_policy
except ImportError as exc:
    raise SystemExit(
        "startup_phase_manager.py requiert startup_ramp.py dans le même dossier : %s" % exc
    )


class PhaseAction(str, Enum):
    HOLD = "HOLD"
    REQUEST_PROMOTION = "REQUEST_PROMOTION"
    REQUEST_PAUSE = "REQUEST_PAUSE"
    REQUEST_DE_RISK = "REQUEST_DE_RISK"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class CycleRecord:
    """Une tentative de cycle quotidien; seul un record validé est comptabilisé."""
    cycle_id: str
    trading_date: str
    phase: str
    market_session_completed: Optional[bool]
    market_data_fresh: Optional[bool]
    pipeline_completed: Optional[bool]
    paper_fills_reconciled: Optional[bool]
    critical_incidents_open: Optional[int]
    status: str
    policy_version: str = ""


@dataclass(frozen=True)
class PhasePortfolioState:
    """État portfolio source de vérité, à alimenter plus tard par portfolio_state.py."""
    nav_eur: float
    cash_eur: float
    invested_eur: float
    strategic_target_invested_eur: float
    current_phase: str
    phase_started_at: str = ""
    regime: str = "RISK_ON"
    current_phase_human_approved: bool = False


@dataclass
class PhaseCheck:
    rule_id: str
    status: str
    severity: str
    message: str
    actual: Optional[float] = None
    expected: Optional[float] = None
    unit: str = ""


@dataclass
class PhaseAssessment:
    current_phase: str
    recommended_phase: str
    next_phase: Optional[str]
    action: PhaseAction
    reason: str
    deployment_pct_target: Optional[float]
    invested_pct_nav: Optional[float]
    cash_pct_nav: Optional[float]
    valid_cycles_in_current_phase: int
    required_cycles_for_next_phase: Optional[int]
    promotion_eligible: bool
    phase_change_requires_human_approval: bool
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    effective_regime: str
    checks: List[PhaseCheck] = field(default_factory=list)
    blocking_codes: List[str] = field(default_factory=list)
    warning_codes: List[str] = field(default_factory=list)
    valid_cycle_ids: List[str] = field(default_factory=list)
    invalid_cycle_reasons: Dict[str, List[str]] = field(default_factory=dict)
    input_snapshot_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["action"] = self.action.value
        return result

    def compact(self) -> str:
        pct = "n/a" if self.deployment_pct_target is None else "%.2f%%" % self.deployment_pct_target
        next_phase = self.next_phase or "-"
        return (
            "phase=%-12s recommandé=%-12s action=%-18s déploiement=%-8s cycles=%d next=%s"
            % (
                self.current_phase,
                self.recommended_phase,
                self.action.value,
                pct,
                self.valid_cycles_in_current_phase,
                next_phase,
            )
        )


def _finite(value: Any) -> Optional[float]:
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _fingerprint(policy: Mapping[str, Any]) -> str:
    raw = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _input_hash(portfolio: PhasePortfolioState, health: RampHealth,
                records: Sequence[CycleRecord]) -> str:
    raw = json.dumps(
        {
            "portfolio": asdict(portfolio),
            "health": asdict(health),
            "cycles": [asdict(record) for record in records],
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_phase_manager_policy(policy: Mapping[str, Any]) -> None:
    """Réutilise la validation Ramp et exige les garanties du manager."""
    StartupRamp(policy)
    change = policy.get("change_control", {})
    promotion = policy.get("promotion_protocol", {})
    if change.get("allow_automatic_phase_promotion") is not False:
        raise StartupPolicyError("Phase manager refuse la promotion automatique")
    if promotion.get("require_explicit_human_approval") is not True:
        raise StartupPolicyError("Phase manager exige une approbation humaine explicite")
    if promotion.get("forbid_skipping_phases") is not True:
        raise StartupPolicyError("Phase manager interdit le saut de phase")


def load_phase_manager_policy(path: str = "startup_policy_v1.json") -> Dict[str, Any]:
    policy = load_startup_policy(path)
    validate_phase_manager_policy(policy)
    return policy


class StartupPhaseManager:
    """Analyseur pur : il recommande, mais n'écrit ni ne change une phase."""

    def __init__(self, policy: Mapping[str, Any]):
        validate_phase_manager_policy(policy)
        self.policy = copy.deepcopy(dict(policy))
        self.policy_fingerprint = _fingerprint(self.policy)

    @classmethod
    def from_file(cls, path: str = "startup_policy_v1.json") -> "StartupPhaseManager":
        return cls(load_phase_manager_policy(path))

    def assess(
        self,
        portfolio: PhasePortfolioState,
        health: RampHealth,
        cycle_history: Sequence[CycleRecord],
    ) -> PhaseAssessment:
        """Analyse portefeuille, santé et séances valides.

        La phase recommandée peut être supérieure ou inférieure à la phase active.
        L'action de promotion, elle, ne concerne jamais que la phase immédiatement
        suivante. Une transition effective exige une approbation humaine persistée
        dans le futur portfolio_state.py.
        """
        current, phase_known = self._normalize_phase(portfolio.current_phase)
        regime = _upper(portfolio.regime)
        nav = _finite(portfolio.nav_eur)
        cash = _finite(portfolio.cash_eur)
        invested = _finite(portfolio.invested_eur)
        target = _finite(portfolio.strategic_target_invested_eur)
        records = list(cycle_history)
        checks: List[PhaseCheck] = []
        blocking: List[str] = []
        warnings: List[str] = []

        def check(
            rule_id: str,
            passed: bool,
            message: str,
            actual: Optional[float] = None,
            expected: Optional[float] = None,
            unit: str = "",
            severity: str = "HARD",
        ) -> None:
            status = "PASS" if passed else ("WARN" if severity == "REVIEW" else "FAIL")
            checks.append(PhaseCheck(rule_id, status, severity, message, actual, expected, unit))
            if not passed:
                if severity == "REVIEW":
                    warnings.append(rule_id)
                else:
                    blocking.append(rule_id)

        check(
            "CURRENT_PHASE_RECOGNIZED",
            phase_known,
            "La phase active est connue de la politique",
            severity="REVIEW",
        )
        check("NAV_VALID", nav is not None and nav > 0, "NAV présente et strictement positive", nav, 0.0, "EUR")
        check("CASH_VALID", cash is not None and cash >= 0, "Cash présent et non négatif", cash, 0.0, "EUR")
        check(
            "INVESTED_VALID",
            invested is not None and invested >= 0,
            "Montant investi présent et non négatif",
            invested,
            0.0,
            "EUR",
        )
        check(
            "STRATEGIC_TARGET_VALID",
            target is not None and target > 0,
            "Cible stratégique présente et strictement positive",
            target,
            0.0,
            "EUR",
        )

        deployment = None
        invested_pct = None
        cash_pct = None
        if nav is not None and nav > 0:
            if invested is not None:
                invested_pct = 100.0 * invested / nav
            if cash is not None:
                cash_pct = 100.0 * cash / nav
        if target is not None and target > 0 and invested is not None:
            deployment = 100.0 * invested / target

        if nav is not None and nav > 0 and cash is not None and invested is not None:
            difference = abs(nav - cash - invested)
            check(
                "NAV_CASH_INVESTED_RECONCILED",
                difference <= nav * 0.01,
                "NAV cohérente avec cash + investi à 1% NAV",
                difference,
                nav * 0.01,
                "EUR",
                severity="REVIEW",
            )

        valid_ids, invalid_reasons = self._valid_cycles_for_phase(records, current)
        valid_cycles = len(valid_ids)

        if blocking:
            return self._assessment(
                current=current,
                recommended="PAUSED",
                next_phase=self._next_phase(current),
                action=PhaseAction.REVIEW_REQUIRED,
                reason="Revue requise : " + "; ".join(self._labels(blocking)),
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=self._required_cycles(current),
                eligible=False,
                checks=checks,
                blocking=blocking,
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        if not phase_known:
            if "CURRENT_PHASE_RECOGNIZED" not in warnings:
                warnings.append("CURRENT_PHASE_RECOGNIZED")
            return self._assessment(
                current=current,
                recommended="PAUSED",
                next_phase=None,
                action=PhaseAction.REVIEW_REQUIRED,
                reason="Revue requise : phase portefeuille inconnue",
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=None,
                eligible=False,
                checks=checks,
                blocking=[],
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        safety_action, safety_code, safety_message = self._safety_action(health, regime)
        if safety_action is not None:
            checks.append(PhaseCheck(safety_code, "FAIL", "HARD", safety_message))
            recommended = "DE_RISK" if safety_action == PhaseAction.REQUEST_DE_RISK else "PAUSED"
            return self._assessment(
                current=current,
                recommended=recommended,
                next_phase=None,
                action=safety_action,
                reason=safety_message,
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=self._required_cycles(current),
                eligible=False,
                checks=checks,
                blocking=[safety_code],
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        health_missing = self._missing_health_fields(health)
        if health_missing:
            for code in health_missing:
                checks.append(PhaseCheck(code, "WARN", "REVIEW", self._labels([code])[0]))
            warnings.extend(health_missing)
            return self._assessment(
                current=current,
                recommended=current,
                next_phase=self._next_phase(current),
                action=PhaseAction.REVIEW_REQUIRED,
                reason="Revue requise : " + "; ".join(self._labels(health_missing)),
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=self._required_cycles(current),
                eligible=False,
                checks=checks,
                blocking=[],
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        recommended = self._phase_from_deployment(deployment)
        next_phase = self._next_phase(current)
        required_cycles = self._required_cycles(current)

        if self._phase_index(recommended) < self._phase_index(current):
            checks.append(
                PhaseCheck(
                    "DEPLOYMENT_BELOW_CURRENT_PHASE_BAND",
                    "WARN",
                    "REVIEW",
                    "Déploiement sous la bande de la phase active : conserver la phase, revoir la cause",
                    deployment,
                    self._phase_floor(current),
                    "%",
                )
            )
            warnings.append("DEPLOYMENT_BELOW_CURRENT_PHASE_BAND")
            return self._assessment(
                current=current,
                recommended=recommended,
                next_phase=next_phase,
                action=PhaseAction.REVIEW_REQUIRED,
                reason="Revue requise : déploiement sous la bande du palier actif",
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=required_cycles,
                eligible=False,
                checks=checks,
                blocking=[],
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        if next_phase is None:
            checks.append(PhaseCheck("TERMINAL_PHASE", "PASS", "INFO", "STEADY_STATE est la phase terminale"))
            return self._assessment(
                current=current,
                recommended=recommended,
                next_phase=None,
                action=PhaseAction.HOLD,
                reason="Maintien : phase terminale STEADY_STATE",
                deployment=deployment,
                invested_pct=invested_pct,
                cash_pct=cash_pct,
                valid_cycles=valid_cycles,
                required_cycles=None,
                eligible=False,
                checks=checks,
                blocking=[],
                warnings=warnings,
                valid_ids=valid_ids,
                invalid_reasons=invalid_reasons,
                regime=regime,
                portfolio=portfolio,
                health=health,
                records=records,
            )

        next_floor = self._phase_floor(next_phase)
        deployment_ready = deployment is not None and deployment >= next_floor
        cycles_ready = valid_cycles >= required_cycles
        allowed_regimes = set(self.policy["health_gates_for_promotion"]["regimes_allowed_for_promotion"])
        regime_allowed = regime in allowed_regimes
        human_protocol = bool(self.policy["promotion_protocol"]["require_explicit_human_approval"])

        checks.append(
            PhaseCheck(
                "NEXT_PHASE_DEPLOYMENT_THRESHOLD",
                "PASS" if deployment_ready else "FAIL",
                "HARD",
                "Déploiement minimal pour le palier suivant",
                deployment,
                next_floor,
                "%",
            )
        )
        checks.append(
            PhaseCheck(
                "CURRENT_PHASE_VALID_CYCLES",
                "PASS" if cycles_ready else "FAIL",
                "HARD",
                "Séances valides requises dans la phase active",
                valid_cycles,
                required_cycles,
                "cycles",
            )
        )
        checks.append(
            PhaseCheck(
                "PROMOTION_REGIME",
                "PASS" if regime_allowed else "FAIL",
                "HARD",
                "Régime autorisé pour une promotion",
            )
        )
        checks.append(
            PhaseCheck(
                "HUMAN_APPROVAL_REQUIRED",
                "PASS" if human_protocol else "FAIL",
                "HARD",
                "La promotion doit être approuvée et persistée par un humain",
            )
        )

        promotion_eligible = deployment_ready and cycles_ready and regime_allowed and human_protocol
        if promotion_eligible:
            action = PhaseAction.REQUEST_PROMOTION
            reason = "Promotion proposée : %s -> %s; approbation humaine explicite requise" % (
                current,
                next_phase,
            )
        else:
            action = PhaseAction.HOLD
            reason = "Maintien : " + "; ".join(
                self._promotion_blockers(deployment_ready, cycles_ready, regime_allowed, human_protocol)
            )

        blocker_codes = [] if promotion_eligible else self._promotion_blocker_codes(
            deployment_ready,
            cycles_ready,
            regime_allowed,
            human_protocol,
        )
        return self._assessment(
            current=current,
            recommended=recommended,
            next_phase=next_phase,
            action=action,
            reason=reason,
            deployment=deployment,
            invested_pct=invested_pct,
            cash_pct=cash_pct,
            valid_cycles=valid_cycles,
            required_cycles=required_cycles,
            eligible=promotion_eligible,
            checks=checks,
            blocking=blocker_codes,
            warnings=warnings,
            valid_ids=valid_ids,
            invalid_reasons=invalid_reasons,
            regime=regime,
            portfolio=portfolio,
            health=health,
            records=records,
        )

    def is_valid_cycle(self, record: CycleRecord, phase: str) -> Tuple[bool, List[str]]:
        """Retourne si une séance compte pour une phase et les motifs sinon."""
        reasons: List[str] = []
        if _upper(record.phase) != phase:
            reasons.append("CYCLE_WRONG_PHASE")
        if record.market_session_completed is not True:
            reasons.append("CYCLE_MARKET_SESSION_INCOMPLETE")
        if record.market_data_fresh is not True:
            reasons.append("CYCLE_DATA_NOT_FRESH")
        if record.pipeline_completed is not True:
            reasons.append("CYCLE_PIPELINE_INCOMPLETE")
        if record.paper_fills_reconciled is not True:
            reasons.append("CYCLE_FILLS_NOT_RECONCILED")
        incidents = _finite(record.critical_incidents_open)
        if incidents is None:
            reasons.append("CYCLE_INCIDENT_DATA_MISSING")
        elif incidents > 0:
            reasons.append("CYCLE_CRITICAL_INCIDENT")
        if _upper(record.status) != "COMPLETED":
            reasons.append("CYCLE_STATUS_NOT_COMPLETED")
        if not str(record.cycle_id).strip():
            reasons.append("CYCLE_ID_MISSING")
        if not str(record.trading_date).strip():
            reasons.append("CYCLE_DATE_MISSING")
        return not reasons, reasons

    def _valid_cycles_for_phase(
        self,
        records: Sequence[CycleRecord],
        phase: str,
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        valid: List[str] = []
        invalid: Dict[str, List[str]] = {}
        seen: set[str] = set()
        for record in records:
            key = str(record.cycle_id).strip() or "<missing-%d>" % (len(invalid) + len(valid) + 1)
            if key in seen:
                invalid[key] = ["CYCLE_ID_DUPLICATE"]
                continue
            seen.add(key)
            is_valid, reasons = self.is_valid_cycle(record, phase)
            if is_valid:
                valid.append(key)
            else:
                invalid[key] = reasons
        return valid, invalid

    def _normalize_phase(self, raw: str) -> Tuple[str, bool]:
        phase = _upper(raw)
        return (phase, True) if phase in self.policy["phases"] else ("PAUSED", False)

    def _next_phase(self, current: str) -> Optional[str]:
        order = list(self.policy["phase_order"])
        if current not in order:
            return None
        index = order.index(current)
        return order[index + 1] if index + 1 < len(order) else None

    def _phase_index(self, phase: str) -> int:
        order = list(self.policy["phase_order"])
        return order.index(phase) if phase in order else -1

    def _phase_floor(self, phase: str) -> float:
        """Bande basse d'une phase, dérivée du plafond de la phase précédente."""
        order = list(self.policy["phase_order"])
        if phase not in order:
            return 0.0
        index = order.index(phase)
        if index == 0:
            return 0.0
        previous = self.policy["phases"][order[index - 1]]
        return float(previous["max_deployed_pct_of_strategic_target"])

    def _phase_from_deployment(self, deployment: Optional[float]) -> str:
        if deployment is None or deployment < 0:
            return "BOOTSTRAP"
        selected = self.policy["phase_order"][0]
        for phase in self.policy["phase_order"]:
            if deployment >= self._phase_floor(phase):
                selected = phase
        return selected

    def _required_cycles(self, current: str) -> Optional[int]:
        if current not in self.policy["phase_order"]:
            return None
        return int(self.policy["phases"][current]["min_completed_open_cycles"])

    def _safety_action(
        self,
        health: RampHealth,
        regime: str,
    ) -> Tuple[Optional[PhaseAction], str, str]:
        drawdown = _finite(health.drawdown_pct)
        if drawdown is not None and drawdown >= 12.0:
            return (
                PhaseAction.REQUEST_DE_RISK,
                "DRAWDOWN_HALT",
                "Réduction de risque demandée : drawdown au seuil halt",
            )
        if drawdown is not None and drawdown >= 8.0:
            return (
                PhaseAction.REQUEST_PAUSE,
                "DRAWDOWN_CRITICAL",
                "Pause demandée : drawdown critique",
            )
        if regime in ("RISK_OFF", "UNKNOWN"):
            return (
                PhaseAction.REQUEST_PAUSE,
                "REGIME_PAUSE",
                "Pause demandée : régime défensif ou inconnu",
            )
        if health.paper_fills_reconciled is False:
            return (
                PhaseAction.REQUEST_PAUSE,
                "PAPER_FILLS_NOT_RECONCILED",
                "Pause demandée : fills paper non réconciliés",
            )

        field_rules = [
            ("unreconciled_paper_fills", "UNRECONCILED_PAPER_FILLS", "fills non réconciliés", "max_unreconciled_paper_fills"),
            ("open_critical_incidents", "OPEN_CRITICAL_INCIDENTS", "incident critique ouvert", "max_open_critical_incidents"),
            ("consecutive_failed_cycles", "CONSECUTIVE_FAILED_CYCLES", "cycle échoué consécutif", "max_consecutive_failed_cycles"),
            ("data_staleness_hours", "DATA_STALENESS", "données trop anciennes", "max_recent_data_staleness_hours"),
        ]
        for field, code, label, gate_key in field_rules:
            value = _finite(getattr(health, field))
            if value is None:
                continue
            if value > float(self.policy["health_gates_for_promotion"][gate_key]):
                return PhaseAction.REQUEST_PAUSE, code, "Pause demandée : " + label
        return None, "", ""

    @staticmethod
    def _missing_health_fields(health: RampHealth) -> List[str]:
        required = [
            ("paper_fills_reconciled", "PAPER_FILLS_RECONCILED_MISSING"),
            ("unreconciled_paper_fills", "UNRECONCILED_PAPER_FILLS_MISSING"),
            ("open_critical_incidents", "OPEN_CRITICAL_INCIDENTS_MISSING"),
            ("consecutive_failed_cycles", "CONSECUTIVE_FAILED_CYCLES_MISSING"),
            ("data_staleness_hours", "DATA_STALENESS_MISSING"),
            ("agent_call_success_rate_pct", "AGENT_SUCCESS_RATE_MISSING"),
            ("router_p95_latency_seconds", "ROUTER_P95_MISSING"),
            ("unresolved_review_items", "UNRESOLVED_REVIEW_ITEMS_MISSING"),
            ("drawdown_pct", "DRAWDOWN_MISSING"),
        ]
        missing: List[str] = []
        for field, code in required:
            value = getattr(health, field)
            if isinstance(value, bool):
                continue
            if value is None or _finite(value) is None:
                missing.append(code)
        return missing

    @staticmethod
    def _promotion_blocker_codes(deployment: bool, cycles: bool, regime: bool, human: bool) -> List[str]:
        codes: List[str] = []
        if not deployment:
            codes.append("NEXT_PHASE_DEPLOYMENT_THRESHOLD")
        if not cycles:
            codes.append("CURRENT_PHASE_VALID_CYCLES")
        if not regime:
            codes.append("PROMOTION_REGIME")
        if not human:
            codes.append("HUMAN_APPROVAL_REQUIRED")
        return codes

    @staticmethod
    def _promotion_blockers(deployment: bool, cycles: bool, regime: bool, human: bool) -> List[str]:
        labels: List[str] = []
        if not deployment:
            labels.append("seuil de déploiement du palier suivant non atteint")
        if not cycles:
            labels.append("nombre de séances valides insuffisant")
        if not regime:
            labels.append("régime incompatible avec une promotion")
        if not human:
            labels.append("protocole d'approbation humaine invalide")
        return labels

    @staticmethod
    def _labels(codes: Iterable[str]) -> List[str]:
        mapping = {
            "CURRENT_PHASE_RECOGNIZED": "phase active inconnue",
            "NAV_VALID": "NAV absente ou invalide",
            "CASH_VALID": "cash absent ou invalide",
            "INVESTED_VALID": "montant investi absent ou invalide",
            "STRATEGIC_TARGET_VALID": "cible stratégique absente ou invalide",
            "NAV_CASH_INVESTED_RECONCILED": "NAV incohérente avec cash + investi",
            "PAPER_FILLS_RECONCILED_MISSING": "réconciliation paper inconnue",
            "UNRECONCILED_PAPER_FILLS_MISSING": "nombre de fills non réconciliés absent",
            "OPEN_CRITICAL_INCIDENTS_MISSING": "nombre d'incidents critiques absent",
            "CONSECUTIVE_FAILED_CYCLES_MISSING": "nombre de cycles échoués absent",
            "DATA_STALENESS_MISSING": "fraîcheur des données inconnue",
            "AGENT_SUCCESS_RATE_MISSING": "taux de succès agents inconnu",
            "ROUTER_P95_MISSING": "p95 routeur inconnu",
            "UNRESOLVED_REVIEW_ITEMS_MISSING": "éléments de revue inconnus",
            "DRAWDOWN_MISSING": "drawdown inconnu",
        }
        return [mapping.get(code, code) for code in codes]

    def _assessment(
        self,
        current: str,
        recommended: str,
        next_phase: Optional[str],
        action: PhaseAction,
        reason: str,
        deployment: Optional[float],
        invested_pct: Optional[float],
        cash_pct: Optional[float],
        valid_cycles: int,
        required_cycles: Optional[int],
        eligible: bool,
        checks: List[PhaseCheck],
        blocking: List[str],
        warnings: List[str],
        valid_ids: List[str],
        invalid_reasons: Dict[str, List[str]],
        regime: str,
        portfolio: PhasePortfolioState,
        health: RampHealth,
        records: Sequence[CycleRecord],
    ) -> PhaseAssessment:
        return PhaseAssessment(
            current_phase=current,
            recommended_phase=recommended,
            next_phase=next_phase,
            action=action,
            reason=reason,
            deployment_pct_target=None if deployment is None else round(deployment, 4),
            invested_pct_nav=None if invested_pct is None else round(invested_pct, 4),
            cash_pct_nav=None if cash_pct is None else round(cash_pct, 4),
            valid_cycles_in_current_phase=valid_cycles,
            required_cycles_for_next_phase=required_cycles,
            promotion_eligible=eligible,
            phase_change_requires_human_approval=True,
            policy_id=str(self.policy["policy_id"]),
            policy_version=str(self.policy["version"]),
            policy_fingerprint=self.policy_fingerprint,
            effective_regime=regime,
            checks=checks,
            blocking_codes=sorted(set(blocking)),
            warning_codes=sorted(set(warnings)),
            valid_cycle_ids=valid_ids,
            invalid_cycle_reasons=invalid_reasons,
            input_snapshot_hash=_input_hash(portfolio, health, records),
        )


class StartupPhaseJournal:
    """Journal append-only; la persistance de phase est hors de ce module."""

    def __init__(self, path: str):
        self.path = path
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

    def append(self, assessment: PhaseAssessment, source: str = "live") -> None:
        row = {
            "kind": "startup_phase_manager_v1_assessment",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            **assessment.to_dict(),
        }
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def H(
    reconciled=True,
    unrec=0,
    incidents=0,
    failed=0,
    stale=1.0,
    success=100.0,
    p95=10.0,
    reviews=0,
    dd=0.0,
    promote=None,
) -> RampHealth:
    return RampHealth(
        paper_fills_reconciled=reconciled,
        unreconciled_paper_fills=unrec,
        open_critical_incidents=incidents,
        consecutive_failed_cycles=failed,
        data_staleness_hours=stale,
        agent_call_success_rate_pct=success,
        router_p95_latency_seconds=p95,
        unresolved_review_items=reviews,
        drawdown_pct=dd,
        phase_change_human_approved=promote,
    )


def P(
    nav=1_000_000.0,
    cash=1_000_000.0,
    invested=0.0,
    target=600_000.0,
    phase="BOOTSTRAP",
    regime="RISK_ON",
    approved=True,
) -> PhasePortfolioState:
    return PhasePortfolioState(
        nav_eur=nav,
        cash_eur=cash,
        invested_eur=invested,
        strategic_target_invested_eur=target,
        current_phase=phase,
        phase_started_at="2026-09-01T08:00:00+00:00",
        regime=regime,
        current_phase_human_approved=approved,
    )


def C(cycle_id: str, phase="BOOTSTRAP", valid=True, date="2026-09-01") -> CycleRecord:
    return CycleRecord(
        cycle_id=cycle_id,
        trading_date=date,
        phase=phase,
        market_session_completed=valid,
        market_data_fresh=valid,
        pipeline_completed=valid,
        paper_fills_reconciled=valid,
        critical_incidents_open=0 if valid else 1,
        status="COMPLETED" if valid else "FAILED",
        policy_version="1.0.0",
    )


def cycles(count: int, phase="BOOTSTRAP", valid=True) -> List[CycleRecord]:
    return [
        C(
            "%s-%02d" % (phase, index + 1),
            phase=phase,
            valid=valid,
            date="2026-09-%02d" % (index + 1),
        )
        for index in range(count)
    ]


def selftest() -> int:
    print("=" * 84)
    print("[STARTUP_PHASE_MANAGER_V1.0.1] autotest — analyse de palier quotidienne")
    print("=" * 84)
    try:
        manager = StartupPhaseManager.from_file()
    except Exception as error:
        print("ERREUR politique : %r" % error)
        print("Placez startup_policy_v1.json et startup_ramp.py dans le même dossier.")
        return 1

    failed: List[str] = []

    def ck(name: str, condition: bool, detail: str = "") -> None:
        suffix = ("  " + detail) if detail and not condition else ""
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", suffix))
        if not condition:
            failed.append(name)

    ck("politique chargée et fingerprint présent", len(manager.policy_fingerprint) == 64)
    try:
        invalid = copy.deepcopy(manager.policy)
        invalid["change_control"]["allow_automatic_phase_promotion"] = True
        StartupPhaseManager(invalid)
        rejected = False
    except StartupPolicyError:
        rejected = True
    ck("politique promotion automatique refusée", rejected)

    result = manager.assess(P(), H(), [])
    ck("lancement 100% cash recommandé BOOTSTRAP", result.recommended_phase == "BOOTSTRAP")
    ck("lancement 100% cash reste HOLD", result.action == PhaseAction.HOLD)
    ck("lancement déploiement 0%", result.deployment_pct_target == 0.0)

    result = manager.assess(P(cash=880_000, invested=120_000), H(), cycles(5))
    ck("20% cible recommande OBSERVE", result.recommended_phase == "OBSERVE")
    ck(
        "BOOTSTRAP 20% cible propose OBSERVE",
        result.action == PhaseAction.REQUEST_PROMOTION and result.next_phase == "OBSERVE",
    )
    result = manager.assess(P(cash=760_000, invested=240_000), H(), cycles(5))
    ck("40% cible recommande RAMP_1", result.recommended_phase == "RAMP_1")
    ck(
        "pas de saut : BOOTSTRAP demande seulement OBSERVE",
        result.action == PhaseAction.REQUEST_PROMOTION and result.next_phase == "OBSERVE",
    )
    result = manager.assess(
        P(cash=610_000, invested=390_000, phase="RAMP_1"),
        H(),
        cycles(15, "RAMP_1"),
    )
    ck("65% cible recommande RAMP_2", result.recommended_phase == "RAMP_2")
    ck(
        "RAMP_1 15 séances demande RAMP_2",
        result.action == PhaseAction.REQUEST_PROMOTION and result.next_phase == "RAMP_2",
    )
    result = manager.assess(
        P(cash=520_000, invested=480_000, phase="RAMP_2"),
        H(),
        cycles(20, "RAMP_2"),
    )
    ck("80% cible recommande STEADY_STATE", result.recommended_phase == "STEADY_STATE")
    ck(
        "RAMP_2 demande STEADY_STATE",
        result.action == PhaseAction.REQUEST_PROMOTION and result.next_phase == "STEADY_STATE",
    )

    valid, reasons = manager.is_valid_cycle(C("good"), "BOOTSTRAP")
    ck("séance complète et réconciliée compte comme cycle", valid and not reasons)
    valid, reasons = manager.is_valid_cycle(C("weekend", valid=False), "BOOTSTRAP")
    ck("cycle incomplet ne compte pas", not valid and "CYCLE_MARKET_SESSION_INCOMPLETE" in reasons)
    bad = C("freshness", valid=True)
    bad = CycleRecord(**{**asdict(bad), "market_data_fresh": False})
    valid, reasons = manager.is_valid_cycle(bad, "BOOTSTRAP")
    ck("données périmées ne comptent pas", not valid and "CYCLE_DATA_NOT_FRESH" in reasons)
    bad = C("reconciliation", valid=True)
    bad = CycleRecord(**{**asdict(bad), "paper_fills_reconciled": False})
    valid, reasons = manager.is_valid_cycle(bad, "BOOTSTRAP")
    ck("fills non réconciliés ne comptent pas", not valid and "CYCLE_FILLS_NOT_RECONCILED" in reasons)
    valid, reasons = manager.is_valid_cycle(C("other-phase", phase="OBSERVE"), "BOOTSTRAP")
    ck("cycle d'une autre phase ne compte pas", not valid and "CYCLE_WRONG_PHASE" in reasons)

    # Correctif v1.0.1 : 80k / 600k = 13,33%, donc strictement sous le seuil OBSERVE de 15%.
    result = manager.assess(P(cash=920_000, invested=80_000), H(), cycles(5))
    ck(
        "déploiement sous 15% ne promeut pas",
        result.action == PhaseAction.HOLD
        and not result.promotion_eligible
        and result.recommended_phase == "BOOTSTRAP",
        str(result.to_dict()),
    )
    result = manager.assess(P(cash=880_000, invested=120_000), H(), cycles(4))
    ck(
        "4 cycles ne promeuvent pas BOOTSTRAP",
        result.action == PhaseAction.HOLD and "CURRENT_PHASE_VALID_CYCLES" in result.blocking_codes,
    )
    result = manager.assess(P(cash=880_000, invested=120_000, regime="RISK_OFF"), H(), cycles(5))
    ck(
        "RISK_OFF demande PAUSED",
        result.action == PhaseAction.REQUEST_PAUSE and result.recommended_phase == "PAUSED",
    )
    result = manager.assess(P(cash=880_000, invested=120_000), H(dd=8.0), cycles(5))
    ck(
        "drawdown critique demande PAUSED",
        result.action == PhaseAction.REQUEST_PAUSE and result.recommended_phase == "PAUSED",
    )
    result = manager.assess(P(cash=880_000, invested=120_000), H(dd=12.0), cycles(5))
    ck(
        "drawdown halt demande DE_RISK",
        result.action == PhaseAction.REQUEST_DE_RISK and result.recommended_phase == "DE_RISK",
    )
    result = manager.assess(P(cash=880_000, invested=120_000), H(reconciled=False, unrec=1), cycles(5))
    ck("fills non réconciliés demandent PAUSED", result.action == PhaseAction.REQUEST_PAUSE)
    result = manager.assess(P(cash=880_000, invested=120_000), H(p95=None), cycles(5))
    ck(
        "santé manquante demande revue",
        result.action == PhaseAction.REVIEW_REQUIRED and "ROUTER_P95_MISSING" in result.warning_codes,
    )

    result = manager.assess(P(cash=990_000, invested=10_000, phase="RAMP_1"), H(), cycles(15, "RAMP_1"))
    ck(
        "déploiement inférieur à phase active demande revue",
        result.action == PhaseAction.REVIEW_REQUIRED and result.recommended_phase == "BOOTSTRAP",
    )
    result = manager.assess(P(cash=880_000, invested=120_000, phase="unknown"), H(), cycles(5))
    ck(
        "phase inconnue demande revue",
        result.action == PhaseAction.REVIEW_REQUIRED and result.current_phase == "PAUSED",
    )
    result = manager.assess(P(nav=0), H(), [])
    ck(
        "NAV invalide demande revue",
        result.action == PhaseAction.REVIEW_REQUIRED and "NAV_VALID" in result.blocking_codes,
    )

    # Correctif v1.0.1 : 480k / 600k = 80%, conforme à la bande STEADY_STATE (>= 75%).
    result = manager.assess(
        P(cash=520_000, invested=480_000, phase="STEADY_STATE"),
        H(),
        cycles(30, "STEADY_STATE"),
    )
    ck(
        "STEADY_STATE reste HOLD",
        result.action == PhaseAction.HOLD
        and result.next_phase is None
        and result.recommended_phase == "STEADY_STATE",
        str(result.to_dict()),
    )

    first = manager.assess(P(cash=880_000, invested=120_000), H(), cycles(5)).to_dict()
    second = manager.assess(P(cash=880_000, invested=120_000), H(), cycles(5)).to_dict()
    ck("évaluation déterministe", first == second)

    path = "startup_phase_manager_v1_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        StartupPhaseJournal(path).append(manager.assess(P(), H(), []), source="selftest")
        with open(path, encoding="utf-8") as handle:
            row = json.loads(handle.readline())
        ck("journal JSONL relisible", row["kind"] == "startup_phase_manager_v1_assessment")
    finally:
        if os.path.exists(path):
            os.remove(path)

    print()
    print("-" * 84)
    if failed:
        print("ÉCHECS : %d/28" % len(failed))
        for name in failed:
            print("  - %s" % name)
        return 1
    print("28/28 contrôles passent. Startup Phase Manager v1.0.1 prêt avant portfolio_state.py.")
    return 0


def demo() -> int:
    try:
        manager = StartupPhaseManager.from_file()
    except Exception as error:
        print("ERREUR politique : %r" % error)
        return 1

    print("=" * 84)
    print("[STARTUP_PHASE_MANAGER_V1.0.1] démonstration")
    print("=" * 84)
    cases = [
        ("Lancement, 100% cash", P(), H(), []),
        ("20% cible, 5 séances", P(cash=880_000, invested=120_000), H(), cycles(5)),
        ("40% cible, aucun saut", P(cash=760_000, invested=240_000), H(), cycles(5)),
        (
            "65% cible, RAMP_1",
            P(cash=610_000, invested=390_000, phase="RAMP_1"),
            H(),
            cycles(15, "RAMP_1"),
        ),
        ("Sous 15% de cible", P(cash=920_000, invested=80_000), H(), cycles(5)),
        ("RISK_OFF", P(cash=880_000, invested=120_000, regime="RISK_OFF"), H(), cycles(5)),
        ("Drawdown halt", P(cash=880_000, invested=120_000), H(dd=12.0), cycles(5)),
        ("p95 routeur absente", P(cash=880_000, invested=120_000), H(p95=None), cycles(5)),
        (
            "STEADY_STATE cohérent",
            P(cash=520_000, invested=480_000, phase="STEADY_STATE"),
            H(),
            cycles(30, "STEADY_STATE"),
        ),
    ]

    for label, portfolio, health, history in cases:
        result = manager.assess(portfolio, health, history)
        print("\n  %-28s %s" % (label, result.compact()))
        print("     " + result.reason)
        if result.blocking_codes:
            print("     blocages : " + ", ".join(result.blocking_codes))
        if result.warning_codes:
            print("     revues   : " + ", ".join(result.warning_codes))
        print(
            "     cycles valides : %d; cycles rejetés : %d"
            % (result.valid_cycles_in_current_phase, len(result.invalid_cycle_reasons))
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Startup Phase Manager v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate-policy", metavar="PATH")
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    args = parser.parse_args()

    if args.validate_policy:
        try:
            policy = load_phase_manager_policy(args.validate_policy)
            print("Politique valide : %s v%s" % (policy["policy_id"], policy["version"]))
            print("Fingerprint SHA-256 : %s" % _fingerprint(policy))
            return 0
        except StartupPolicyError as error:
            print("Politique invalide : %s" % error)
            return 1

    return selftest() if args.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
