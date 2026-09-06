# THESIUM SWARM — Templates finaux des priorités P0 à P10

- **Version** : finale 1.1 — gouvernance de mise à jour continue
- **Date** : 5 septembre 2026
- **Document directeur** : `THESIUM_SWARM_architecture_operating_model_v2_3`
- **Usage** : copier un template complet dans un nouveau fil de développement.
- **Règle** : chaque fil est autonome ; le socle commun est donc volontairement répété.

---

# P0 — Stabilisation Paper Execution V3.3

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P0
Titre : Stabilisation Paper Execution V3.3

Objectif exact :
Geler le flux Paper V3.3 validé, documenter son comportement et empêcher les régressions avant d’élargir le périmètre fonctionnel.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Tout document spécifique utile aux tests, au modèle de données ou au runbook Paper
- Historique de travail et commits déjà réalisés sur la branche concernée, notamment 920e7b2, 2e08bbc et e538ecc

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- L’exécution réelle de référence est Approval #4 → Order #674 → Fill #318, ZEC SELL 4.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Ajouter les tests unitaires de PaperBroker.
- Ajouter des tests d’intégration SQLite sur base temporaire.
- Tester BUY, SELL partiel, SELL complet, LIMIT non atteint, double exécution et rollback.
- Vérifier l’unicité fills(order_id) et la protection contre les retries concurrents.
- Tester le refus strict du chemin Paper lorsque Live est activé dans un environnement isolé.
- Rédiger un runbook d’exécution, de contrôle, d’incident et de rollback Paper.
- Diagnostiquer séparément le 401 de /api/universe/candidates sans rendre la route publique par défaut.

Hors périmètre :
- Aucun changement du consensus SWARM.
- Aucun changement de stratégie.
- Aucun broker réel.
- Aucun refactor large sans nécessité démontrée pour la sécurité ou les tests.

Critères de sortie mesurables :
- Tous les tests Paper automatisés passent sur une DB temporaire.
- Un second appel d’exécution ne crée jamais un second fill.
- Une exception injectée produit un rollback complet et cohérent.
- Un LIMIT non atteint reste approved sans fill ni impact portefeuille.
- Le runbook est complet et versionné.
- Le 401 universe est corrigé ou documenté avec cause, risque et action suivante.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P1 — Observabilité et UX d’exécution Paper

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P1
Titre : Observabilité et UX d’exécution Paper

Objectif exact :
Permettre au manager de comprendre immédiatement ce qui est proposé, approuvé, exécuté, bloqué ou rejeté, sans utiliser DevTools ni effectuer de requêtes SQL manuelles.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Maquettes, captures et documents UX disponibles dans l’espace
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Recent Fills apparaît avant Order History.
- Recent Fills affiche Fill ID, PAPER, instrument, side, quantité, prix, frais, slippage, timestamp et mémo.
- Order History est séparé et limité aux 20 derniers ordres.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Créer une navigation Approval → Order → Fill → Audit.
- Ajouter des détails auditables dans l’UI sans dupliquer les sources de vérité.
- Ajouter les filtres Order History : All, Action Required, Approved, Filled, Rejected, Cancelled.
- Ajouter filtres ticker et période lorsque les contrats API sont prêts.
- Ajouter pagination ou Load More aux ordres et fills.
- Afficher le timestamp absolu au survol d’une date relative.
- Ajouter un toast post-exécution avec Fill ID, prix, frais, slippage et accès direct au fill.
- Uniformiser la langue et les libellés de l’interface.

Hors périmètre :
- Aucun changement aux calculs de fill, frais, slippage ou portefeuille.
- Aucun changement de RUNE ou du consensus.
- Aucun accès Live.

Critères de sortie mesurables :
- Un manager retrouve le fill et l’audit d’un ordre sans console ni SQL.
- Les ordres nécessitant une action restent toujours visibles.
- Les filtres et la pagination donnent des résultats déterministes.
- Les tables restent lisibles sur un écran standard.
- Les erreurs API sont présentées clairement sans masquer les données existantes.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P2 — Consolidation du Paper Execution Gateway

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P2
Titre : Consolidation et modularisation du Paper Execution Gateway

