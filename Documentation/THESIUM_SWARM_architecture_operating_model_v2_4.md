# THESIUM SWARM — Architecture et modèle opérationnel v2.4

## Recherche multi-agents · constitution progressive du portefeuille · gouvernance humaine Paper · PPLX 27B local sur DGX Spark · cohabitation PROSIGNAL

- **Date** : 6 septembre 2026
- **Version** : 2.4
- **Statut** : architecture consolidée et état de développement validé
- **Remplace comme document courant** : v2.3 + addendum v2.3.1
- **Historique conservé** : v2.2, v2.3 et v2.3.1 restent archivés et immuables
- **Approche** : extension incrémentale de ThesiumDesk ; aucune réécriture big-bang
- **Runtime cognitif SWARM** : instance unique PPLX 27B locale sur DGX Spark
- **Modèle cible** : `qwen38-27b-dflash2-20260824`
- **Endpoint local** : `http://127.0.0.1:18000/v1`
- **Mode portefeuille actuel** : Paper
- **Broker Live** : désactivé, `BROKER_LIVE_ENABLED = False`
- **Shadow broker** : activé pour monitoring séparé, jamais utilisé par l’exécution Paper humaine

---

# 1. Résumé exécutif

THESIUM SWARM est une architecture de recherche, de constitution de portefeuille, de décision et d’exécution gouvernée pour ThesiumDesk.

Elle sépare strictement les responsabilités :

```text
PPLX 27B local propose, synthétise et explique
Python calcule, valide et persiste les faits
Le Consensus Engine agrège selon des règles déterministes
ZEPHR contraint la capacité et la taille
RUNE applique les règles de risque et peut bloquer
VESKA vérifie et prépare l’exécution
Le manager humain approuve puis autorise séparément l’exécution Paper
```

Le LLM n’est jamais l’autorité de décision. Ses sorties sont des propositions structurées, soumises à JSON Schema, Pydantic et aux calculs Python. RUNE reste déterministe et fail-closed. La gouvernance humaine constitue une barrière indépendante entre une proposition, une approval et une modification du portefeuille.

Le flux Paper durable validé est :

```text
Decision Cycle
→ thèses et propositions
→ ordre pending_validation
→ paper_approval durable
→ Approve Proposal / Reject
→ ordre approved ou rejected
→ confirmation distincte Execute Paper Trade
→ fill Paper unique
→ positions, cash, NAV et audit mis à jour
→ order filled
→ paper_execution_status = paper_executed
```

La version 2.4 ajoute comme fonction centrale la constitution progressive du portefeuille : mandat versionné, admission de tickers, portefeuille cible, écarts réel/cible, montée en charge par tranches, cash réservé, réconciliation, rebalancement, sorties et remplacements gouvernés.

---

# 2. Principes d’architecture

## 2.1 Séparation des responsabilités

| Couche | Responsabilité | Décide ? | Modifie le portefeuille ? |
|---|---|---:|---:|
| Feature Engine Python | Prix, facteurs, exposition, risque, liquidité | Oui, calcul déterministe | Non |
| Agents / PPLX 27B | Interprétation, scénarios, propositions structurées | Non | Non |
| Portfolio Construction Engine | Mandat, cible, écarts, tranches et priorités | Oui, déterministe | Non |
| Consensus Engine | Agrégation pondérée et gardes structurelles | Oui, déterministe | Non |
| ZEPHR | Tradabilité, capacité, coûts et plafonds de taille | Oui, contrainte déterministe | Non |
| RUNE | Contrôles pré-trade, veto, limites | Oui, déterministe | Non |
| VESKA | Intégrité du mandat, préparation et gateway | Oui, sous mandat valide | Paper uniquement après autorisation |
| Manager | Admission, Approve, Reject, Confirm Paper Execution | Oui, gouvernance | Oui, à l’étape explicite |
| Broker Live | Hors périmètre actif | Non | Non |

## 2.2 Invariants de sécurité

