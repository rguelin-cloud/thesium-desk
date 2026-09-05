#!/usr/bin/env python3
# legacy_cycle_adapter.py
# [LEGACY_CYCLE_ADAPTER_V1.0.0]
"""Adaptateur lecture seule : cycle historique Nextones -> file paper-only THESIUM.

RÃ´le
----
Lit les ordres historiques crÃ©Ã©s pour un cycle, les convertit en CycleProposal,
les fait passer dans DailyCycleOrchestrator puis laisse ApprovalService crÃ©er les
Ã©lÃ©ments PENDING paper-only.

Ce module ne modifie JAMAIS les tables historiques orders, fills, theses,
portfoliopositions ou portfoliostate. Il ne crÃ©e aucun ordre, aucun fill et
n'importe jamais execution_engine, PaperBroker ou un module broker.

Source historique attendue
--------------------------
- orders : instrumentid, thesisid, side, quantity, ordertype, limitprice,
  status, riskcheckresult, cycleid, createdat
- instruments : id, ticker, assetclass
- prices : dernier close par instrument, pour reconstruire le notionnel
- portfoliopositions : permet de dÃ©terminer is_new_position

Statuts source lus par dÃ©faut
-----------------------------
pendingvalidation, approved, pending, proposed

Les ordres dans tout autre statut sont exclus. Les BUY et SELL sont tous lus :
les SELL dÃ©fensifs sont transmis au nouvel orchestrateur mais ne crÃ©ent jamais
une demande d'approbation achat dans ApprovalService.

CLI
---
py -3.13 legacy_cycle_adapter.py --selftest
py -3.13 legacy_cycle_adapter.py --demo
py -3.13 legacy_cycle_adapter.py --cycle <cycle_id> --db thesium.db
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from approval_service import ApprovalService
    from daily_cycle_orchestrator import CycleContext, CycleProposal, CycleRunResult, DailyCycleOrchestrator
    from portfolio_state import PortfolioSnapshotInput, PortfolioStateStore
    from startup_ramp import RampHealth
except ImportError as exc:
    raise SystemExit("DÃ©pendance THESIUM absente : %s" % exc)


class LegacyAdapterError(RuntimeError):
    pass


@dataclass(frozen=True)
class LegacyOrder:
    order_id: int
    cycle_id: str
    ticker: str
    asset_class: str
    side: str
    quantity: float
    price_eur: float
    notional_eur: float
    legacy_status: str
    riskcheckresult: Dict[str, Any]
    thesis_id: Optional[int]
    is_new_position: bool
    created_at: str


@dataclass
class LegacyAdapterResult:
    cycle_id: str
    legacy_orders_found: int
    converted_proposals: int
    skipped_orders: List[Dict[str, Any]]
    orchestrator_result: Optional[Dict[str, Any]]
    approvals_created: int
    approvals_existing: int
    approvals_skipped: int
    mode: str
    input_hash: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


DEFAULT_LEGACY_STATUSES = ("pendingvalidation", "approved", "pending", "proposed")


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _safe_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_safe_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"raw": parsed}
    except Exception:
        return {"raw": str(value)}


def _risk_status(risk: Mapping[str, Any], legacy_status: str) -> str:
    """Mappe de faÃ§on conservatrice le rÃ©sultat historique vers le contrat v1."""
    approved = risk.get("approved")
    action = _upper(risk.get("action"), "")
    raw_status = _upper(risk.get("status"), "")
    legacy = _upper(legacy_status)
    if approved is True or action in {"APPROVED", "PASS", "ALLOW"} or raw_status in {"APPROVED", "PASS", "ALLOW"}:
        return "RISK_APPROVED"
    if action in {"REDUCED", "CAPPED", "WARN"} or raw_status in {"REDUCED", "CAPPED", "WARN"}:
        return "RISK_REDUCED"
    # Les ordres legacy pendingvalidation/approved ont dÃ©jÃ  franchi l'Ã©tape de
    # contrÃ´le historique; Ã  dÃ©faut de boolÃ©en explicite ils sont conservÃ©s comme
    # RISK_REDUCED, jamais RISK_APPROVED.
    if legacy in {"PENDINGVALIDATION", "APPROVED", "PENDING", "PROPOSED"}:
        return "RISK_REDUCED"
    return "RISK_REJECTED"


def _conviction(risk: Mapping[str, Any]) -> str:
    value = _finite(risk.get("conviction"))
    if value is None:
        value = _finite(risk.get("conviction_score"))
    if value is None:
        return "NORMAL"
    if value >= 8:
        return "FORTE"
    if value <= 4:
        return "FAIBLE"
    return "NORMALE"


def _consensus_score(risk: Mapping[str, Any]) -> float:
    for key in ("consensus_score", "consensus", "score", "quality_score"):
        value = _finite(risk.get(key))
        if value is not None:
            # Accepte les scores v2 [0.75, 1.20] seulement. Les autres sont
            # volontairement ramenÃ©s au neutre pour ne pas inventer de signal.
            return value if 0.75 <= value <= 1.20 else 0.90
    return 0.90


def _liquidity_score(risk: Mapping[str, Any]) -> float:
    for key in ("liquidity_score", "liquidity", "liquidityscore"):
        value = _finite(risk.get(key))
        if value is not None:
            return max(0.0, min(1.0, value))
    return 0.50


def _urgency_score(risk: Mapping[str, Any], side: str) -> float:
    if side == "SELL":
        return 1.0
    for key in ("urgency_score", "urgency"):
        value = _finite(risk.get(key))
        if value is not None:
            return max(0.0, min(1.0, value))
    return 0.10


def _is_defensive_sell(risk: Mapping[str, Any], side: str) -> Tuple[bool, bool, str]:
    source = _upper(risk.get("source"), "")
    reason = " ".join(str(risk.get(k) or "") for k in ("reason", "reasons", "blockedby", "action", "source"))
    upper = reason.upper()
    forced = "RUNE" in upper or "STOPLOSS" in upper or "TAKEPROFIT" in upper
    concentration = "DRIFT" in upper or "CONCENTRATION" in upper
    risk_reducing = side == "SELL" and (forced or "EXITAGENT" in source or concentration)
    return risk_reducing, concentration, reason[:240]


class LegacyCycleAdapter:
    """Pont read-only entre la base historique et le pipeline paper-only."""

    VERSION = "LEGACY_CYCLE_ADAPTER_V1.0.0"

    def __init__(self, db_path: str = "thesium.db", policy_path: str = "startup_policy_v1.json"):
        self.db_path = str(db_path)
        self.policy_path = policy_path

    def adapt_cycle(
        self,
        cycle_id: str,
        regime: str = "RISK_ON",
        health: Optional[RampHealth] = None,
        statuses: Sequence[str] = DEFAULT_LEGACY_STATUSES,
        dry_run: bool = False,
    ) -> LegacyAdapterResult:
        cycle_id = str(cycle_id or "").strip()
        if not cycle_id:
            raise LegacyAdapterError("cycle_id obligatoire")
        if not os.path.exists(self.db_path):
            raise LegacyAdapterError("Base introuvable : %s" % self.db_path)
        if not os.path.exists(self.policy_path):
            raise LegacyAdapterError("Politique introuvable : %s" % self.policy_path)

        orders, skipped = self.read_legacy_orders(cycle_id, statuses)
        proposals = [self.to_cycle_proposal(order) for order in orders]
        input_hash = _hash({"cycle_id": cycle_id, "orders": [asdict(x) for x in orders], "regime": regime})
        result = LegacyAdapterResult(
            cycle_id=cycle_id,
            legacy_orders_found=len(orders),
            converted_proposals=len(proposals),
            skipped_orders=skipped,
            orchestrator_result=None,
            approvals_created=0,
            approvals_existing=0,
            approvals_skipped=0,
            mode="DRY_RUN" if dry_run else "PAPER_ONLY",
            input_hash=input_hash,
        )
        if dry_run or not proposals:
            if not proposals:
                result.warnings.append("NO_ELIGIBLE_LEGACY_ORDERS")
            return result

        self._ensure_portfolio_snapshot()
        store = PortfolioStateStore(self.db_path)
        orchestrator = DailyCycleOrchestrator(store, self.policy_path)
        context = CycleContext(
            cycle_id="legacy_" + cycle_id,
            trading_date=datetime.now().date().isoformat(),
            market_session_completed=True,
            market_data_fresh=True,
            pipeline_completed=True,
            paper_fills_reconciled=True,
            critical_incidents_open=0,
            regime=_upper(regime),
            health=health or healthy_health(),
            source="legacy_cycle_adapter",
            strategic_target_invested_eur=self._strategic_target(),
            notes="Adaptation lecture seule du cycle historique %s" % cycle_id,
        )
        outcome = orchestrator.run(context, proposals)
        result.orchestrator_result = outcome.to_dict()

        # L'orchestrateur patchÃ© fait dÃ©jÃ  l'ingestion. Cet appel reste idempotent
        # et garantit le fonctionnement si le patch n'est pas prÃ©sent.
        if outcome.status.value == "COMPLETED":
            service = ApprovalService(self.db_path)
            ingest = service.ingest_cycle_result(outcome, requested_by="legacy_cycle_adapter")
            result.approvals_created = len(ingest.created)
            result.approvals_existing = len(ingest.existing)
            result.approvals_skipped = len(ingest.skipped)
        else:
            result.warnings.append("ORCHESTRATOR_NOT_COMPLETED:%s" % outcome.status.value)
        return result

    def adapt_order(
        self,
        order_id: int,
        regime: str = "RISK_ON",
        health: Optional[RampHealth] = None,
        statuses: Sequence[str] = DEFAULT_LEGACY_STATUSES,
        dry_run: bool = False,
    ) -> LegacyAdapterResult:
        """
        Adapte un ordre historique prÃ©cis vers la file paper-only.

        Cette mÃ©thode ne modifie jamais les tables historiques orders,
        fills ou theses. Elle construit une CycleProposal puis dÃ©lÃ¨gue
        l'arbitrage Ã  DailyCycleOrchestrator et ApprovalService.
        """
        try:
            normalized_order_id = int(order_id)
        except (TypeError, ValueError) as exc:
            raise LegacyAdapterError("order_id obligatoire et entier") from exc

        if normalized_order_id <= 0:
            raise LegacyAdapterError("order_id doit Ãªtre positif")

        if not os.path.exists(self.db_path):
            raise LegacyAdapterError("Base introuvable : %s" % self.db_path)

        if not os.path.exists(self.policy_path):
            raise LegacyAdapterError("Politique introuvable : %s" % self.policy_path)

        allowed = [
            str(status).lower().strip()
            for status in statuses
            if str(status).strip()
        ]

        if not allowed:
            raise LegacyAdapterError("Au moins un statut legacy doit Ãªtre autorisÃ©")

        placeholders = ",".join("?" for _ in allowed)

        query = f"""
            SELECT
                o.id AS order_id,
                o.cycleid AS cycle_id,
                o.side AS side,
                o.quantity AS quantity,
                o.status AS legacy_status,
                o.riskcheckresult AS riskcheckresult,
                o.thesisid AS thesis_id,
                o.createdat AS created_at,
                i.ticker AS ticker,
                i.assetclass AS asset_class,
                COALESCE(o.limitprice, p.close, pp.currentprice, 0) AS price_eur,
                COALESCE(pp.quantity, 0) AS held_quantity
            FROM orders o
            JOIN instruments i ON i.id = o.instrumentid
            LEFT JOIN portfoliopositions pp ON pp.instrumentid = o.instrumentid
            LEFT JOIN prices p ON p.instrumentid = o.instrumentid
                AND p.date = (
                    SELECT MAX(p2.date)
                    FROM prices p2
                    WHERE p2.instrumentid = o.instrumentid
                )
            WHERE o.id = ?
              AND LOWER(COALESCE(o.status, '')) IN ({placeholders})
            LIMIT 1
        """

        with self._connection() as conn:
            try:
                row = conn.execute(
                    query,
                    [normalized_order_id, *allowed],
                ).fetchone()
            except sqlite3.OperationalError as exc:
                raise LegacyAdapterError(
                    "SchÃ©ma historique incompatible : %s" % exc
                ) from exc

        skipped: List[Dict[str, Any]] = []
        orders: List[LegacyOrder] = []

        if row is not None:
            data = dict(row)
            quantity = _finite(data.get("quantity"))
            price = _finite(data.get("price_eur"))

            if quantity is None or quantity <= 0:
                skipped.append({
                    "order_id": normalized_order_id,
                    "ticker": data.get("ticker"),
                    "reason": "INVALID_QUANTITY",
                })
            elif price is None or price <= 0:
                skipped.append({
                    "order_id": normalized_order_id,
                    "ticker": data.get("ticker"),
                    "reason": "MISSING_PRICE",
                })
            else:
                orders.append(LegacyOrder(
                    order_id=int(data["order_id"]),
                    cycle_id=str(data.get("cycle_id") or "order_%d" % normalized_order_id),
                    ticker=_upper(data["ticker"]),
                    asset_class=_upper(data.get("asset_class"), "EQUITY"),
                    side=_upper(data["side"]),
                    quantity=quantity,
                    price_eur=price,
                    notional_eur=round(quantity * price, 2),
                    legacy_status=str(data.get("legacy_status") or ""),
                    riskcheckresult=_json_object(data.get("riskcheckresult")),
                    thesis_id=data.get("thesis_id"),
                    is_new_position=(
                        _finite(data.get("held_quantity")) or 0.0
                    ) <= 0.0,
                    created_at=str(data.get("created_at") or ""),
                ))

        synthetic_cycle_id = "order_%d" % normalized_order_id
        proposals = [self.to_cycle_proposal(order) for order in orders]

        result = LegacyAdapterResult(
            cycle_id=synthetic_cycle_id,
            legacy_orders_found=len(orders),
            converted_proposals=len(proposals),
            skipped_orders=skipped,
            orchestrator_result=None,
            approvals_created=0,
            approvals_existing=0,
            approvals_skipped=0,
            mode="DRY_RUN" if dry_run else "PAPER_ONLY",
            input_hash=_hash({
                "order_id": normalized_order_id,
                "orders": [asdict(x) for x in orders],
                "regime": regime,
            }),
        )

        if not orders and not skipped:
            result.warnings.append("LEGACY_ORDER_NOT_FOUND_OR_STATUS_NOT_ELIGIBLE")

        if dry_run or not proposals:
            if not proposals and not result.warnings:
                result.warnings.append("NO_ELIGIBLE_LEGACY_ORDERS")
            return result

        self._ensure_portfolio_snapshot()

        store = PortfolioStateStore(self.db_path)
        orchestrator = DailyCycleOrchestrator(store, self.policy_path)

        context = CycleContext(
            cycle_id="legacy_" + synthetic_cycle_id,
            trading_date=datetime.now().date().isoformat(),
            market_session_completed=True,
            market_data_fresh=True,
            pipeline_completed=True,
            paper_fills_reconciled=True,
            critical_incidents_open=0,
            regime=_upper(regime),
            health=health or healthy_health(),
            source="legacy_cycle_adapter",
            strategic_target_invested_eur=self._strategic_target(),
            notes=(
                "Adaptation lecture seule de l'ordre historique %d"
                % normalized_order_id
            ),
        )

        outcome = orchestrator.run(context, proposals)
        result.orchestrator_result = outcome.to_dict()

        if outcome.status.value == "COMPLETED":
            service = ApprovalService(self.db_path)
            ingest = service.ingest_cycle_result(
                outcome,
                requested_by="legacy_cycle_adapter",
            )
            result.approvals_created = len(ingest.created)
            result.approvals_existing = len(ingest.existing)
            result.approvals_skipped = len(ingest.skipped)
        else:
            result.warnings.append(
                "ORCHESTRATOR_NOT_COMPLETED:%s" % outcome.status.value
            )

        return result
    def read_legacy_orders(self, cycle_id: str, statuses: Sequence[str]) -> Tuple[List[LegacyOrder], List[Dict[str, Any]]]:
        allowed = [str(status).lower().strip() for status in statuses if str(status).strip()]
        if not allowed:
            raise LegacyAdapterError("Au moins un statut legacy doit Ãªtre autorisÃ©")
        placeholders = ",".join("?" for _ in allowed)
        query = f"""
            SELECT
                o.id AS order_id,
                o.cycleid AS cycle_id,
                o.side AS side,
                o.quantity AS quantity,
                o.status AS legacy_status,
                o.riskcheckresult AS riskcheckresult,
                o.thesisid AS thesis_id,
                o.createdat AS created_at,
                i.ticker AS ticker,
                i.assetclass AS asset_class,
                COALESCE(o.limitprice, p.close, pp.currentprice, 0) AS price_eur,
                COALESCE(pp.quantity, 0) AS held_quantity
            FROM orders o
            JOIN instruments i ON i.id = o.instrumentid
            LEFT JOIN portfoliopositions pp ON pp.instrumentid = o.instrumentid
            LEFT JOIN prices p ON p.instrumentid = o.instrumentid
                AND p.date = (SELECT MAX(p2.date) FROM prices p2 WHERE p2.instrumentid = o.instrumentid)
            WHERE o.cycleid = ?
              AND LOWER(COALESCE(o.status, '')) IN ({placeholders})
            ORDER BY o.id ASC
        """
        rows: List[sqlite3.Row]
        with self._connection() as conn:
            try:
                rows = conn.execute(query, [cycle_id, *allowed]).fetchall()
            except sqlite3.OperationalError as exc:
                raise LegacyAdapterError("SchÃ©ma historique incompatible : %s" % exc) from exc

        orders: List[LegacyOrder] = []
        skipped: List[Dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            quantity = _finite(data.get("quantity"))
            price = _finite(data.get("price_eur"))
            if quantity is None or quantity <= 0:
                skipped.append({"order_id": data.get("order_id"), "ticker": data.get("ticker"), "reason": "INVALID_QUANTITY"})
                continue
            if price is None or price <= 0:
                skipped.append({"order_id": data.get("order_id"), "ticker": data.get("ticker"), "reason": "MISSING_PRICE"})
                continue
            orders.append(LegacyOrder(
                order_id=int(data["order_id"]),
                cycle_id=str(data["cycle_id"]),
                ticker=_upper(data["ticker"]),
                asset_class=_upper(data.get("asset_class"), "EQUITY"),
                side=_upper(data["side"]),
                quantity=quantity,
                price_eur=price,
                notional_eur=round(quantity * price, 2),
                legacy_status=str(data.get("legacy_status") or ""),
                riskcheckresult=_json_object(data.get("riskcheckresult")),
                thesis_id=data.get("thesis_id"),
                is_new_position=(_finite(data.get("held_quantity")) or 0.0) <= 0.0,
                created_at=str(data.get("created_at") or ""),
            ))
        return orders, skipped

    def to_cycle_proposal(self, order: LegacyOrder) -> CycleProposal:
        risk = order.riskcheckresult
        risk_status = _risk_status(risk, order.legacy_status)
        risk_reducing, concentration, forced_reason = _is_defensive_sell(risk, order.side)
        return CycleProposal(
            proposal_id="legacy_order_%d" % order.order_id,
            ticker=order.ticker,
            side=order.side,
            risk_status=risk_status,
            risk_approved_notional_eur=order.notional_eur,
            asset_class=order.asset_class,
            is_new_position=order.is_new_position,
            conviction=_conviction(risk),
            consensus_score=_consensus_score(risk),
            liquidity_score=_liquidity_score(risk),
            urgency_score=_urgency_score(risk, order.side),
            is_risk_reducing=risk_reducing,
            is_concentration_reduction=concentration,
            forced_exit_reason=forced_reason if risk_reducing and order.side == "SELL" else "",
            decision_gate_status="LEGACY_ADAPTED",
            metadata={
                "legacy_order_id": order.order_id,
                "legacy_cycle_id": order.cycle_id,
                "legacy_status": order.legacy_status,
                "legacy_thesis_id": order.thesis_id,
                "legacy_quantity": order.quantity,
                "legacy_price_eur": order.price_eur,
                "legacy_riskcheckresult": risk,
                "adapter_version": self.VERSION,
            },
        )

    def _ensure_portfolio_snapshot(self) -> None:
        """CrÃ©e un snapshot ps_ si absent, Ã  partir des valeurs historiques en lecture seule."""
        store = PortfolioStateStore(self.db_path)
        if store.get_latest_snapshot() is not None:
            return
        with self._connection() as conn:
            portfolio = conn.execute("SELECT * FROM portfoliostate WHERE id=1").fetchone()
            if portfolio is None:
                raise LegacyAdapterError("portfoliostate.id=1 introuvable")
            values = dict(portfolio)
            nav = _finite(values.get("totalvalue")) or 0.0
            cash = _finite(values.get("cash")) or 0.0
            if nav <= 0:
                raise LegacyAdapterError("NAV historique absente ou invalide")
            invested = max(0.0, nav - cash)
        target = max(1.0, nav * 0.60)
        store.record_portfolio_snapshot(
            PortfolioSnapshotInput(
                as_of=_utc_now(), nav_eur=nav, cash_eur=max(0.0, cash), invested_eur=invested,
                source="legacy_cycle_adapter_bootstrap",
                metadata={"strategic_target_invested_eur": target, "source": "legacy_portfoliostate"},
            ),
            actor="legacy_cycle_adapter",
        )

    def _strategic_target(self) -> float:
        store = PortfolioStateStore(self.db_path)
        latest = store.get_latest_snapshot()
        if latest:
            target = _finite(latest.get("metadata", {}).get("strategic_target_invested_eur"))
            if target is not None and target > 0:
                return target
            nav = _finite(latest.get("nav_eur"))
            if nav is not None and nav > 0:
                return nav * 0.60
        return 600_000.0

    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return _ConnectionContext(conn)


class _ConnectionContext:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    def __enter__(self) -> sqlite3.Connection:
        return self.conn
    def __exit__(self, exc_type, exc, tb) -> None:
        self.conn.close()


def healthy_health() -> RampHealth:
    return RampHealth(
        paper_fills_reconciled=True, unreconciled_paper_fills=0,
        open_critical_incidents=0, consecutive_failed_cycles=0,
        data_staleness_hours=1.0, agent_call_success_rate_pct=100.0,
        router_p95_latency_seconds=10.0, unresolved_review_items=0,
        drawdown_pct=0.0, phase_change_human_approved=None,
    )


def _seed_legacy_db(path: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
        CREATE TABLE instruments (id INTEGER PRIMARY KEY, ticker TEXT, assetclass TEXT);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, instrumentid INTEGER, thesisid INTEGER, side TEXT, quantity REAL, ordertype TEXT, limitprice REAL, status TEXT, riskcheckresult TEXT, cycleid TEXT, createdat TEXT);
        CREATE TABLE prices (instrumentid INTEGER, date TEXT, close REAL);
        CREATE TABLE portfoliopositions (instrumentid INTEGER, quantity REAL, currentprice REAL);
        CREATE TABLE portfoliostate (id INTEGER PRIMARY KEY, totalvalue REAL, cash REAL);
        INSERT INTO instruments VALUES (1,'AAPL','equity'),(2,'JPM','equity'),(3,'BTC','crypto'),(4,'JNJ','equity');
        INSERT INTO prices VALUES (1,'2026-09-04',250),(2,'2026-09-04',300),(3,'2026-09-04',90000),(4,'2026-09-04',200);
        INSERT INTO portfoliostate VALUES (1,1000000,1000000);
        INSERT INTO orders VALUES
        (101,1,1,'buy',20,'market',NULL,'pendingvalidation','{"approved":true,"conviction":8,"consensus_score":1.16,"liquidity_score":0.9}','legacy-001','2026-09-04T10:00:00'),
        (102,2,2,'buy',20,'market',NULL,'pendingvalidation','{"approved":true,"conviction":6,"consensus_score":0.90,"liquidity_score":0.9}','legacy-001','2026-09-04T10:00:00'),
        (103,3,3,'sell',0.02,'market',NULL,'pendingvalidation','{"approved":true,"source":"ExitAgentSTOPLOSS","reason":"RUNE_LONG_VETO","conviction":8}','legacy-001','2026-09-04T10:00:00'),
        (104,4,4,'buy',10,'market',NULL,'rejected','{"approved":false}','legacy-001','2026-09-04T10:00:00');
        """)
        conn.commit()
    finally:
        conn.close()


