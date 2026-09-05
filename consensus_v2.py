#!/usr/bin/env python3
# consensus_v2.py
# [CONSENSUS_V2]
"""Consensus v2 — moteur déterministe de sélection THESIUM.

Contexte expérimental
---------------------
Les prompts v2 et les vues strictes ont transformé l'essaim :
  - 0/35 unanimité totale (contre 80% avant) ;
  - 11% à 57% d'accord directionnel par paire ;
  - LUMEN/NORO alimentés ; MARIN/OKAPI signaux rares ;
  - TIDAL sélectif (5/35 engagements), confirmatoire seulement.

Le consensus v1 faisait passer 8 candidats sur 10, parce que :
  - min_convergence=0.60 acceptait 2/3 ;
  - les votes proches de 5.0 étaient comptés ;
  - la force des convictions n'était pas exigée.

Ce module remplace cette logique par un noyau pur et déterministe.

Règles v2
---------
1. Seuls les votes ENGAGÉS comptent : |conviction - 5.0| > 0.75.
2. Au moins 3 votes engagés directionnels (L ou S), jamais un seul.
3. Convergence minimum dépendante du nombre de votants :
     3 votants : 3/3 = 1.00 (unanimité)
     4 votants : 3/4 = 0.75
     5 votants : 4/5 = 0.80
     6 votants : 5/6 = 0.833...
4. Force directionnelle : poids w=max(0,(c-5)/5), somme des poids de
   la direction gagnante >= min_weight_sum (1.20 par défaut).
   Trois votes mous a c=5.8 pèsent 0.48 et ne forment pas de mandat.
5. Marge de poids : la direction gagnante doit dominer l'opposée par
   min_weight_margin (0.35 par défaut).
6. RUNE est un veto de risque, pas un votant directionnel : son SHORT
   engagé bloque LONG, son NEUTRAL n'affecte pas le décompte.
7. TIDAL est confirmatoire : son vote n'est jamais requis pour remplir
   min_voting. S'il confirme la direction, une prime est journalisée;
   s'il contredit, la force est pénalisée sans bloquer automatiquement.

Usage
-----
    from consensus_v2 import ConsensusEngine, ConsensusConfig
    from inference_router import Vote

    engine = ConsensusEngine(ConsensusConfig())
    decision = engine.decide(votes_for_one_ticker)
    print(decision.to_dict())

    decisions = engine.decide_all(all_votes)

Autotest
--------
    py -3.13 consensus_v2.py --selftest
    py -3.13 consensus_v2.py --demo
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


# ==========================================================================
# CONFIGURATION
# ==========================================================================

@dataclass(frozen=True)
class ConsensusConfig:
    """Paramètres versionnés du consensus. Ne pas disperser les seuils."""

    # Abstention : identique au router et aux benchmarks v2.
    abstain_center: float = 5.0
    abstain_band: float = 0.75

    # Garde anti-agent-isolé, validée au jalon 1.
    min_voting: int = 3

    # Seuils de convergence stricts par nombre de votants engagés.
    # S'il y a davantage de votants, la règle générale exige n-1 voix,
    # soit presque l'unanimité sans rendre 5/5 obligatoire.
    convergence_by_n: Tuple[Tuple[int, float], ...] = (
        (3, 1.00),
        (4, 0.75),
        (5, 0.80),
        (6, 5.0 / 6.0),
    )

    # Force des votes. w=max(0,(c-5)/5): c=5.8 -> .16; c=6.5 -> .30.
    min_weight_sum: float = 1.20
    min_weight_margin: float = 0.35

    # Agents et rôles. Ces noms doivent correspondre aux prompts v2.
    risk_agent: str = "RUNE"
    confirmatory_agents: Tuple[str, ...] = ("TIDAL",)

    # Veto : un SHORT engagé de RUNE bloque un mandat LONG.
    # Par construction, RUNE ne peut pas voter LONG dans le router v2.
    rune_veto_long: bool = True
    rune_veto_min_conviction: float = 6.0

    # Effet non bloquant de TIDAL, appliqué au score de rang seulement.
    confirm_bonus: float = 0.10
    contradict_penalty: float = 0.15

    # Contrôle défensif : conviction attendue de 0 à 7 après le router.
    conviction_floor: float = 0.0
    conviction_cap: float = 7.0

    # Traçabilité
    version: str = "consensus_v2.0"

    def convergence_threshold(self, n: int) -> float:
        """Retourne le seuil applicable ; pour n>6, exige n-1 voix."""
        by_n = dict(self.convergence_by_n)
        if n in by_n:
            return by_n[n]
        return (n - 1) / n if n > 1 else 1.0


# ==========================================================================
# DONNÉES
# ==========================================================================

@dataclass(frozen=True)
class NormalizedVote:
    ticker: str
    agent: str
    direction: str           # L / S / N
    conviction: float
    weight: float
    engaged: bool
    source: str = ""


@dataclass
class ConsensusDecision:
    """Décision intégralement explicable pour un ticker et un cycle."""

    ticker: str
    formed: bool
    direction: Optional[str]             # LONG / SHORT / None
    reason: str

    # Population de votes
    n_raw: int = 0
    n_engaged: int = 0                   # engagé, N inclus
    n_directional: int = 0               # engagé L ou S, RUNE/TIDAL inclus
    n_core_directional: int = 0          # hors RUNE et hors confirmatoires
    n_neutral_engaged: int = 0
    n_abstained: int = 0

    # Direction gagnante
    winning_votes: int = 0
    opposing_votes: int = 0
    convergence: float = 0.0
    convergence_threshold: float = 1.0
    winning_weight: float = 0.0
    opposing_weight: float = 0.0
    weight_margin: float = 0.0

    # Rôles spéciaux
    rune_direction: str = "N"
    rune_conviction: float = 5.0
    vetoed: bool = False
    confirmatory_for: List[str] = field(default_factory=list)
    confirmatory_against: List[str] = field(default_factory=list)
    ranking_score: float = 0.0

    # Observabilité et audit
    rejection_codes: List[str] = field(default_factory=list)
    vote_ledger: List[Dict[str, Any]] = field(default_factory=list)
    config_version: str = "consensus_v2.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compact(self) -> str:
        """Une ligne utile pour les logs console."""
        d = self.direction or "-"
        status = "FORME" if self.formed else "ECARTE"
        return (
            "%-8s %-7s %-6s n=%d/%d conv=%.3f/%.3f "
            "w=%.2f mar=%.2f %s"
            % (self.ticker, status, d, self.winning_votes, self.n_core_directional,
               self.convergence, self.convergence_threshold, self.winning_weight,
               self.weight_margin, ",".join(self.rejection_codes) or "OK")
        )


# ==========================================================================
# NORMALISATION
# ==========================================================================

_VALID_DIRECTIONS = {"L", "S", "N"}


def _read(vote: Any, name: str, default: Any = None) -> Any:
    """Lit indifféremment attribut d'objet, dataclass ou dictionnaire."""
    if isinstance(vote, Mapping):
        return vote.get(name, default)
    return getattr(vote, name, default)


