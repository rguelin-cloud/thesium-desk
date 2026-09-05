#!/usr/bin/env python3
# proposal_ranker.py
# [PROPOSAL_RANKER_V1.0.1]
"""Classement déterministe et explicable des propositions THESIUM.

Rôle
----
Classe des propositions déjà produites par les composants amont :
consensus -> decision gate -> sizing -> risk gate -> proposal_ranker -> orchestrator.

Le rangueur ne modifie jamais :
- le sens de l'opération ;
- le statut Risk Gate ;
- le notionnel Risk Gate ;
- les plafonds Startup Ramp ;
- la phase portefeuille ;
- un ordre ou un fill broker.

Il fournit uniquement un ordre de traitement stable lorsque les budgets Startup Ramp
sont limités, par exemple deux nouvelles positions maximum en BOOTSTRAP.

Ordre de priorité
-----------------
1. Ventes réductrices de risque ou sorties forcées.
2. Réductions de concentration / délestages défensifs.
3. Achats RISK_APPROVED.
4. Achats RISK_REDUCED.
5. Tout élément non éligible ou incomplet en dernier, explicitement signalé.

Important v1.0.1
----------------
Les avertissements de qualité (consensus, liquidité, conviction) sont calculés AVANT
le choix de bucket. Ainsi un BUY RISK_APPROVED avec consensus absent n'est pas traité
comme un achat éligible : il est classé INELIGIBLE_OR_REVIEW, score zéro, en dernier.

CLI
---
    py -3.13 proposal_ranker.py --selftest
    py -3.13 proposal_ranker.py --demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


class ProposalRankError(ValueError):
    pass


class RankBucket(str, Enum):
    RISK_REDUCING_SELL = "RISK_REDUCING_SELL"
    CONCENTRATION_REDUCTION = "CONCENTRATION_REDUCTION"
    BUY_RISK_APPROVED = "BUY_RISK_APPROVED"
    BUY_RISK_REDUCED = "BUY_RISK_REDUCED"
    INELIGIBLE_OR_REVIEW = "INELIGIBLE_OR_REVIEW"


@dataclass(frozen=True)
class RankableProposal:
    proposal_id: str
    ticker: str
    side: str
    risk_status: str
    risk_approved_notional_eur: float
    asset_class: str
    is_new_position: bool
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
class RankedProposal:
    proposal: RankableProposal
    rank: int
    bucket: RankBucket
    bucket_priority: int
    score: float
    score_components: Dict[str, float]
    reasons: List[str]
    eligibility_warnings: List[str]
    sort_key: Tuple[Any, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal": asdict(self.proposal),
            "rank": self.rank,
            "bucket": self.bucket.value,
            "bucket_priority": self.bucket_priority,
            "score": self.score,
            "score_components": self.score_components,
            "reasons": self.reasons,
            "eligibility_warnings": self.eligibility_warnings,
            "sort_key": list(self.sort_key),
        }


@dataclass
class RankingResult:
    ranked: List[RankedProposal]
    input_hash: str
    ranker_version: str = "PROPOSAL_RANKER_V1.0.1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ranker_version": self.ranker_version,
            "input_hash": self.input_hash,
            "ranked": [item.to_dict() for item in self.ranked],
        }


CONVICTION_SCORES = {
    "VERY_STRONG": 1.00,
    "FORTE": 1.00,
    "STRONG": 1.00,
    "HIGH": 0.85,
    "NORMALE": 0.60,
    "NORMAL": 0.60,
    "MEDIUM": 0.60,
    "FAIBLE": 0.30,
    "LOW": 0.30,
    "UNKNOWN": 0.00,
}


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    result = str(value or default).strip().upper()
    return result or default


def _finite(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clamp(value: Optional[float], low: float = 0.0, high: float = 1.0) -> Optional[float]:
    if value is None:
        return None
    return max(low, min(high, value))


def _safe_json(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _safe_json(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(item) for item in value]
    if hasattr(value, "value"):
        return _safe_json(value.value)
    return value


def _hash(value: Any) -> str:
    raw = json.dumps(_safe_json(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ProposalRanker:
    """Classeur pur : même entrée, même ordre, aucune mutation des propositions."""

    VERSION = "PROPOSAL_RANKER_V1.0.1"

    def rank(self, proposals: Sequence[RankableProposal]) -> RankingResult:
        normalized = list(proposals)
        self._validate_unique_ids(normalized)
        ranked = [self._score(item) for item in normalized]
        ranked.sort(key=lambda item: item.sort_key)
        for index, item in enumerate(ranked, start=1):
            item.rank = index
        return RankingResult(ranked=ranked, input_hash=_hash(normalized), ranker_version=self.VERSION)

    def _score(self, proposal: RankableProposal) -> RankedProposal:
        ticker = _upper(proposal.ticker)
        side = _upper(proposal.side)
        risk = _upper(proposal.risk_status)
        warnings: List[str] = []
        reasons: List[str] = []

        if ticker == "UNKNOWN":
            warnings.append("TICKER_MISSING")
        if side not in {"BUY", "SELL"}:
            warnings.append("SIDE_INVALID")
        if risk not in {"RISK_APPROVED", "RISK_REDUCED"}:
            warnings.append("RISK_STATUS_NOT_ELIGIBLE")
        notional = _finite(proposal.risk_approved_notional_eur)
        if notional is None or notional <= 0:
            warnings.append("RISK_NOTIONAL_INVALID")
        asset_class = _upper(proposal.asset_class)
        if asset_class == "UNKNOWN":
            warnings.append("ASSET_CLASS_MISSING")

        # Correctif v1.0.1 : collecter d'abord tous les warnings de données.
        # _bucket peut alors envoyer une proposition incomplète vers REVIEW.
        components = self._score_components(proposal, warnings)
        bucket, priority, bucket_reason = self._bucket(proposal, side, risk, warnings)
        reasons.append(bucket_reason)

        score = round(sum(components.values()), 6)
        if bucket == RankBucket.INELIGIBLE_OR_REVIEW:
            score = 0.0

        if warnings:
            reasons.append("Données ou éligibilité à vérifier : " + ", ".join(sorted(set(warnings))))
        else:
            reasons.append("Score calculé sur conviction, consensus, liquidité et urgence")

        sort_key = (priority, -score, ticker, str(proposal.proposal_id))
        return RankedProposal(
            proposal=proposal,
            rank=0,
            bucket=bucket,
            bucket_priority=priority,
            score=score,
            score_components=components,
            reasons=reasons,
            eligibility_warnings=sorted(set(warnings)),
            sort_key=sort_key,
        )

    @staticmethod
    def _bucket(
        proposal: RankableProposal,
        side: str,
        risk: str,
        warnings: List[str],
    ) -> Tuple[RankBucket, int, str]:
        forced = bool(str(proposal.forced_exit_reason or "").strip())

        # Une vente réductrice reste prioritaire même si le consensus est absent :
        # ne pas bloquer une réduction de risque pour une donnée de sélection manquante.
        if side == "SELL" and (proposal.is_risk_reducing or forced):
            detail = "Vente réductrice prioritaire"
            if forced:
                detail += " : " + str(proposal.forced_exit_reason).strip()
            return RankBucket.RISK_REDUCING_SELL, 10, detail
        if side == "SELL" and proposal.is_concentration_reduction:
            return RankBucket.CONCENTRATION_REDUCTION, 20, "Délestage de concentration prioritaire"

        if warnings:
            return RankBucket.INELIGIBLE_OR_REVIEW, 90, "Proposition non éligible ou incomplète"
        if side == "BUY" and risk == "RISK_APPROVED":
            return RankBucket.BUY_RISK_APPROVED, 30, "Achat validé par Risk Gate"
        if side == "BUY" and risk == "RISK_REDUCED":
            return RankBucket.BUY_RISK_REDUCED, 40, "Achat réduit par Risk Gate"
        return RankBucket.INELIGIBLE_OR_REVIEW, 90, "Proposition non éligible ou ambiguë"

    @staticmethod
    def _score_components(proposal: RankableProposal, warnings: List[str]) -> Dict[str, float]:
        conviction_label = _upper(proposal.conviction)
        conviction = CONVICTION_SCORES.get(conviction_label)
        if conviction is None:
            conviction = 0.0
            warnings.append("CONVICTION_UNKNOWN")

        consensus = _finite(proposal.consensus_score)
        if consensus is None:
            consensus_normalized = 0.0
            warnings.append("CONSENSUS_SCORE_MISSING")
        else:
            if consensus < 0.75 or consensus > 1.20:
                warnings.append("CONSENSUS_SCORE_OUT_OF_RANGE")
            consensus_normalized = _clamp((consensus - 0.75) / 0.45) or 0.0

        liquidity = _finite(proposal.liquidity_score)
        if liquidity is None:
            liquidity_normalized = 0.0
            warnings.append("LIQUIDITY_SCORE_MISSING")
        else:
            if liquidity < 0.0 or liquidity > 1.0:
                warnings.append("LIQUIDITY_SCORE_OUT_OF_RANGE")
            liquidity_normalized = _clamp(liquidity) or 0.0

        urgency = _finite(proposal.urgency_score)
        if urgency is None:
            urgency_normalized = 0.0
        else:
            if urgency < 0.0 or urgency > 1.0:
                warnings.append("URGENCY_SCORE_OUT_OF_RANGE")
            urgency_normalized = _clamp(urgency) or 0.0

        return {
            "conviction": round(0.35 * conviction, 6),
            "consensus": round(0.35 * consensus_normalized, 6),
            "liquidity": round(0.20 * liquidity_normalized, 6),
            "urgency": round(0.10 * urgency_normalized, 6),
        }

    @staticmethod
    def _validate_unique_ids(proposals: Sequence[RankableProposal]) -> None:
        seen: set[str] = set()
        for proposal in proposals:
            proposal_id = str(proposal.proposal_id).strip()
            if not proposal_id:
                raise ProposalRankError("proposal_id obligatoire")
            if proposal_id in seen:
                raise ProposalRankError("proposal_id dupliqué : %s" % proposal_id)
            seen.add(proposal_id)


def selftest() -> int:
    print("=" * 84)
    print("[PROPOSAL_RANKER_V1.0.1] autotest — classement déterministe avant Ramp")
    print("=" * 84)
    failures: List[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        suffix = ("  " + detail) if detail and not condition else ""
        print("  %-67s %s%s" % (name, "OK" if condition else "ECHEC", suffix))
        if not condition:
            failures.append(name)

    ranker = ProposalRanker()

    def good(proposal_id: str, ticker: str, **kwargs: Any) -> RankableProposal:
        return RankableProposal(
            proposal_id=proposal_id,
            ticker=ticker,
            side=kwargs.pop("side", "BUY"),
            risk_status=kwargs.pop("risk", "RISK_APPROVED"),
            risk_approved_notional_eur=kwargs.pop("amount", 5_000),
            asset_class=kwargs.pop("asset", "EQUITY"),
            is_new_position=kwargs.pop("new", True),
            conviction=kwargs.pop("conviction", "FORTE"),
            consensus_score=kwargs.pop("consensus", 1.10),
            liquidity_score=kwargs.pop("liquidity", 0.90),
            urgency_score=kwargs.pop("urgency", 0.10),
            is_risk_reducing=kwargs.pop("risk_reducing", False),
            is_concentration_reduction=kwargs.pop("concentration", False),
            forced_exit_reason=kwargs.pop("forced", ""),
            **kwargs,
        )

    result = ranker.rank([good("1", "AAPL"), good("2", "JPM")])
    check("deux propositions classées", len(result.ranked) == 2)
    check("rangs séquentiels", [row.rank for row in result.ranked] == [1, 2])
    check("hash entrée présent", len(result.input_hash) == 64)

    result = ranker.rank([
        good("buy", "AAPL"),
        good("sell", "MS", side="SELL", risk_reducing=True),
    ])
    check("vente réductrice avant achat", result.ranked[0].proposal.proposal_id == "sell")
    check("bucket vente réductrice", result.ranked[0].bucket == RankBucket.RISK_REDUCING_SELL)

    result = ranker.rank([
        good("approved", "AAPL", risk="RISK_APPROVED"),
        good("reduced", "JPM", risk="RISK_REDUCED"),
    ])
    check("RISK_APPROVED avant RISK_REDUCED", result.ranked[0].proposal.proposal_id == "approved")

    result = ranker.rank([
        good("concentration", "TSLA", side="SELL", concentration=True),
        good("buy", "AAPL"),
    ])
    check("délestage concentration avant achat", result.ranked[0].proposal.proposal_id == "concentration")

    result = ranker.rank([
        good("forced", "BTC", side="SELL", forced="RUNE_LONG_VETO"),
        good("concentration", "TSLA", side="SELL", concentration=True),
    ])
    check("sortie forcée avant délestage", result.ranked[0].proposal.proposal_id == "forced")

    result = ranker.rank([
        good("weak", "AAPL", conviction="FAIBLE", consensus=0.90, liquidity=0.50),
        good("strong", "JPM", conviction="FORTE", consensus=1.16, liquidity=0.90),
    ])
    check("score meilleur classement dans même bucket", result.ranked[0].proposal.proposal_id == "strong")
    check(
        "composants de score explicables",
        set(result.ranked[0].score_components) == {"conviction", "consensus", "liquidity", "urgency"},
    )

    result = ranker.rank([
        good("z", "ZZZ", consensus=1.0, liquidity=0.8),
        good("a", "AAA", consensus=1.0, liquidity=0.8),
    ])
    check("égalité départagée par ticker", [row.proposal.ticker for row in result.ranked] == ["AAA", "ZZZ"])

    invalid = good("invalid", "BAD", risk="RISK_REJECTED")
    result = ranker.rank([good("good", "AAPL"), invalid])
    check("Risk Gate non éligible en dernier", result.ranked[-1].proposal.proposal_id == "invalid")
    check(
        "Risk Gate non éligible signalé",
        "RISK_STATUS_NOT_ELIGIBLE" in result.ranked[-1].eligibility_warnings,
    )

    missing = good("missing", "MISS", consensus=None)
    result = ranker.rank([good("good", "AAPL"), missing])
    check(
        "consensus manquant en revue",
        result.ranked[-1].bucket == RankBucket.INELIGIBLE_OR_REVIEW
        and result.ranked[-1].score == 0.0,
        str(result.ranked[-1].to_dict()),
    )
    check(
        "consensus manquant signalé",
        "CONSENSUS_SCORE_MISSING" in result.ranked[-1].eligibility_warnings,
    )

    # Les ventes qui réduisent le risque restent prioritaires même sans données de sélection.
    missing_sell = good("sell-missing", "TSLA", side="SELL", risk_reducing=True, consensus=None, liquidity=None)
    result = ranker.rank([good("buy", "AAPL"), missing_sell])
    check("vente réductrice incomplète reste prioritaire", result.ranked[0].proposal.proposal_id == "sell-missing")

    duplicate_rejected = False
    try:
        ranker.rank([good("duplicate", "AAPL"), good("duplicate", "JPM")])
    except ProposalRankError:
        duplicate_rejected = True
    check("proposal_id dupliqué refusé", duplicate_rejected)

    initial = [good("b", "JPM"), good("a", "AAPL"), good("c", "MS", risk="RISK_REDUCED")]
    first = ranker.rank(initial).to_dict()
    second = ranker.rank(list(reversed(initial))).to_dict()
    order_first = [item["proposal"]["proposal_id"] for item in first["ranked"]]
    order_second = [item["proposal"]["proposal_id"] for item in second["ranked"]]
    check("classement indépendant de l'ordre entrée", order_first == order_second)
    check("propositions non mutées", initial[0].ticker == "JPM" and initial[0].risk_status == "RISK_APPROVED")

    print()
    print("-" * 84)
    if failures:
        print("ÉCHECS : %d/17" % len(failures))
        for item in failures:
            print("  - %s" % item)
        return 1
    print("17/17 contrôles passent. Proposal Ranker v1.0.1 prêt avant intégration orchestrateur.")
    return 0


def demo() -> int:
    ranker = ProposalRanker()
    proposals = [
        RankableProposal("p-aapl", "AAPL", "BUY", "RISK_APPROVED", 5_000, "EQUITY", True, "FORTE", 1.16, 0.95, 0.20),
        RankableProposal("p-jpm", "JPM", "BUY", "RISK_APPROVED", 5_000, "EQUITY", True, "NORMALE", 0.90, 0.90, 0.10),
        RankableProposal("p-ms", "MS", "BUY", "RISK_REDUCED", 4_000, "EQUITY", True, "FORTE", 1.10, 0.85, 0.10),
        RankableProposal("p-tsla", "TSLA", "SELL", "RISK_APPROVED", 7_000, "EQUITY", False, "NORMAL", 1.00, 0.90, 0.70, is_concentration_reduction=True),
        RankableProposal("p-btc", "BTC", "SELL", "RISK_APPROVED", 3_000, "CRYPTO", False, "NORMAL", 1.00, 0.90, 1.00, is_risk_reducing=True, forced_exit_reason="RUNE_LONG_VETO"),
        RankableProposal("p-missing", "JNJ", "BUY", "RISK_APPROVED", 5_000, "EQUITY", True, "NORMAL", None, 0.90, 0.0),
        RankableProposal("p-bad", "BAD", "BUY", "RISK_REJECTED", 0, "EQUITY", True, "NORMAL", 0.75, 0.90, 0.0),
    ]
    result = ranker.rank(proposals)
    print("=" * 112)
    print("[PROPOSAL_RANKER_V1.0.1] démonstration")
    print("=" * 112)
    for item in result.ranked:
        components = item.score_components
        print(
            "\n  #%d %-6s %-4s %-24s score=%0.4f  conviction=%0.3f consensus=%0.3f liquidité=%0.3f urgence=%0.3f"
            % (
                item.rank, item.proposal.ticker, item.proposal.side, item.bucket.value,
                item.score, components["conviction"], components["consensus"],
                components["liquidity"], components["urgency"],
            )
        )
        for reason in item.reasons:
            print("     " + reason)
    print("\n  Input hash : %s" % result.input_hash)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIUM Proposal Ranker v1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--selftest", action="store_true")
    group.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    return selftest() if args.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
