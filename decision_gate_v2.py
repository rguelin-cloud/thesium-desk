#!/usr/bin/env python3
# decision_gate_v2.py
# [DECISION_GATE_V2]
"""Decision Gate v2 — qualification déterministe après passe 2.

Rôle dans le pipeline
---------------------
router passe 1 -> consensus_v2 -> candidats formés -> router passe 2
                                                       |
                                                       v
                                              DECISION GATE v2
                                                       |
                              +------------------------+---------------------+
                              |                        |                     |
                       READY_FOR_SIZING        REVIEW_REQUIRED       REJECTED_BY_POST_ANALYSIS
                              |
                              v
                   (futur) risk_gate.py -> sizing -> ordre humain / broker

Ce module ne passe JAMAIS d'ordre, ne calcule JAMAIS de taille, et
n'écrit JAMAIS dans la base. Il qualifie les mandats analytiques.

Pourquoi il existe
------------------
Un mandat formé en passe 1 satisfait un consensus quantitatif, mais
ne devient pas automatiquement une intention exécutable. La passe 2
peut révéler :
  - une analyse contradictoire ;
  - un avertissement RUNE tardif ;
  - une thèse vide, un ticker incohérent ou des données manquantes ;
  - un consensus initial marginal, qui doit être revu.

Règles v2
---------
R1  Intégrité : analyses de passe 2 présentes pour chaque agent requis,
    ticker cohérent, thèse non vide pour tout vote engagé.
R2  Confirmation directionnelle : au moins 2 analyses engagées dans
    le sens du mandat, hors RUNE. Jamais un agent seul.
R3  Contradiction : 2 analyses engagées ou plus dans la direction opposée
    rejettent le mandat. Une seule déclenche REVIEW_REQUIRED.
R4  RUNE : un SHORT engagé >= 6.0 bloque un LONG. Pour un SHORT, le même
    signal ne l'autorise pas : il déclenche REVIEW_REQUIRED, car RUNE est
    un signal de risque, pas un moteur de vente à découvert.
R5  Force : ranking_score / poids gagnant du consensus v2.
      score >= .85 -> admissible à READY_FOR_SIZING si R1-R4 passent.
      .75 <= score < .85 -> REVIEW_REQUIRED (mandat marginal).
      score < .75 -> REJECTED_BY_POST_ANALYSIS (ne devrait pas arriver).
R6  Lacunes : une lacune critique déclarée par un agent engagé empêche
    READY_FOR_SIZING. Elle déclenche REVIEW_REQUIRED.

Ces règles reflètent le premier cycle préproduction :
  AAPL : score 1.16, 4/4, RUNE N -> READY_FOR_SIZING
  JPM  : score  .90, 3/3, RUNE N -> READY_FOR_SIZING
  JNJ  : score  .76 -> REVIEW_REQUIRED
  MS   : score  .76 -> REVIEW_REQUIRED
  BTC  : score  .67 + RUNE S@6.5 -> REVIEW_REQUIRED

Usage
-----
    from decision_gate_v2 import DecisionGate, DecisionGateConfig

    gate = DecisionGate()
    outcome = gate.evaluate(consensus_decision, pass2_votes)
    print(outcome.to_dict())

    outcomes = gate.evaluate_all(decisions, all_pass2_votes)

Autotest
--------
    py -3.13 decision_gate_v2.py --selftest
    py -3.13 decision_gate_v2.py --demo
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    from consensus_v2 import ConsensusDecision
except ImportError:
    ConsensusDecision = Any  # permet l'autotest avec dictionnaires


# ==========================================================================
# CONFIGURATION
# ==========================================================================

@dataclass(frozen=True)
class DecisionGateConfig:
    """Paramètres versionnés. Aucun seuil dispersé dans les règles."""

    # Confirmation analytique post-passe-2, hors agent de risque.
    min_aligned_analyses: int = 2
    reject_opposing_analyses: int = 2

    # RUNE : il protège les longs et ne rend jamais un short automatique.
    risk_agent: str = "RUNE"
    rune_veto_min_conviction: float = 6.0

    # Bandes de score issues de la calibration préproduction du 03/09/2026.
    ready_score_min: float = 0.85
    review_score_min: float = 0.75

    # Même convention que router / consensus v2.
    abstain_center: float = 5.0
    abstain_band: float = 0.75
    conviction_cap: float = 7.0

    # Les analyses RUNE sont requises : ne pas ignorer le risque par absence.
    required_agents: Tuple[str, ...] = ("LUMEN", "NORO", "MARIN", "OKAPI", "RUNE")

    # Lexique volontairement conservateur de lacunes bloquantes. Une lacune
    # explicite sur l'intégrité, les données ou la classification doit amener
    # une revue. Les lacunes analytiques ordinaires restent informatives.
    critical_gap_terms: Tuple[str, ...] = (
        "donnée manquante", "donnee manquante", "données manquantes",
        "donnees manquantes", "non vérifié", "non verifie", "incohérent",
        "incoherent", "non classifiable", "secteur non identifié",
        "secteur non identifie", "comparaison impossible", "instruction suspecte",
        "source non fiable", "source inconnue", "volume réel", "volume reel",
    )

    version: str = "decision_gate_v2.0"


class DecisionStatus(str, Enum):
    READY_FOR_SIZING = "READY_FOR_SIZING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED_BY_POST_ANALYSIS = "REJECTED_BY_POST_ANALYSIS"


# ==========================================================================
# STRUCTURES
# ==========================================================================

@dataclass(frozen=True)
class AnalysisVote:
    ticker: str
    agent: str
    direction: str              # LONG / SHORT / NEUTRAL
    conviction: float
    thesis: str = ""
    risks: Tuple[str, ...] = ()
    invalidation: str = ""
    gaps: Tuple[str, ...] = ()
    horizon_days: Optional[int] = None

    @property
    def engaged(self) -> bool:
        return abs(self.conviction - 5.0) > 0.75


@dataclass
class GateOutcome:
    """Résultat explicable et stable de qualification d'un mandat."""

    ticker: str
    status: DecisionStatus
    direction: Optional[str]
    reason: str

    # Provenance consensus
    consensus_formed: bool
    consensus_score: float
    consensus_weight: float
    consensus_convergence: float
    consensus_core_votes: int

    # Lecture passe 2
    n_pass2_raw: int = 0
    n_pass2_engaged: int = 0
    n_aligned: int = 0
    n_opposing: int = 0
    n_neutral: int = 0
    aligned_agents: List[str] = field(default_factory=list)
    opposing_agents: List[str] = field(default_factory=list)
    neutral_agents: List[str] = field(default_factory=list)

    # RUNE
    rune_direction: str = "NEUTRAL"
    rune_conviction: float = 5.0
    rune_vetoed_long: bool = False
    rune_short_review: bool = False

    # Intégrité et données
    missing_agents: List[str] = field(default_factory=list)
    duplicate_agents: List[str] = field(default_factory=list)
    invalid_ticker_agents: List[str] = field(default_factory=list)
    empty_thesis_agents: List[str] = field(default_factory=list)
    critical_gaps: List[Dict[str, str]] = field(default_factory=list)

    # Explication machine et audit
    rejection_codes: List[str] = field(default_factory=list)
    review_codes: List[str] = field(default_factory=list)
    analysis_ledger: List[Dict[str, Any]] = field(default_factory=list)
    config_version: str = "decision_gate_v2.0"

    @property
    def is_ready(self) -> bool:
        return self.status == DecisionStatus.READY_FOR_SIZING

    @property
    def needs_review(self) -> bool:
        return self.status == DecisionStatus.REVIEW_REQUIRED

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def compact(self) -> str:
        return ("%-8s %-27s %-6s score=%.2f aligned=%d opposed=%d %s"
                % (self.ticker, self.status.value, self.direction or "-",
                   self.consensus_score, self.n_aligned, self.n_opposing,
                   ",".join(self.rejection_codes + self.review_codes) or "OK"))