def normalize_vote(vote: Any, cfg: ConsensusConfig) -> NormalizedVote:
    """Normalise un vote non fiable sans jamais lever sur une donnée LLM."""
    ticker = str(_read(vote, "ticker", _read(vote, "t", "UNKNOWN")))
    agent = str(_read(vote, "agent", "UNKNOWN")).upper()
    raw_d = str(_read(vote, "direction", _read(vote, "d", "N"))).upper()
    direction = {"LONG": "L", "SHORT": "S", "NEUTRAL": "N"}.get(raw_d, raw_d)
    if direction not in _VALID_DIRECTIONS:
        direction = "N"

    try:
        conviction = float(_read(vote, "conviction", _read(vote, "c", 5.0)))
    except (TypeError, ValueError):
        conviction = cfg.abstain_center
    if not math.isfinite(conviction):
        conviction = cfg.abstain_center
    conviction = min(cfg.conviction_cap, max(cfg.conviction_floor, conviction))

    # Invariant : le poids est TOUJOURS recalculé, jamais accepté du LLM.
    weight = max(0.0, (conviction - cfg.abstain_center) / 5.0)
    engaged = abs(conviction - cfg.abstain_center) > cfg.abstain_band
    source = str(_read(vote, "source", ""))
    return NormalizedVote(ticker, agent, direction, conviction, weight, engaged, source)


# ==========================================================================
# MOTEUR
# ==========================================================================

