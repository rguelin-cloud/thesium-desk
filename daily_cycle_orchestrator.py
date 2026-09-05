#!/usr/bin/env python3
# daily_cycle_orchestrator.py
# [DAILY_CYCLE_ORCHESTRATOR_V1.1.1]
"""Orchestrateur quotidien paper-only THESIUM.

Rôle
----
Coordonne un cycle de marché quotidien déterministe et audit-able :
- charge PortfolioState SQLite ;
- contrôle les préconditions de santé et de données ;
- évalue StartupPhaseManager ;
- classe les propositions Risk Gate via ProposalRanker ;
- applique StartupRamp dans cet ordre ;
- persiste évaluation, classement et résultat de cycle.

Ce module ne lance aucun agent, ne crée aucun ordre, aucun fill et ne se connecte
à aucun broker. Ses sorties sont uniquement des intentions paper-only.

Pré-requis
----------
- startup_policy_v1.json
- startup_ramp.py
- startup_phase_manager.py
- portfolio_state.py
- proposal_ranker.py

CLI
---
    py -3.13 daily_cycle_orchestrator.py --selftest
    py -3.13 daily_cycle_orchestrator.py --demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence

try:
    from portfolio_state import MarketCycleInput, PortfolioSnapshotInput, PortfolioStateStore
    from startup_phase_manager import PhaseAction, PhaseAssessment, PhasePortfolioState, StartupPhaseManager
    from startup_ramp import RampHealth, RampOutcome, RampPortfolio, RiskApprovedProposal, StartupRamp
    from proposal_ranker import ProposalRanker, RankableProposal, RankedProposal
except ImportError as exc:
    raise SystemExit("Dépendance THESIUM absente dans le dossier courant : %s" % exc)


class CycleRunStatus(str, Enum):
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CycleContext:
    cycle_id: str
    trading_date: str
    market_session_completed: Optional[bool]
    market_data_fresh: Optional[bool]
    pipeline_completed: Optional[bool]
    paper_fills_reconciled: Optional[bool]
    critical_incidents_open: Optional[int]
    regime: str
    health: RampHealth
    source: str = "daily_orchestrator"
    policy_path: str = "startup_policy_v1.json"
    strategic_target_invested_eur: Optional[float] = None
    cycle_net_buys_eur: float = 0.0
    cycle_asset_class_net_buys_eur: Mapping[str, float] = field(default_factory=dict)
    cycle_new_positions: int = 0
    notes: str = ""


@dataclass(frozen=True)
class CycleProposal:
    """Proposition issue de Risk Gate ; aucune instruction d'exécution."""
    ticker: str
    side: str
    risk_status: str
    risk_approved_notional_eur: float
    asset_class: str
    is_new_position: bool
    proposal_id: str = ""
    conviction: str = "NORMAL"
    consensus_score: Optional[float] = None
    liquidity_score: Optional[float] = None
    urgency_score: Optional[float] = None
    is_risk_reducing: bool = False
    is_concentration_reduction: bool = False
    forced_exit_reason: str = ""
    decision_gate_status: str = "READY_FOR_SIZING"
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class ProposalResult:
    proposal_id: str
    rank: int
    bucket: str
    ranking_score: float
    ranking_reasons: List[str]
    ranking_warnings: List[str]
    ticker: str
    side: str
    risk_status: str
    risk_approved_notional_eur: float
    ramp_status: str
    ramp_approved_notional_eur: float
    reason: str
    rejection_codes: List[str] = field(default_factory=list)
    review_codes: List[str] = field(default_factory=list)
    pause_codes: List[str] = field(default_factory=list)
    reductions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CycleRunResult:
    cycle_id: str
    trading_date: str
    status: CycleRunStatus
    reason: str
    current_phase: str
    phase_assessment_id: Optional[str]
    phase_action: Optional[str]
    ranking_input_hash: Optional[str]
    ranker_version: str
    ramp_results: List[ProposalResult]
    approved_total_eur: float
    proposed_total_eur: float
    persisted_cycle: bool
    transition_request_recommended: bool
    transition_target_phase: Optional[str]
    input_hash: str
    started_at: str
    completed_at: str
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result

    def compact(self) -> str:
        return (
            "cycle=%s status=%-16s phase=%-12s proposed=%9.2f€ approved=%9.2f€ %s"
            % (
                self.cycle_id,
                self.status.value,
                self.current_phase,
                self.proposed_total_eur,
                self.approved_total_eur,
                self.reason,
            )
        )


