#!/usr/bin/env python3
# portfolio_state.py
# [PORTFOLIO_STATE_V1.0.0]
"""Source de vérité SQLite pour le portefeuille et les phases THESIUM.

Rôle
----
Ce module persiste de manière transactionnelle et audit-able :
- snapshots NAV / cash / investi ;
- positions valorisées ;
- cycles de marché quotidiens validés ou invalidés ;
- évaluations de startup_phase_manager ;
- demandes, approbations, rejets et application de transitions de phase.

Il ne crée aucun ordre, aucun fill, aucune connexion broker et aucune exécution.

Dépendances runtime
-------------------
- Python standard library uniquement pour le stockage.
- startup_phase_manager.py est utilisé seulement par les démonstrations/adaptateurs.

Usage
-----
    from portfolio_state import PortfolioStateStore

    store = PortfolioStateStore("data/thesium.db")
    store.initialize()
    store.record_portfolio_snapshot(...)
    store.record_market_cycle(...)
    transition_id = store.request_phase_transition(...)
    store.approve_phase_transition(transition_id, "RichardGUELIN", "Justification")
    store.apply_approved_phase_transition(transition_id, "RichardGUELIN")

CLI
---
    py -3.13 portfolio_state.py --selftest
    py -3.13 portfolio_state.py --demo
    py -3.13 portfolio_state.py --inspect data/thesium.db
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


# ============================================================================
# CONSTANTES, ERREURS ET UTILITAIRES
# ============================================================================

SCHEMA_VERSION = "PORTFOLIO_STATE_V1.0.0"
DEFAULT_PHASE = "BOOTSTRAP"
VALID_PHASES = {
    "BOOTSTRAP", "OBSERVE", "RAMP_1", "RAMP_2", "STEADY_STATE", "PAUSED", "DE_RISK"
}
PROMOTABLE_PHASES = ("BOOTSTRAP", "OBSERVE", "RAMP_1", "RAMP_2", "STEADY_STATE")
PHASE_ORDER = ("BOOTSTRAP", "OBSERVE", "RAMP_1", "RAMP_2", "STEADY_STATE")
VALID_TRANSITION_STATES = {"REQUESTED", "APPROVED", "REJECTED", "APPLIED", "CANCELLED"}


class PortfolioStateError(RuntimeError):
    pass


class NotFoundError(PortfolioStateError):
    pass


class TransitionError(PortfolioStateError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _finite(value: Any, field_name: str, allow_zero: bool = True) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise PortfolioStateError("%s doit être numérique" % field_name) from exc
    if not math.isfinite(result):
        raise PortfolioStateError("%s doit être fini" % field_name)
    if result < 0 or (not allow_zero and result <= 0):
        comparator = "strictement positif" if not allow_zero else "positif ou nul"
        raise PortfolioStateError("%s doit être %s" % (field_name, comparator))
    return result


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


def canonical_json(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def payload_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _next_phase(phase: str) -> Optional[str]:
    phase = _upper(phase)
    if phase not in PHASE_ORDER:
        return None
    index = PHASE_ORDER.index(phase)
    return PHASE_ORDER[index + 1] if index + 1 < len(PHASE_ORDER) else None


def _validate_transition(source: str, target: str) -> None:
    source = _upper(source)
    target = _upper(target)
    if source not in VALID_PHASES or target not in VALID_PHASES:
        raise TransitionError("Phase source ou cible inconnue")
    if source == target:
        raise TransitionError("Une transition doit changer de phase")
    if target in ("PAUSED", "DE_RISK"):
        return
    if source in ("PAUSED", "DE_RISK"):
        raise TransitionError("Une sortie de PAUSED/DE_RISK exige une reprise explicite dédiée")
    expected = _next_phase(source)
    if target != expected:
        raise TransitionError("Transition interdite : %s -> %s; suivant autorisé : %s" % (source, target, expected or "aucun"))


# ============================================================================
# MODÈLES DE DONNÉES
# ============================================================================

@dataclass(frozen=True)
class PortfolioSnapshotInput:
    as_of: str
    nav_eur: float
    cash_eur: float
    invested_eur: float
    source: str = "manual"
    snapshot_id: str = ""
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionInput:
    ticker: str
    asset_class: str
    quantity: float
    market_price_eur: float
    average_cost_eur: float = 0.0
    market_value_eur: Optional[float] = None
    currency: str = "EUR"
    as_of: str = ""
    source: str = "manual"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketCycleInput:
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
    notes: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PhaseTransitionRequest:
    requested_target_phase: str
    requested_by: str
    reason: str
    assessment_id: str = ""
    request_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CurrentPortfolioState:
    snapshot_id: Optional[str]
    as_of: Optional[str]
    nav_eur: Optional[float]
    cash_eur: Optional[float]
    invested_eur: Optional[float]
    current_phase: str
    phase_started_at: Optional[str]
    phase_version: int
    policy_id: Optional[str]
    policy_version: Optional[str]
    policy_fingerprint: Optional[str]
    snapshot_source: Optional[str]
    position_count: int
    updated_at: Optional[str]


# ============================================================================
# SQLITE STORE
# ============================================================================

class PortfolioStateStore:
    """Stockage SQLite local, transactionnel et append-only pour les événements."""

    def __init__(self, db_path: str = "data/thesium.db"):
        self.db_path = str(db_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        directory = os.path.dirname(os.path.abspath(self.db_path))
        if directory:
            os.makedirs(directory, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        """Crée le schéma. Idempotent; ne modifie jamais les données existantes."""
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ps_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ps_portfolio_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    as_of TEXT NOT NULL,
                    nav_eur REAL NOT NULL CHECK(nav_eur >= 0),
                    cash_eur REAL NOT NULL CHECK(cash_eur >= 0),
                    invested_eur REAL NOT NULL CHECK(invested_eur >= 0),
                    source TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ps_snapshots_as_of
                    ON ps_portfolio_snapshots(as_of DESC, created_at DESC);

                CREATE TABLE IF NOT EXISTS ps_positions (
                    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    quantity REAL NOT NULL CHECK(quantity >= 0),
                    average_cost_eur REAL NOT NULL CHECK(average_cost_eur >= 0),
                    market_price_eur REAL NOT NULL CHECK(market_price_eur >= 0),
                    market_value_eur REAL NOT NULL CHECK(market_value_eur >= 0),
                    currency TEXT NOT NULL,
                    source TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    UNIQUE(snapshot_id, ticker),
                    FOREIGN KEY(snapshot_id) REFERENCES ps_portfolio_snapshots(snapshot_id)
                );
                CREATE INDEX IF NOT EXISTS ix_ps_positions_snapshot
                    ON ps_positions(snapshot_id, ticker);

                CREATE TABLE IF NOT EXISTS ps_phase_state (
                    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id = 1),
                    current_phase TEXT NOT NULL,
                    phase_started_at TEXT NOT NULL,
                    phase_version INTEGER NOT NULL CHECK(phase_version >= 1),
                    policy_id TEXT,
                    policy_version TEXT,
                    policy_fingerprint TEXT,
                    source_transition_id TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ps_phase_transitions (
                    transition_id TEXT PRIMARY KEY,
                    source_phase TEXT NOT NULL,
                    target_phase TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('REQUESTED','APPROVED','REJECTED','APPLIED','CANCELLED')),
                    requested_by TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    request_reason TEXT NOT NULL,
                    assessment_id TEXT,
                    request_metadata_json TEXT NOT NULL DEFAULT '{}',
                    approved_by TEXT,
                    approved_at TEXT,
                    approval_note TEXT,
                    rejected_by TEXT,
                    rejected_at TEXT,
                    rejection_note TEXT,
                    applied_by TEXT,
                    applied_at TEXT,
                    application_note TEXT,
                    policy_id TEXT,
                    policy_version TEXT,
                    policy_fingerprint TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ps_transitions_status
                    ON ps_phase_transitions(status, requested_at DESC);

                CREATE TABLE IF NOT EXISTS ps_market_cycles (
                    cycle_id TEXT PRIMARY KEY,
                    trading_date TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    market_session_completed INTEGER,
                    market_data_fresh INTEGER,
                    pipeline_completed INTEGER,
                    paper_fills_reconciled INTEGER,
                    critical_incidents_open INTEGER CHECK(critical_incidents_open >= 0),
                    status TEXT NOT NULL,
                    policy_version TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    payload_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ps_cycles_phase_date
                    ON ps_market_cycles(phase, trading_date DESC);

                CREATE TABLE IF NOT EXISTS ps_phase_assessments (
                    assessment_id TEXT PRIMARY KEY,
                    assessed_at TEXT NOT NULL,
                    current_phase TEXT NOT NULL,
                    recommended_phase TEXT NOT NULL,
                    next_phase TEXT,
                    action TEXT NOT NULL,
                    promotion_eligible INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    deployment_pct_target REAL,
                    invested_pct_nav REAL,
                    cash_pct_nav REAL,
                    valid_cycles_in_current_phase INTEGER NOT NULL,
                    required_cycles_for_next_phase INTEGER,
                    policy_id TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    policy_fingerprint TEXT NOT NULL,
                    effective_regime TEXT NOT NULL,
                    assessment_json TEXT NOT NULL,
                    input_snapshot_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ps_assessments_at
                    ON ps_phase_assessments(assessed_at DESC);

                CREATE TABLE IF NOT EXISTS ps_audit_log (
                    audit_id TEXT PRIMARY KEY,
                    event_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    payload_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ix_ps_audit_entity
                    ON ps_audit_log(entity_type, entity_id, event_at DESC);
                """
            )
            now = utc_now()
            conn.execute(
                "INSERT OR IGNORE INTO ps_meta(key, value, updated_at) VALUES (?, ?, ?)",
                ("schema_version", SCHEMA_VERSION, now),
            )
            conn.execute(
                """INSERT OR IGNORE INTO ps_phase_state(
                    singleton_id, current_phase, phase_started_at, phase_version, updated_at
                ) VALUES (1, ?, ?, 1, ?)""",
                (DEFAULT_PHASE, now, now),
            )

    # ------------------------------------------------------------------
    # Snapshots et positions
    # ------------------------------------------------------------------

    def record_portfolio_snapshot(
        self,
        snapshot: PortfolioSnapshotInput,
        positions: Sequence[PositionInput] = (),
        actor: str = "system",
    ) -> str:
        """Insère un snapshot immuable et ses positions, dans une transaction unique."""
        self.initialize()
        nav = _finite(snapshot.nav_eur, "nav_eur")
        cash = _finite(snapshot.cash_eur, "cash_eur")
        invested = _finite(snapshot.invested_eur, "invested_eur")
        if nav <= 0:
            raise PortfolioStateError("nav_eur doit être strictement positif")
        if cash > nav * 1.01 or invested > nav * 1.50:
            raise PortfolioStateError("Snapshot incohérent : cash/investi dépasse des bornes raisonnables")
        snapshot_id = snapshot.snapshot_id.strip() or self._new_id("snapshot")
        as_of = self._required_text(snapshot.as_of, "as_of")
        source = self._required_text(snapshot.source, "source")
        normalized_positions = [self._normalize_position(pos, snapshot_id, as_of) for pos in positions]
        tickers = [row["ticker"] for row in normalized_positions]
        if len(tickers) != len(set(tickers)):
            raise PortfolioStateError("Une position ticker ne peut apparaître qu'une fois par snapshot")

        payload = {"snapshot": asdict(snapshot), "positions": [asdict(pos) for pos in positions]}
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO ps_portfolio_snapshots(
                    snapshot_id, as_of, nav_eur, cash_eur, invested_eur, source,
                    notes, metadata_json, payload_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    snapshot_id, as_of, nav, cash, invested, source, snapshot.notes or "",
                    canonical_json(snapshot.metadata), payload_hash(payload), now,
                ),
            )
            for row in normalized_positions:
                conn.execute(
                    """INSERT INTO ps_positions(
                        snapshot_id, ticker, asset_class, quantity, average_cost_eur,
                        market_price_eur, market_value_eur, currency, source,
                        metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        snapshot_id, row["ticker"], row["asset_class"], row["quantity"],
                        row["average_cost_eur"], row["market_price_eur"], row["market_value_eur"],
                        row["currency"], row["source"], canonical_json(row["metadata"]), now,
                    ),
                )
            self._audit(conn, actor, "PORTFOLIO_SNAPSHOT_RECORDED", "portfolio_snapshot", snapshot_id, payload)
        return snapshot_id

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM ps_portfolio_snapshots ORDER BY as_of DESC, created_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["metadata"] = json.loads(result.pop("metadata_json"))
            result["positions"] = self._positions_for_snapshot(conn, result["snapshot_id"])
            return result

    def get_positions(self, snapshot_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.initialize()
        with self._connection() as conn:
            if snapshot_id is None:
                latest = conn.execute(
                    "SELECT snapshot_id FROM ps_portfolio_snapshots ORDER BY as_of DESC, created_at DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    return []
                snapshot_id = latest["snapshot_id"]
            return self._positions_for_snapshot(conn, snapshot_id)

    # ------------------------------------------------------------------
    # Cycles et évaluations
    # ------------------------------------------------------------------

    def record_market_cycle(self, cycle: MarketCycleInput, actor: str = "system") -> str:
        """Crée un cycle. Un cycle existant ne peut être écrasé silencieusement."""
        self.initialize()
        cycle_id = self._required_text(cycle.cycle_id, "cycle_id")
        phase = _upper(cycle.phase)
        if phase not in VALID_PHASES:
            raise PortfolioStateError("Phase de cycle invalide : %s" % phase)
        status = self._required_text(cycle.status, "status").upper()
        trading_date = self._required_text(cycle.trading_date, "trading_date")
        incidents = self._nullable_nonnegative_int(cycle.critical_incidents_open, "critical_incidents_open")
        payload = asdict(cycle)
        now = utc_now()
        with self._connection() as conn:
            try:
                conn.execute(
                    """INSERT INTO ps_market_cycles(
                        cycle_id, trading_date, phase, market_session_completed,
                        market_data_fresh, pipeline_completed, paper_fills_reconciled,
                        critical_incidents_open, status, policy_version, notes,
                        payload_json, payload_hash, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        cycle_id, trading_date, phase,
                        self._nullable_bool(cycle.market_session_completed),
                        self._nullable_bool(cycle.market_data_fresh),
                        self._nullable_bool(cycle.pipeline_completed),
                        self._nullable_bool(cycle.paper_fills_reconciled),
                        incidents, status, cycle.policy_version or "", cycle.notes or "",
                        canonical_json(cycle.payload), payload_hash(payload), now, now,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise PortfolioStateError("cycle_id déjà enregistré : %s" % cycle_id) from exc
            self._audit(conn, actor, "MARKET_CYCLE_RECORDED", "market_cycle", cycle_id, payload)
        return cycle_id

    def list_market_cycles(self, phase: Optional[str] = None, limit: int = 250) -> List[Dict[str, Any]]:
        self.initialize()
        limit = max(1, min(int(limit), 10_000))
        with self._connection() as conn:
            if phase is None:
                rows = conn.execute(
                    "SELECT * FROM ps_market_cycles ORDER BY trading_date DESC, created_at DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                phase = _upper(phase)
                rows = conn.execute(
                    "SELECT * FROM ps_market_cycles WHERE phase = ? ORDER BY trading_date DESC, created_at DESC LIMIT ?",
                    (phase, limit),
                ).fetchall()
            return [self._cycle_row(row) for row in rows]

    def get_cycle_records_for_phase_manager(self, phase: Optional[str] = None, limit: int = 250) -> List[Any]:
        """Retourne des CycleRecord si startup_phase_manager est disponible; sinon des dicts."""
        rows = self.list_market_cycles(phase=phase, limit=limit)
        try:
            from startup_phase_manager import CycleRecord
            return [
                CycleRecord(
                    cycle_id=row["cycle_id"], trading_date=row["trading_date"], phase=row["phase"],
                    market_session_completed=self._from_db_bool(row["market_session_completed"]),
                    market_data_fresh=self._from_db_bool(row["market_data_fresh"]),
                    pipeline_completed=self._from_db_bool(row["pipeline_completed"]),
                    paper_fills_reconciled=self._from_db_bool(row["paper_fills_reconciled"]),
                    critical_incidents_open=row["critical_incidents_open"], status=row["status"],
                    policy_version=row["policy_version"],
                )
                for row in rows
            ]
        except ImportError:
            return rows

    def record_phase_assessment(self, assessment: Any, actor: str = "system", assessment_id: str = "") -> str:
        """Persiste une sortie de StartupPhaseManager, sans en modifier le contenu."""
        self.initialize()
        data = _json_safe(assessment)
        if not isinstance(data, dict):
            raise PortfolioStateError("assessment doit être dataclass ou mapping")
        required = [
            "current_phase", "recommended_phase", "action", "promotion_eligible", "reason",
            "valid_cycles_in_current_phase", "policy_id", "policy_version",
            "policy_fingerprint", "effective_regime", "input_snapshot_hash",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            raise PortfolioStateError("Assessment incomplet : %s" % ", ".join(missing))
        identifier = assessment_id.strip() or self._new_id("assessment")
        now = utc_now()
        with self._connection() as conn:
            conn.execute(
                """INSERT INTO ps_phase_assessments(
                    assessment_id, assessed_at, current_phase, recommended_phase, next_phase,
                    action, promotion_eligible, reason, deployment_pct_target,
                    invested_pct_nav, cash_pct_nav, valid_cycles_in_current_phase,
                    required_cycles_for_next_phase, policy_id, policy_version,
                    policy_fingerprint, effective_regime, assessment_json,
                    input_snapshot_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    identifier, now, _upper(data["current_phase"]), _upper(data["recommended_phase"]),
                    data.get("next_phase"), str(data["action"]), int(bool(data["promotion_eligible"])),
                    str(data["reason"]), data.get("deployment_pct_target"), data.get("invested_pct_nav"),
                    data.get("cash_pct_nav"), int(data["valid_cycles_in_current_phase"]),
                    data.get("required_cycles_for_next_phase"), str(data["policy_id"]),
                    str(data["policy_version"]), str(data["policy_fingerprint"]),
                    _upper(data["effective_regime"]), canonical_json(data),
                    str(data["input_snapshot_hash"]), now,
                ),
            )
            self._audit(conn, actor, "PHASE_ASSESSMENT_RECORDED", "phase_assessment", identifier, data)
        return identifier

    def get_latest_phase_assessment(self) -> Optional[Dict[str, Any]]:
        self.initialize()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM ps_phase_assessments ORDER BY assessed_at DESC, created_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["assessment"] = json.loads(result.pop("assessment_json"))
            result["promotion_eligible"] = bool(result["promotion_eligible"])
            return result

    # ------------------------------------------------------------------
    # Transitions humaines de phase
    # ------------------------------------------------------------------

    def request_phase_transition(self, request: PhaseTransitionRequest) -> str:
        """Enregistre une demande; ne change jamais la phase active."""
        self.initialize()
        target = _upper(request.requested_target_phase)
        requester = self._required_text(request.requested_by, "requested_by")
        reason = self._required_text(request.reason, "reason")
        transition_id = request.request_id.strip() or self._new_id("transition")
        now = utc_now()
        with self._connection() as conn:
            state = self._phase_state_row(conn)
            source = state["current_phase"]
            _validate_transition(source, target)
            self._assert_no_open_transition(conn)
            if request.assessment_id:
                assessment = conn.execute(
                    "SELECT * FROM ps_phase_assessments WHERE assessment_id = ?", (request.assessment_id,)
                ).fetchone()
                if assessment is None:
                    raise NotFoundError("Assessment introuvable : %s" % request.assessment_id)
                if not bool(assessment["promotion_eligible"]):
                    raise TransitionError("Assessment non éligible à une promotion")
                if _upper(assessment["current_phase"]) != source or _upper(assessment["next_phase"]) != target:
                    raise TransitionError("Assessment incompatible avec la transition demandée")
            conn.execute(
                """INSERT INTO ps_phase_transitions(
                    transition_id, source_phase, target_phase, status, requested_by,
                    requested_at, request_reason, assessment_id, request_metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, 'REQUESTED', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    transition_id, source, target, requester, now, reason,
                    request.assessment_id or None, canonical_json(request.metadata), now, now,
                ),
            )
            self._audit(
                conn, requester, "PHASE_TRANSITION_REQUESTED", "phase_transition", transition_id,
                {"source_phase": source, "target_phase": target, "reason": reason, "assessment_id": request.assessment_id},
            )
        return transition_id

    def approve_phase_transition(
        self,
        transition_id: str,
        approved_by: str,
        approval_note: str,
        policy_id: str = "",
        policy_version: str = "",
        policy_fingerprint: str = "",
    ) -> None:
        """Approbation humaine explicite. L'application reste une opération séparée."""
        self.initialize()
        approver = self._required_text(approved_by, "approved_by")
        note = self._required_text(approval_note, "approval_note")
        now = utc_now()
        with self._connection() as conn:
            row = self._transition_row(conn, transition_id)
            if row["status"] != "REQUESTED":
                raise TransitionError("Seule une transition REQUESTED peut être approuvée")
            state = self._phase_state_row(conn)
            if row["source_phase"] != state["current_phase"]:
                raise TransitionError("La phase active a changé depuis la demande")
            _validate_transition(row["source_phase"], row["target_phase"])
            conn.execute(
                """UPDATE ps_phase_transitions
                   SET status='APPROVED', approved_by=?, approved_at=?, approval_note=?,
                       policy_id=?, policy_version=?, policy_fingerprint=?, updated_at=?
                   WHERE transition_id=?""",
                (approver, now, note, policy_id or None, policy_version or None,
                 policy_fingerprint or None, now, transition_id),
            )
            self._audit(
                conn, approver, "PHASE_TRANSITION_APPROVED", "phase_transition", transition_id,
                {"approval_note": note, "policy_id": policy_id, "policy_version": policy_version,
                 "policy_fingerprint": policy_fingerprint},
            )

    def reject_phase_transition(self, transition_id: str, rejected_by: str, rejection_note: str) -> None:
        self.initialize()
        actor = self._required_text(rejected_by, "rejected_by")
        note = self._required_text(rejection_note, "rejection_note")
        now = utc_now()
        with self._connection() as conn:
            row = self._transition_row(conn, transition_id)
            if row["status"] != "REQUESTED":
                raise TransitionError("Seule une transition REQUESTED peut être rejetée")
            conn.execute(
                """UPDATE ps_phase_transitions
                   SET status='REJECTED', rejected_by=?, rejected_at=?, rejection_note=?, updated_at=?
                   WHERE transition_id=?""",
                (actor, now, note, now, transition_id),
            )
            self._audit(conn, actor, "PHASE_TRANSITION_REJECTED", "phase_transition", transition_id,
                        {"rejection_note": note})

    def cancel_phase_transition(self, transition_id: str, cancelled_by: str, cancellation_note: str) -> None:
        self.initialize()
        actor = self._required_text(cancelled_by, "cancelled_by")
        note = self._required_text(cancellation_note, "cancellation_note")
        now = utc_now()
        with self._connection() as conn:
            row = self._transition_row(conn, transition_id)
            if row["status"] not in {"REQUESTED", "APPROVED"}:
                raise TransitionError("Seule une transition REQUESTED ou APPROVED peut être annulée")
            conn.execute(
                "UPDATE ps_phase_transitions SET status='CANCELLED', updated_at=? WHERE transition_id=?",
                (now, transition_id),
            )
            self._audit(conn, actor, "PHASE_TRANSITION_CANCELLED", "phase_transition", transition_id,
                        {"cancellation_note": note})

    def apply_approved_phase_transition(
        self,
        transition_id: str,
        applied_by: str,
        application_note: str = "",
    ) -> CurrentPortfolioState:
        """Applique atomiquement une transition APPROVED à l'état singleton.

        Cette opération ne peut être appelée qu'après approbation humaine explicite.
        Elle ne correspond à aucun ordre de marché.
        """
        self.initialize()
        actor = self._required_text(applied_by, "applied_by")
        now = utc_now()
        with self._connection() as conn:
            transition = self._transition_row(conn, transition_id)
            if transition["status"] != "APPROVED":
                raise TransitionError("Seule une transition APPROVED peut être appliquée")
            state = self._phase_state_row(conn)
            if transition["source_phase"] != state["current_phase"]:
                raise TransitionError("La phase active a changé avant application")
            _validate_transition(transition["source_phase"], transition["target_phase"])
            new_version = int(state["phase_version"]) + 1
            conn.execute(
                """UPDATE ps_phase_state
                   SET current_phase=?, phase_started_at=?, phase_version=?,
                       policy_id=?, policy_version=?, policy_fingerprint=?,
                       source_transition_id=?, updated_at=?
                   WHERE singleton_id=1""",
                (
                    transition["target_phase"], now, new_version,
                    transition["policy_id"], transition["policy_version"],
                    transition["policy_fingerprint"], transition_id, now,
                ),
            )
            conn.execute(
                """UPDATE ps_phase_transitions
                   SET status='APPLIED', applied_by=?, applied_at=?, application_note=?, updated_at=?
                   WHERE transition_id=?""",
                (actor, now, application_note or "", now, transition_id),
            )
            self._audit(
                conn, actor, "PHASE_TRANSITION_APPLIED", "phase_transition", transition_id,
                {"source_phase": transition["source_phase"], "target_phase": transition["target_phase"],
                 "application_note": application_note or "", "phase_version": new_version},
            )
        return self.get_current_portfolio_state()

    def request_safety_transition(
        self,
        target_phase: str,
        requested_by: str,
        reason: str,
        assessment_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Demande une transition vers PAUSED/DE_RISK; elle requiert aussi approbation puis application."""
        target = _upper(target_phase)
        if target not in {"PAUSED", "DE_RISK"}:
            raise TransitionError("Safety transition cible uniquement PAUSED ou DE_RISK")
        return self.request_phase_transition(
            PhaseTransitionRequest(
                requested_target_phase=target,
                requested_by=requested_by,
                reason=reason,
                assessment_id=assessment_id,
                metadata=metadata or {},
            )
        )

    def list_phase_transitions(self, limit: int = 100) -> List[Dict[str, Any]]:
        self.initialize()
        limit = max(1, min(int(limit), 10_000))
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM ps_phase_transitions ORDER BY requested_at DESC, created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [self._transition_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # États dérivés pour les moteurs amont
    # ------------------------------------------------------------------

    def get_current_portfolio_state(self) -> CurrentPortfolioState:
        self.initialize()
        with self._connection() as conn:
            state = self._phase_state_row(conn)
            snapshot = conn.execute(
                "SELECT * FROM ps_portfolio_snapshots ORDER BY as_of DESC, created_at DESC LIMIT 1"
            ).fetchone()
            position_count = 0
            if snapshot is not None:
                position_count = int(conn.execute(
                    "SELECT COUNT(*) AS n FROM ps_positions WHERE snapshot_id=? AND quantity > 0",
                    (snapshot["snapshot_id"],),
                ).fetchone()["n"])
            return CurrentPortfolioState(
                snapshot_id=None if snapshot is None else snapshot["snapshot_id"],
                as_of=None if snapshot is None else snapshot["as_of"],
                nav_eur=None if snapshot is None else snapshot["nav_eur"],
                cash_eur=None if snapshot is None else snapshot["cash_eur"],
                invested_eur=None if snapshot is None else snapshot["invested_eur"],
                current_phase=state["current_phase"],
                phase_started_at=state["phase_started_at"],
                phase_version=state["phase_version"],
                policy_id=state["policy_id"],
                policy_version=state["policy_version"],
                policy_fingerprint=state["policy_fingerprint"],
                snapshot_source=None if snapshot is None else snapshot["source"],
                position_count=position_count,
                updated_at=state["updated_at"],
            )

    def get_phase_portfolio_state(self, regime: str = "RISK_ON", current_phase_human_approved: bool = True) -> Any:
        """Adaptateur optionnel prêt pour StartupPhaseManager.PhasePortfolioState."""
        current = self.get_current_portfolio_state()
        if current.nav_eur is None or current.cash_eur is None or current.invested_eur is None:
            raise PortfolioStateError("Aucun snapshot portefeuille disponible")
        target = self._strategic_target_from_latest_assessment()
        if target is None:
            raise PortfolioStateError("Cible stratégique inconnue : enregistrez-la dans metadata.strategic_target_invested_eur du snapshot")
        try:
            from startup_phase_manager import PhasePortfolioState
            return PhasePortfolioState(
                nav_eur=current.nav_eur, cash_eur=current.cash_eur, invested_eur=current.invested_eur,
                strategic_target_invested_eur=target, current_phase=current.current_phase,
                phase_started_at=current.phase_started_at or "", regime=_upper(regime),
                current_phase_human_approved=current_phase_human_approved,
            )
        except ImportError:
            return {
                "nav_eur": current.nav_eur, "cash_eur": current.cash_eur, "invested_eur": current.invested_eur,
                "strategic_target_invested_eur": target, "current_phase": current.current_phase,
                "phase_started_at": current.phase_started_at, "regime": _upper(regime),
                "current_phase_human_approved": current_phase_human_approved,
            }

    def get_ramp_portfolio_state(
        self,
        strategic_target_invested_eur: Optional[float] = None,
        regime: str = "RISK_ON",
        cycle_net_buys_eur: float = 0.0,
        cycle_asset_class_net_buys_eur: float = 0.0,
        cycle_new_positions: int = 0,
        phase_human_approved: bool = True,
    ) -> Any:
        """Adaptateur optionnel prêt pour StartupRamp.RampPortfolio."""
        current = self.get_current_portfolio_state()
        if current.nav_eur is None or current.invested_eur is None:
            raise PortfolioStateError("Aucun snapshot portefeuille disponible")
        target = strategic_target_invested_eur or self._strategic_target_from_latest_assessment()
        if target is None:
            raise PortfolioStateError("Cible stratégique investie absente")
        cycle_count = self.count_valid_cycles_in_current_phase()
        try:
            from startup_ramp import RampPortfolio
            return RampPortfolio(
                nav_eur=current.nav_eur, invested_eur=current.invested_eur,
                strategic_target_invested_eur=float(target), phase=current.current_phase,
                regime=_upper(regime), cycle_net_buys_eur=float(cycle_net_buys_eur),
                cycle_asset_class_net_buys_eur=float(cycle_asset_class_net_buys_eur),
                cycle_new_positions=int(cycle_new_positions),
                completed_open_cycles_in_phase=cycle_count,
                phase_human_approved=phase_human_approved,
            )
        except ImportError:
            return {
                "nav_eur": current.nav_eur, "invested_eur": current.invested_eur,
                "strategic_target_invested_eur": float(target), "phase": current.current_phase,
                "regime": _upper(regime), "cycle_net_buys_eur": float(cycle_net_buys_eur),
                "cycle_asset_class_net_buys_eur": float(cycle_asset_class_net_buys_eur),
                "cycle_new_positions": int(cycle_new_positions),
                "completed_open_cycles_in_phase": cycle_count,
                "phase_human_approved": phase_human_approved,
            }

    def count_valid_cycles_in_current_phase(self) -> int:
        current = self.get_current_portfolio_state()
        cycles = self.get_cycle_records_for_phase_manager(phase=current.current_phase, limit=10_000)
        try:
            from startup_phase_manager import StartupPhaseManager
            policy_path = "startup_policy_v1.json"
            if not os.path.exists(policy_path):
                return 0
            manager = StartupPhaseManager.from_file(policy_path)
            return sum(1 for cycle in cycles if manager.is_valid_cycle(cycle, current.current_phase)[0])
        except ImportError:
            return 0

    def verify_audit_chain(self) -> Dict[str, Any]:
        """Vérifie que les hashes d'événements existent et que les entités critiques sont lisibles."""
        self.initialize()
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM ps_audit_log ORDER BY event_at, audit_id").fetchall()
            errors: List[str] = []
            for row in rows:
                if len(row["payload_hash"]) != 64:
                    errors.append("Hash invalide audit_id=%s" % row["audit_id"])
                try:
                    payload = json.loads(row["payload_json"])
                except json.JSONDecodeError:
                    errors.append("JSON invalide audit_id=%s" % row["audit_id"])
                    continue
                if payload_hash(payload) != row["payload_hash"]:
                    errors.append("Hash non concordant audit_id=%s" % row["audit_id"])
            return {"valid": not errors, "events_checked": len(rows), "errors": errors}

    # ------------------------------------------------------------------
    # Internes SQLite
    # ------------------------------------------------------------------

    @staticmethod
    def _new_id(prefix: str) -> str:
        return "%s_%s" % (prefix, uuid.uuid4().hex)

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise PortfolioStateError("%s est obligatoire" % field_name)
        return text

    @staticmethod
    def _nullable_bool(value: Optional[bool]) -> Optional[int]:
        if value is None:
            return None
        if not isinstance(value, bool):
            raise PortfolioStateError("Booléen attendu")
        return int(value)

    @staticmethod
    def _from_db_bool(value: Optional[int]) -> Optional[bool]:
        return None if value is None else bool(value)

    @staticmethod
    def _nullable_nonnegative_int(value: Optional[int], field_name: str) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            raise PortfolioStateError("%s doit être entier" % field_name)
        try:
            result = int(value)
        except (ValueError, TypeError) as exc:
            raise PortfolioStateError("%s doit être entier" % field_name) from exc
        if result < 0:
            raise PortfolioStateError("%s doit être positif ou nul" % field_name)
        return result

    @staticmethod
    def _normalize_position(position: PositionInput, snapshot_id: str, as_of: str) -> Dict[str, Any]:
        ticker = str(position.ticker).strip().upper()
        if not ticker:
            raise PortfolioStateError("ticker position obligatoire")
        asset_class = str(position.asset_class).strip().upper()
        if not asset_class:
            raise PortfolioStateError("asset_class position obligatoire")
        quantity = _finite(position.quantity, "quantity")
        price = _finite(position.market_price_eur, "market_price_eur")
        avg = _finite(position.average_cost_eur, "average_cost_eur")
        market_value = quantity * price if position.market_value_eur is None else _finite(position.market_value_eur, "market_value_eur")
        return {
            "snapshot_id": snapshot_id,
            "as_of": position.as_of or as_of,
            "ticker": ticker,
            "asset_class": asset_class,
            "quantity": quantity,
            "average_cost_eur": avg,
            "market_price_eur": price,
            "market_value_eur": market_value,
            "currency": str(position.currency or "EUR").strip().upper(),
            "source": str(position.source or "manual").strip(),
            "metadata": dict(position.metadata or {}),
        }

    @staticmethod
    def _positions_for_snapshot(conn: sqlite3.Connection, snapshot_id: str) -> List[Dict[str, Any]]:
        rows = conn.execute(
            "SELECT * FROM ps_positions WHERE snapshot_id=? ORDER BY market_value_eur DESC, ticker", (snapshot_id,)
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json"))
            result.append(item)
        return result

    @staticmethod
    def _cycle_row(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        for key in ("market_session_completed", "market_data_fresh", "pipeline_completed", "paper_fills_reconciled"):
            item[key] = None if item[key] is None else bool(item[key])
        return item

    @staticmethod
    def _transition_dict(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["request_metadata"] = json.loads(item.pop("request_metadata_json"))
        return item

    @staticmethod
    def _phase_state_row(conn: sqlite3.Connection) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM ps_phase_state WHERE singleton_id=1").fetchone()
        if row is None:
            raise PortfolioStateError("État de phase absent; appelez initialize()")
        return row

    @staticmethod
    def _transition_row(conn: sqlite3.Connection, transition_id: str) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM ps_phase_transitions WHERE transition_id=?", (transition_id,)).fetchone()
        if row is None:
            raise NotFoundError("Transition introuvable : %s" % transition_id)
        return row

    @staticmethod
    def _assert_no_open_transition(conn: sqlite3.Connection) -> None:
        row = conn.execute(
            "SELECT transition_id FROM ps_phase_transitions WHERE status IN ('REQUESTED','APPROVED') LIMIT 1"
        ).fetchone()
        if row is not None:
            raise TransitionError("Transition ouverte existante : %s" % row["transition_id"])

    @staticmethod
    def _audit(
        conn: sqlite3.Connection,
        actor: str,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: Any,
    ) -> None:
        now = utc_now()
        encoded = canonical_json(payload)
        conn.execute(
            """INSERT INTO ps_audit_log(
                audit_id, event_at, actor, event_type, entity_type, entity_id, payload_json, payload_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("audit_" + uuid.uuid4().hex, now, actor or "system", event_type, entity_type,
             entity_id, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest()),
        )

    def _strategic_target_from_latest_assessment(self) -> Optional[float]:
        latest = self.get_latest_snapshot()
        if latest is None:
            return None
        metadata = latest.get("metadata", {})
        target = metadata.get("strategic_target_invested_eur")
        if target is None:
            return None
        try:
            return _finite(target, "strategic_target_invested_eur", allow_zero=False)
        except PortfolioStateError:
            return None


# ============================================================================
# DÉMONSTRATION ET TESTS
# ============================================================================

def _healthy_cycle(cycle_id: str, phase: str = "BOOTSTRAP", day: str = "2026-09-04") -> MarketCycleInput:
    return MarketCycleInput(
        cycle_id=cycle_id, trading_date=day, phase=phase,
        market_session_completed=True, market_data_fresh=True, pipeline_completed=True,
        paper_fills_reconciled=True, critical_incidents_open=0, status="COMPLETED",
        policy_version="1.0.0",
    )


def selftest() -> int:
    print("=" * 84)
    print("[PORTFOLIO_STATE_V1.0.0] autotest — source de vérité SQLite")
    print("=" * 84)
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", ("  " + detail) if detail and not condition else ""))
        if not condition:
            failures.append(name)

    with tempfile.TemporaryDirectory() as directory:
        db = os.path.join(directory, "thesium_test.db")
        store = PortfolioStateStore(db)
        store.initialize()
        state = store.get_current_portfolio_state()
        check("initialisation crée BOOTSTRAP", state.current_phase == "BOOTSTRAP" and state.phase_version == 1)
        check("base SQLite créée", os.path.exists(db) and os.path.getsize(db) > 0)

        snapshot_id = store.record_portfolio_snapshot(
            PortfolioSnapshotInput(
                as_of="2026-09-04T18:00:00+00:00", nav_eur=1_000_000, cash_eur=1_000_000,
                invested_eur=0, source="selftest",
                metadata={"strategic_target_invested_eur": 600_000},
            ),
            actor="selftest",
        )
        latest = store.get_latest_snapshot()
        check("snapshot enregistré", latest is not None and latest["snapshot_id"] == snapshot_id)
        check("métadonnée stratégique persistée", latest is not None and latest["metadata"]["strategic_target_invested_eur"] == 600_000)
        check("lancement a zéro position", store.get_current_portfolio_state().position_count == 0)

        pos_snapshot = store.record_portfolio_snapshot(
            PortfolioSnapshotInput(
                as_of="2026-09-05T18:00:00+00:00", nav_eur=1_002_000, cash_eur=997_000,
                invested_eur=5_000, source="selftest",
                metadata={"strategic_target_invested_eur": 600_000},
            ),
            [PositionInput("AAPL", "EQUITY", 20, 250, 240, source="selftest")],
            actor="selftest",
        )
        positions = store.get_positions(pos_snapshot)
        check("position AAPL persistée", len(positions) == 1 and positions[0]["ticker"] == "AAPL")
        check("valeur position calculée", len(positions) == 1 and abs(positions[0]["market_value_eur"] - 5000) < 0.01)
        check("position_count dérivé", store.get_current_portfolio_state().position_count == 1)

        duplicate_rejected = False
        try:
            store.record_portfolio_snapshot(
                PortfolioSnapshotInput(as_of="2026-09-06", nav_eur=1_000, cash_eur=0, invested_eur=1_000, source="test"),
                [PositionInput("AAPL", "EQUITY", 1, 1), PositionInput("aapl", "EQUITY", 1, 1)],
            )
        except PortfolioStateError:
            duplicate_rejected = True
        check("tickers dupliqués refusés", duplicate_rejected)

        for number in range(1, 6):
            store.record_market_cycle(_healthy_cycle("bootstrap-%d" % number, day="2026-09-%02d" % number), actor="selftest")
        cycle_rows = store.list_market_cycles("BOOTSTRAP")
        check("cinq cycles enregistrés", len(cycle_rows) == 5)
        adapter_records = store.get_cycle_records_for_phase_manager("BOOTSTRAP")
        check("adaptateur CycleRecord disponible", len(adapter_records) == 5)

        assessment_id = store.record_phase_assessment({
            "current_phase": "BOOTSTRAP", "recommended_phase": "OBSERVE", "next_phase": "OBSERVE",
            "action": "REQUEST_PROMOTION", "promotion_eligible": True,
            "reason": "Test de promotion", "deployment_pct_target": 20.0,
            "invested_pct_nav": 0.5, "cash_pct_nav": 99.5,
            "valid_cycles_in_current_phase": 5, "required_cycles_for_next_phase": 5,
            "policy_id": "STARTUP_POLICY_V1", "policy_version": "1.0.0",
            "policy_fingerprint": "a" * 64, "effective_regime": "RISK_ON",
            "input_snapshot_hash": "b" * 64,
        }, actor="selftest")
        check("assessment persistée", store.get_latest_phase_assessment()["assessment_id"] == assessment_id)

        tid = store.request_phase_transition(
            PhaseTransitionRequest("OBSERVE", "selftest", "5 séances valides", assessment_id=assessment_id)
        )
        check("transition BOOTSTRAP->OBSERVE demandée", store.list_phase_transitions()[0]["status"] == "REQUESTED")
        unchanged = store.get_current_portfolio_state()
        check("demande ne change pas la phase", unchanged.current_phase == "BOOTSTRAP")

        open_transition_rejected = False
        try:
            store.request_phase_transition(PhaseTransitionRequest("PAUSED", "selftest", "Ne doit pas passer"))
        except TransitionError:
            open_transition_rejected = True
        check("une seule transition ouverte", open_transition_rejected)

        store.approve_phase_transition(tid, "RichardGUELIN", "Contrôles vérifiés", "STARTUP_POLICY_V1", "1.0.0", "c" * 64)
        check("approbation humaine persistée", store.list_phase_transitions()[0]["status"] == "APPROVED")
        applied = store.apply_approved_phase_transition(tid, "RichardGUELIN", "Activation OBSERVE")
        check("transition approuvée appliquée", applied.current_phase == "OBSERVE" and applied.phase_version == 2)
        check("transition finale APPLIED", store.list_phase_transitions()[0]["status"] == "APPLIED")

        jump_rejected = False
        try:
            store.request_phase_transition(PhaseTransitionRequest("RAMP_2", "selftest", "Saut interdit"))
        except TransitionError:
            jump_rejected = True
        check("saut OBSERVE->RAMP_2 refusé", jump_rejected)

        pause_id = store.request_safety_transition("PAUSED", "risk_monitor", "RISK_OFF")
        store.approve_phase_transition(pause_id, "RichardGUELIN", "Pause validée")
        paused = store.apply_approved_phase_transition(pause_id, "RichardGUELIN")
        check("transition de sécurité vers PAUSED", paused.current_phase == "PAUSED")

        no_resume = False
        try:
            store.request_phase_transition(PhaseTransitionRequest("BOOTSTRAP", "selftest", "Reprise directe interdite"))
        except TransitionError:
            no_resume = True
        check("sortie de PAUSED non implicite", no_resume)

        audit = store.verify_audit_chain()
        check("journal audit hashé et vérifiable", audit["valid"] and audit["events_checked"] >= 10, str(audit))

        latest_state = store.get_current_portfolio_state()
        check("état final cohérent", latest_state.current_phase == "PAUSED" and latest_state.position_count == 1)

    print()
    print("-" * 84)
    if failures:
        print("ÉCHECS : %d/20" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("20/20 contrôles passent. Portfolio State v1 prêt pour l'intégration API/UI.")
    return 0


def demo(db_path: str = "data/thesium_demo.db") -> int:
    if os.path.exists(db_path):
        os.remove(db_path)
    store = PortfolioStateStore(db_path)
    store.initialize()
    print("=" * 84)
    print("[PORTFOLIO_STATE_V1.0.0] démonstration")
    print("=" * 84)

    snapshot_id = store.record_portfolio_snapshot(
        PortfolioSnapshotInput(
            as_of="2026-09-04T18:00:00+00:00", nav_eur=1_000_000, cash_eur=1_000_000,
            invested_eur=0, source="demo", notes="Lancement portefeuille",
            metadata={"strategic_target_invested_eur": 600_000},
        ),
        actor="demo",
    )
    print("\n  Snapshot lancement : %s" % snapshot_id)
    state = store.get_current_portfolio_state()
    print("  Phase : %s v%d | NAV : %.2f€ | Cash : %.2f€ | Investi : %.2f€" % (
        state.current_phase, state.phase_version, state.nav_eur or 0, state.cash_eur or 0, state.invested_eur or 0))

    for number in range(1, 6):
        store.record_market_cycle(_healthy_cycle("bootstrap-demo-%d" % number, day="2026-09-%02d" % number), actor="demo")
    print("  Cycles BOOTSTRAP enregistrés : %d" % len(store.list_market_cycles("BOOTSTRAP")))

    assessment_id = store.record_phase_assessment({
        "current_phase": "BOOTSTRAP", "recommended_phase": "OBSERVE", "next_phase": "OBSERVE",
        "action": "REQUEST_PROMOTION", "promotion_eligible": True,
        "reason": "20% de cible et 5 séances valides", "deployment_pct_target": 20.0,
        "invested_pct_nav": 12.0, "cash_pct_nav": 88.0,
        "valid_cycles_in_current_phase": 5, "required_cycles_for_next_phase": 5,
        "policy_id": "STARTUP_POLICY_V1", "policy_version": "1.0.0",
        "policy_fingerprint": "demo-policy-fingerprint", "effective_regime": "RISK_ON",
        "input_snapshot_hash": "demo-input-hash",
    }, actor="demo")
    print("  Assessment promotion : %s" % assessment_id)

    transition_id = store.request_phase_transition(
        PhaseTransitionRequest("OBSERVE", "system", "Promotion proposée par le manager", assessment_id=assessment_id)
    )
    print("  Demande créée : %s | phase active inchangée : %s" % (
        transition_id, store.get_current_portfolio_state().current_phase))
    store.approve_phase_transition(
        transition_id, "RichardGUELIN", "5 séances réconciliées; métriques et régime conformes.",
        "STARTUP_POLICY_V1", "1.0.0", "demo-policy-fingerprint",
    )
    applied = store.apply_approved_phase_transition(transition_id, "RichardGUELIN", "Activation après validation")
    print("  Transition appliquée : %s | phase : %s v%d" % (
        transition_id, applied.current_phase, applied.phase_version))

    audit = store.verify_audit_chain()
    print("  Audit : %s | événements contrôlés : %d" % ("OK" if audit["valid"] else "ECHEC", audit["events_checked"]))
    print("  Base de démonstration : %s" % db_path)
    return 0


def inspect(db_path: str) -> int:
    store = PortfolioStateStore(db_path)
    store.initialize()
    state = store.get_current_portfolio_state()
    print(json.dumps(asdict(state), ensure_ascii=False, indent=2, default=str))
    print("\nTransitions :")
    print(json.dumps(store.list_phase_transitions(20), ensure_ascii=False, indent=2, default=str))
    print("\nAudit :")
    print(json.dumps(store.verify_audit_chain(), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Portfolio State v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    group.add_argument("--inspect", metavar="DATABASE")
    parser.add_argument("--db", default="data/thesium_demo.db", help="Base utilisée par --demo")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if args.demo:
        return demo(args.db)
    return inspect(args.inspect)


if __name__ == "__main__":
    sys.exit(main())