class ConsensusEngine:
    """Moteur pur, déterministe et sans I/O de formation de mandat."""

    def __init__(self, cfg: Optional[ConsensusConfig] = None):
        self.cfg = cfg or ConsensusConfig()

    def decide(self, votes: Sequence[Any], ticker: Optional[str] = None) -> ConsensusDecision:
        cfg = self.cfg
        nv = [normalize_vote(v, cfg) for v in votes]
        tk = ticker or (nv[0].ticker if nv else "UNKNOWN")

        d = ConsensusDecision(
            ticker=tk,
            formed=False,
            direction=None,
            reason="",
            n_raw=len(nv),
            config_version=cfg.version,
        )

        # Ledger complet : indispensable à l'audit et au recalcul.
        d.vote_ledger = [
            {
                "agent": v.agent, "direction": v.direction,
                "conviction": round(v.conviction, 4), "weight": round(v.weight, 4),
                "engaged": v.engaged, "source": v.source,
                "role": ("risk" if v.agent == cfg.risk_agent else
                         "confirmatory" if v.agent in cfg.confirmatory_agents else
                         "directional"),
            }
            for v in nv
        ]

        engaged = [v for v in nv if v.engaged]
        directional = [v for v in engaged if v.direction in ("L", "S")]
        core = [v for v in directional
                if v.agent != cfg.risk_agent and v.agent not in cfg.confirmatory_agents]
        neutrals = [v for v in engaged if v.direction == "N"]

        d.n_engaged = len(engaged)
        d.n_directional = len(directional)
        d.n_core_directional = len(core)
        d.n_neutral_engaged = len(neutrals)
        d.n_abstained = len(nv) - len(engaged)

        # RUNE est traité avant tout consensus directionnel.
        rune_votes = [v for v in engaged if v.agent == cfg.risk_agent]
        if rune_votes:
            # En cas de plusieurs réponses, garder la plus convaincue.
            r = max(rune_votes, key=lambda x: x.conviction)
            d.rune_direction, d.rune_conviction = r.direction, r.conviction

        # Garde 1 — min_voting porte sur le noyau directionnel, pas TIDAL/RUNE.
        if len(core) < cfg.min_voting:
            d.rejection_codes.append("INSUFFICIENT_CORE_VOTES")

        if not core:
            d.rejection_codes.append("NO_DIRECTIONAL_CORE")
            d.reason = self._reason(d)
            return d

        # Direction gagnante et métriques : UNIQUEMENT le noyau indépendant.
        # C'est le point crucial : RUNE (veto) et TIDAL (confirmation) ne gonflent
        # jamais artificiellement la convergence.
        long_core = [v for v in core if v.direction == "L"]
        short_core = [v for v in core if v.direction == "S"]
        if len(long_core) >= len(short_core):
            winner, loser, compact = long_core, short_core, "L"
        else:
            winner, loser, compact = short_core, long_core, "S"

        d.direction = "LONG" if compact == "L" else "SHORT"
        d.winning_votes = len(winner)
        d.opposing_votes = len(loser)
        d.convergence = len(winner) / len(core)
        d.convergence_threshold = cfg.convergence_threshold(len(core))
        d.winning_weight = sum(v.weight for v in winner)
        d.opposing_weight = sum(v.weight for v in loser)
        d.weight_margin = d.winning_weight - d.opposing_weight

        # Garde 2 — convergence stricte selon le nombre de VRAIS votants.
        if d.convergence + 1e-12 < d.convergence_threshold:
            d.rejection_codes.append("CONVERGENCE_BELOW_THRESHOLD")

        # Garde 3 — force absolue : interdit les trois votes mous.
        if d.winning_weight + 1e-12 < cfg.min_weight_sum:
            d.rejection_codes.append("WINNING_WEIGHT_TOO_LOW")

        # Garde 4 — force relative : interdit les majorités fragiles.
        if d.weight_margin + 1e-12 < cfg.min_weight_margin:
            d.rejection_codes.append("WEIGHT_MARGIN_TOO_LOW")

        # RUNE : un avertissement SHORT fort bloque seulement un LONG.
        if (cfg.rune_veto_long and compact == "L" and d.rune_direction == "S"
                and d.rune_conviction + 1e-12 >= cfg.rune_veto_min_conviction):
            d.vetoed = True
            d.rejection_codes.append("RUNE_VETO_LONG")

        # TIDAL : confirmation au score, jamais au quorum.
        for v in directional:
            if v.agent not in cfg.confirmatory_agents:
                continue
            if v.direction == compact:
                d.confirmatory_for.append(v.agent)
            else:
                d.confirmatory_against.append(v.agent)

        d.ranking_score = d.winning_weight
        d.ranking_score += cfg.confirm_bonus * len(d.confirmatory_for)
        d.ranking_score -= cfg.contradict_penalty * len(d.confirmatory_against)
        d.ranking_score = max(0.0, d.ranking_score)

        d.formed = not d.rejection_codes
        d.reason = self._reason(d)
        return d

    def decide_all(self, votes: Sequence[Any]) -> List[ConsensusDecision]:
        """Groupe les votes par ticker et retourne une décision stablement triée."""
        grouped: Dict[str, List[Any]] = {}
        for v in votes:
            tk = str(_read(v, "ticker", _read(v, "t", "UNKNOWN")))
            grouped.setdefault(tk, []).append(v)
        return [self.decide(grouped[tk], ticker=tk) for tk in sorted(grouped)]

    def select_features(self, decisions: Sequence[ConsensusDecision],
                        features: Sequence[Mapping[str, Any]],
                        max_candidates: int = 8) -> List[Mapping[str, Any]]:
        """Retourne les features des mandats formés, rangés par score décroissant."""
        by_tk = {str(f.get("ticker")): f for f in features if f.get("ticker")}
        selected = sorted((x for x in decisions if x.formed),
                          key=lambda x: (x.ranking_score, x.convergence,
                                         x.winning_weight), reverse=True)
        return [by_tk[x.ticker] for x in selected[:max_candidates] if x.ticker in by_tk]

    @staticmethod
    def _reason(d: ConsensusDecision) -> str:
        if d.formed:
            extra = []
            if d.confirmatory_for:
                extra.append("TIDAL confirme")
            if d.confirmatory_against:
                extra.append("TIDAL contredit")
            return ("%s formé : %d/%d, convergence %.3f, poids %.2f, marge %.2f%s"
                    % (d.direction, d.winning_votes, d.n_core_directional,
                       d.convergence, d.winning_weight, d.weight_margin,
                       (", " + ", ".join(extra)) if extra else ""))
        labels = {
            "INSUFFICIENT_CORE_VOTES": "moins de 3 votes directionnels indépendants",
            "NO_DIRECTIONAL_CORE": "aucun vote directionnel indépendant",
            "CONVERGENCE_BELOW_THRESHOLD": "convergence insuffisante",
            "WINNING_WEIGHT_TOO_LOW": "force de conviction insuffisante",
            "WEIGHT_MARGIN_TOO_LOW": "marge de poids insuffisante",
            "RUNE_VETO_LONG": "RUNE bloque le LONG pour risque élevé",
        }
        why = "; ".join(labels.get(x, x) for x in d.rejection_codes)
        return "Mandat écarté : " + (why or "raison non spécifiée")