# ==========================================================================
# NORMALISATION
# ==========================================================================

def _get(v: Any, key: str, default: Any = None) -> Any:
    if isinstance(v, Mapping):
        return v.get(key, default)
    return getattr(v, key, default)


def normalize_analysis(v: Any, cfg: DecisionGateConfig) -> AnalysisVote:
    """Transforme un DeepVote, dict ou objet incomplet sans exception."""
    ticker = str(_get(v, "ticker", "UNKNOWN"))
    agent = str(_get(v, "agent", "UNKNOWN")).upper()
    raw = str(_get(v, "direction", "NEUTRAL")).upper()
    direction = {"L": "LONG", "S": "SHORT", "N": "NEUTRAL"}.get(raw, raw)
    if direction not in ("LONG", "SHORT", "NEUTRAL"):
        direction = "NEUTRAL"
    try:
        conviction = float(_get(v, "conviction", 5.0))
    except (ValueError, TypeError):
        conviction = cfg.abstain_center
    if not math.isfinite(conviction):
        conviction = cfg.abstain_center
    conviction = min(cfg.conviction_cap, max(0.0, conviction))

    def strings(x: Any) -> Tuple[str, ...]:
        if not isinstance(x, (list, tuple)):
            return ()
        return tuple(str(a) for a in x if str(a).strip())

    return AnalysisVote(
        ticker=ticker, agent=agent, direction=direction, conviction=conviction,
        thesis=str(_get(v, "thesis", "") or "").strip(),
        risks=strings(_get(v, "risks", [])),
        invalidation=str(_get(v, "invalidation", "") or "").strip(),
        gaps=strings(_get(v, "gaps", [])),
        horizon_days=_get(v, "horizon_days", None),
    )