Objectif exact :
Réduire la dette technique et rendre le chemin Paper modulaire, configuré, testable et prêt à accueillir un futur adaptateur broker, sans ouvrir ni appeler le Live.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Tests et runbook produits en P0
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- PaperBroker applique actuellement 10 bps de slippage et 0.005 de frais par unité.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Cartographier le flux V3.3 actuel.
- Séparer pricing, validation d’état, persistence du fill, ledger cash/positions, transitions order/approval et audit.
- Définir une interface broker publique cohérente.
- Éliminer la dépendance du code métier à des méthodes privées de PaperBroker.
- Centraliser slippage, frais et arrondis dans une configuration versionnée.
- Transformer les migrations ad hoc en migrations officielles, idempotentes et testées.
- Maintenir la compatibilité des endpoints et de l’UI.

Hors périmètre :
- Aucun changement fonctionnel non couvert par tests.
- Aucun broker réel.
- Aucune migration PostgreSQL.
- Aucun changement de stratégie ou de consensus.

Critères de sortie mesurables :
- Aucun flux métier ne dépend d’une méthode privée d’adapter.
- Chaque responsabilité est testable séparément.
- La configuration Paper est reproductible par environnement.
- Les migrations sont idempotentes.
- Tous les tests P0 restent verts sans modification du comportement attendu.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P3 — Benchmark PPLX 27B local

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P3 — Jalon 0
Titre : Benchmark et qualification PPLX 27B local

Objectif exact :
Démontrer que PPLX 27B local apporte une valeur mesurable pour les rôles agents, sans lui déléguer de décision déterministe, de risque, de sizing ou d’exécution.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Résultats et scripts de benchmarks existants disponibles dans l’espace ou le dépôt
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Le modèle local cible est qwen38-27b-dflash2-20260824 via endpoint compatible OpenAI local.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Définir un corpus de 50 à 100 cas représentatifs.
- Couvrir les rôles TIDAL, NORO, LUMEN, ZEPHR, OKAPI, MARIN et VESKA.
- Versionner prompts et schémas de sortie.
- Mesurer validité JSON, latence, taux d’échec, stabilité inter-runs et qualité de justification.
- Définir des seuils d’acceptation par agent.
- Persister les métadonnées de benchmark dans pplx_audit ou un stockage officiel équivalent.

Hors périmètre :
- Aucun vote de production.
- Aucun ordre généré par le benchmark.
- Aucun changement de RUNE.
- Aucun appel broker.

Critères de sortie mesurables :
- Corpus, prompts et schémas sont versionnés.
- Le benchmark est reproductible.
- Un rapport compare objectivement les rôles et scénarios.
- Chaque agent reçoit un statut qualifié, dégradé ou non retenu.
- Aucune sortie LLM non validée n’entre dans une décision de portefeuille.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P4 — Votes structurés et consensus pondéré en shadow

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P4 — Jalon 1
Titre : Agent Votes et Weighted Consensus en Shadow

Objectif exact :
Créer agent_votes, swarm_consensus et les calculs de consensus pondéré en shadow, sans modifier le chemin Paper de production ni créer d’ordre à partir du shadow.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Résultats du benchmark P3
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Le consensus SWARM doit initialement rester sans effet sur orders, fills et paper_approvals.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Créer agent_votes, swarm_consensus et execution_mandates.
- Définir AgentVote, RiskVerdict et ExecutionMandate.
- Implémenter la formule pondérée et les gardes n_voting >= 3 et total_weight >= 1.0.
- Appliquer le seuil par régime, le veto RUNE et la contrainte ZEPHR.
- Exécuter le consensus en shadow sur les cycles existants.
- Persister et visualiser les divergences avec le comportement historique.