- Aucun cycle ne peut modifier directement le portefeuille.
- Une approval n’est jamais une exécution.
- Une exécution Paper exige une approval approuvée, un ordre approuvé, une confirmation distincte et l’absence de fill existant.
- Un fill est unique par `order_id`.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- L’admission d’un ticker est distincte de son achat.
- Un écart portefeuille réel/cible ne crée jamais automatiquement un ordre.
- Les quantités et poids cibles sont calculés et bornés par Python.
- RUNE peut bloquer indépendamment du consensus.
- ZEPHR peut réduire ou bloquer une quantité indépendamment de la direction.
- Le Live reste désactivé tant que Paper, replay, risque, liquidité et observabilité ne sont pas démontrés.
- Les écritures critiques sont transactionnelles, idempotentes et auditables.

## 2.3 Source de vérité

| Domaine | Source de vérité |
|---|---|
| Prix | `prices` et contrôles de fraîcheur |
| Positions | `portfolio_positions` |
| Cash et NAV | `portfolio_state` |
| Intentions | `orders` |
| Exécutions | `fills` |
| Gouvernance Paper | `paper_approvals` |
| Audit transverse | `event_log` |
| Mandat portefeuille | `portfolio_mandates` cible |
| Allocations cibles | `target_allocations` cible |
| Votes | `agent_votes` cible |
| Consensus | `swarm_consensus` cible |
| Mandat d’exécution | `execution_mandates` cible |

---

# 3. Architecture cognitive DGX

## 3.1 Vue logique

```text
Données marché / macro / crypto / portefeuille / broker-reference
│
▼
Feature Engine Python
│
├─ facteurs
├─ valorisation
├─ liquidité
├─ risque
└─ portefeuille
│
▼
Orchestrateur de cycle
│
▼
Inference Router DGX
│
├─ priorité 0 : RUNE explanation / VESKA
├─ priorité 1 : NORO / ZEPHR / OKAPI / MARIN
└─ priorité 2 : TIDAL / LUMEN
│
▼
PPLX 27B local — instance unique
│
▼
JSON Schema / Pydantic
│
▼
Consensus + Portfolio Construction + ZEPHR + RUNE
│
▼
ExecutionMandate immuable et hashé
│
▼
Approval Gateway
│
▼
Manager humain
```

## 3.2 Runtime PPLX 27B

Dans son rôle runtime SWARM :

- l’instance sert les interfaces cognitives de TIDAL, NORO, LUMEN, ZEPHR, OKAPI, MARIN et VESKA ;
- pour RUNE, elle peut uniquement expliquer un verdict déjà calculé ;
- les prompts sont versionnés ;
- les sorties sont validées par schéma ;
- les appels sont journalisés dans `pplx_audit` ;
- les valeurs déterminantes sont recalculées ou vérifiées par Python ;
- aucune sortie brute du modèle ne devient directement un mandat, un ordre ou un fill.

## 3.3 Inference Router

Le routeur doit fournir :

- priorités d’agents ;
- concurrence limitée à 2–3 requêtes ;
- cache par hash des données, prompt et version ;
- lots de 10 tickers lorsque pertinent ;
- timeout individuel ;
- un retry maximal ;
- validation Pydantic ;
- mode dégradé explicite ;
- journalisation latence, route, erreur et résultat.

## 3.4 Cohabitation PROSIGNAL

PROSIGNAL est prioritaire sur le DGX. THESIUM respecte la fenêtre d’exclusion :

```text
08:55–09:20 Europe/Paris
```

Un verrou coopératif Redis ou fichier couvre les déclenchements manuels et débordements.

```text
verrou actif
→ mise en attente
→ après 7 minutes : mode dégradé
→ persistance llm_route = unavailable
```

Si NORO et LUMEN sont simultanément dégradés, aucun mandat BUY ne peut être formé. Les sorties déterministes MARIN restent possibles.

## 3.5 Outillage local du PPLX 27B

La même instance peut être utilisée hors runtime pour :

- inspection locale de fichiers sensibles ;
- inventaires de code et de schémas ;
- rapports factuels ;
- première revue de patch ;
- documentation et préparation de tests.

Ce rôle est séparé du runtime : il ne participe pas aux agents, au consensus, à RUNE ou à l’exécution, et n’est pas journalisé dans `pplx_audit` comme un appel d’agent.

---

# 4. Agents et responsabilités