def selftest() -> int:
    print("=" * 84)
    print("[LEGACY_CYCLE_ADAPTER_V1.0.0] autotest â€” bridge lecture seule vers paper-only")
    print("=" * 84)
    failures: List[str] = []
    def check(name: str, condition: bool, detail: str = "") -> None:
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", ("  " + detail) if detail and not condition else ""))
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as directory:
        db = os.path.join(directory, "legacy.db")
        _seed_legacy_db(db)
        policy = Path("startup_policy_v1.json")
        if not policy.exists():
            print("Politique manquante : startup_policy_v1.json")
            return 1
        adapter = LegacyCycleAdapter(db, str(policy))
        before = Path(db).read_bytes()
        orders, skipped = adapter.read_legacy_orders("legacy-001", DEFAULT_LEGACY_STATUSES)
        after = Path(db).read_bytes()
        check("lecture legacy trouve 3 ordres admissibles", len(orders) == 3 and len(skipped) == 0)
        check("lecture legacy ne modifie pas la base", before == after)
        aapl = next(x for x in orders if x.ticker == "AAPL")
        check("notionnel AAPL quantity x prix", aapl.notional_eur == 5000.0)
        cp = adapter.to_cycle_proposal(aapl)
        check("AAPL mappe RISK_APPROVED", cp.risk_status == "RISK_APPROVED")
        btc = next(x for x in orders if x.ticker == "BTC")
        btc_cp = adapter.to_cycle_proposal(btc)
        check("BTC SELL reconnue dÃ©fensive", btc_cp.is_risk_reducing and btc_cp.forced_exit_reason)
        dry = adapter.adapt_cycle("legacy-001", dry_run=True)
        check("dry run ne lance pas orchestrateur", dry.orchestrator_result is None and dry.converted_proposals == 3)
        result = adapter.adapt_cycle("legacy-001")
        check("adaptation lance orchestrateur", result.orchestrator_result is not None)
        check("adaptation reste paper-only", result.mode == "PAPER_ONLY")
        service = ApprovalService(db)
        pending = service.list_pending()
        check("BUY legacy crÃ©ent approvals", len(pending) == 2, str([x.to_dict() for x in pending]))
        check("SELL legacy ne crÃ©e pas approval BUY", all(x.ticker != "BTC" for x in pending))
        again = adapter.adapt_cycle("legacy-001")
        check("adaptation rÃ©pÃ©tÃ©e ne double pas approvals", len(service.list_pending()) == 2 and again.approvals_created == 0)
        check("aucun ordre historique crÃ©Ã© par adaptateur", len(adapter.read_legacy_orders("legacy-001", DEFAULT_LEGACY_STATUSES)[0]) == 3)

    print("\n" + "-" * 84)
    if failures:
        print("Ã‰CHECS : %d/12" % len(failures))
        for failure in failures:
            print("  - " + failure)
        return 1
    print("12/12 contrÃ´les passent. Legacy Cycle Adapter v1 prÃªt pour le patch API.")
    return 0


