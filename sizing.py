#!/usr/bin/env python3
# sizing.py
# [SIZING_V1_CORRECTED]
"""Sizing v1 — proposition déterministe de taille pour THESIUM.

Position dans le pipeline
-------------------------
consensus_v2 -> decision_gate_v2 -> SIZING -> risk_gate.py -> startup_ramp.py

Le sizing propose une exposition théorique. Il n'autorise rien : RiskGate reste
l'autorité finale sur les limites portefeuille, la liquidité, le régime et le cash.
StartupRamp limitera ensuite la vitesse de déploiement dans un portefeuille neuf.

Ce module ne crée ni ordre, ni fill, ni écriture SQLite, ni appel LLM.

Formule v1
----------
1. Qualité du mandat : normalisation linéaire du score consensus dans [0,1].
2. Risque instrument : poids inversement proportionnel à la volatilité annualisée.
3. Risque de base : budget par idée, exprimé en % de NAV.
4. Plafond : cap par classe d'actif de risk_policy_v1.json.
5. Modulateurs : régime, statut post-analyse, qualité des données et RUNE.

    raw_weight = (risk_budget_pct / annualized_vol_pct) * 100
    quality_weight = raw_weight * quality_multiplier
    proposed_weight = min(quality_weight, position_cap_pct)

Exemple avec budget 0.75%, vol 25%, qualité 1.0:

    (0.75 / 25) * 100 = 3.00% de NAV

Le poids final proposé peut être inférieur du fait du cap instrument, du régime,
du statut de revue ou des données incomplètes. Le Risk Gate recalculera ensuite
ses propres plafonds à partir du portefeuille réel.

Correction v1.0.1
-----------------
Un score exactement égal au plancher de consensus (0.75) est admissible au
processus, mais sa qualité normalisée vaut 0. Il crée donc une cible nulle.
Cette situation est désormais distinguée explicitement de celle où une position
existante est déjà à sa cible :

    score < 0.75  -> CONSENSUS_SCORE_TOO_LOW
    score = 0.75  -> CONSENSUS_SCORE_AT_FLOOR_NO_ALLOCATION
    score > 0.75  -> taille progressive selon qualité, vol et régime

Usage
-----
    from sizing import SizingEngine, SizingConfig, MandateInput
    proposal = SizingEngine().propose(mandate, instrument, portfolio)

Autotest
--------
    py -3.13 sizing.py --selftest
    py -3.13 sizing.py --demo
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
    from risk_gate import load_policy, PolicyError
except ImportError:
    load_policy = None
    PolicyError = ValueError


# ==========================================================================
# ENUMS ET STRUCTURES
# ==========================================================================

class SizingStatus(str, Enum):
    SIZING_PROPOSED = "SIZING_PROPOSED"
    SIZING_REVIEW_REQUIRED = "SIZING_REVIEW_REQUIRED"
    SIZING_REJECTED = "SIZING_REJECTED"


@dataclass(frozen=True)
class SizingConfig:
    """Paramètres propres au sizing, distincts de la politique de risque."""
    policy_path: str = "risk_policy_v1.json"
    risk_budget_pct: float = 0.75
    min_consensus_score: float = 0.75
    full_quality_score: float = 1.20
    ready_statuses: Tuple[str, ...] = ("READY_FOR_SIZING",)
    review_statuses: Tuple[str, ...] = ("REVIEW_REQUIRED",)
    rejected_statuses: Tuple[str, ...] = ("REJECTED_BY_POST_ANALYSIS",)
    review_size_multiplier: float = 0.0
    unknown_volatility_action: str = "REVIEW_REQUIRED"
    default_annualized_vol_pct: float = 35.0
    max_annualized_vol_pct: float = 150.0
    min_proposed_notional_eur: float = 100.0
    regime_multipliers: Tuple[Tuple[str, float], ...] = (
        ("RISK_ON", 1.0),
        ("MAINTAIN", 0.70),
        ("RISK_OFF", 0.0),
        ("UNKNOWN", 0.0),
    )
    version: str = "sizing_v1.0.1"

    def regime_multiplier(self, regime: str) -> float:
        return dict(self.regime_multipliers).get(str(regime or "UNKNOWN").upper(), 0.0)


@dataclass(frozen=True)
class MandateInput:
    """Entrée issue de Decision Gate et Consensus v2."""
    ticker: str
    direction: str
    decision_gate_status: str
    consensus_score: float
    consensus_weight: float
    consensus_convergence: float
    n_aligned_analyses: int
    rune_direction: str = "NEUTRAL"
    rune_conviction: float = 5.0
    cycle_id: str = ""


@dataclass(frozen=True)
class SizingInstrument:
    ticker: str
    asset_class: str
    annualized_vol_pct: Optional[float]
    universe_state: str = "ELIGIBLE"
    instrument_role: str = "DIRECTIONAL"
    sector: str = "UNKNOWN"


@dataclass(frozen=True)
class SizingPortfolio:
    nav_eur: float
    regime: str
    current_position_value_eur: float = 0.0
    current_position_weight_pct: float = 0.0


@dataclass
class SizingFactor:
    name: str
    value: float
    explanation: str


@dataclass
class SizingProposal:
    ticker: str
    direction: str
    status: SizingStatus
    reason: str
    cycle_id: str
    policy_id: str
    policy_version: str
    sizing_version: str
    effective_regime: str

    nav_eur: float
    current_weight_pct: float
    raw_risk_weight_pct: float = 0.0
    quality_multiplier: float = 0.0
    regime_multiplier: float = 0.0
    proposed_weight_pct: float = 0.0
    proposed_notional_eur: float = 0.0
    target_position_weight_pct: float = 0.0
    target_position_notional_eur: float = 0.0
    incremental_notional_eur: float = 0.0
    position_cap_pct: float = 0.0
    annualized_vol_pct: Optional[float] = None

    factors: List[SizingFactor] = field(default_factory=list)
    rejection_codes: List[str] = field(default_factory=list)
    review_codes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def compact(self) -> str:
        return ("%-8s %-6s %-22s w=%.3f%% notional=%9.2f€ target=%.3f%% %s"
                % (self.ticker, self.direction, self.status.value,
                   self.proposed_weight_pct, self.proposed_notional_eur,
                   self.target_position_weight_pct,
                   ",".join(self.rejection_codes + self.review_codes) or "OK"))


# ==========================================================================
# UTILITAIRES
# ==========================================================================

def _finite(value: Any) -> Optional[float]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def _upper(value: Any, default: str = "UNKNOWN") -> str:
    s = str(value or default).strip().upper()
    return s or default


def _policy_position_cap(policy: Mapping[str, Any], asset_class: str) -> float:
    caps = policy["position_caps_pct"]
    return float(caps.get(asset_class, caps["default"]))


def _policy_allowed_class(policy: Mapping[str, Any], asset_class: str) -> bool:
    return asset_class in set(policy["scope"]["allowed_asset_classes"])


# ==========================================================================
# MOTEUR
# ==========================================================================

class SizingEngine:
    """Moteur pur de proposition de taille. RiskGate doit toujours suivre."""

    def __init__(self, config: Optional[SizingConfig] = None,
                 policy: Optional[Mapping[str, Any]] = None):
        self.config = config or SizingConfig()
        if policy is not None:
            self.policy = dict(policy)
        elif load_policy is not None:
            self.policy = load_policy(self.config.policy_path)
        else:
            raise RuntimeError("risk_gate.py est requis pour charger risk_policy_v1.json")

    def propose(self, mandate: MandateInput, instrument: SizingInstrument,
                portfolio: SizingPortfolio) -> SizingProposal:
        cfg, p = self.config, self.policy
        ticker = str(mandate.ticker).upper().strip() or "UNKNOWN"
        direction = _upper(mandate.direction, "NEUTRAL")
        asset_class = _upper(instrument.asset_class)
        regime = _upper(portfolio.regime)
        nav = _finite(portfolio.nav_eur)
        current_weight = _finite(portfolio.current_position_weight_pct) or 0.0
        current_value = _finite(portfolio.current_position_value_eur) or 0.0
        cap = _policy_position_cap(p, asset_class)

        out = SizingProposal(
            ticker=ticker,
            direction=direction,
            status=SizingStatus.SIZING_REJECTED,
            reason="",
            cycle_id=mandate.cycle_id,
            policy_id=str(p["policy_id"]),
            policy_version=str(p["version"]),
            sizing_version=cfg.version,
            effective_regime=regime if regime in dict(cfg.regime_multipliers) else "UNKNOWN",
            nav_eur=max(0.0, nav or 0.0),
            current_weight_pct=max(0.0, current_weight),
            position_cap_pct=cap,
        )
        rejected: List[str] = []
        review: List[str] = []

        def factor(name: str, value: float, explanation: str) -> None:
            out.factors.append(SizingFactor(name, round(value, 8), explanation))

        # Préconditions : l'achat est long-only dans la politique v1.
        if nav is None or nav <= 0.0:
            rejected.append("NAV_INVALID")
        if ticker == "UNKNOWN":
            rejected.append("TICKER_INVALID")
        if direction != "LONG":
            rejected.append("DIRECTION_NOT_LONG_ONLY")
        if mandate.decision_gate_status in cfg.rejected_statuses:
            rejected.append("DECISION_GATE_REJECTED")
        elif mandate.decision_gate_status in cfg.review_statuses:
            review.append("DECISION_GATE_REVIEW")
        elif mandate.decision_gate_status not in cfg.ready_statuses:
            rejected.append("DECISION_GATE_STATUS_INVALID")
        if not _policy_allowed_class(p, asset_class):
            rejected.append("ASSET_CLASS_NOT_ALLOWED")
        if _upper(instrument.universe_state) != "ELIGIBLE":
            rejected.append("UNIVERSE_NOT_ELIGIBLE")
        if _upper(instrument.instrument_role, "DIRECTIONAL") in set(p["scope"]["excluded_instrument_roles"]):
            rejected.append("INSTRUMENT_ROLE_EXCLUDED")

        # RUNE ne crée jamais un achat. Le Decision Gate l'a déjà traité, mais
        # l'invariant est répété ici car le sizing ne doit jamais assouplir un veto.
        rune_d = _upper(mandate.rune_direction, "NEUTRAL")
        rune_c = _finite(mandate.rune_conviction) or 5.0
        rune_veto = float(p["rune_controls"]["block_long_if_short_conviction_gte"])
        if rune_d == "SHORT" and rune_c >= rune_veto:
            rejected.append("RUNE_LONG_VETO")

        # Qualité de consensus : un score sous plancher ne mérite aucune taille.
        score = _finite(mandate.consensus_score)
        if score is None:
            review.append("CONSENSUS_SCORE_MISSING")
        elif score < cfg.min_consensus_score:
            rejected.append("CONSENSUS_SCORE_TOO_LOW")

        if rejected:
            out.rejection_codes = sorted(set(rejected))
            out.review_codes = sorted(set(review))
            out.reason = self._reason(out)
            return out

        # Les éléments en revue ne reçoivent aucune taille automatique.
        if review:
            out.status = SizingStatus.SIZING_REVIEW_REQUIRED
            out.review_codes = sorted(set(review))
            out.reason = self._reason(out)
            return out

        # Volatilité : aucune approximation silencieuse. La valeur par défaut
        # est documentée mais non utilisée tant que le Risk Gate est fail-closed.
        vol = _finite(instrument.annualized_vol_pct)
        if vol is None or vol <= 0.0:
            out.status = SizingStatus.SIZING_REVIEW_REQUIRED
            out.review_codes = ["VOLATILITY_MISSING"]
            out.reason = self._reason(out)
            return out
        if vol > cfg.max_annualized_vol_pct:
            out.rejection_codes = ["VOLATILITY_OUT_OF_RANGE"]
            out.reason = self._reason(out)
            return out
        out.annualized_vol_pct = vol

        # Régime : le sizing ne donne jamais de taille si le régime est défensif.
        regime_mult = cfg.regime_multiplier(regime)
        out.regime_multiplier = regime_mult
        factor("regime_multiplier", regime_mult,
               "Modulateur de régime %s" % out.effective_regime)
        if regime_mult <= 0.0:
            out.rejection_codes = ["REGIME_BLOCKS_NEW_LONGS"]
            out.reason = self._reason(out)
            return out

        # Score de qualité : .75 => 0, 1.20 => 1.0, borné entre les deux.
        denom = cfg.full_quality_score - cfg.min_consensus_score
        quality = 1.0 if denom <= 0 else (score - cfg.min_consensus_score) / denom
        quality = max(0.0, min(1.0, quality))
        out.quality_multiplier = quality
        factor("quality_multiplier", quality,
               "Score consensus %.3f normalisé de %.2f à %.2f" %
               (score, cfg.min_consensus_score, cfg.full_quality_score))

        # Formule inverse-vol. Les pourcentages s'annulent puis sont remis sur 100.
        raw = 100.0 * cfg.risk_budget_pct / vol
        out.raw_risk_weight_pct = raw
        factor("raw_inverse_vol_weight_pct", raw,
               "Budget risque %.2f%% / volatilité %.2f%%" % (cfg.risk_budget_pct, vol))

        quality_weight = raw * quality
        factor("quality_adjusted_weight_pct", quality_weight,
               "Poids inverse-vol × qualité du consensus")
        regime_weight = quality_weight * regime_mult
        factor("regime_adjusted_weight_pct", regime_weight,
               "Poids qualité × régime")

        target_weight = min(regime_weight, cap)
        if target_weight < regime_weight - 1e-12:
            factor("position_cap_pct", cap, "Cap de position pour %s" % asset_class)
        out.target_position_weight_pct = target_weight
        out.target_position_notional_eur = nav * target_weight / 100.0

        # Le sizing propose l'INCRÉMENT nécessaire pour atteindre la cible, pas
        # une position supplémentaire entière.
        increment_weight = max(0.0, target_weight - out.current_weight_pct)
        increment_notional = max(0.0, out.target_position_notional_eur - current_value)
        out.proposed_weight_pct = increment_weight
        out.proposed_notional_eur = increment_notional
        out.incremental_notional_eur = increment_notional
        factor("incremental_weight_pct", increment_weight,
               "Cible %.3f%% moins poids actuel %.3f%%" %
               (target_weight, out.current_weight_pct))

        # Cas frontière explicite : un score exactement au plancher est
        # formellement admissible, mais qualité=0 et cible=0. Ce n'est PAS une
        # position déjà remplie; c'est une absence volontaire d'allocation.
        if target_weight <= 1e-9:
            out.status = SizingStatus.SIZING_REJECTED
            out.rejection_codes = ["CONSENSUS_SCORE_AT_FLOOR_NO_ALLOCATION"]
            out.reason = self._reason(out)
            return out

        # Cas distinct : une cible non nulle existe, mais la position actuelle
        # est déjà à cette cible ou au-dessus. Aucun achat supplémentaire.
        if increment_notional <= 1e-9:
            out.status = SizingStatus.SIZING_REJECTED
            out.rejection_codes = ["CURRENT_POSITION_AT_OR_ABOVE_TARGET"]
            out.reason = self._reason(out)
            return out

        # Cible positive mais incrément trop faible : pas d'ordre microscopique.
        if increment_notional < cfg.min_proposed_notional_eur:
            out.status = SizingStatus.SIZING_REJECTED
            out.rejection_codes = ["PROPOSED_NOTIONAL_BELOW_MIN"]
            out.reason = self._reason(out)
            return out

        out.status = SizingStatus.SIZING_PROPOSED
        out.reason = self._reason(out)
        return out

    @staticmethod
    def _reason(out: SizingProposal) -> str:
        labels = {
            "NAV_INVALID": "NAV absente ou invalide",
            "TICKER_INVALID": "ticker invalide",
            "DIRECTION_NOT_LONG_ONLY": "direction incompatible avec la politique long-only",
            "DECISION_GATE_REJECTED": "Decision Gate a rejeté le mandat",
            "DECISION_GATE_REVIEW": "Decision Gate exige une revue humaine",
            "DECISION_GATE_STATUS_INVALID": "statut Decision Gate inconnu",
            "ASSET_CLASS_NOT_ALLOWED": "classe d'actif non autorisée",
            "UNIVERSE_NOT_ELIGIBLE": "instrument non éligible dans l'univers",
            "INSTRUMENT_ROLE_EXCLUDED": "rôle d'instrument exclu",
            "RUNE_LONG_VETO": "RUNE bloque le LONG",
            "CONSENSUS_SCORE_MISSING": "score de consensus absent",
            "CONSENSUS_SCORE_TOO_LOW": "score de consensus sous le seuil de sizing",
            "CONSENSUS_SCORE_AT_FLOOR_NO_ALLOCATION": "score de consensus au plancher : aucune allocation automatique",
            "VOLATILITY_MISSING": "volatilité absente",
            "VOLATILITY_OUT_OF_RANGE": "volatilité hors plage",
            "REGIME_BLOCKS_NEW_LONGS": "régime défensif : nouveaux LONG interdits",
            "CURRENT_POSITION_AT_OR_ABOVE_TARGET": "position actuelle déjà à la cible ou au-dessus",
            "PROPOSED_NOTIONAL_BELOW_MIN": "proposition sous le minimum de notionnel",
        }
        codes = out.rejection_codes + out.review_codes
        if out.status == SizingStatus.SIZING_PROPOSED:
            return ("Sizing proposé : cible %.3f%%, incrément %.3f%%, %.2f€"
                    % (out.target_position_weight_pct, out.proposed_weight_pct,
                       out.proposed_notional_eur))
        if out.status == SizingStatus.SIZING_REVIEW_REQUIRED:
            return "Sizing en revue : " + "; ".join(labels.get(c, c) for c in codes)
        return "Sizing rejeté : " + "; ".join(labels.get(c, c) for c in codes)


# ==========================================================================
# JOURNAL JSONL
# ==========================================================================

class SizingJournal:
    """Journal append-only de propositions; SQLite viendra avec l'orchestrateur."""

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

    def append(self, proposal: SizingProposal, source: str = "live") -> None:
        rec = {
            "kind": "sizing_v1_proposal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            **proposal.to_dict(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")