# ==========================================================================
# JOURNAL JSONL
# ==========================================================================

class ConsensusJournal:
    """Append-only JSONL. Compatible avec les audits et backfills."""

    def __init__(self, path: str):
        self.path = path
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)

    def append(self, decision: ConsensusDecision, cycle_id: Optional[str] = None,
               source: str = "live") -> None:
        rec = {
            "kind": "consensus_v2_decision",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle_id,
            "source": source,
            **decision.to_dict(),
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n")

    def append_all(self, decisions: Sequence[ConsensusDecision],
                   cycle_id: Optional[str] = None, source: str = "live") -> None:
        for d in decisions:
            self.append(d, cycle_id=cycle_id, source=source)


# ==========================================================================
# DONNÉES DE TEST
# ==========================================================================

def V(agent: str, d: str, c: float, ticker: str = "TEST") -> Dict[str, Any]:
    return {"ticker": ticker, "agent": agent, "direction": d, "conviction": c}


def base_long(c: float = 7.0) -> List[Dict[str, Any]]:
    return [V("LUMEN", "L", c), V("NORO", "L", c), V("MARIN", "L", c)]


# ==========================================================================
# AUTOTEST
# ==========================================================================

def selftest() -> int:
    print("=" * 78)
    print("[CONSENSUS_V2] autotest — noyau déterministe")
    print("=" * 78)
    e = ConsensusEngine()
    fails: List[str] = []

    def ck(name: str, cond: bool, detail: str = "") -> None:
        print("  %-58s %s%s" % (name, "OK" if cond else "ECHEC",
                                ("  " + detail) if detail and not cond else ""))
        if not cond:
            fails.append(name)

    # 1-4 — poids et normalisation : formule validée sur 5000 snapshots.
    for c, expected in [(5.0, 0.0), (5.8, 0.16), (6.5, 0.30), (7.0, 0.40)]:
        x = normalize_vote(V("LUMEN", "L", c), e.cfg)
        ck("poids c=%.1f -> %.2f" % (c, expected), abs(x.weight - expected) < 1e-9)
    ck("c=5.75 est encore abstention (borne stricte)",
       not normalize_vote(V("LUMEN", "L", 5.75), e.cfg).engaged)
    ck("c=5.76 est engagé", normalize_vote(V("LUMEN", "L", 5.76), e.cfg).engaged)
    ck("c=NaN devient abstention", not normalize_vote(V("LUMEN", "L", float("nan")), e.cfg).engaged)
    ck("conviction 99 plafonnée à 7", normalize_vote(V("LUMEN", "L", 99), e.cfg).conviction == 7.0)

    # 5-8 — garde du noyau : jamais un agent isolé, TIDAL/RUNE exclus.
    d = e.decide([V("LUMEN", "L", 7)])
    ck("un seul agent : écarté", not d.formed and "INSUFFICIENT_CORE_VOTES" in d.rejection_codes)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("TIDAL", "L", 7)])
    ck("TIDAL ne complète pas le quorum", not d.formed and d.n_core_directional == 2)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("RUNE", "S", 6.5)])
    ck("RUNE ne complète pas le quorum", not d.formed and d.n_core_directional == 2)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 5.0)])
    ck("abstention ne complète pas le quorum", not d.formed and d.n_core_directional == 2)

    # 9-12 — seuils de convergence, noyau 3 / 4 / 5 / 6.
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "S", 7)])
    ck("2/3 : écarté, unanimité exigée", not d.formed and "CONVERGENCE_BELOW_THRESHOLD" in d.rejection_codes)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 7)])
    ck("3/3 fort : mandat LONG formé", d.formed and d.direction == "LONG")
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 7), V("OKAPI", "S", 7)])
    ck("3/4 : passe à 0.75", d.formed and abs(d.convergence - .75) < 1e-9)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 7), V("OKAPI", "S", 7), V("AXIS", "S", 7)])
    ck("3/5 : écarté, 4/5 exigé", not d.formed and "CONVERGENCE_BELOW_THRESHOLD" in d.rejection_codes)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 7), V("OKAPI", "L", 7), V("AXIS", "S", 7)])
    ck("4/5 : passe à 0.80", d.formed and abs(d.convergence - .80) < 1e-9)

    # 13-15 — force : poids absolu et marge.
    d = e.decide(base_long(5.8))
    ck("3 votes mous c=5.8 : poids insuffisant", not d.formed and "WINNING_WEIGHT_TOO_LOW" in d.rejection_codes,
       "w=%.2f" % d.winning_weight)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "L", 7)])
    ck("3 votes c=7 : poids 1.20 exact accepté", d.formed and abs(d.winning_weight - 1.2) < 1e-9)
    loose = ConsensusConfig(convergence_by_n=((3, 2/3),), min_weight_sum=0.1,
                            min_weight_margin=0.35)
    d = ConsensusEngine(loose).decide([V("LUMEN", "L", 6.0), V("NORO", "L", 6.0), V("MARIN", "S", 6.0)])
    ck("majorité fragile : marge de poids bloque", not d.formed and "WEIGHT_MARGIN_TOO_LOW" in d.rejection_codes,
       "marge=%.2f" % d.weight_margin)

    # 16-18 — RUNE est un vrai veto, mais seulement sur LONG.
    d = e.decide(base_long(7) + [V("RUNE", "S", 6.0)])
    ck("RUNE S@6.0 bloque LONG", not d.formed and d.vetoed and "RUNE_VETO_LONG" in d.rejection_codes)
    d = e.decide(base_long(7) + [V("RUNE", "S", 5.8)])
    ck("RUNE S@5.8 ne bloque pas", d.formed and not d.vetoed)
    d = e.decide([V("LUMEN", "S", 7), V("NORO", "S", 7), V("MARIN", "S", 7), V("RUNE", "S", 7)])
    ck("RUNE S ne bloque pas un SHORT", d.formed and d.direction == "SHORT")

    # 19-22 — TIDAL confirme, contredit, mais ne compte jamais au quorum.
    d = e.decide(base_long(7) + [V("TIDAL", "L", 6.5)])
    ck("TIDAL LONG confirme, bonus appliqué", d.formed and "TIDAL" in d.confirmatory_for
       and abs(d.ranking_score - 1.3) < 1e-9, "score=%.2f" % d.ranking_score)
    d = e.decide(base_long(7) + [V("TIDAL", "S", 6.5)])
    ck("TIDAL SHORT contredit, pénalité appliquée", d.formed and "TIDAL" in d.confirmatory_against
       and abs(d.ranking_score - 1.05) < 1e-9, "score=%.2f" % d.ranking_score)
    d = e.decide([V("LUMEN", "L", 7), V("NORO", "L", 7), V("TIDAL", "L", 7)])
    ck("TIDAL ne forme jamais seul le mandat", not d.formed)
    d = e.decide(base_long(7) + [V("TIDAL", "N", 7)])
    ck("TIDAL N engagé ne modifie pas le score", d.formed and abs(d.ranking_score - 1.2) < 1e-9)

    # 23-26 — robustesse et invariants.
    d = e.decide([V("LUMEN", "BIZARRE", 7), V("NORO", "L", "oops"), V("MARIN", "L", 7)])
    ck("données LLM invalides : pas de crash", not d.formed and d.n_raw == 3)
    d = e.decide([V("LUMEN", "L", 7, "A"), V("NORO", "L", 7, "B"), V("MARIN", "L", 7, "A")])
    ck("ticker explicite prime sur votes hétérogènes", d.ticker == "A")
    dec = e.decide_all([V("LUMEN", "L", 7, "Z"), V("NORO", "L", 7, "Z"), V("MARIN", "L", 7, "Z"),
                        V("LUMEN", "L", 7, "A"), V("NORO", "L", 7, "A"), V("MARIN", "L", 7, "A")])
    ck("decide_all trie les tickers", [x.ticker for x in dec] == ["A", "Z"])
    ck("ledger conserve tous les votes", len(dec[0].vote_ledger) == 3)

    # 27-29 — sélection et journal.
    feats = [{"ticker": "A", "x": 1}, {"ticker": "Z", "x": 2}]
    got = e.select_features(dec, feats, max_candidates=1)
    ck("select_features respecte max_candidates", len(got) == 1 and got[0]["ticker"] in {"A", "Z"})
    path = "consensus_v2_selftest.jsonl"
    try:
        if os.path.exists(path):
            os.remove(path)
        j = ConsensusJournal(path)
        j.append_all(dec, cycle_id="test", source="selftest")
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(x) for x in f]
        ck("journal JSONL relisible", len(rows) == 2 and rows[0]["config_version"] == "consensus_v2.0")
    finally:
        if os.path.exists(path):
            os.remove(path)

    # 30 — déterminisme : mêmes votes, même décision JSON.
    inp = base_long(7) + [V("TIDAL", "S", 6.5)]
    a = e.decide(inp).to_dict()
    b = e.decide(inp).to_dict()
    ck("décision déterministe", a == b)

    print()
    print("-" * 78)
    if fails:
        print("ÉCHECS : %d/%d" % (len(fails), 30))
        for x in fails:
            print("  - %s" % x)
        return 1
    print("30/30 contrôles passent. Consensus v2 prêt à intégrer au router.")
    return 0