def demo() -> int:
    with tempfile.TemporaryDirectory() as directory:
        db = os.path.join(directory, "legacy_demo.db")
        _seed_legacy_db(db)
        adapter = LegacyCycleAdapter(db)
        print("=" * 84)
        print("[LEGACY_CYCLE_ADAPTER_V1.0.0] dÃ©monstration")
        print("=" * 84)
        orders, _ = adapter.read_legacy_orders("legacy-001", DEFAULT_LEGACY_STATUSES)
        for order in orders:
            print("  legacy #%d %-5s %-4s qty=%9.4f price=%10.2fâ‚¬ notionnel=%10.2fâ‚¬" % (
                order.order_id, order.ticker, order.side, order.quantity, order.price_eur, order.notional_eur))
        outcome = adapter.adapt_cycle("legacy-001")
        print("\n  converted=%d approvals_created=%d existing=%d skipped=%d" % (
            outcome.converted_proposals, outcome.approvals_created,
            outcome.approvals_existing, outcome.approvals_skipped))
        if outcome.orchestrator_result:
            print("  orchestrator status=%s approved_total=%.2fâ‚¬" % (
                outcome.orchestrator_result["status"], outcome.orchestrator_result["approved_total_eur"]))
        for approval in ApprovalService(db).list_pending():
            print("  PENDING #%d %s %s %.2fâ‚¬" % (approval.rank, approval.ticker, approval.side, approval.proposed_notional_eur))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Legacy Cycle Adapter THESIUM")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    group.add_argument("--cycle", metavar="CYCLE_ID")
    parser.add_argument("--db", default="thesium.db")
    parser.add_argument("--policy", default="startup_policy_v1.json")
    parser.add_argument("--regime", default="RISK_ON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.demo:
        return demo()
    try:
        result = LegacyCycleAdapter(args.db, args.policy).adapt_cycle(
            args.cycle, regime=args.regime, dry_run=args.dry_run
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print("ERREUR : %s" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