| Agent | Mission | Pouvoir | Rôle du LLM |
|---|---|---|---|
| TIDAL | Découverte et admission d’univers | Long / observation ; pas de veto | Interpréter anomalies calculées |
| NORO | Juste valeur et qualité | Vote bidirectionnel | Comparer scénarios et expliquer |
| LUMEN | Sentiment et contexte | Vote bidirectionnel, conviction ≤ 7 | Synthétiser preuves fraîches |
| ZEPHR | Liquidité et capacité | Neutre ; plafonne ou bloque | Expliquer contraintes calculées |
| RUNE | Risque et veto | Veto déterministe | Explication post-verdict seulement |
| OKAPI | Couverture | Vote short si réduction du risque ; hedge mandates | Proposer parmi couvertures autorisées |
| MARIN | Réduction et sortie | Forced exit déterministe | Expliquer une règle existante |
| VESKA | Gateway d’exécution | Vérifie, ne vote pas | Justifier le plan et le mémo |

## 4.1 TIDAL

- Calcule momentum, volatilité, Sharpe, tendance, volume et corrélation.
- Produit des candidats et des dossiers d’admission.
- Ne crée pas d’ordre.

## 4.2 NORO

- Calcule juste valeur, multiples, DCF simplifié et qualité de bilan.
- Le vote est dérivé des faits calculés et de l’écart prix/valeur.

## 4.3 LUMEN

- Agrège actualité, sentiment, géopolitique et divergences prix-volume.
- Toute preuve cloud est horodatée et persistée pour replay.

## 4.4 ZEPHR

- Calcule volume USD, spread estimé, lot step, contract size, minimum lot, tick size et capacité.
- Produit `max_executable_qty`, `est_slippage_bps` et `constrained`.

## 4.5 RUNE

- Calcule VaR, concentration, exposition, corrélation, drawdown et limites.
- Produit `block`, `warn` ou `ignore` selon une politique déterministe.

## 4.6 OKAPI

- Détecte bêta, concentration, stress et drawdown.
- Produit des propositions de couverture soumises au même processus de gouvernance.

## 4.7 MARIN

- Applique `STOP_LOSS`, `TAKE_PROFIT`, `DRIFT`, `TIME_DECAY` et sorties forcées autorisées.

## 4.8 VESKA

- Vérifie hash, quantité finale, état de l’ordre et conditions d’exécution.
- Ne choisit ni le mandat ni le verdict de risque.

---

# 5. Consensus et sizing

## 5.1 Poids d’un vote

\[
w_i = \max\left(0, \frac{c_i - 5}{5}\right)
\]

Une conviction de 5 est une abstention de poids nul.

## 5.2 Convergence pondérée

\[
C = \frac{\left|\sum_i w_i s_i\right|}{\sum_i w_i}
\]

avec `long = +1`, `neutral = 0`, `short = -1`.

## 5.3 Gardes

```text
mandate_formed =
convergence_weighted >= threshold_for_regime
AND n_voting >= 3
AND total_weight >= 1.0
AND not rune_blocks
AND not zephr_constrained
```

## 5.4 Seuils par régime

| Régime | Seuil |
|---|---:|
| `risk_on` | 0,700 |
| `neutral` | 0,768 |
| `risk_off` | 0,850 |
| `crisis` | 0,900 |

## 5.5 Multiplicateurs de taille

| Convergence | Multiplicateur |
|---:|---:|
| ≥ 0,950 | 1,50 |
| 0,850–0,950 | 1,25 |
| 0,768–0,850 | 1,00 |
| 0,700–0,768 | 0,50 |
| < 0,700 | 0,00 |

Ordre d’application : régime → convergence → cible portefeuille → plafond ZEPHR → limites portefeuille → RUNE.

---

# 6. Univers et admission des tickers

## 6.1 Entités

| Entité | Rôle |
|---|---|
| `instruments` | Instruments suivis |
| `target_universe` | Univers stratégique cible |
| `universe_candidates` | Candidats TIDAL |
| `tradability_exclusions` | Exclusions |
| `instrument_broker_mapping` | Mapping et contraintes broker |
| `prices` | Prix historiques et référence |
| `universe_admission_decisions` | Décisions d’admission cibles |

## 6.2 Processus

```text
TIDAL candidate
→ qualité et fraîcheur des données
→ exclusions
→ mapping
→ ZEPHR
→ compatibilité mandat
→ décision d’admission
→ target_universe
```