# ==========================================================================
# FABRIQUES DE TEST
# ==========================================================================

def M(ticker="AAPL", score=1.16, status="READY_FOR_SIZING", direction="LONG",
      rune_d="NEUTRAL", rune_c=5.0) -> MandateInput:
    return MandateInput(ticker=ticker, direction=direction,
                        decision_gate_status=status, consensus_score=score,
                        consensus_weight=score, consensus_convergence=1.0,
                        n_aligned_analyses=3, rune_direction=rune_d,
                        rune_conviction=rune_c, cycle_id="selftest")


def I(ticker="AAPL", cls="EQUITY", vol=25.0, state="ELIGIBLE",
      role="DIRECTIONAL") -> SizingInstrument:
    return SizingInstrument(ticker=ticker, asset_class=cls,
                            annualized_vol_pct=vol, universe_state=state,
                            instrument_role=role, sector="Technology")


def P(nav=1_000_000.0, regime="RISK_ON", value=0.0, weight=0.0) -> SizingPortfolio:
    return SizingPortfolio(nav_eur=nav, regime=regime,
                           current_position_value_eur=value,
                           current_position_weight_pct=weight)


# ==========================================================================
# AUTOTEST
# ==========================================================================

def selftest() -> int:
    print("=" * 82)
    print("[SIZING_V1.0.1] autotest — proposition déterministe avant Risk Gate")
    print("=" * 82)
    try:
        engine = SizingEngine()
    except Exception as e:
        print("ERREUR politique : %r" % e)
        print("Placez risk_policy_v1.json et risk_gate.py dans le même dossier.")
        return 1
    failed: List[str] = []

    def ck(name: str, condition: bool, detail: str = "") -> None:
        print("  %-66s %s%s" % (name, "OK" if condition else "ECHEC",
                                ("  " + detail) if detail and not condition else ""))
        if not condition:
            failed.append(name)

    # 1–5 : chemin nominal, formule et frontière de score.
    o = engine.propose(M(score=1.20), I(vol=25), P())
    ck("score 1.20 + vol 25% -> 3.00% brut, cap equity 3%", o.status == SizingStatus.SIZING_PROPOSED and abs(o.target_position_weight_pct - 3.0) < 1e-9)
    ck("notionnel 3% de NAV 1M = 30 000€ avant Risk Gate", abs(o.proposed_notional_eur - 30_000) < 1e-6)
    o = engine.propose(M(score=.75), I(vol=25), P())
    ck("score plancher .75 -> cible nulle, rejet explicite", o.status == SizingStatus.SIZING_REJECTED and "CONSENSUS_SCORE_AT_FLOOR_NO_ALLOCATION" in o.rejection_codes)
    o = engine.propose(M(score=.975), I(vol=25), P())
    ck("score médian .975 -> qualité .50, cible 1.50%", o.status == SizingStatus.SIZING_PROPOSED and abs(o.target_position_weight_pct - 1.5) < 1e-9)
    o = engine.propose(M(score=1.20), I(vol=50), P())
    ck("vol 50% -> taille inverse-vol 1.50%", abs(o.target_position_weight_pct - 1.5) < 1e-9)

    # 6–10 : caps et position existante.
    o = engine.propose(M(score=1.20), I(cls="ETF", vol=10), P())
    ck("ETF vol 10% brut 7.5%, cap ETF 4%", o.status == SizingStatus.SIZING_PROPOSED and abs(o.target_position_weight_pct - 4.0) < 1e-9)
    o = engine.propose(M(score=1.20), I(cls="CRYPTO_DIRECTIONAL", vol=50), P())
    ck("crypto vol 50% -> 1.50%, sous cap crypto 2%", o.status == SizingStatus.SIZING_PROPOSED and abs(o.target_position_weight_pct - 1.5) < 1e-9)
    o = engine.propose(M(score=1.20), I(vol=25), P(value=10_000, weight=1.0))
    ck("position existante 1% -> incrément 2%", abs(o.proposed_weight_pct - 2.0) < 1e-9 and abs(o.proposed_notional_eur - 20_000) < 1e-9)
    o = engine.propose(M(score=1.20), I(vol=25), P(value=30_000, weight=3.0))
    ck("position déjà à cible -> aucun achat", o.status == SizingStatus.SIZING_REJECTED and "CURRENT_POSITION_AT_OR_ABOVE_TARGET" in o.rejection_codes)
    o = engine.propose(M(score=1.20), I(vol=25), P(value=35_000, weight=3.5))
    ck("position au-dessus cible -> aucun achat", o.status == SizingStatus.SIZING_REJECTED and "CURRENT_POSITION_AT_OR_ABOVE_TARGET" in o.rejection_codes)

    # 11–16 : régime et Decision Gate.
    o = engine.propose(M(score=1.20), I(vol=25), P(regime="MAINTAIN"))
    ck("MAINTAIN applique x0.70 -> 2.10%", o.status == SizingStatus.SIZING_PROPOSED and abs(o.target_position_weight_pct - 2.1) < 1e-9)
    o = engine.propose(M(score=1.20), I(vol=25), P(regime="RISK_OFF"))
    ck("RISK_OFF bloque nouveaux longs", o.status == SizingStatus.SIZING_REJECTED and "REGIME_BLOCKS_NEW_LONGS" in o.rejection_codes)
    o = engine.propose(M(score=1.20), I(vol=25), P(regime="autre"))
    ck("régime inconnu bloque nouveaux longs", o.status == SizingStatus.SIZING_REJECTED and "REGIME_BLOCKS_NEW_LONGS" in o.rejection_codes)
    o = engine.propose(M(status="REVIEW_REQUIRED"), I(), P())
    ck("Decision Gate review -> sizing review", o.status == SizingStatus.SIZING_REVIEW_REQUIRED and "DECISION_GATE_REVIEW" in o.review_codes)
    o = engine.propose(M(status="REJECTED_BY_POST_ANALYSIS"), I(), P())
    ck("Decision Gate rejeté -> sizing rejeté", o.status == SizingStatus.SIZING_REJECTED and "DECISION_GATE_REJECTED" in o.rejection_codes)
    o = engine.propose(M(direction="SHORT"), I(), P())
    ck("SHORT interdit dans sizing long-only", o.status == SizingStatus.SIZING_REJECTED and "DIRECTION_NOT_LONG_ONLY" in o.rejection_codes)

    # 17–22 : données, univers et RUNE.
    o = engine.propose(M(), I(vol=None), P())
    ck("volatilité absente -> sizing review", o.status == SizingStatus.SIZING_REVIEW_REQUIRED and "VOLATILITY_MISSING" in o.review_codes)
    o = engine.propose(M(), I(vol=151), P())
    ck("volatilité hors plage -> sizing rejeté", o.status == SizingStatus.SIZING_REJECTED and "VOLATILITY_OUT_OF_RANGE" in o.rejection_codes)
    o = engine.propose(M(), I(state="OBSERVING"), P())
    ck("ticker OBSERVING -> sizing rejeté", o.status == SizingStatus.SIZING_REJECTED and "UNIVERSE_NOT_ELIGIBLE" in o.rejection_codes)
    o = engine.propose(M(), I(role="STABLE_RESERVE"), P())
    ck("stable reserve -> sizing rejeté", o.status == SizingStatus.SIZING_REJECTED and "INSTRUMENT_ROLE_EXCLUDED" in o.rejection_codes)
    o = engine.propose(M(rune_d="SHORT", rune_c=6.0), I(), P())
    ck("RUNE SHORT@6.0 bloque LONG", o.status == SizingStatus.SIZING_REJECTED and "RUNE_LONG_VETO" in o.rejection_codes)
    o = engine.propose(M(rune_d="SHORT", rune_c=5.8), I(), P())
    ck("RUNE SHORT@5.8 ne bloque pas", o.status == SizingStatus.SIZING_PROPOSED)

    # 23–28 : robustesse, journal et déterminisme.
    o = engine.propose(M(score=.74), I(), P())
    ck("score sous .75 rejeté", o.status == SizingStatus.SIZING_REJECTED and "CONSENSUS_SCORE_TOO_LOW" in o.rejection_codes)
    o = engine.propose(M(score=float("nan")), I(), P())
    ck("score NaN -> sizing review", o.status == SizingStatus.SIZING_REVIEW_REQUIRED and "CONSENSUS_SCORE_MISSING" in o.review_codes)
    o = engine.propose(M(), I(cls="MYSTERY"), P())
    ck("classe inconnue rejetée", o.status == SizingStatus.SIZING_REJECTED and "ASSET_CLASS_NOT_ALLOWED" in o.rejection_codes)
    a = engine.propose(M(), I(), P()).to_dict()
    b = engine.propose(M(), I(), P()).to_dict()
    ck("sizing déterministe", a == b)
    path = "sizing_v1_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        SizingJournal(path).append(engine.propose(M(), I(), P()), source="selftest")
        with open(path, encoding="utf-8") as f:
            row = json.loads(f.readline())
        ck("journal JSONL relisible", row["kind"] == "sizing_v1_proposal" and row["status"] == "SIZING_PROPOSED")
    finally:
        if os.path.exists(path):
            os.remove(path)
    o = engine.propose(M(), I(), P())
    ck("factors de sizing conservés", len(o.factors) >= 5)

    print()
    print("-" * 82)
    if failed:
        print("ÉCHECS : %d/28" % len(failed))
        for x in failed:
            print("  - %s" % x)
        return 1
    print("28/28 contrôles passent. Sizing v1.0.1 prêt avant startup_ramp.py.")
    return 0