Hors périmètre :
- Aucun mandat shadow ne devient un ordre.
- Aucun changement du flux Paper V3.3.
- Aucun remplacement de RUNE.
- Aucun Live.

Critères de sortie mesurables :
- Les votes sont uniques par cycle, ticker et agent.
- Le consensus est reproductible à partir des données persistées.
- Les gardes bloquent les faux consensus.
- Les divergences sont inspectables.
- Aucune écriture n’apparaît dans orders, fills ou paper_approvals à cause du shadow.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P5 — Inference Router DGX et PROSIGNAL

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P5 — Jalon 2
Titre : Inference Router DGX, cache, batching et verrou PROSIGNAL

Objectif exact :
Rendre l’utilisation du DGX gouvernée, performante et compatible avec la charge prioritaire PROSIGNAL grâce à une file d’inférence, un cache, des priorités, des timeouts et des modes dégradés auditables.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Résultats du benchmark P3 et contrats P4
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- PROSIGNAL garde la priorité DGX entre 08:55 et 09:20 Europe/Paris.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Construire les priorités : P0 RUNE/VESKA, P1 NORO/ZEPHR/OKAPI/MARIN, P2 TIDAL/LUMEN.
- Limiter la concurrence à 2 ou 3 requêtes.
- Ajouter cache hashé, batching, timeout et retry unique.
- Implémenter le verrou coopératif PROSIGNAL et la fenêtre d’exclusion.
- Persister routes, latences, erreurs, contention et états dégradés.
- Bloquer la formation d’un mandat BUY si NORO et LUMEN sont simultanément dégradés.

Hors périmètre :
- Aucun changement direct de l’exécution Paper.
- Aucun LLM non schématisé dans un chemin critique.
- Aucun Live.

Critères de sortie mesurables :
- Les priorités et la concurrence sont testables et observables.
- Aucun conflit DGX avec PROSIGNAL dans la fenêtre réservée.
- Les états dégradés sont explicites et persistés.
- La règle de double dégradation NORO/LUMEN est testée.
- Toutes les requêtes LLM sont auditables.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P6 — ZEPHR liquidité et sizing

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P6 — Jalon 3
Titre : ZEPHR Liquidité et sizing exécutable

Objectif exact :
Garantir que toute proposition est techniquement exécutable et correctement bornée avant de devenir un mandat, grâce à des contraintes de liquidité déterministes.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Modèles de données et résultats P4/P5
- Données de marché, mappings et contraintes broker disponibles
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- ZEPHR ne vote pas directionnellement ; il réduit la taille ou bloque.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Créer liquidity_assessments et le contrat ZEPHR.
- Calculer ou estimer ADV, volume USD, spread, lot step, minimum lot, tick size, tick value et contract size.
- Produire liquidity_score, max_executable_qty, est_slippage_bps, constrained, source et raisons.
- Intégrer le plafond ZEPHR avant le contrôle RUNE final.
- Afficher les contraintes dans le mandat et l’approval Paper.
- Tester instruments non tradables, tailles excessives et données insuffisantes.

Hors périmètre :
- Aucun appel Live.
- Aucun changement directionnel du consensus.
- Aucun contournement de RUNE.

Critères de sortie mesurables :
- Toute proposition possède une taille maximale ou une raison de blocage.
- Une taille excessive ne peut pas atteindre l’exécution.
- Les données manquantes conduisent à un blocage ou une dégradation explicite.
- Les contraintes sont visibles dans l’audit et l’UI.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P7 — Consolidation TIDAL, NORO, LUMEN et MARIN

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P7 — Jalon 4
Titre : Consolidation des agents directionnels et de sortie

