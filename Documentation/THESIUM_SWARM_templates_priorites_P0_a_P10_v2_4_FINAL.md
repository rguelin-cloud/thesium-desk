# THESIUM SWARM — Templates finaux des priorités P0 à P10 — alignés v2.4

- **Version** : finale 2.0
- **Date** : 5 septembre 2026
- **Document directeur** : `THESIUM_SWARM_architecture_operating_model_v2_4`
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Ajouter les tests de constitution multi-tranches, de cash réservé, de matérialité des écarts et d’absence de tranche automatique.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Exposer portefeuille réel, portefeuille cible, écarts, cash réservé, admissions et étapes de construction.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Séparer explicitement Portfolio Construction Engine, Paper Execution Gateway et ledger portefeuille.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Vérifier que le LLM n’a aucune autorité sur les poids cibles, quantités, budgets de risque ou tranches.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Faire produire au consensus des propositions structurées ; aucun vote ou consensus ne crée directement un ordre.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Séparer dans le routage et l’audit les appels runtime SWARM des usages locaux de développement.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Évaluer et plafonner chaque tranche de construction, chaque admission et chaque rebalancement.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Formaliser TIDAL pour l’admission et MARIN pour la réduction, la sortie et les règles de réadmission.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Rejouer mandat, admissions, portefeuille cible, tranches, cash réservé, réconciliations et rebalancements sans look-ahead.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Évaluer les couvertures sur le portefeuille résultant et intégrer les invariants de construction à la CI.
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
- THESIUM_SWARM_architecture_operating_model_v2_4
- THESIUM_SWARM_architecture_operating_model_v2_3, comme historique gelé
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
- La constitution progressive du portefeuille est une fonction centrale : mandat, admission, cible, écarts, tranches, réconciliation et rebalancement.
- L’admission d’un ticker reste distincte de son achat.
- Une tranche exécutée n’autorise jamais automatiquement la tranche suivante.
- Les rôles runtime SWARM, outillage local PPLX 27B et modèles externes de développement restent strictement séparés.
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
- Les modèles externes restent hors runtime et ne peuvent participer aux agents, au consensus, à RUNE ou à l’exécution.
- Les données sensibles, la base active, les secrets, les logs bruts et les configurations broker ne quittent pas l’environnement local.
- Python, pytest, les contrôles de schéma et RUNE produisent les verdicts techniques ; aucune sortie LLM ne constitue une validation.

Périmètre spécifique :
- Conserver la construction progressive, la gouvernance par tranche et le cash réservé dans tout rollout Paper ou sandbox.
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


# Gouvernance de mise à jour des priorités

Ce document est actualisé à la fin de chaque priorité avant l’ouverture de la suivante.

## Statuts autorisés

`À ouvrir`, `En cours`, `Partiellement terminée`, `Clôturée`, `Bloquée`, `Reportée`.

## Mise à jour obligatoire en clôture

1. Vérifier chaque critère de sortie avec une preuve.
2. Compléter la fiche de fin de priorité officielle.
3. Mettre à jour le statut et le journal des priorités.
4. Reporter les nouveaux invariants dans les templates dépendants.
5. Mettre à jour l’architecture v2.4 ou sa version suivante si nécessaire.
6. Mettre à jour spécifications, runbooks et workflow Git concernés.
7. Vérifier branche, commits, push distant et rollback.
8. Actualiser le prompt de la priorité suivante.
9. Ne pas déclarer la priorité terminée sur la seule base d’un backend sain ou d’un test partiel.

## Référence de clôture

Utiliser le document :

```text
THESIUM_SWARM_fiche_fin_de_priorite
```

## Registre initial

| Priorité | Statut | Dépendance principale |
|---|---|---|
| P0 | À ouvrir | V3.3 validée |
| P1 | Planifiée | P0 |
| P2 | Planifiée | P0–P1 |
| P3 | Planifiée | Socle Paper stable |
| P4 | Planifiée | P3 |
| P5 | Planifiée | P3–P4 |
| P6 | Planifiée | P4–P5 |
| P7 | Planifiée | P3–P6 |
| P8 | Planifiée | P4–P7 |
| P9 | Planifiée | P8 |
| P10 | Bloquée par prérequis | P0–P9 et go/no-go favorable |

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
| 11 | P10 | P0–P9 + go/no-go | Rollout Paper et sandbox ; Live désactivé |

# Règle de clôture globale

Ne commencer une nouvelle priorité que lorsque la précédente est explicitement :

- **clôturée** avec critères de sortie atteints ;
- **bloquée** avec cause et action documentées ; ou
- **reportée** avec dette, risque et dépendance identifiés.