Admission et achat sont deux décisions distinctes.

## 6.3 États

```text
candidate
under_review
admitted
rejected
suspended
removed
```

---

# 7. Cycle opérationnel

## 7.1 Préparation

1. Rafraîchir les données.
2. Calculer les features.
3. Contrôler qualité et fraîcheur.
4. Produire le diagnostic portefeuille.
5. Dégrader ou s’abstenir en cas de données insuffisantes.

## 7.2 Recherche

1. TIDAL actualise les candidats.
2. NORO, LUMEN, OKAPI, MARIN et la voix macro produisent leurs sorties.
3. ZEPHR calcule la capacité.
4. Le consensus calcule convergence et gardes.
5. Le Portfolio Construction Engine compare portefeuille réel et cible.
6. RUNE contrôle le portefeuille résultant.
7. Un mandat immuable peut être formé.

## 7.3 Gouvernance Paper

```text
mandat
→ ordre pending_validation
→ approval pending
→ Approve ou Reject
→ approved_not_executed
→ confirmation Execute Paper Trade
→ fill
```

---

# 8. Constitution progressive du portefeuille

## 8.1 Principe

Le portefeuille n’est pas la somme d’ordres opportunistes. Il est construit à partir d’un mandat, d’une cible, d’écarts et d’un plan de montée en charge gouverné.

## 8.2 Mandat portefeuille

Le mandat versionné contient :

- capital et devise ;
- objectif et horizon ;
- univers autorisé ;
- exposition brute et nette ;
- cash minimal, cible et maximal ;
- drawdown maximal ;
- nombre de positions ;
- poids maximal par instrument ;
- limites sectorielles, géographiques et par classe ;
- contraintes de concentration et corrélation ;
- shorts et couvertures autorisés ;
- fréquence de revue ;
- environnement Paper autorisé.

## 8.3 Diagnostic initial

Python calcule sans créer d’ordre :

- cash et cash réservé ;
- positions, quantités et coûts moyens ;
- prix et fraîcheur ;
- poids, expositions, bêta et concentration ;
- VaR, volatilité et drawdown ;
- positions hors mandat ou non tradables ;
- écart réel/mandat.

## 8.4 Portefeuille cible

Pour chaque instrument :

```text
target_weight
current_weight
weight_gap
target_quantity
current_quantity
quantity_gap
target_notional
current_notional
action_proposed
construction_stage
constraint_flags
```

Les poids et quantités sont calculés par Python à partir du mandat, des votes, du régime, de la diversification, de ZEPHR et de RUNE.

## 8.5 Actions normalisées

```text
OPEN
ADD
HOLD
TRIM
CLOSE
HEDGE
SUSPEND
```

## 8.6 Priorisation

Ordre recommandé :

```text
sorties forcées
→ violations de risque
→ réductions de concentration
→ couvertures
→ réductions vers cible
→ nouvelles entrées
→ renforcements
```

## 8.7 Montée en charge

États d’une position :

```text
candidate
admitted
watching
initial_entry
building
at_target
overweight
reducing
exiting
closed
suspended
```

Convention initiale configurable :

| Étape | Part cumulée maximale du poids cible |
|---|---:|
| Observation | 0 % |
| Entrée initiale | 25 % |
| Deuxième tranche | 50 % |
| Troisième tranche | 75 % |
| Position complète | 100 % |

Chaque tranche requiert données fraîches, thèse valide, recalcul cible, ZEPHR, RUNE, approval et confirmation Paper distincte.

## 8.8 Cash et risque réservés

Le moteur tient compte :

- du cash minimum ;
- du cash cible ;
- du cash réservé aux ordres approuvés ;
- du budget de risque réservé ;
- des limites calculées sur le portefeuille résultant ;
- des couvertures requises.

Le cash est une allocation possible, pas nécessairement un état d’incomplétude.

## 8.9 Écarts et matérialité

```text
portefeuille réel
vs
portefeuille cible
→ écarts matériels
→ propositions
→ contrôles
→ gouvernance
```

Un seuil de matérialité empêche les micro-ordres et le sur-rebalancement.

## 8.10 Exécution d’une tranche