# ==========================================================================
# DÉMONSTRATION
# ==========================================================================

def demo() -> int:
    try:
        engine = SizingEngine()
    except Exception as e:
        print("ERREUR : %r" % e)
        return 1
    print("=" * 82)
    print("[SIZING_V1.0.1] démonstration")
    print("=" * 82)
    cases = [
        ("AAPL conviction forte", M("AAPL", 1.16), I("AAPL", "EQUITY", 19.4), P()),
        ("JPM conviction normale", M("JPM", .90), I("JPM", "EQUITY", 13.5), P()),
        ("JNJ au plancher", M("JNJ", .75), I("JNJ", "EQUITY", 20.6), P()),
        ("BTC veto RUNE", M("BTC", .82, rune_d="SHORT", rune_c=6.5), I("BTC", "CRYPTO_DIRECTIONAL", 45.1), P()),
        ("AAPL MAINTAIN", M("AAPL", 1.16), I("AAPL", "EQUITY", 19.4), P(regime="MAINTAIN")),
        ("AAPL déjà détenue", M("AAPL", 1.16), I("AAPL", "EQUITY", 19.4), P(value=20_000, weight=2.0)),
    ]
    for label, mandate, inst, port in cases:
        o = engine.propose(mandate, inst, port)
        print("\n  %-24s %s" % (label, o.compact()))
        print("     " + o.reason)
        for f in o.factors:
            print("     %-31s %8.4f  %s" % (f.name, f.value, f.explanation))
    return 0


# ==========================================================================
# CLI
# ==========================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="THESIUM Sizing v1.0.1")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--demo", action="store_true")
    a = p.parse_args()
    return selftest() if a.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