Objectif exact :
Remplacer progressivement les comportements agents historiques par des contrats SWARM auditables pour TIDAL, NORO, LUMEN et MARIN, d’abord en shadow.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Résultats P3 à P6
- Prompts, schémas et contextes agents existants
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Les agents consolidés restent en shadow jusqu’à une validation explicite.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- TIDAL : découverte, qualification, exclusion et admission d’univers.
- NORO : valorisation, qualité, preuves et calculs hors LLM.
- LUMEN : sentiment, fraîcheur, provenance, plafonnement et dégradation.
- MARIN : règles STOP_LOSS, TAKE_PROFIT, DRIFT et TIME_DECAY.
- Versionner prompts, schémas, données d’entrée et sorties.
- Comparer les sorties shadow à l’existant.

Hors périmètre :
- Aucun ordre direct émis par un agent LLM.
- Aucun changement de gouvernance Paper.
- Aucun contournement de RUNE.
- Aucun Live.

Critères de sortie mesurables :
- Chaque agent possède un contrat d’entrée et de sortie documenté.
- Chaque sortie est rattachée à des données, preuves et versions.
- Les échecs et états dégradés sont persistés.
- Les sorties MARIN sont reproductibles sans LLM.
- Les résultats shadow sont comparables au comportement historique.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P8 — Replay historique et go/no-go

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P8 — Jalon 5
Titre : Replay historique et décision go/no-go du consensus SWARM

Objectif exact :
Mesurer l’impact réel du consensus SWARM sur données historiques avant toute bascule, et produire une décision go/no-go explicite, reproductible et auditée.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- Résultats, schémas et configurations P3 à P7
- Backtests, historiques, snapshots et journaux disponibles
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Le replay ne doit créer aucun ordre ou fill dans la base opérationnelle.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Construire un moteur de replay déterministe par cycle, date et ticker.
- Rejouer comportement historique et consensus SWARM avec les mêmes données disponibles au moment du cycle.
- Intégrer frais, slippage Paper et contraintes ZEPHR.
- Comparer taux de mandat, turnover, concentration, exposition, drawdown, P&L, blocages RUNE et liquidité.
- Analyser les divergences importantes.
- Définir des critères formels de go/no-go.

Hors périmètre :
- Aucun ordre Paper ou Live créé par le replay.
- Aucun look-ahead bias accepté.
- Aucun ajustement opportuniste non versionné.
- Aucune bascule automatique après le rapport.

Critères de sortie mesurables :
- Le replay est relançable et donne les mêmes résultats.
- Les données, règles, prompts et paramètres sont versionnés.
- Le rapport quantitatif et qualitatif est complet.
- Les biais et limites sont documentés.
- La décision go/no-go est explicite et bloque la suite en cas d’échec.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P9 — OKAPI et industrialisation

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P9 — Jalon 6
Titre : OKAPI, industrialisation, CI, alerting et préparation stockage

Objectif exact :
Ajouter la couverture gouvernée et préparer la scalabilité opérationnelle, les tests continus, les alertes et les sauvegardes, sans activer le Live ni migrer PostgreSQL sans justification objective.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Résultats et critères P0 à P8
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Toute couverture OKAPI doit subir les mêmes contrôles que les ordres standard.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Construire OKAPI et hedge_mandates.
- Soumettre les couvertures à RUNE, ZEPHR et à la gouvernance manager.
- Installer une CI pour syntaxe, tests unitaires, intégration et sécurité de base.
- Ajouter alertes sur jobs, LLM, transactions, idempotence et anomalies portefeuille.
- Documenter sauvegardes, restauration et exploitation.
- Évaluer SQLite vs PostgreSQL sur critères de concurrence, volume et multi-processus.

Hors périmètre :
- Aucun broker Live.
- Aucune migration PostgreSQL sans décision documentée.
- Aucun hedge automatique sans approval et confirmation Paper.

Critères de sortie mesurables :
- Les couvertures sont distinctes, auditables et gouvernées.
- La CI bloque les régressions essentielles.
- Les alertes sont testées.
- Les procédures de backup et restore sont testées.
- La décision SQLite/PostgreSQL est justifiée par des métriques.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---