Chaque tranche suit le workflow V3.3. Toute modification d’instrument, quantité, limite ou type requiert une nouvelle proposition.

## 8.11 Réconciliation

Après fill :

- mise à jour cash, quantité et coût moyen ;
- recalcul NAV, P&L, poids, exposition et risque ;
- recalcul de l’écart cible ;
- mise à jour de l’étape de construction ;
- contrôle du mandat ;
- audit ;
- aucune tranche suivante automatique.

## 8.12 Rebalancement

Types :

```text
rebalance de dérive
rebalance de risque
rebalance de régime
rebalance de conviction
rebalance de mandat
```

Chaque action de rebalancement reste gouvernée.

## 8.13 Sorties et remplacements

Une sortie précise motif, règle MARIN/RUNE, quantité, urgence, impact cash/risque et réadmission future. Une vente ne déclenche jamais automatiquement un remplacement.

## 8.14 Modèle de données cible

| Table | Finalité |
|---|---|
| `portfolio_mandates` | Mandats versionnés |
| `portfolio_construction_runs` | Calculs de cible |
| `target_allocations` | Poids et quantités cibles |
| `position_build_plans` | Plans par position |
| `position_build_steps` | Tranches et états |
| `universe_admission_decisions` | Admission et suspension |
| `rebalance_proposals` | Écarts et actions |
| `portfolio_constraint_snapshots` | Contraintes au moment de la décision |

## 8.15 Validation de la constitution

La fonction est validée lorsque :

1. une cible est calculable sans créer d’ordre ;
2. un ticker peut être admis sans achat ;
3. une position est construite en plusieurs tranches ;
4. chaque tranche repasse par ZEPHR, RUNE et manager ;
5. le cash réservé empêche le sur-engagement ;
6. les limites sont vérifiées sur le portefeuille résultant ;
7. une tranche rejetée n’a aucun effet ;
8. la réconciliation actualise les écarts ;
9. aucune tranche suivante n’est automatique ;
10. le replay peut reconstruire toutes les étapes.

---

# 9. Paper Execution explicite

## 9.1 Convention

```text
prix de référence = dernier prices.close
slippage = 0.001
frais = quantity × 0.005
BUY fill = close × 1.001
SELL fill = close × 0.999
```

## 9.2 Préconditions

- manager authentifié ;
- Live désactivé ;
- approval liée à un ordre ;
- approval `approved` ;
- `paper_execution_status = approved_not_executed` ;
- ordre `approved` ;
- aucun fill existant ;
- prix valide ;
- limite satisfaite ;
- cash/position suffisants ;
- contraintes RUNE et ZEPHR encore valides.

## 9.3 Transaction

```text
BEGIN IMMEDIATE
→ relire approval et order
→ vérifier absence de fill
→ recalculer conditions
→ créer fill
→ order = filled
→ approval = paper_executed
→ mettre à jour ledger
→ refresh portfolio
→ event_log
→ COMMIT
```

## 9.4 Validation réelle V3.3

| Élément | Valeur |
|---|---|
| Approval | `#4` |
| Order | `#674` |
| Fill | `#318` |
| Instrument | ZEC |
| Side | SELL |
| Quantité | 4 |
| Fill price | 1011.1878 |
| Frais | 0.02 |
| Slippage | 4.0488 |
| Audit | `order_filled_human_v33` |

## 9.5 Isolation

Le chemin humain n’appelle ni Live, ni Shadow, ni le runner de cycle.

## 9.6 Tests Paper obligatoires

- BUY ;
- SELL partiel ;
- SELL complet ;
- LIMIT non atteint ;
- ordre déjà rempli ;
- double clic et concurrence ;
- approval invalide ;
- prix absent ;
- vente supérieure à la position ;
- rollback injecté ;
- refus lorsque Live est activé en environnement isolé ;
- isolation Shadow ;
- cohérence comptable ;
- audit ;
- confirmation et rendu UI.

Python, pytest et RUNE produisent les validations. Une sortie LLM ne constitue pas une preuve.

## 9.7 Runbook

Référence cible :

```text
Documentation/RUNBOOK_PAPER_EXECUTION_V3_3.md
```

Il documente préconditions, confirmation, requêtes avant/après, incident, backup, rollback, idempotence et interdictions Live/Shadow.

