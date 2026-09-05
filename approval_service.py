#!/usr/bin/env python3
# approval_service.py
# [APPROVAL_SERVICE_V1.0.0]
"""Service d'approbations humaines paper-only pour THESIUM.

Rôle
----
Transforme les résultats RAMP_APPROVED / RAMP_REDUCED du cycle quotidien en
approbations humaines persistées, traçables et idempotentes.

Ce service ne crée AUCUN ordre, fill, appel broker, ou exécution de marché.
Une approbation signifie uniquement : « l'intention paper-only est revue et peut
être affichée / transmise au futur simulateur d'exécution ». L'exécution réelle
reste absente de cette version.

Pipeline
--------
daily_cycle_orchestrator (CycleRunResult)
    -> approval_service.ingest_cycle_result()
    -> ps_approval_requests
    -> interface Pending Approvals
    -> approve / reject / expire
    -> audit SQLite append-only

Statuts
-------
PENDING   : attente d'une décision humaine.
APPROVED  : validée par un humain; aucun ordre n'est créé.
REJECTED  : refusée par un humain.
EXPIRED   : expirée avant décision.
CANCELLED : annulée par un opérateur.

CLI
---
    py -3.13 approval_service.py --selftest
    py -3.13 approval_service.py --demo
    py -3.13 approval_service.py --inspect data/thesium_approvals_demo.db
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
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

try:
    from daily_cycle_orchestrator import (
        CycleContext,
        CycleProposal,
        CycleRunResult,
        CycleRunStatus,
        DailyCycleOrchestrator,
        context as demo_context,
        proposal as demo_proposal,
        seed_snapshot,
    )
    from portfolio_state import PortfolioSnapshotInput, PortfolioStateStore
except ImportError as exc:
    raise SystemExit("Dépendance THESIUM absente dans le dossier courant : %s" % exc)


class ApprovalError(RuntimeError):
    pass


class ApprovalNotFoundError(ApprovalError):
    pass


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = {
    ApprovalStatus.APPROVED.value,
    ApprovalStatus.REJECTED.value,
    ApprovalStatus.EXPIRED.value,
    ApprovalStatus.CANCELLED.value,
}


@dataclass
class ApprovalRequest:
    approval_id: str
    idempotency_key: str
    cycle_id: str
    proposal_id: str
    ticker: str
    side: str
    asset_class: str
    status: ApprovalStatus
    rank: int
    bucket: str
    ranking_score: float
    risk_status: str
    risk_approved_notional_eur: float
    ramp_status: str
    proposed_notional_eur: float
    reason: str
    expires_at: str
    created_at: str
    updated_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    approval_note: Optional[str] = None
    rejected_by: Optional[str] = None
    rejected_at: Optional[str] = None
    rejection_note: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[str] = None
    cancellation_note: Optional[str] = None
    source_input_hash: str = ""
    source_ranking_hash: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass
class IngestResult:
    cycle_id: str
    created: List[ApprovalRequest]
    existing: List[ApprovalRequest]
    skipped: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "created": [item.to_dict() for item in self.created],
            "existing": [item.to_dict() for item in self.existing],
            "skipped": self.skipped,
        }


class ApprovalService:
    """Service SQLite d'approbation humaine. Aucun chemin d'exécution broker."""

    VERSION = "APPROVAL_SERVICE_V1.0.0"

    def __init__(self, db_path: str = "data/thesium.db"):
        self.db_path = str(db_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        directory = os.path.dirname(os.path.abspath(self.db_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = FULL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        """Crée les tables propres au service. Idempotent et sans broker."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ps_approval_requests (
                    approval_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    cycle_id TEXT NOT NULL,
                    proposal_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('PENDING','APPROVED','REJECTED','EXPIRED','CANCELLED')),
                    rank INTEGER NOT NULL CHECK(rank >= 1),
                    bucket TEXT NOT NULL,
                    ranking_score REAL NOT NULL,
                    risk_status TEXT NOT NULL,
                    risk_approved_notional_eur REAL NOT NULL CHECK(risk_approved_notional_eur >= 0),
                    ramp_status TEXT NOT NULL,
                    proposed_notional_eur REAL NOT NULL CHECK(proposed_notional_eur > 0),
                    reason TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    approval_note TEXT,
                    rejected_by TEXT,
                    rejected_at TEXT,
                    rejection_note TEXT,
                    cancelled_by TEXT,
                    cancelled_at TEXT,
                    cancellation_note TEXT,
                    source_input_hash TEXT NOT NULL,
                    source_ranking_hash TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(cycle_id, proposal_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ps_approvals_pending
                    ON ps_approval_requests(status, expires_at, rank, created_at);
                CREATE INDEX IF NOT EXISTS ix_ps_approvals_cycle
                    ON ps_approval_requests(cycle_id, rank);

                CREATE TABLE IF NOT EXISTS ps_approval_audit_log (
                    audit_id TEXT PRIMARY KEY,
                    event_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    approval_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    FOREIGN KEY(approval_id) REFERENCES ps_approval_requests(approval_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ps_approval_audit
                    ON ps_approval_audit_log(approval_id, event_at DESC);
                """
            )

    def ingest_cycle_result(
        self,
        cycle_result: Any,
        requested_by: str = "daily_cycle_orchestrator",
        ttl_hours: float = 24.0,
    ) -> IngestResult:
        """Crée les approbations pour les seuls RAMP_APPROVED/RAMP_REDUCED BUY.

        Idempotent par (cycle_id, proposal_id). Les éléments rejetés, en pause, en
        revue ou les SELL sont conservés dans le cycle, mais n'apparaissent pas dans
        Pending Approvals car ils ne nécessitent pas une autorisation d'achat.
        """
        self.initialize()
        data = _to_data(cycle_result)
        cycle_id = _required_text(data.get("cycle_id"), "cycle_id")
        source_input_hash = _required_text(data.get("input_hash"), "input_hash")
        if data.get("status") != CycleRunStatus.COMPLETED.value:
            return IngestResult(cycle_id=cycle_id, created=[], existing=[], skipped=[{
                "reason": "CYCLE_NOT_COMPLETED",
                "cycle_status": data.get("status"),
            }])
        ttl = _positive_number(ttl_hours, "ttl_hours")
        now = _utc_now()
        expires_at = _utc_after_hours(ttl)
        created: List[ApprovalRequest] = []
        existing: List[ApprovalRequest] = []
        skipped: List[Dict[str, Any]] = []

        with self._connection() as conn:
            for item in data.get("ramp_results", []):
                result = _to_data(item)
                eligible, reason = self._approval_eligible(result)
                proposal_id = str(result.get("proposal_id") or "").strip()
                if not eligible:
                    skipped.append({
                        "proposal_id": proposal_id,
                        "ticker": result.get("ticker"),
                        "reason": reason,
                        "ramp_status": result.get("ramp_status"),
                    })
                    continue

                key = _idempotency_key(cycle_id, proposal_id, source_input_hash, result)
                row = conn.execute(
                    "SELECT * FROM ps_approval_requests WHERE idempotency_key=?", (key,)
                ).fetchone()
                if row is not None:
                    existing.append(self._row_to_request(row))
                    continue

                collision = conn.execute(
                    "SELECT * FROM ps_approval_requests WHERE cycle_id=? AND proposal_id=?", (cycle_id, proposal_id)
                ).fetchone()
                if collision is not None:
                    existing.append(self._row_to_request(collision))
                    continue

                request = self._insert_request(
                    conn=conn,
                    cycle_id=cycle_id,
                    source_input_hash=source_input_hash,
                    source_ranking_hash=str(data.get("ranking_input_hash") or ""),
                    result=result,
                    requested_by=requested_by,
                    idempotency_key=key,
                    expires_at=expires_at,
                    now=now,
                )
                created.append(request)
        return IngestResult(cycle_id=cycle_id, created=created, existing=existing, skipped=skipped)

    def list_pending(self, include_expired: bool = False, limit: int = 100) -> List[ApprovalRequest]:
        self.initialize()
        self.expire_due(actor="system")
        limit = max(1, min(int(limit), 10_000))
        with self._connection() as conn:
            if include_expired:
                rows = conn.execute(
                    "SELECT * FROM ps_approval_requests WHERE status IN ('PENDING','EXPIRED') "
                    "ORDER BY rank ASC, created_at ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM ps_approval_requests WHERE status='PENDING' "
                    "ORDER BY rank ASC, created_at ASC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_request(row) for row in rows]

    def get(self, approval_id: str) -> ApprovalRequest:
        self.initialize()
        self.expire_due(actor="system")
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM ps_approval_requests WHERE approval_id=?", (approval_id,)).fetchone()
            if row is None:
                raise ApprovalNotFoundError("Approval introuvable : %s" % approval_id)
            return self._row_to_request(row)

    def approve(self, approval_id: str, approved_by: str, approval_note: str) -> ApprovalRequest:
        """Approuve une intention paper-only. Ne génère pas d'ordre."""
        self.initialize()
        actor = _required_text(approved_by, "approved_by")
        note = _required_text(approval_note, "approval_note")
        now = _utc_now()
        with self._connection() as conn:
            self._expire_due_in_connection(conn, now, actor="system")
            row = self._row_for_update(conn, approval_id)
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ApprovalError("Seule une demande PENDING peut être approuvée; statut=%s" % row["status"])
            conn.execute(
                """UPDATE ps_approval_requests
                   SET status='APPROVED', approved_by=?, approved_at=?, approval_note=?, updated_at=?
                   WHERE approval_id=?""",
                (actor, now, note, now, approval_id),
            )
            self._audit(conn, approval_id, actor, "APPROVAL_APPROVED", {
                "approval_note": note,
                "execution": "NONE_PAPER_ONLY",
            })
            return self._row_to_request(self._row_for_update(conn, approval_id))

    def reject(self, approval_id: str, rejected_by: str, rejection_note: str) -> ApprovalRequest:
        self.initialize()
        actor = _required_text(rejected_by, "rejected_by")
        note = _required_text(rejection_note, "rejection_note")
        now = _utc_now()
        with self._connection() as conn:
            self._expire_due_in_connection(conn, now, actor="system")
            row = self._row_for_update(conn, approval_id)
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ApprovalError("Seule une demande PENDING peut être refusée; statut=%s" % row["status"])
            conn.execute(
                """UPDATE ps_approval_requests
                   SET status='REJECTED', rejected_by=?, rejected_at=?, rejection_note=?, updated_at=?
                   WHERE approval_id=?""",
                (actor, now, note, now, approval_id),
            )
            self._audit(conn, approval_id, actor, "APPROVAL_REJECTED", {"rejection_note": note})
            return self._row_to_request(self._row_for_update(conn, approval_id))

    def cancel(self, approval_id: str, cancelled_by: str, cancellation_note: str) -> ApprovalRequest:
        self.initialize()
        actor = _required_text(cancelled_by, "cancelled_by")
        note = _required_text(cancellation_note, "cancellation_note")
        now = _utc_now()
        with self._connection() as conn:
            self._expire_due_in_connection(conn, now, actor="system")
            row = self._row_for_update(conn, approval_id)
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ApprovalError("Seule une demande PENDING peut être annulée; statut=%s" % row["status"])
            conn.execute(
                """UPDATE ps_approval_requests
                   SET status='CANCELLED', cancelled_by=?, cancelled_at=?, cancellation_note=?, updated_at=?
                   WHERE approval_id=?""",
                (actor, now, note, now, approval_id),
            )
            self._audit(conn, approval_id, actor, "APPROVAL_CANCELLED", {"cancellation_note": note})
            return self._row_to_request(self._row_for_update(conn, approval_id))

    def expire_due(self, actor: str = "system") -> int:
        self.initialize()
        with self._connection() as conn:
            return self._expire_due_in_connection(conn, _utc_now(), actor)

    def list_history(self, status: Optional[str] = None, limit: int = 100) -> List[ApprovalRequest]:
        self.initialize()
        self.expire_due(actor="system")
        limit = max(1, min(int(limit), 10_000))
        with self._connection() as conn:
            if status is None:
                rows = conn.execute(
                    "SELECT * FROM ps_approval_requests ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                desired = _upper(status)
                if desired not in {item.value for item in ApprovalStatus}:
                    raise ApprovalError("Statut inconnu : %s" % desired)
                rows = conn.execute(
                    "SELECT * FROM ps_approval_requests WHERE status=? ORDER BY created_at DESC LIMIT ?",
                    (desired, limit),
                ).fetchall()
            return [self._row_to_request(row) for row in rows]

    def verify_audit_chain(self) -> Dict[str, Any]:
        self.initialize()
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM ps_approval_audit_log ORDER BY event_at, audit_id").fetchall()
            errors: List[str] = []
            for row in rows:
                try:
                    payload = json.loads(row["payload_json"])
                except json.JSONDecodeError:
                    errors.append("JSON invalide audit_id=%s" % row["audit_id"])
                    continue
                if _hash(payload) != row["payload_hash"]:
                    errors.append("Hash incohérent audit_id=%s" % row["audit_id"])
            return {"valid": not errors, "events_checked": len(rows), "errors": errors}

    @staticmethod
    def _approval_eligible(result: Mapping[str, Any]) -> tuple[bool, str]:
        side = _upper(result.get("side"))
        ramp_status = _upper(result.get("ramp_status"))
        notional = _finite(result.get("ramp_approved_notional_eur"))
        proposal_id = str(result.get("proposal_id") or "").strip()
        if not proposal_id:
            return False, "PROPOSAL_ID_MISSING"
        if side != "BUY":
            return False, "SIDE_NOT_BUY"
        if ramp_status not in {"RAMP_APPROVED", "RAMP_REDUCED"}:
            return False, "RAMP_NOT_APPROVED"
        if notional is None or notional <= 0:
            return False, "RAMP_NOTIONAL_INVALID"
        return True, "OK"

    def _insert_request(
        self,
        conn: sqlite3.Connection,
        cycle_id: str,
        source_input_hash: str,
        source_ranking_hash: str,
        result: Mapping[str, Any],
        requested_by: str,
        idempotency_key: str,
        expires_at: str,
        now: str,
    ) -> ApprovalRequest:
        approval_id = "approval_" + uuid.uuid4().hex
        payload = {
            "approval_service_version": self.VERSION,
            "cycle_id": cycle_id,
            "proposal_result": result,
            "requested_by": requested_by,
            "created_at": now,
            "execution": "NONE_PAPER_ONLY",
        }
        request = ApprovalRequest(
            approval_id=approval_id,
            idempotency_key=idempotency_key,
            cycle_id=cycle_id,
            proposal_id=_required_text(result.get("proposal_id"), "proposal_id"),
            ticker=_required_text(result.get("ticker"), "ticker").upper(),
            side=_required_text(result.get("side"), "side").upper(),
            asset_class="UNKNOWN",
            status=ApprovalStatus.PENDING,
            rank=max(1, int(result.get("rank") or 1)),
            bucket=str(result.get("bucket") or ""),
            ranking_score=float(_finite(result.get("ranking_score")) or 0.0),
            risk_status=str(result.get("risk_status") or ""),
            risk_approved_notional_eur=max(0.0, float(_finite(result.get("risk_approved_notional_eur")) or 0.0)),
            ramp_status=str(result.get("ramp_status") or ""),
            proposed_notional_eur=float(_finite(result.get("ramp_approved_notional_eur")) or 0.0),
            reason=str(result.get("reason") or ""),
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
            source_input_hash=source_input_hash,
            source_ranking_hash=source_ranking_hash,
            payload=payload,
        )
        asset_class = str(result.get("asset_class") or result.get("metadata", {}).get("asset_class") or "UNKNOWN").upper()
        request.asset_class = asset_class
        conn.execute(
            """INSERT INTO ps_approval_requests(
                approval_id, idempotency_key, cycle_id, proposal_id, ticker, side, asset_class,
                status, rank, bucket, ranking_score, risk_status, risk_approved_notional_eur,
                ramp_status, proposed_notional_eur, reason, expires_at, source_input_hash,
                source_ranking_hash, payload_json, payload_hash, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.approval_id, request.idempotency_key, request.cycle_id, request.proposal_id,
                request.ticker, request.side, request.asset_class, request.status.value, request.rank,
                request.bucket, request.ranking_score, request.risk_status,
                request.risk_approved_notional_eur, request.ramp_status,
                request.proposed_notional_eur, request.reason, request.expires_at,
                request.source_input_hash, request.source_ranking_hash,
                _canonical_json(payload), _hash(payload), request.created_at, request.updated_at,
            ),
        )
        self._audit(conn, approval_id, requested_by, "APPROVAL_REQUEST_CREATED", {
            "cycle_id": cycle_id,
            "proposal_id": request.proposal_id,
            "ticker": request.ticker,
            "side": request.side,
            "proposed_notional_eur": request.proposed_notional_eur,
            "expires_at": expires_at,
            "execution": "NONE_PAPER_ONLY",
        })
        return request

    def _expire_due_in_connection(self, conn: sqlite3.Connection, now: str, actor: str) -> int:
        rows = conn.execute(
            "SELECT approval_id FROM ps_approval_requests WHERE status='PENDING' AND expires_at <= ?", (now,)
        ).fetchall()
        for row in rows:
            approval_id = row["approval_id"]
            conn.execute(
                "UPDATE ps_approval_requests SET status='EXPIRED', updated_at=? WHERE approval_id=?",
                (now, approval_id),
            )
            self._audit(conn, approval_id, actor, "APPROVAL_EXPIRED", {"expired_at": now})
        return len(rows)

    @staticmethod
    def _row_for_update(conn: sqlite3.Connection, approval_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM ps_approval_requests WHERE approval_id=?", (approval_id,)).fetchone()
        if row is None:
            raise ApprovalNotFoundError("Approval introuvable : %s" % approval_id)
        return row

    def _audit(self, conn: sqlite3.Connection, approval_id: str, actor: str, event_type: str, payload: Mapping[str, Any]) -> None:
        conn.execute(
            """INSERT INTO ps_approval_audit_log(
                audit_id, event_at, actor, event_type, approval_id, payload_json, payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "approval_audit_" + uuid.uuid4().hex,
                _utc_now(),
                actor or "system",
                event_type,
                approval_id,
                _canonical_json(payload),
                _hash(payload),
            ),
        )

    @staticmethod
    def _row_to_request(row: sqlite3.Row) -> ApprovalRequest:
        item = dict(row)
        return ApprovalRequest(
            approval_id=item["approval_id"],
            idempotency_key=item["idempotency_key"],
            cycle_id=item["cycle_id"],
            proposal_id=item["proposal_id"],
            ticker=item["ticker"],
            side=item["side"],
            asset_class=item["asset_class"],
            status=ApprovalStatus(item["status"]),
            rank=item["rank"],
            bucket=item["bucket"],
            ranking_score=item["ranking_score"],
            risk_status=item["risk_status"],
            risk_approved_notional_eur=item["risk_approved_notional_eur"],
            ramp_status=item["ramp_status"],
            proposed_notional_eur=item["proposed_notional_eur"],
            reason=item["reason"],
            expires_at=item["expires_at"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            approved_by=item["approved_by"],
            approved_at=item["approved_at"],
            approval_note=item["approval_note"],
            rejected_by=item["rejected_by"],
            rejected_at=item["rejected_at"],
            rejection_note=item["rejection_note"],
            cancelled_by=item["cancelled_by"],
            cancelled_at=item["cancelled_at"],
            cancellation_note=item["cancellation_note"],
            source_input_hash=item["source_input_hash"],
            source_ranking_hash=item["source_ranking_hash"],
            payload=json.loads(item["payload_json"]),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc_after_hours(hours: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_number(value: Any, name: str) -> float:
    number = _finite(value)
    if number is None or number <= 0:
        raise ApprovalError("%s doit être strictement positif" % name)
    return number


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ApprovalError("%s est obligatoire" % name)
    return text


def _to_data(value: Any) -> Dict[str, Any]:
    if is_dataclass(value):
        data = asdict(value)
    elif isinstance(value, Mapping):
        data = dict(value)
    elif hasattr(value, "to_dict"):
        data = value.to_dict()
    else:
        raise ApprovalError("Objet non sérialisable en approval")
    return _convert_enums(data)


def _convert_enums(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _convert_enums(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_convert_enums(item) for item in value]
    if isinstance(value, tuple):
        return [_convert_enums(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(_convert_enums(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _idempotency_key(cycle_id: str, proposal_id: str, source_input_hash: str, result: Mapping[str, Any]) -> str:
    relevant = {
        "cycle_id": cycle_id,
        "proposal_id": proposal_id,
        "source_input_hash": source_input_hash,
        "ticker": result.get("ticker"),
        "side": result.get("side"),
        "ramp_status": result.get("ramp_status"),
        "ramp_approved_notional_eur": result.get("ramp_approved_notional_eur"),
    }
    return _hash(relevant)


# ============================================================================
# AUTOTEST ET DÉMONSTRATION
# ============================================================================

def _run_cycle(store: PortfolioStateStore, cycle_id: str, proposals: Sequence[CycleProposal]) -> CycleRunResult:
    orchestrator = DailyCycleOrchestrator(store)
    return orchestrator.run(demo_context(cycle_id), proposals)


def selftest() -> int:
    print("=" * 84)
    print("[APPROVAL_SERVICE_V1.0.0] autotest — validations humaines paper-only")
    print("=" * 84)
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        suffix = ("  " + detail) if detail and not condition else ""
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", suffix))
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as directory:
        db = os.path.join(directory, "approvals.db")
        store = PortfolioStateStore(db)
        seed_snapshot(store)
        service = ApprovalService(db)
        service.initialize()

        cycle = _run_cycle(store, "approval-cycle-001", [
            demo_proposal("AAPL", 5_000, proposal_id="aapl"),
            demo_proposal("JPM", 5_000, proposal_id="jpm"),
            demo_proposal("JNJ", 5_000, proposal_id="jnj", consensus=None),
        ])
        check("cycle amont complété", cycle.status == CycleRunStatus.COMPLETED)
        ingest = service.ingest_cycle_result(cycle, ttl_hours=24)
        check("deux BUY Ramp approuvés créent demandes", len(ingest.created) == 2, str(ingest.to_dict()))
        check("JNJ en revue ne crée pas demande", any(x.get("proposal_id") == "jnj" for x in ingest.skipped))
        pending = service.list_pending()
        check("Pending Approvals contient deux éléments", len(pending) == 2)
        check("ordre Pending suit rank", [item.proposal_id for item in pending] == ["aapl", "jpm"])
        check("approval contient montant Ramp", pending[0].proposed_notional_eur == 5_000)
        check("approval est paper-only", pending[0].payload["execution"] == "NONE_PAPER_ONLY")

        duplicate = service.ingest_cycle_result(cycle, ttl_hours=24)
        check("ingestion idempotente ne recrée rien", len(duplicate.created) == 0 and len(duplicate.existing) == 2)

        approved = service.approve(pending[0].approval_id, "RichardGUELIN", "AAPL validée pour paper trading")
        check("approbation humaine persistée", approved.status == ApprovalStatus.APPROVED and approved.approved_by == "RichardGUELIN")
        check("approbation ne crée pas ordre broker", approved.payload["execution"] == "NONE_PAPER_ONLY")

        rejected = service.reject(pending[1].approval_id, "RichardGUELIN", "JPM non retenue ce cycle")
        check("refus humain persisté", rejected.status == ApprovalStatus.REJECTED and rejected.rejected_by == "RichardGUELIN")

        immutable_terminal = False
        try:
            service.approve(rejected.approval_id, "RichardGUELIN", "Tentative interdite")
        except ApprovalError:
            immutable_terminal = True
        check("statut terminal non modifiable", immutable_terminal)

        no_pending = service.list_pending()
        check("aucune demande pending après décisions", len(no_pending) == 0)

        cycle_sell = _run_cycle(store, "approval-cycle-002", [
            demo_proposal("BTC", 3_000, side="SELL", asset_class="CRYPTO", new=False,
                          proposal_id="btc-exit", risk_reducing=True, forced="RUNE_LONG_VETO"),
        ])
        ingest_sell = service.ingest_cycle_result(cycle_sell)
        check("vente réductrice ne crée pas approval achat", len(ingest_sell.created) == 0)
        check("vente réductrice est explicitement skip", ingest_sell.skipped[0]["reason"] == "SIDE_NOT_BUY")

        cycle_bad = _run_cycle(store, "approval-cycle-003", [
            demo_proposal("BAD", 0, proposal_id="bad", risk="RISK_REJECTED"),
        ])
        ingest_bad = service.ingest_cycle_result(cycle_bad)
        check("Risk Gate rejeté ne crée pas approval", len(ingest_bad.created) == 0)

        blocked = DailyCycleOrchestrator(store).run(
            demo_context("approval-cycle-004", regime="RISK_OFF"),
            [demo_proposal("AAPL", 5_000, proposal_id="aapl")],
        )
        ingest_blocked = service.ingest_cycle_result(blocked)
        check("cycle bloqué ne crée pas approval", len(ingest_blocked.created) == 0 and ingest_blocked.skipped[0]["reason"] == "CYCLE_NOT_COMPLETED")

        expiring_cycle = _run_cycle(store, "approval-cycle-005", [demo_proposal("MS", 5_000, proposal_id="ms")])
        expiring = service.ingest_cycle_result(expiring_cycle, ttl_hours=0.000001)
        check("demande expirable créée", len(expiring.created) == 1)
        expired_count = service.expire_due()
        expired = service.get(expiring.created[0].approval_id)
        check("expiration automatique persistée", expired_count >= 1 and expired.status == ApprovalStatus.EXPIRED)

        cancelled_cycle = _run_cycle(store, "approval-cycle-006", [demo_proposal("NVDA", 5_000, proposal_id="nvda")])
        cancelled = service.ingest_cycle_result(cancelled_cycle)
        cancelled_request = service.cancel(cancelled.created[0].approval_id, "RichardGUELIN", "Annulation test")
        check("annulation persistée", cancelled_request.status == ApprovalStatus.CANCELLED)

        audit = service.verify_audit_chain()
        check("audit approvals vérifiable", audit["valid"] and audit["events_checked"] >= 8, str(audit))

        serialized = json.dumps([item.to_dict() for item in service.list_history(limit=100)], ensure_ascii=False).lower()
        check("service ne contient aucun ordre broker", "broker_order" not in serialized and "send_order" not in serialized)

    print()
    print("-" * 84)
    if failures:
        print("ÉCHECS : %d/20" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("20/20 contrôles passent. Approval Service v1 prêt pour l'API Pending Approvals.")
    return 0


def demo(db_path: str = "data/thesium_approvals_demo.db") -> int:
    if os.path.exists(db_path):
        os.remove(db_path)
    store = PortfolioStateStore(db_path)
    seed_snapshot(store)
    service = ApprovalService(db_path)
    cycle = _run_cycle(store, "approval-demo-001", [
        demo_proposal("AAPL", 5_000, proposal_id="aapl"),
        demo_proposal("JPM", 5_000, proposal_id="jpm", conviction="NORMALE", consensus=0.90),
        demo_proposal("JNJ", 5_000, proposal_id="jnj", consensus=None),
    ])

    print("=" * 100)
    print("[APPROVAL_SERVICE_V1.0.0] démonstration paper-only")
    print("=" * 100)
    print("\n  Cycle : %s | statut : %s | allocation Ramp : %.2f€" % (
        cycle.cycle_id, cycle.status.value, cycle.approved_total_eur))

    ingest = service.ingest_cycle_result(cycle, requested_by="daily_orchestrator", ttl_hours=24)
    print("  Demandes créées : %d | existantes : %d | ignorées : %d" % (
        len(ingest.created), len(ingest.existing), len(ingest.skipped)))
    for request in service.list_pending():
        print("\n  #%d %-6s %-4s %-22s montant=%8.2f€ expires=%s" % (
            request.rank, request.ticker, request.side, request.status.value,
            request.proposed_notional_eur, request.expires_at))
        print("     bucket=%s score=%.4f risk=%s ramp=%s" % (
            request.bucket, request.ranking_score, request.risk_status, request.ramp_status))
        print("     motif=%s" % request.reason)

    if ingest.created:
        approved = service.approve(ingest.created[0].approval_id, "RichardGUELIN", "Validation démo paper-only")
        print("\n  Approbation : %s -> %s par %s; exécution=%s" % (
            approved.ticker, approved.status.value, approved.approved_by, approved.payload["execution"]))

    for skipped in ingest.skipped:
        print("  Ignorée : %(ticker)s / %(proposal_id)s -> %(reason)s" % skipped)

    print("\n  Audit : %s" % service.verify_audit_chain())
    print("  Base démonstration : %s" % db_path)
    return 0


def inspect(db_path: str) -> int:
    service = ApprovalService(db_path)
    service.initialize()
    payload = {
        "pending": [item.to_dict() for item in service.list_pending(include_expired=True)],
        "history": [item.to_dict() for item in service.list_history(limit=100)],
        "audit": service.verify_audit_chain(),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Approval Service v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    group.add_argument("--inspect", metavar="DATABASE")
    parser.add_argument("--db", default="data/thesium_approvals_demo.db", help="Base utilisée par --demo")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.demo:
        return demo(args.db)
    return inspect(args.inspect)


if __name__ == "__main__":
    sys.exit(main())