# ==========================================================================
# DÉMONSTRATION
# ==========================================================================

def demo() -> int:
    e = ConsensusEngine()
    cases = {
        "A_unanime_fort": base_long(7) + [V("TIDAL", "L", 6.5)],
        "B_majorite_2_contre_1": [V("LUMEN", "L", 7), V("NORO", "L", 7), V("MARIN", "S", 7)],
        "C_votes_mous": base_long(5.8),
        "D_veto_RUNE": base_long(7) + [V("RUNE", "S", 6.5)],
        "E_TIDAL_non_requis": [V("LUMEN", "S", 7), V("NORO", "S", 7), V("MARIN", "S", 7), V("TIDAL", "N", 5)],
        "F_SHORT_avec_RUNE": [V("LUMEN", "S", 7), V("NORO", "S", 7), V("MARIN", "S", 7), V("RUNE", "S", 7)],
    }
    print("=" * 78)
    print("[CONSENSUS_V2] démonstration")
    print("=" * 78)
    for name, votes in cases.items():
        d = e.decide(votes, ticker=name)
        print("\n  " + d.compact())
        print("     " + d.reason)
        for x in d.vote_ledger:
            print("     %-7s %s@%.1f  w=%.2f  %-13s"
                  % (x["agent"], x["direction"], x["conviction"], x["weight"], x["role"]))
    return 0


# ==========================================================================

def main() -> int:
    p = argparse.ArgumentParser(description="Consensus v2 THESIUM")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true")
    g.add_argument("--demo", action="store_true")
    a = p.parse_args()
    return selftest() if a.selftest else demo()


if __name__ == "__main__":
    sys.exit(main())