---

# 10. Modèle de données

## 10.1 Tables existantes

`instruments`, `prices`, `theses`, `orders`, `fills`, `paper_approvals`, `portfolio_positions`, `portfolio_state`, `portfolio_history`, `risk_config`, `risk_policy_config`, `risk_pretrade_log`, `event_log`, `universe_candidates`, `tradability_exclusions`, tables shadow et replay.

## 10.2 Tables SWARM cibles

`agent_votes`, `swarm_consensus`, `execution_mandates`, `liquidity_assessments`, `hedge_mandates`, `gpu_contention_log`, `pplx_audit`.

## 10.3 Tables portefeuille cibles

`portfolio_mandates`, `portfolio_construction_runs`, `target_allocations`, `position_build_plans`, `position_build_steps`, `universe_admission_decisions`, `rebalance_proposals`, `portfolio_constraint_snapshots`.

## 10.4 Règles de migration

- migrations versionnées ;
- idempotence ;
- tests sur DB temporaire ;
- backup avant application ;
- aucun changement de base active sans autorisation manager ;
- index et contraintes vérifiés avant création.

---

# 11. API cible

## 11.1 Opérationnel

| Endpoint | Méthode | Rôle |
|---|---|---|
| `/api/orders/execute-cycle` | POST | Cycle |
| `/api/approvals/pending` | GET | Approvals pending |
| `/api/approvals/{id}/approve` | POST | Approval sans exécution |
| `/api/approvals/{id}/reject` | POST | Rejet |
| `/api/approvals/ready-to-execute` | GET | Ordres prêts |
| `/api/approvals/{id}/execute-paper` | POST | Exécution Paper |
| `/api/orders?limit=20` | GET | Order History |
| `/api/fills` | GET | Recent Fills |
| `/api/dashboard` | GET | Portefeuille |

## 11.2 Constitution cible

```text
GET  /api/portfolio/mandate
POST /api/portfolio/mandate/versions
GET  /api/portfolio/construction/latest
POST /api/portfolio/construction/run
GET  /api/portfolio/target-allocations
GET  /api/portfolio/gaps
GET  /api/portfolio/build-plans
GET  /api/portfolio/build-steps
GET  /api/universe/admissions
POST /api/universe/admissions/{id}/approve
POST /api/universe/admissions/{id}/reject
GET  /api/portfolio/rebalance-proposals
```

Ces contrats restent indicatifs jusqu’à la conception détaillée et la validation des schémas.

---

# 12. Architecture du code cible

```text
src/
├── agents/
├── consensus/
├── portfolio/
│   ├── mandate.py
│   ├── construction.py
│   ├── allocations.py
│   ├── build_plan.py
│   ├── rebalance.py
│   └── reconciliation.py
├── risk/
├── execution/
│   ├── adapter.py
│   ├── paper_gateway.py
│   └── ledger.py
├── inference/
├── research/
├── features/
├── orchestration/
└── storage/
schemas/
migrations/
prompts/
tests/
├── unit/
├── integration/
├── replay/
└── adversarial/
config/
scripts/
Documentation/
```

Le socle ThesiumDesk existant reste en place. La migration se fait par adaptateurs testables.

---

# 13. État de développement

## 13.1 Réalisé

- Paper Approval durable.
- Approve et Reject séparés de l’exécution.
- Diagnostic V3.2.
- Exécution Paper V3.3 réelle et auditée.
- Fill unique, cash, positions et NAV mis à jour.
- Recent Fills avant Order History.
- Order History limitée à 20.
- Live désactivé et Shadow isolé.

## 13.2 Prochaine priorité

P0 — Stabilisation : tests automatisés, runbook, rollback et diagnostic du 401 universe.

## 13.3 Dette connue

- méthodes et responsabilités d’exécution à modulariser ;
- mocks et dette frontend ;
- chaînes historiques mal encodées ;
- scripts et backups locaux à exclure du dépôt ;
- processus de constitution progressive à implémenter ;
- filtres et pagination à finaliser ;
- tests de concurrence et rollback à automatiser.

---

# 14. Couche d’outillage de développement — hors runtime