# P10 — Bascule contrôlée et préparation Live sans activation

```text
Contexte projet : THESIUM SWARM / ThesiumDesk.

Priorité : P10 — Jalon 7 / préparation Live
Titre : Bascule contrôlée du consensus SWARM et préparation Live sans activation

Objectif exact :
Préparer une bascule graduelle et réversible du consensus SWARM vers le Paper de production, puis préparer un environnement broker sandbox, sans activer de trading Live tant que tous les prérequis de tests, replay, risque, gouvernance et observabilité ne sont pas démontrés.

Documents de référence à utiliser :
- THESIUM_SWARM_architecture_operating_model_v2_3
- THESIUM_SWARM_architecture_operating_model_v2_2.docx, comme historique d’architecture
- THESIUM_SWARM_specification_v2_1.docx
- GITHUB_WORKFLOW_THESIUM_DESK.md
- Rapports de clôture P0 à P9
- Rapport replay et décision go/no-go P8
- Historique de travail et commits déjà réalisés sur la branche concernée

État déjà validé :
- Paper Execution V3.3 fonctionne de bout en bout.
- Le manager approuve séparément de l’exécution.
- L’exécution crée un fill Paper unique et met à jour positions, cash, NAV et event_log.
- Le broker Live est désactivé.
- Le Shadow broker reste séparé.
- Les changements doivent préserver ces invariants.
- Aucune activation Live n’est autorisée dans ce fil.

Contraintes impératives :
- Ne jamais activer, appeler ou simuler un broker Live hors environnement explicitement prévu.
- Le LLM n’est jamais l’autorité de décision.
- Python/RUNE restent déterministes et fail-closed pour le risque.
- Toute écriture doit être précédée d’un plan, de contrôles et d’un backup.
- Préférer des patches atomiques et des commits petits, lisibles et réversibles.
- Ne pas ajouter les fichiers .bak.*, les bases SQLite, artefacts temporaires ou scripts ponctuels au dépôt sans décision explicite.
- Toute modification doit être testée avant commit.
- Toute validation doit préciser les critères de réussite et d’échec.

Périmètre spécifique :
- Auditer les prérequis P0 à P9.
- Définir le rollout shadow → advisory → gated Paper.
- Définir métriques, seuils d’arrêt et rollback du consensus.
- Définir un adapter broker sandbox/demo isolé de PaperBroker.
- Construire et tester kill switch, plafonds de notionnel, quantité, fréquence, exposition et pertes.
- Définir la réconciliation broker/order/fill/portfolio.
- Préparer la checklist formelle de revue Live.

Hors périmètre :
- Aucune activation Live.
- Aucun secret broker dans Git.
- Aucun ordre réel.
- Aucun contournement de RUNE, ZEPHR ou de la confirmation manager.
- Aucun calendrier Live imposé indépendamment des preuves.

Critères de sortie mesurables :
- La bascule du consensus Paper est graduelle, mesurée et réversible.
- Le sandbox ne peut pas déclencher un ordre réel.
- Kill switch et limites sont testés.
- Les écarts de réconciliation sont détectés et alertés.
- Une checklist de gouvernance Live est complète.
- BROKER_LIVE_ENABLED reste False à la clôture.

Attendu dans ce fil :
1. Lire les documents de référence pertinents.
2. Établir le périmètre et les invariants.
3. Proposer l’architecture et le plan de travail.
4. Identifier les fichiers et tables concernés avant modification.
5. Donner les tests de non-régression.
6. Proposer des commits atomiques.
7. Mettre à jour la documentation de suivi lors de la clôture.

Commence par :
- résumer l’objectif ;
- lister les critères de sortie mesurables ;
- identifier les risques ;
- proposer le plan en étapes ;
- ne proposer aucun patch avant que le plan soit validé.
```

---


# Gouvernance de mise à jour continue

Ce document est le registre directeur des priorités P0 à P10. Il doit être actualisé à la clôture de chaque priorité avant l’ouverture du fil suivant.