def consensus_fields(d: Any) -> Dict[str, Any]:
    """Lit un ConsensusDecision ou dictionnaire, avec défauts sûrs."""
    direction = _get(d, "direction", None)
    if direction in ("L", "S", "N"):
        direction = {"L": "LONG", "S": "SHORT", "N": None}[direction]
    return {
        "ticker": str(_get(d, "ticker", "UNKNOWN")),
        "formed": bool(_get(d, "formed", False)),
        "direction": direction if direction in ("LONG", "SHORT") else None,
        "score": float(_get(d, "ranking_score", 0.0) or 0.0),
        "weight": float(_get(d, "winning_weight", 0.0) or 0.0),
        "convergence": float(_get(d, "convergence", 0.0) or 0.0),
        "core_votes": int(_get(d, "n_core_directional", 0) or 0),
    }


# ==========================================================================
# MOTEUR
# ==========================================================================

class DecisionGate:
    """Garde de qualification pure. Zéro I/O, zéro ordre, zéro mutation DB."""

    def __init__(self, cfg: Optional[DecisionGateConfig] = None):
        self.cfg = cfg or DecisionGateConfig()

    def evaluate(self, consensus: Any, analyses: Sequence[Any]) -> GateOutcome:
        cfg = self.cfg
        c = consensus_fields(consensus)
        av = [normalize_analysis(x, cfg) for x in analyses]

        out = GateOutcome(
            ticker=c["ticker"],
            status=DecisionStatus.REJECTED_BY_POST_ANALYSIS,
            direction=c["direction"],
            reason="",
            consensus_formed=c["formed"],
            consensus_score=c["score"],
            consensus_weight=c["weight"],
            consensus_convergence=c["convergence"],
            consensus_core_votes=c["core_votes"],
            n_pass2_raw=len(av),
            config_version=cfg.version,
        )

        # Ledger d'abord : pas de décision sans trace complète.
        out.analysis_ledger = [
            {"ticker": x.ticker, "agent": x.agent, "direction": x.direction,
             "conviction": round(x.conviction, 4), "engaged": x.engaged,
             "thesis_present": bool(x.thesis), "risks": list(x.risks),
             "invalidation": x.invalidation, "gaps": list(x.gaps)}
            for x in av
        ]

        # Précondition absolue : le consensus v2 doit déjà avoir formé le mandat.
        if not c["formed"] or not c["direction"]:
            out.rejection_codes.append("CONSENSUS_NOT_FORMED")
            out.reason = self._reason(out)
            return out

        # Intégrité : ticker et unicité d'agent.
        agents_seen: Dict[str, int] = {}
        for x in av:
            agents_seen[x.agent] = agents_seen.get(x.agent, 0) + 1
            if x.ticker != c["ticker"]:
                out.invalid_ticker_agents.append(x.agent)
        out.duplicate_agents = sorted(a for a, n in agents_seen.items() if n > 1)
        out.missing_agents = sorted(set(cfg.required_agents) - set(agents_seen))
        if out.invalid_ticker_agents:
            out.rejection_codes.append("PASS2_TICKER_MISMATCH")
        if out.duplicate_agents:
            out.rejection_codes.append("PASS2_DUPLICATE_AGENT")
        if out.missing_agents:
            out.rejection_codes.append("PASS2_REQUIRED_AGENT_MISSING")

        # Une analyse engagée sans thèse n'est pas exploitable. Une abstention
        # peut explicitement avoir une thèse d'abstention ou rester concise.
        for x in av:
            if x.engaged and not x.thesis:
                out.empty_thesis_agents.append(x.agent)
        if out.empty_thesis_agents:
            out.rejection_codes.append("PASS2_EMPTY_THESIS")

        # Classifie le vote de chaque agent par rapport au mandat.
        for x in av:
            if x.agent == cfg.risk_agent:
                continue
            if not x.engaged or x.direction == "NEUTRAL":
                out.n_neutral += 1
                out.neutral_agents.append(x.agent)
            elif x.direction == c["direction"]:
                out.n_aligned += 1
                out.aligned_agents.append(x.agent)
            else:
                out.n_opposing += 1
                out.opposing_agents.append(x.agent)
        out.n_pass2_engaged = sum(1 for x in av if x.engaged)

        # RUNE : une seule réponse est attendue; les doublons sont déjà traités.
        runes = [x for x in av if x.agent == cfg.risk_agent]
        if runes:
            r = max(runes, key=lambda x: x.conviction)
            out.rune_direction, out.rune_conviction = r.direction, r.conviction
            if r.direction == "SHORT" and r.engaged and r.conviction >= cfg.rune_veto_min_conviction:
                if c["direction"] == "LONG":
                    out.rune_vetoed_long = True
                    out.rejection_codes.append("RUNE_POST_ANALYSIS_VETO_LONG")
                else:
                    out.rune_short_review = True
                    out.review_codes.append("RUNE_SHORT_RISK_REVIEW")

        # Lacunes : uniquement celles déclarées par un agent engagé.
        for x in av:
            if not x.engaged:
                continue
            for gap in x.gaps:
                low = gap.lower()
                if any(term in low for term in cfg.critical_gap_terms):
                    out.critical_gaps.append({"agent": x.agent, "gap": gap})
        if out.critical_gaps:
            out.review_codes.append("CRITICAL_DATA_GAP")

        # R2 : deux confirmations analytiques, excluant RUNE.
        if out.n_aligned < cfg.min_aligned_analyses:
            out.rejection_codes.append("POST_ANALYSIS_CONFIRMATION_TOO_LOW")

        # R3 : désaccord substantiel = rejet; désaccord isolé = revue.
        if out.n_opposing >= cfg.reject_opposing_analyses:
            out.rejection_codes.append("POST_ANALYSIS_OPPOSITION_TOO_HIGH")
        elif out.n_opposing == 1:
            out.review_codes.append("POST_ANALYSIS_SINGLE_OPPOSITION")

        # R5 : score de formation du mandat, pas une nouvelle invention LLM.
        if c["score"] < cfg.review_score_min:
            out.rejection_codes.append("CONSENSUS_SCORE_BELOW_REVIEW")
        elif c["score"] < cfg.ready_score_min:
            out.review_codes.append("CONSENSUS_SCORE_MARGINAL")

        # Ordre de priorité volontairement strict.
        if out.rejection_codes:
            out.status = DecisionStatus.REJECTED_BY_POST_ANALYSIS
        elif out.review_codes:
            out.status = DecisionStatus.REVIEW_REQUIRED
        else:
            out.status = DecisionStatus.READY_FOR_SIZING
        out.reason = self._reason(out)
        return out

    def evaluate_all(self, decisions: Sequence[Any], analyses: Sequence[Any]) -> List[GateOutcome]:
        """Évalue toutes les décisions formées en groupant les analyses par ticker."""
        by_ticker: Dict[str, List[Any]] = {}
        for a in analyses:
            tk = str(_get(a, "ticker", "UNKNOWN"))
            by_ticker.setdefault(tk, []).append(a)
        out = [self.evaluate(d, by_ticker.get(consensus_fields(d)["ticker"], []))
               for d in decisions]
        return sorted(out, key=lambda x: x.ticker)

    @staticmethod
    def _reason(o: GateOutcome) -> str:
        labels = {
            "CONSENSUS_NOT_FORMED": "le consensus v2 n'a pas formé de mandat",
            "PASS2_TICKER_MISMATCH": "ticker incohérent en passe 2",
            "PASS2_DUPLICATE_AGENT": "réponse dupliquée d'un agent",
            "PASS2_REQUIRED_AGENT_MISSING": "analyse requise absente",
            "PASS2_EMPTY_THESIS": "analyse engagée sans thèse",
            "POST_ANALYSIS_CONFIRMATION_TOO_LOW": "moins de deux confirmations post-analyse",
            "POST_ANALYSIS_OPPOSITION_TOO_HIGH": "au moins deux contradictions post-analyse",
            "RUNE_POST_ANALYSIS_VETO_LONG": "RUNE bloque le LONG après analyse",
            "CONSENSUS_SCORE_BELOW_REVIEW": "score de consensus sous le seuil de revue",
            "RUNE_SHORT_RISK_REVIEW": "RUNE signale un risque de portage sur le SHORT",
            "CRITICAL_DATA_GAP": "lacune critique de données déclarée",
            "POST_ANALYSIS_SINGLE_OPPOSITION": "une contradiction analytique doit être revue",
            "CONSENSUS_SCORE_MARGINAL": "score de consensus marginal",
        }
        codes = o.rejection_codes + o.review_codes
        prefix = {
            DecisionStatus.READY_FOR_SIZING: "Prêt pour le dimensionnement",
            DecisionStatus.REVIEW_REQUIRED: "Revue humaine requise",
            DecisionStatus.REJECTED_BY_POST_ANALYSIS: "Mandat rejeté après analyse",
        }[o.status]
        if not codes:
            return "%s : confirmations %d, score %.2f" % (
                prefix, o.n_aligned, o.consensus_score)
        return "%s : %s" % (prefix, "; ".join(labels.get(x, x) for x in codes))