class DailyCycleOrchestrator:
    """Coordonne un cycle sans effet broker et persiste le résultat dans SQLite."""

    VERSION = "DAILY_CYCLE_ORCHESTRATOR_V1.1.1"

    def __init__(self, store: PortfolioStateStore, policy_path: str = "startup_policy_v1.json"):
        self.store = store
        self.policy_path = policy_path
        self.phase_manager = StartupPhaseManager.from_file(policy_path)
        self.ramp = StartupRamp.from_file(policy_path)
        self.ranker = ProposalRanker()

    def run(self, context: CycleContext, proposals: Sequence[CycleProposal]) -> CycleRunResult:
        """Exécute un cycle logique unique, sans ordre ni appel broker.

        Les propositions sont classées avant Ramp. Les éléments classés
        INELIGIBLE_OR_REVIEW ne traversent pas Startup Ramp et ne consomment aucun
        budget de phase ou de cycle.
        """
        started = _utc_now()
        input_hash = _hash({"context": context, "proposals": list(proposals), "version": self.VERSION})
        self.store.initialize()

        try:
            self._validate_context(context)
            current = self.store.get_current_portfolio_state()

            if current.nav_eur is None or current.cash_eur is None or current.invested_eur is None:
                return self._finish_non_completed(
                    context=context,
                    started=started,
                    input_hash=input_hash,
                    current_phase=current.current_phase,
                    status=CycleRunStatus.REVIEW_REQUIRED,
                    reason="Snapshot portefeuille absent : aucun sizing de cycle autorisé",
                    errors=["PORTFOLIO_SNAPSHOT_MISSING"],
                )

            target = self._strategic_target(context)
            if target is None:
                return self._finish_non_completed(
                    context=context,
                    started=started,
                    input_hash=input_hash,
                    current_phase=current.current_phase,
                    status=CycleRunStatus.REVIEW_REQUIRED,
                    reason="Cible stratégique investie absente : aucune progression autorisée",
                    errors=["STRATEGIC_TARGET_MISSING"],
                )

            phase_portfolio = PhasePortfolioState(
                nav_eur=current.nav_eur,
                cash_eur=current.cash_eur,
                invested_eur=current.invested_eur,
                strategic_target_invested_eur=target,
                current_phase=current.current_phase,
                phase_started_at=current.phase_started_at or "",
                regime=_upper(context.regime),
                current_phase_human_approved=True,
            )
            history = self.store.get_cycle_records_for_phase_manager(
                phase=current.current_phase,
                limit=10_000,
            )
            assessment = self.phase_manager.assess(phase_portfolio, context.health, history)
            assessment_id = self.store.record_phase_assessment(assessment, actor=context.source)

            if assessment.action in {
                PhaseAction.REQUEST_PAUSE,
                PhaseAction.REQUEST_DE_RISK,
                PhaseAction.REVIEW_REQUIRED,
            }:
                status = (
                    CycleRunStatus.BLOCKED
                    if assessment.action in {PhaseAction.REQUEST_PAUSE, PhaseAction.REQUEST_DE_RISK}
                    else CycleRunStatus.REVIEW_REQUIRED
                )
                return self._finish_non_completed(
                    context=context,
                    started=started,
                    input_hash=input_hash,
                    current_phase=current.current_phase,
                    status=status,
                    reason=assessment.reason,
                    assessment_id=assessment_id,
                    phase_action=assessment.action.value,
                    transition_request_recommended=assessment.action in {
                        PhaseAction.REQUEST_PAUSE,
                        PhaseAction.REQUEST_DE_RISK,
                    },
                    transition_target_phase=(
                        assessment.recommended_phase
                        if assessment.action in {PhaseAction.REQUEST_PAUSE, PhaseAction.REQUEST_DE_RISK}
                        else None
                    ),
                    errors=assessment.blocking_codes + assessment.warning_codes,
                )

            ranking = self._rank(proposals)
            ramp_results = self._evaluate_ranked_proposals(
                context=context,
                current=current,
                target=target,
                ranked=ranking.ranked,
            )
            proposed_total = round(
                sum(max(0.0, _float_or_zero(item.risk_approved_notional_eur)) for item in proposals),
                2,
            )
            approved_total = round(sum(item.ramp_approved_notional_eur for item in ramp_results), 2)
            transition_recommended = assessment.action == PhaseAction.REQUEST_PROMOTION
            transition_target = assessment.next_phase if transition_recommended else None
            reason = "Cycle paper-only complété; propositions classées avant Ramp"
            if transition_recommended:
                reason += "; promotion %s -> %s à soumettre à validation humaine" % (
                    assessment.current_phase,
                    transition_target,
                )

            result = CycleRunResult(
                cycle_id=context.cycle_id,
                trading_date=context.trading_date,
                status=CycleRunStatus.COMPLETED,
                reason=reason,
                current_phase=current.current_phase,
                phase_assessment_id=assessment_id,
                phase_action=assessment.action.value,
                ranking_input_hash=ranking.input_hash,
                ranker_version=ranking.ranker_version,
                ramp_results=ramp_results,
                approved_total_eur=approved_total,
                proposed_total_eur=proposed_total,
                persisted_cycle=False,
                transition_request_recommended=transition_recommended,
                transition_target_phase=transition_target,
                input_hash=input_hash,
                started_at=started,
                completed_at=_utc_now(),
            )
            self._persist_cycle(context, result, assessment)
            result.persisted_cycle = True
            self._ingest_paper_approvals(result)
            return result

        except Exception as exc:
            return self._handle_exception(context, started, input_hash, exc)



    # APPROVAL_INGESTION_V1_BEGIN
    def _ingest_paper_approvals(self, result: CycleRunResult) -> None:
        """Crée les demandes PENDING après un cycle COMPLETED, sans exécution broker.

        L'ingestion est volontairement best-effort : le cycle et son audit SQLite
        existent déjà. En cas d'erreur, aucun ordre n'est créé et le message est
        conservé dans le résultat pour revue opérationnelle.
        """
        if result.status != CycleRunStatus.COMPLETED:
            return
        try:
            from approval_service import ApprovalService
            service = ApprovalService(self.store.db_path)
            ingest = service.ingest_cycle_result(result, requested_by="daily_cycle_orchestrator")
            result.errors.append(
                "APPROVAL_INGESTED created=%d existing=%d skipped=%d" % (
                    len(ingest.created), len(ingest.existing), len(ingest.skipped)
                )
            )
        except Exception as exc:
            result.errors.append("APPROVAL_INGESTION_FAILED: %s" % str(exc))
    # APPROVAL_INGESTION_V1_END

    def _rank(self, proposals: Sequence[CycleProposal]) -> Any:
        rankable = [self._to_rankable(item, index) for index, item in enumerate(proposals, start=1)]
        return self.ranker.rank(rankable)

    @staticmethod
    def _to_rankable(item: CycleProposal, index: int) -> RankableProposal:
        supplied = str(item.proposal_id or "").strip()
        proposal_id = supplied or "auto_%04d_%s_%s" % (index, _upper(item.ticker), _upper(item.side))
        return RankableProposal(
            proposal_id=proposal_id,
            ticker=item.ticker,
            side=item.side,
            risk_status=item.risk_status,
            risk_approved_notional_eur=item.risk_approved_notional_eur,
            asset_class=item.asset_class,
            is_new_position=item.is_new_position,
            conviction=item.conviction,
            consensus_score=item.consensus_score,
            liquidity_score=item.liquidity_score,
            urgency_score=item.urgency_score,
            is_risk_reducing=item.is_risk_reducing,
            is_concentration_reduction=item.is_concentration_reduction,
            forced_exit_reason=item.forced_exit_reason,
            decision_gate_status=item.decision_gate_status,
            metadata=item.metadata,
        )

    def _evaluate_ranked_proposals(
        self,
        context: CycleContext,
        current: Any,
        target: float,
        ranked: Sequence[RankedProposal],
    ) -> List[ProposalResult]:
        results: List[ProposalResult] = []
        running_net_buys = _nonnegative(context.cycle_net_buys_eur, "cycle_net_buys_eur")
        running_new_positions = _nonnegative_int(context.cycle_new_positions, "cycle_new_positions")
        by_asset_class: Dict[str, float] = {
            _upper(asset): _nonnegative(amount, "cycle_asset_class_net_buys_eur")
            for asset, amount in dict(context.cycle_asset_class_net_buys_eur).items()
        }

        for ranked_item in ranked:
            source = ranked_item.proposal

            if ranked_item.bucket.value == "INELIGIBLE_OR_REVIEW":
                results.append(
                    ProposalResult(
                        proposal_id=source.proposal_id,
                        rank=ranked_item.rank,
                        bucket=ranked_item.bucket.value,
                        ranking_score=ranked_item.score,
                        ranking_reasons=ranked_item.reasons,
                        ranking_warnings=ranked_item.eligibility_warnings,
                        ticker=_upper(source.ticker),
                        side=_upper(source.side),
                        risk_status=_upper(source.risk_status),
                        risk_approved_notional_eur=max(0.0, _float_or_zero(source.risk_approved_notional_eur)),
                        ramp_status="RAMP_REVIEW_REQUIRED",
                        ramp_approved_notional_eur=0.0,
                        reason="Non transmis à Startup Ramp : proposition inéligible ou données à vérifier",
                        review_codes=list(ranked_item.eligibility_warnings),
                    )
                )
                continue

            asset_class = _upper(source.asset_class)
            ramp_proposal = RiskApprovedProposal(
                ticker=source.ticker,
                side=_upper(source.side),
                risk_status=_upper(source.risk_status),
                risk_approved_notional_eur=float(source.risk_approved_notional_eur),
                asset_class=asset_class,
                is_new_position=bool(source.is_new_position),
                decision_gate_status=source.decision_gate_status,
                cycle_id=context.cycle_id,
            )
            ramp_portfolio = RampPortfolio(
                nav_eur=current.nav_eur,
                invested_eur=current.invested_eur,
                strategic_target_invested_eur=target,
                phase=current.current_phase,
                regime=_upper(context.regime),
                cycle_net_buys_eur=running_net_buys,
                cycle_asset_class_net_buys_eur=by_asset_class.get(asset_class, 0.0),
                cycle_new_positions=running_new_positions,
                completed_open_cycles_in_phase=0,
                phase_human_approved=True,
            )
            outcome: RampOutcome = self.ramp.evaluate(ramp_proposal, ramp_portfolio, context.health)
            results.append(
                ProposalResult(
                    proposal_id=source.proposal_id,
                    rank=ranked_item.rank,
                    bucket=ranked_item.bucket.value,
                    ranking_score=ranked_item.score,
                    ranking_reasons=ranked_item.reasons,
                    ranking_warnings=ranked_item.eligibility_warnings,
                    ticker=outcome.ticker,
                    side=outcome.side,
                    risk_status=ramp_proposal.risk_status,
                    risk_approved_notional_eur=outcome.requested_notional_eur,
                    ramp_status=outcome.status.value,
                    ramp_approved_notional_eur=outcome.approved_notional_eur,
                    reason=outcome.reason,
                    rejection_codes=outcome.rejection_codes,
                    review_codes=outcome.review_codes,
                    pause_codes=outcome.pause_codes,
                    reductions=outcome.reductions,
                )
            )

            if outcome.side == "BUY" and outcome.approved_notional_eur > 0:
                running_net_buys += outcome.approved_notional_eur
                by_asset_class[asset_class] = by_asset_class.get(asset_class, 0.0) + outcome.approved_notional_eur
                if source.is_new_position:
                    running_new_positions += 1
        return results

    def _strategic_target(self, context: CycleContext) -> Optional[float]:
        target = _positive_or_none(context.strategic_target_invested_eur)
        if target is not None:
            return target
        latest = self.store.get_latest_snapshot()
        if latest is None:
            return None
        return _positive_or_none(latest.get("metadata", {}).get("strategic_target_invested_eur"))

    def _persist_cycle(self, context: CycleContext, result: CycleRunResult, assessment: PhaseAssessment) -> None:
        payload = {
            "orchestrator_version": self.VERSION,
            "run": result.to_dict(),
            "assessment_id": result.phase_assessment_id,
            "ranking": {
                "ranker_version": result.ranker_version,
                "input_hash": result.ranking_input_hash,
                "proposals": [
                    {
                        "proposal_id": item.proposal_id,
                        "rank": item.rank,
                        "bucket": item.bucket,
                        "score": item.ranking_score,
                        "reasons": item.ranking_reasons,
                        "warnings": item.ranking_warnings,
                    }
                    for item in result.ramp_results
                ],
            },
            "notes": context.notes,
        }
        cycle = MarketCycleInput(
            cycle_id=context.cycle_id,
            trading_date=context.trading_date,
            phase=result.current_phase,
            market_session_completed=context.market_session_completed,
            market_data_fresh=context.market_data_fresh,
            pipeline_completed=context.pipeline_completed,
            paper_fills_reconciled=context.paper_fills_reconciled,
            critical_incidents_open=context.critical_incidents_open,
            status="COMPLETED",
            policy_version=assessment.policy_version,
            notes=result.reason,
            payload=payload,
        )
        self.store.record_market_cycle(cycle, actor=context.source)

    def _finish_non_completed(
        self,
        context: CycleContext,
        started: str,
        input_hash: str,
        current_phase: str,
        status: CycleRunStatus,
        reason: str,
        assessment_id: Optional[str] = None,
        phase_action: Optional[str] = None,
        transition_request_recommended: bool = False,
        transition_target_phase: Optional[str] = None,
        errors: Optional[List[str]] = None,
    ) -> CycleRunResult:
        result = CycleRunResult(
            cycle_id=context.cycle_id,
            trading_date=context.trading_date,
            status=status,
            reason=reason,
            current_phase=current_phase,
            phase_assessment_id=assessment_id,
            phase_action=phase_action,
            ranking_input_hash=None,
            ranker_version=ProposalRanker.VERSION,
            ramp_results=[],
            approved_total_eur=0.0,
            proposed_total_eur=0.0,
            persisted_cycle=False,
            transition_request_recommended=transition_request_recommended,
            transition_target_phase=transition_target_phase,
            input_hash=input_hash,
            started_at=started,
            completed_at=_utc_now(),
            errors=sorted(set(errors or [])),
        )
        self._persist_non_completed_cycle(context, result)
        result.persisted_cycle = True
        return result

    def _persist_non_completed_cycle(self, context: CycleContext, result: CycleRunResult) -> None:
        payload = {
            "orchestrator_version": self.VERSION,
            "run": result.to_dict(),
            "notes": context.notes,
        }
        cycle = MarketCycleInput(
            cycle_id=context.cycle_id,
            trading_date=context.trading_date,
            phase=result.current_phase,
            market_session_completed=context.market_session_completed,
            market_data_fresh=context.market_data_fresh,
            pipeline_completed=context.pipeline_completed,
            paper_fills_reconciled=context.paper_fills_reconciled,
            critical_incidents_open=context.critical_incidents_open,
            status=result.status.value,
            policy_version="",
            notes=result.reason,
            payload=payload,
        )
        try:
            self.store.record_market_cycle(cycle, actor=context.source)
        except Exception:
            result.persisted_cycle = False

    def _handle_exception(self, context: CycleContext, started: str, input_hash: str, exc: Exception) -> CycleRunResult:
        current_phase = "BOOTSTRAP"
        try:
            current_phase = self.store.get_current_portfolio_state().current_phase
        except Exception:
            pass

        result = CycleRunResult(
            cycle_id=context.cycle_id,
            trading_date=context.trading_date,
            status=CycleRunStatus.FAILED,
            reason="Cycle échoué : %s" % str(exc),
            current_phase=current_phase,
            phase_assessment_id=None,
            phase_action=None,
            ranking_input_hash=None,
            ranker_version=ProposalRanker.VERSION,
            ramp_results=[],
            approved_total_eur=0.0,
            proposed_total_eur=0.0,
            persisted_cycle=False,
            transition_request_recommended=False,
            transition_target_phase=None,
            input_hash=input_hash,
            started_at=started,
            completed_at=_utc_now(),
            errors=[type(exc).__name__, str(exc)],
        )
        self._persist_non_completed_cycle(context, result)
        return result

    @staticmethod
    def _validate_context(context: CycleContext) -> None:
        if not str(context.cycle_id).strip():
            raise ValueError("cycle_id obligatoire")
        if not str(context.trading_date).strip():
            raise ValueError("trading_date obligatoire")
        if _upper(context.regime) == "UNKNOWN":
            raise ValueError("regime obligatoire")
        _nonnegative(context.cycle_net_buys_eur, "cycle_net_buys_eur")
        _nonnegative_int(context.cycle_new_positions, "cycle_new_positions")
        if context.critical_incidents_open is not None:
            _nonnegative_int(context.critical_incidents_open, "critical_incidents_open")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _positive_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _float_or_zero(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _nonnegative(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("%s doit être numérique" % name) from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError("%s doit être fini et positif ou nul" % name)
    return number


def _nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError("%s doit être un entier" % name)
    try:
        number = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("%s doit être un entier" % name) from exc
    if number < 0:
        raise ValueError("%s doit être positif ou nul" % name)
    return number


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "value"):
        return _json_safe(value.value)
    return value


def _hash(value: Any) -> str:
    raw = json.dumps(_json_safe(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def healthy_health() -> RampHealth:
    return RampHealth(
        paper_fills_reconciled=True,
        unreconciled_paper_fills=0,
        open_critical_incidents=0,
        consecutive_failed_cycles=0,
        data_staleness_hours=1.0,
        agent_call_success_rate_pct=100.0,
        router_p95_latency_seconds=10.0,
        unresolved_review_items=0,
        drawdown_pct=0.0,
        phase_change_human_approved=None,
    )


def context(cycle_id: str, health: Optional[RampHealth] = None, **kwargs: Any) -> CycleContext:
    base = dict(
        cycle_id=cycle_id,
        trading_date="2026-09-04",
        market_session_completed=True,
        market_data_fresh=True,
        pipeline_completed=True,
        paper_fills_reconciled=True,
        critical_incidents_open=0,
        regime="RISK_ON",
        health=health or healthy_health(),
        source="selftest",
        strategic_target_invested_eur=600_000.0,
    )
    base.update(kwargs)
    return CycleContext(**base)


def proposal(
    ticker="AAPL",
    amount=5_000.0,
    asset_class="EQUITY",
    new=True,
    side="BUY",
    risk="RISK_APPROVED",
    proposal_id="",
    conviction="FORTE",
    consensus=1.10,
    liquidity=0.90,
    urgency=0.10,
    risk_reducing=False,
    concentration=False,
    forced="",
) -> CycleProposal:
    return CycleProposal(
        ticker=ticker,
        side=side,
        risk_status=risk,
        risk_approved_notional_eur=amount,
        asset_class=asset_class,
        is_new_position=new,
        proposal_id=proposal_id,
        conviction=conviction,
        consensus_score=consensus,
        liquidity_score=liquidity,
        urgency_score=urgency,
        is_risk_reducing=risk_reducing,
        is_concentration_reduction=concentration,
        forced_exit_reason=forced,
    )


def seed_snapshot(store: PortfolioStateStore, invested=0.0, cash=1_000_000.0, nav=1_000_000.0) -> None:
    store.record_portfolio_snapshot(
        PortfolioSnapshotInput(
            as_of="2026-09-04T08:00:00+00:00",
            nav_eur=nav,
            cash_eur=cash,
            invested_eur=invested,
            source="selftest",
            metadata={"strategic_target_invested_eur": 600_000.0},
        ),
        positions=[],
        actor="selftest",
    )


def selftest() -> int:
    print("=" * 84)
    print("[DAILY_CYCLE_ORCHESTRATOR_V1.1.1] autotest — classement puis Ramp paper-only")
    print("=" * 84)
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        suffix = ("  " + detail) if detail and not condition else ""
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", suffix))
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as directory:
        policy = "startup_policy_v1.json"
        if not os.path.exists(policy):
            print("Politique manquante : %s" % policy)
            return 1

        db = os.path.join(directory, "orchestrator.db")
        store = PortfolioStateStore(db)
        seed_snapshot(store)
        orchestrator = DailyCycleOrchestrator(store, policy)

        result = orchestrator.run(context("cycle-001"), [proposal("AAPL", 5_000, proposal_id="aapl")])
        check("cycle nominal COMPLETED", result.status == CycleRunStatus.COMPLETED, str(result.to_dict()))
        check("cycle nominal persistant", result.persisted_cycle)
        check(
            "AAPL 5k accepté en BOOTSTRAP",
            len(result.ramp_results) == 1 and result.ramp_results[0].ramp_approved_notional_eur == 5_000,
        )
        check("classement est persisté", result.ranking_input_hash is not None and result.ramp_results[0].rank == 1)
        check("cycle persiste avec statut COMPLETED", store.list_market_cycles(limit=1)[0]["status"] == "COMPLETED")
        check("assessment phase persistée", result.phase_assessment_id is not None)

        result = orchestrator.run(
            context("cycle-002"),
            [
                proposal("MS", 5_000, risk="RISK_REDUCED", proposal_id="ms", consensus=1.16),
                proposal("JPM", 5_000, proposal_id="jpm", conviction="NORMALE", consensus=0.90),
                proposal("AAPL", 5_000, proposal_id="aapl", conviction="FORTE", consensus=1.16),
            ],
        )
        ids = [item.proposal_id for item in result.ramp_results]
        amounts = {item.proposal_id: item.ramp_approved_notional_eur for item in result.ramp_results}
        check("Risk APPROVED classés avant REDUCED", ids[:2] == ["aapl", "jpm"], str(ids))
        check("quota bootstrap sert AAPL et JPM", amounts["aapl"] == 5_000 and amounts["jpm"] == 5_000)
        check(
            "MS reduced rejeté après quota",
            amounts["ms"] == 0 and result.ramp_results[2].ramp_status == "RAMP_REJECTED",
        )

        result = orchestrator.run(
            context("cycle-003"),
            [proposal("AAPL", 5_000, proposal_id="aapl"), proposal("JNJ", 5_000, proposal_id="jnj", consensus=None)],
        )
        jnj = next(item for item in result.ramp_results if item.proposal_id == "jnj")
        check(
            "consensus manquant ne traverse pas Ramp",
            jnj.ramp_status == "RAMP_REVIEW_REQUIRED" and jnj.ramp_approved_notional_eur == 0,
        )
        check("warning ranker est conservé", "CONSENSUS_SCORE_MISSING" in jnj.ranking_warnings)

        result = orchestrator.run(
            context("cycle-004"),
            [
                proposal("AAPL", 5_000, proposal_id="buy"),
                proposal(
                    "BTC", 3_000, side="SELL", asset_class="CRYPTO", new=False,
                    proposal_id="sell", risk_reducing=True, forced="RUNE_LONG_VETO",
                ),
            ],
        )
        check("vente défensive traitée avant achat", result.ramp_results[0].proposal_id == "sell")
        check("vente défensive approuvée sous Ramp", result.ramp_results[0].ramp_approved_notional_eur == 3_000)

        result = orchestrator.run(
            context("cycle-005", regime="RISK_OFF"),
            [proposal("AAPL", 5_000, proposal_id="aapl")],
        )
        check("RISK_OFF bloque cycle", result.status == CycleRunStatus.BLOCKED and result.approved_total_eur == 0)
        check(
            "RISK_OFF recommande PAUSED",
            result.transition_request_recommended and result.transition_target_phase == "PAUSED",
        )

        review_health = RampHealth(**{**asdict(healthy_health()), "router_p95_latency_seconds": None})
        result = orchestrator.run(
            context("cycle-006", health=review_health),
            [proposal("AAPL", 5_000, proposal_id="aapl")],
        )
        check("métrique santé manquante impose revue", result.status == CycleRunStatus.REVIEW_REQUIRED)

        missing_store = PortfolioStateStore(os.path.join(directory, "empty.db"))
        empty_orchestrator = DailyCycleOrchestrator(missing_store, policy)
        result = empty_orchestrator.run(
            context("cycle-007"),
            [proposal("AAPL", 5_000, proposal_id="aapl")],
        )
        check("snapshot absent impose revue", result.status == CycleRunStatus.REVIEW_REQUIRED)
        check("cycle revue est persisté", result.persisted_cycle)

        result = orchestrator.run(
            context("cycle-008"),
            [proposal("AAPL", 5_000, risk="RISK_REJECTED", proposal_id="rejected")],
        )
        check("Risk Gate rejeté ne traverse pas Ramp", result.ramp_results[0].ramp_status == "RAMP_REVIEW_REQUIRED")
        check("Risk Gate rejeté allocation nulle", result.ramp_results[0].ramp_approved_notional_eur == 0)

        duplicate_id = orchestrator.run(
            context("cycle-009"),
            [proposal("AAPL", 5_000, proposal_id="same"), proposal("JPM", 5_000, proposal_id="same")],
        )
        check("proposal_id dupliqué échoue fermé", duplicate_id.status == CycleRunStatus.FAILED)

        duplicate_cycle = orchestrator.run(context("cycle-001"), [])
        check("cycle_id dupliqué échoue fermé", duplicate_cycle.status == CycleRunStatus.FAILED)

        audit = store.verify_audit_chain()
        check("audit SQLite reste valide", audit["valid"] and audit["events_checked"] >= 12, str(audit))

        # Correctif v1.1.1 : list_market_cycles retourne déjà une liste de dicts.
        serialized = json.dumps(store.list_market_cycles(limit=100), ensure_ascii=False).lower()
        check("aucun ordre broker créé", "broker_order" not in serialized and "send_order" not in serialized)

    print()
    print("-" * 84)
    if failures:
        print("ÉCHECS : %d/24" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("24/24 contrôles passent. Daily Cycle Orchestrator v1.1.1 prêt pour API/UI paper-only.")
    return 0


def demo(db_path: str = "data/thesium_orchestrator_demo.db") -> int:
    if os.path.exists(db_path):
        os.remove(db_path)

    store = PortfolioStateStore(db_path)
    seed_snapshot(store)
    orchestrator = DailyCycleOrchestrator(store)

    print("=" * 112)
    print("[DAILY_CYCLE_ORCHESTRATOR_V1.1.1] démonstration paper-only — ranker puis Ramp")
    print("=" * 112)

    cases = [
        (
            "Priorité BOOTSTRAP",
            context("demo-001"),
            [
                proposal("MS", 5_000, risk="RISK_REDUCED", proposal_id="ms", consensus=1.12),
                proposal("JPM", 5_000, proposal_id="jpm", conviction="NORMALE", consensus=0.90),
                proposal("AAPL", 5_000, proposal_id="aapl", conviction="FORTE", consensus=1.16),
            ],
        ),
        (
            "Vente défensive + achat",
            context("demo-002"),
            [
                proposal("AAPL", 5_000, proposal_id="aapl"),
                proposal(
                    "BTC", 3_000, asset_class="CRYPTO", new=False, side="SELL",
                    proposal_id="btc-exit", risk_reducing=True, forced="RUNE_LONG_VETO",
                ),
            ],
        ),
        (
            "Consensus manquant",
            context("demo-003"),
            [
                proposal("AAPL", 5_000, proposal_id="aapl"),
                proposal("JNJ", 5_000, proposal_id="jnj", consensus=None),
            ],
        ),
        (
            "RISK_OFF",
            context("demo-004", regime="RISK_OFF"),
            [proposal("AAPL", 5_000, proposal_id="aapl")],
        ),
    ]

    for label, cycle_context, proposals in cases:
        result = orchestrator.run(cycle_context, proposals)
        print("\n  %-28s %s" % (label, result.compact()))
        if result.phase_assessment_id:
            print("     assessment : %s | action : %s" % (result.phase_assessment_id, result.phase_action))
        if result.ranking_input_hash:
            print("     ranking    : %s | %s" % (result.ranker_version, result.ranking_input_hash))
        if result.transition_request_recommended:
            print("     transition à soumettre : %s" % result.transition_target_phase)
        for item in result.ramp_results:
            print(
                "     #%d %-6s %-4s %-24s score=%0.4f %-22s risk=%8.2f€ ramp=%8.2f€"
                % (
                    item.rank,
                    item.ticker,
                    item.side,
                    item.bucket,
                    item.ranking_score,
                    item.ramp_status,
                    item.risk_approved_notional_eur,
                    item.ramp_approved_notional_eur,
                )
            )
            print("        ranker : " + " | ".join(item.ranking_reasons))
            print("        ramp   : " + item.reason)

    print("\n  Audit : %s" % store.verify_audit_chain())
    print("  Base démonstration : %s" % db_path)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Daily Cycle Orchestrator v1.1.1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    parser.add_argument("--db", default="data/thesium_orchestrator_demo.db")
    args = parser.parse_args()
    return selftest() if args.selftest else demo(args.db)


if __name__ == "__main__":
    sys.exit(main())