## Statut initial des priorités

| Priorité | Statut | Condition d’ouverture | Condition de clôture |
|---|---|---|---|
| P0 | À ouvrir | V3.3 livrée et documentée | Tests Paper, runbook et diagnostic 401 terminés |
| P1 | Planifiée | P0 clôturée ou dérogation documentée | Parcours Approval → Order → Fill → Audit exploitable sans DevTools |
| P2 | Planifiée | P0 stabilisée ; P1 recommandée | Gateway modulaire, public, configuré et couvert par tests |
| P3 | Planifiée | Socle Paper stable | Benchmark PPLX reproductible et décision par rôle |
| P4 | Planifiée | P3 qualifiée | Consensus shadow déterministe, auditable et sans effet portefeuille |
| P5 | Planifiée | P3 et P4 disponibles | Router DGX, dégradation et verrou PROSIGNAL validés |
| P6 | Planifiée | Contrats de mandat disponibles | Contraintes ZEPHR calculées, auditables et bloquantes |
| P7 | Planifiée | P3 à P6 suffisamment stables | Agents consolidés en shadow avec contrats versionnés |
| P8 | Planifiée | P4 à P7 clôturées | Replay reproductible et décision go/no-go formelle |
| P9 | Planifiée | P8 favorable ou dette explicitement acceptée | OKAPI, CI, alerting et stratégie de stockage validés |
| P10 | Bloquée par prérequis | P0 à P9 et go/no-go favorable | Rollout Paper réversible et sandbox prêt ; Live toujours désactivé |

Statuts autorisés : `À ouvrir`, `En cours`, `Partiellement terminée`, `Clôturée`, `Bloquée`, `Reportée`.

## Mise à jour obligatoire en fin de priorité

À la clôture de chaque priorité, effectuer les opérations suivantes dans cet ordre :

1. Vérifier chaque critère de sortie et enregistrer le résultat réel : réussi, échoué ou non exécuté.
2. Ajouter la fiche de clôture de la priorité dans ce document.
3. Mettre à jour son statut dans le registre ci-dessus.
4. Reporter les nouveaux invariants dans la section `État déjà validé` de toutes les priorités dépendantes.
5. Mettre à jour les documents de référence et leurs versions.
6. Mettre à jour le document `THESIUM_SWARM_architecture_operating_model` si l’architecture, les flux, les tables, les endpoints ou les règles de gouvernance ont changé.
7. Mettre à jour la spécification fonctionnelle si un comportement utilisateur ou métier a changé.
8. Mettre à jour le workflow Git si les règles de branche, test, migration, rollback ou exploitation ont changé.
9. Vérifier que les commits et la branche distante correspondent exactement aux livrables documentés.
10. Actualiser le prompt de la priorité suivante avant d’ouvrir son fil.

## Fiche de clôture obligatoire

Copier cette fiche à la fin du présent document pour chaque priorité terminée, bloquée ou reportée :

```text
FICHE DE CLÔTURE DE PRIORITÉ

Priorité :
Titre :
Statut final : Clôturée / Partiellement terminée / Bloquée / Reportée
Date d’ouverture :
Date de clôture :
Responsable de validation :

Objectif initial :

Résultat obtenu :

Critères de sortie :
- Critère 1 : Réussi / Échoué / Non exécuté — preuve
- Critère 2 : Réussi / Échoué / Non exécuté — preuve
- Critère 3 : Réussi / Échoué / Non exécuté — preuve

Livrables :
- 

Fichiers modifiés :
- fichier : raison

Tables, index et migrations :
- objet : modification / aucune

Endpoints et contrats API :
- endpoint : modification / aucune

Tests exécutés :
- commande ou scénario : résultat

Validation fonctionnelle de bout en bout :
- scénario : résultat

Garanties de sécurité vérifiées :
- Live désactivé : Oui / Non
- Shadow isolé : Oui / Non
- RUNE fail-closed préservé : Oui / Non
- Idempotence vérifiée : Oui / Non / Non applicable
- Rollback testé : Oui / Non / Non applicable

Branche Git :
Commits :
Push distant vérifié : Oui / Non
Pull Request / merge :

Rollback disponible :

Dette et risques résiduels :
- 

Éléments explicitement hors périmètre :
- 

Documents mis à jour :
- 

Nouveaux invariants à reporter dans les priorités suivantes :
- 

Décision sur la priorité suivante : Ouvrir / Bloquer / Reporter
Priorité suivante :
Conditions ou prérequis :
```