# ==========================================================================
# JOURNAL
# ==========================================================================

class DecisionGateJournal:
    """Journal JSONL append-only; aucune dépendance à SQLite."""

    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def append(self, outcome: GateOutcome, cycle_id: Optional[str] = None,
               source: str = "live") -> None:
        rec = {
            "kind": "decision_gate_v2_outcome",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle_id,
            "source": source,
            **outcome.to_dict(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")

    def append_all(self, outcomes: Sequence[GateOutcome], cycle_id: Optional[str] = None,
                   source: str = "live") -> None:
        for o in outcomes:
            self.append(o, cycle_id, source)


# ==========================================================================
# FABRIQUES DE TEST
# ==========================================================================

def C(ticker="TEST", direction="LONG", score=1.00, formed=True, weight=None):
    return {
        "ticker": ticker, "formed": formed, "direction": direction,
        "ranking_score": score, "winning_weight": score if weight is None else weight,
        "convergence": 1.0, "n_core_directional": 3,
    }


def A(agent, direction, conviction=6.5, ticker="TEST", thesis="thèse test",
      gaps=None):
    return {
        "ticker": ticker, "agent": agent, "direction": direction,
        "conviction": conviction, "thesis": thesis, "risks": [],
        "invalidation": "seuil test", "gaps": gaps or [], "horizon_days": 21,
    }


def good_long(score=1.0, ticker="TEST"):
    return [
        A("LUMEN", "LONG", ticker=ticker),
        A("NORO", "LONG", ticker=ticker),
        A("MARIN", "LONG", ticker=ticker),
        A("OKAPI", "NEUTRAL", 5.0, ticker=ticker, thesis="abstention"),
        A("RUNE", "NEUTRAL", 5.0, ticker=ticker, thesis="risque neutre"),
    ]


def good_short(score=1.0, ticker="TEST"):
    return [
        A("LUMEN", "SHORT", ticker=ticker),
        A("NORO", "SHORT", ticker=ticker),
        A("MARIN", "NEUTRAL", 5.0, ticker=ticker, thesis="abstention"),
        A("OKAPI", "SHORT", ticker=ticker),
        A("RUNE", "NEUTRAL", 5.0, ticker=ticker, thesis="risque neutre"),
    ]


# ==========================================================================
# AUTOTEST
# ==========================================================================

def selftest() -> int:
    print("=" * 78)
    print("[DECISION_GATE_V2] autotest — qualification post-analyse")
    print("=" * 78)
    gate = DecisionGate()
    failed: List[str] = []

    def ck(name: str, cond: bool, detail: str = "") -> None:
        print("  %-61s %s%s" % (name, "OK" if cond else "ECHEC",
                                ("  " + detail) if detail and not cond else ""))
        if not cond:
            failed.append(name)

    # 1-5: chemin nominal et bandes de score.
    o = gate.evaluate(C(score=1.00), good_long())
    ck("LONG fort, 3 confirmations, RUNE N -> READY", o.status == DecisionStatus.READY_FOR_SIZING)
    ck("chemin nominal : 3 analyses alignées", o.n_aligned == 3)
    o = gate.evaluate(C(score=.85), good_long())
    ck("score .85 exact -> READY", o.status == DecisionStatus.READY_FOR_SIZING)
    o = gate.evaluate(C(score=.84), good_long())
    ck("score .84 -> REVIEW marginal", o.status == DecisionStatus.REVIEW_REQUIRED and "CONSENSUS_SCORE_MARGINAL" in o.review_codes)
    o = gate.evaluate(C(score=.74), good_long())
    ck("score .74 -> REJECTED", o.status == DecisionStatus.REJECTED_BY_POST_ANALYSIS and "CONSENSUS_SCORE_BELOW_REVIEW" in o.rejection_codes)

    # 6-10 : confirmations et opposition.
    xs = good_long()
    xs[1] = A("NORO", "NEUTRAL", 5.0, thesis="abstention")
    xs[2] = A("MARIN", "NEUTRAL", 5.0, thesis="abstention")
    o = gate.evaluate(C(), xs)
    ck("une confirmation seule -> REJECTED", "POST_ANALYSIS_CONFIRMATION_TOO_LOW" in o.rejection_codes)
    xs = good_long()
    xs[3] = A("OKAPI", "SHORT")
    o = gate.evaluate(C(), xs)
    ck("une opposition -> REVIEW", o.status == DecisionStatus.REVIEW_REQUIRED and "POST_ANALYSIS_SINGLE_OPPOSITION" in o.review_codes)
    xs = good_long()
    xs[2] = A("MARIN", "SHORT")
    xs[3] = A("OKAPI", "SHORT")
    o = gate.evaluate(C(), xs)
    ck("deux oppositions -> REJECTED", "POST_ANALYSIS_OPPOSITION_TOO_HIGH" in o.rejection_codes)
    o = gate.evaluate(C(direction="SHORT"), good_short())
    ck("SHORT avec 3 confirmations -> READY", o.status == DecisionStatus.READY_FOR_SIZING)
    ck("votes NEUTRAL non comptés comme alignés", o.n_neutral >= 1)

    # 11-15 : RUNE, asymétrie imposée.
    xs = good_long()
    xs[-1] = A("RUNE", "SHORT", 6.0, thesis="risque")
    o = gate.evaluate(C(direction="LONG"), xs)
    ck("RUNE S@6.0 bloque LONG", o.status == DecisionStatus.REJECTED_BY_POST_ANALYSIS and o.rune_vetoed_long)
    xs = good_long()
    xs[-1] = A("RUNE", "SHORT", 5.8, thesis="risque faible")
    o = gate.evaluate(C(direction="LONG"), xs)
    ck("RUNE S@5.8 ne bloque pas LONG", o.status == DecisionStatus.READY_FOR_SIZING)
    xs = good_short()
    xs[-1] = A("RUNE", "SHORT", 6.5, thesis="risque portage")
    o = gate.evaluate(C(direction="SHORT"), xs)
    ck("RUNE S@6.5 sur SHORT -> REVIEW, pas READY", o.status == DecisionStatus.REVIEW_REQUIRED and o.rune_short_review)
    xs = good_short()
    xs[-1] = A("RUNE", "LONG", 7.0, thesis="LLM erroné")
    o = gate.evaluate(C(direction="SHORT"), xs)
    ck("RUNE LONG invalide ne crée pas d'autorisation", o.status == DecisionStatus.READY_FOR_SIZING)
    xs = good_long()
    xs[-1] = A("RUNE", "SHORT", 6.0, ticker="AUTRE", thesis="risque")
    o = gate.evaluate(C(direction="LONG"), xs)
    ck("ticker RUNE incohérent -> REJECTED", "PASS2_TICKER_MISMATCH" in o.rejection_codes)

    # 16-21 : intégrité et lacunes.
    xs = good_long()[:-1]
    o = gate.evaluate(C(), xs)
    ck("RUNE manquant -> REJECTED", "PASS2_REQUIRED_AGENT_MISSING" in o.rejection_codes)
    xs = good_long() + [A("LUMEN", "LONG", thesis="duplicat")]
    o = gate.evaluate(C(), xs)
    ck("agent dupliqué -> REJECTED", "PASS2_DUPLICATE_AGENT" in o.rejection_codes)
    xs = good_long()
    xs[0] = A("LUMEN", "LONG", thesis="")
    o = gate.evaluate(C(), xs)
    ck("vote engagé sans thèse -> REJECTED", "PASS2_EMPTY_THESIS" in o.rejection_codes)
    xs = good_long()
    xs[0] = A("LUMEN", "LONG", gaps=["donnée manquante : volume réel"])
    o = gate.evaluate(C(), xs)
    ck("lacune critique -> REVIEW", o.status == DecisionStatus.REVIEW_REQUIRED and "CRITICAL_DATA_GAP" in o.review_codes)
    xs = good_long()
    xs[0] = A("LUMEN", "LONG", gaps=["catalyseur récent non disponible"])
    o = gate.evaluate(C(), xs)
    ck("lacune informative non bloquante", o.status == DecisionStatus.READY_FOR_SIZING)
    o = gate.evaluate(C(formed=False), good_long())
    ck("consensus non formé -> REJECTED", "CONSENSUS_NOT_FORMED" in o.rejection_codes)

    # 22-25 : normalisation résistante.
    o = gate.evaluate(C(), [
        {"ticker": "TEST", "agent": "LUMEN", "direction": "LONG", "conviction": "6.5", "thesis": "ok"},
        {"ticker": "TEST", "agent": "NORO", "direction": "LONG", "conviction": 99, "thesis": "ok"},
        {"ticker": "TEST", "agent": "MARIN", "direction": "LONG", "conviction": 6.5, "thesis": "ok"},
        {"ticker": "TEST", "agent": "OKAPI", "direction": "NEUTRAL", "conviction": None, "thesis": "n"},
        {"ticker": "TEST", "agent": "RUNE", "direction": "NEUTRAL", "conviction": 5, "thesis": "n"},
    ])
    ck("convictions texte/99/None sans crash", o.n_pass2_raw == 5)
    n = normalize_analysis({"ticker": "X", "agent": "A", "direction": "???", "conviction": float("nan")}, gate.cfg)
    ck("direction inconnue -> NEUTRAL", n.direction == "NEUTRAL")
    ck("NaN -> 5.0", n.conviction == 5.0)
    ck("borne abstention stricte .75", not normalize_analysis(A("X", "LONG", 5.75), gate.cfg).engaged)

    # 26-28 : evaluate_all, ledger et journal.
    ds = [C(ticker="B"), C(ticker="A")]
    all_a = good_long(ticker="A") + good_long(ticker="B")
    outs = gate.evaluate_all(ds, all_a)
    ck("evaluate_all trie par ticker", [x.ticker for x in outs] == ["A", "B"])
    ck("ledger garde 5 analyses", len(outs[0].analysis_ledger) == 5)
    path = "decision_gate_v2_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        j = DecisionGateJournal(path)
        j.append_all(outs, cycle_id="selftest", source="test")
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        ck("journal JSONL relisible", len(rows) == 2 and rows[0]["status"] == "READY_FOR_SIZING")
    finally:
        if os.path.exists(path):
            os.remove(path)

    # 29 : déterminisme.
    a = gate.evaluate(C(), good_long()).to_dict()
    b = gate.evaluate(C(), good_long()).to_dict()
    ck("décision déterministe", a == b)

    print()
    print("-" * 78)
    if failed:
        print("ÉCHECS : %d/29" % len(failed))
        for x in failed:
            print("  - %s" % x)
        return 1
    print("29/29 contrôles passent. Decision Gate v2 prêt avant risk_gate.py.")
    return 0


# ==========================================================================
# DÉMO PREMIER CYCLE PRÉPRODUCTION
# ==========================================================================

def demo() -> int:
    print("=" * 78)
    print("[DECISION_GATE_V2] démonstration — profils du cycle préproduction")
    print("=" * 78)
    gate = DecisionGate()

    cases = [
        ("AAPL", C("AAPL", "LONG", 1.16, weight=1.16), good_long(1.16, "AAPL")),
        ("JPM", C("JPM", "LONG", .90, weight=.90), good_long(.90, "JPM")),
        ("JNJ", C("JNJ", "LONG", .76, weight=.76), good_long(.76, "JNJ")),
        ("MS", C("MS", "LONG", .76, weight=.76), good_long(.76, "MS")),
        ("BTC", C("BTC", "SHORT", .67, weight=.82), [
            A("LUMEN", "SHORT", ticker="BTC"), A("NORO", "SHORT", 6.8, ticker="BTC"),
            A("MARIN", "NEUTRAL", 5.0, ticker="BTC", thesis="milieu amplitude"),
            A("OKAPI", "SHORT", 6.0, ticker="BTC"),
            A("RUNE", "SHORT", 6.5, ticker="BTC", thesis="risque portage"),
        ]),
    ]
    for name, con, analyses in cases:
        o = gate.evaluate(con, analyses)
        print("\n  " + o.compact())
        print("     " + o.reason)
        print("     alignés=%s | opposés=%s | neutres=%s | RUNE=%s@%.1f"
              % (",".join(o.aligned_agents) or "-", ",".join(o.opposing_agents) or "-",
                 ",".join(o.neutral_agents) or "-", o.rune_direction, o.rune_conviction))
    return 0


# ==========================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="Decision Gate v2 THESIUM")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--demo", action="store_true")
    a = p.parse_args()
    return selftest() if a.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