Le développement, la revue de code et la rédaction documentaire peuvent s’appuyer sur des modèles externes. Cette couche est strictement hors runtime et ne fait pas partie de l’architecture SWARM.

## 14.1 Autorisé

- proposer architecture, tests, patches et documentation ;
- analyser diffs, schémas et extraits anonymisés ;
- produire des plans de validation et de rollback ;
- relire contrats et migrations ;
- expliquer des erreurs fournies explicitement.

## 14.2 Interdit

- participer aux agents SWARM, au consensus ou au verdict RUNE ;
- écrire dans `orders`, `fills`, `paper_approvals`, `portfolio_*` ou `event_log` ;
- déclencher un Decision Cycle, une approval ou une exécution Paper ;
- activer `BROKER_LIVE_ENABLED` ;
- appeler Live ou Shadow ;
- committer, pousser ou modifier la base active sans autorisation manager ;
- recevoir des secrets, `.env`, configurations broker, base active ou logs bruts sensibles.

## 14.3 Validation

Aucune sortie d’un modèle externe ne constitue une validation. Les validations reposent sur :

- Python ;
- pytest ;
- JSON Schema et Pydantic ;
- RUNE ;
- tests d’intégration ;
- revue et autorisation manager.

## 14.4 Données sensibles

Ne quittent pas l’environnement local :

- `thesium.db` ;
- secrets, clés et tokens ;
- `.env` ;
- logs bruts ;
- configurations broker ;
- identifiants de compte ;
- portefeuilles non anonymisés.

## 14.5 Traçabilité séparée

L’outillage de développement n’utilise pas `pplx_audit`, réservé au runtime SWARM. Sa traçabilité repose sur le fil de priorité, la branche, les diffs, tests, commits, revues et plans de rollback.

---

# 15. Validation et runbooks

## 15.1 Principe

Une fonctionnalité n’est pas validée par un backend sain ou un appel API isolé. Le workflow fonctionnel attendu doit être démontré de bout en bout.

## 15.2 Catégories de tests

- unitaires ;
- intégration DB temporaire ;
- API ;
- UI E2E ;
- concurrence ;
- rollback ;
- replay ;
- adversariaux ;
- sécurité et isolation Live/Shadow.

## 15.3 Runbooks requis

- Paper Execution V3.3 ;
- constitution progressive ;
- admission de ticker ;
- migration DB ;
- incident et rollback ;
- DGX / PROSIGNAL ;
- restauration et sauvegarde.

---

# 16. Feuille de route P0 à P10

| Priorité | Contenu | Statut |
|---|---|---|
| P0 | Stabilisation Paper, tests, runbook, 401 | À ouvrir |
| P1 | Observabilité et UX | Planifiée |
| P2 | Gateway Paper modulaire | Planifiée |
| P3 | Benchmark PPLX 27B | Planifiée |
| P4 | Votes et consensus shadow | Planifiée |
| P5 | Router DGX / PROSIGNAL | Planifiée |
| P6 | ZEPHR et sizing | Planifiée |
| P7 | Consolidation agents | Planifiée |
| P8 | Replay et go/no-go | Planifiée |
| P9 | OKAPI, CI et stockage | Planifiée |
| P10 | Rollout consensus et sandbox ; Live désactivé | Bloquée par prérequis |

La constitution progressive est transversale : P0 teste ses invariants comptables, P1 l’expose, P2 sépare construction et exécution, P4 produit les propositions, P6 plafonne les tranches, P7 gère admissions et sorties, P8 la rejoue, P9 l’industrialise et P10 conserve ses barrières.

---

# 17. Gouvernance finale

```text
Le modèle externe conseille le développement mais n’entre jamais dans le runtime.
Le PPLX 27B local peut servir le runtime SWARM ou l’outillage local,
mais ces rôles sont strictement séparés.
Le LLM ne décide pas.
Python calcule, valide et persiste.
ZEPHR contraint.
RUNE peut bloquer.
Le mandat est immuable.
Le manager approuve puis autorise séparément l’exécution.
Le portefeuille se construit progressivement par tranches gouvernées.
Chaque tranche est recalculée, contrôlée, approuvée et exécutée séparément.
Le Live reste désactivé tant que Paper, replay, risque, liquidité,
gouvernance et observabilité ne sont pas démontrés.
```