## Règles de version documentaire

- Incrémenter la version mineure de ce document après chaque clôture : `1.1`, `1.2`, `1.3`, etc.
- Incrémenter la version majeure si l’ordre des priorités, la gouvernance ou les invariants structurants changent.
- Conserver un seul document courant clairement identifié comme référence.
- Archiver les versions précédentes sans les utiliser comme source opérationnelle principale.
- Mentionner dans chaque fiche de clôture le hash Git correspondant à l’état documenté.
- Ne jamais déclarer une priorité clôturée sur la seule base d’un backend sain ou d’un test partiel : le workflow fonctionnel attendu doit être validé de bout en bout.

## Mise à jour du prompt suivant

Avant d’ouvrir une nouvelle priorité :

1. Partir du template correspondant dans ce document.
2. Remplacer son `État déjà validé` par les faits réellement démontrés lors des priorités précédentes.
3. Ajouter les nouveaux documents et commits de référence.
4. Retirer les hypothèses devenues fausses ou obsolètes.
5. Ajouter les dettes qui constituent un risque pour cette priorité.
6. Vérifier les dépendances et prérequis.
7. Conserver intégralement les contraintes de gouvernance et de sécurité.

## Journal des clôtures

| Priorité | Date | Statut final | Branche | Commits principaux | Document d’architecture | Décision suivante |
|---|---|---|---|---|---|---|
| P0 | — | À ouvrir | — | — | v2.3 | — |
| P1 | — | Planifiée | — | — | v2.3 | — |
| P2 | — | Planifiée | — | — | v2.3 | — |
| P3 | — | Planifiée | — | — | v2.3 | — |
| P4 | — | Planifiée | — | — | v2.3 | — |
| P5 | — | Planifiée | — | — | v2.3 | — |
| P6 | — | Planifiée | — | — | v2.3 | — |
| P7 | — | Planifiée | — | — | v2.3 | — |
| P8 | — | Planifiée | — | — | v2.3 | — |
| P9 | — | Planifiée | — | — | v2.3 | — |
| P10 | — | Bloquée par prérequis | — | — | v2.3 | — |

---

# Séquence recommandée

| Ordre | Priorité | Dépendance | Résultat attendu |
|---:|---|---|---|
| 1 | P0 | V3.3 validée | Paper testé, gelé et documenté |
| 2 | P1 | P0 | Observabilité complète manager |
| 3 | P2 | P0–P1 | Gateway Paper modulaire |
| 4 | P3 | P2 recommandé | PPLX 27B qualifié par rôle |
| 5 | P4 | P3 | Consensus SWARM en shadow |
| 6 | P5 | P3–P4 | Routeur DGX gouverné |
| 7 | P6 | P4–P5 | Sizing ZEPHR exécutable |
| 8 | P7 | P3–P6 | Agents consolidés en shadow |
| 9 | P8 | P4–P7 | Replay et go/no-go |
| 10 | P9 | P8 | OKAPI et industrialisation |
| 11 | P10 | P0–P9 | Rollout Paper et sandbox ; Live désactivé |

# Règle de clôture globale

Ne commencer une nouvelle priorité que lorsque la précédente est explicitement :

- **clôturée** avec critères de sortie atteints ;
- **bloquée** avec cause et action documentées ; ou
- **reportée** avec dette, risque et dépendance identifiés.
