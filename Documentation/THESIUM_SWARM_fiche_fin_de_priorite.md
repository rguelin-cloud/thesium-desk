# THESIUM SWARM — Fiche de fin de priorité

- **Version du formulaire** : 1.0
- **Document d’architecture de référence** : `THESIUM_SWARM_architecture_operating_model_v2_4`
- **Usage** : compléter cette fiche à la clôture de chaque priorité P0 à P10
- **Règle** : une priorité ne peut être déclarée clôturée sans preuves de validation fonctionnelle, technique, de sécurité et documentaire adaptées à son périmètre

---

# 1. Identification

| Champ | Valeur |
|---|---|
| Priorité | P… |
| Titre |  |
| Statut final | Clôturée / Partiellement terminée / Bloquée / Reportée |
| Date d’ouverture |  |
| Date de clôture |  |
| Responsable de validation |  |
| Branche Git |  |
| Pull Request |  |
| Version architecture au démarrage |  |
| Version architecture à la clôture |  |

---

# 2. Objectif

## Objectif initial

```text
Recopier l’objectif exact du template de priorité.
```

## Résultat obtenu

Décrire le comportement effectivement livré, sans confondre code écrit, backend sain et workflow fonctionnel validé.

```text
Résultat :
```

## Écart par rapport à l’objectif

```text
Aucun / Écart documenté :
```

---

# 3. Périmètre réalisé

## Réalisé

- [ ] Élément 1
- [ ] Élément 2
- [ ] Élément 3

## Non réalisé

- Élément : raison, risque, décision.

## Hors périmètre confirmé

- Élément volontairement non traité.

---

# 4. Critères de sortie

Pour chaque critère, indiquer `Réussi`, `Échoué` ou `Non exécuté`, puis fournir une preuve.

| Critère | Statut | Preuve | Commentaire |
|---|---|---|---|
| Critère 1 |  | Test, capture, requête, commit |  |
| Critère 2 |  |  |  |
| Critère 3 |  |  |  |

## Décision sur la priorité

```text
Tous les critères obligatoires sont-ils atteints ? Oui / Non
Décision : Clôturer / Clôturer avec dette acceptée / Bloquer / Reporter
Justification :
```

---

# 5. Architecture livrée

## Composants ajoutés ou modifiés

| Composant | Responsabilité | Changement |
|---|---|---|
|  |  |  |

## Flux fonctionnel final

```text
Décrire le workflow de bout en bout livré.
```

## Invariants préservés

- [ ] Le LLM n’est pas l’autorité de décision.
- [ ] Python reste la source des calculs et validations déterministes.
- [ ] RUNE reste fail-closed et peut bloquer.
- [ ] Le manager autorise séparément les actions Paper.
- [ ] Le Live reste désactivé.
- [ ] Le Shadow reste isolé du chemin Paper humain.
- [ ] Les opérations critiques sont idempotentes.
- [ ] Les écritures critiques sont transactionnelles.
- [ ] La constitution progressive reste gouvernée par tranche.
- [ ] Une tranche exécutée n’autorise pas automatiquement la suivante.
- [ ] L’admission d’un ticker reste distincte de son achat.
- [ ] L’outillage externe reste hors runtime.

## Nouveaux invariants

- Invariant à reporter dans les priorités suivantes.

---

# 6. Fichiers et code

## Fichiers modifiés

| Fichier | Type de changement | Justification |
|---|---|---|
|  | feat / fix / refactor / test / docs |  |

## Fichiers créés

| Fichier | Rôle | Maintenu dans le dépôt ? |
|---|---|---:|
|  |  | Oui / Non |

## Scripts ponctuels et backups

```text
Lister les artefacts locaux qui ne doivent pas être versionnés.
```

## Contrôles syntaxiques

| Commande | Résultat |
|---|---|
| `py -3.13 -m py_compile ...` |  |
| `node --check app.js` |  |
| Autre |  |

---

# 7. Base de données

## Tables concernées

| Table | Lecture / écriture | Changement |
|---|---|---|
|  |  |  |

## Migrations

| Migration | Idempotente ? | Testée sur DB temporaire ? | Résultat |
|---|---:|---:|---|
|  | Oui / Non | Oui / Non |  |

## Index et contraintes

- Index ou contrainte : justification et validation.

## Données de production ou Paper modifiées

```text
Aucune / Décrire précisément l’action explicitement autorisée.
```

## Cohérence et rollback DB

- [ ] Backup créé avant migration.
- [ ] API/processus d’écriture stabilisé avant changement.
- [ ] Migration testée sur copie.
- [ ] Rollback documenté.
- [ ] Aucune base active ajoutée à Git.

---

# 8. API et contrats

## Endpoints concernés

| Endpoint | Méthode | Changement | Authentification | Effet de bord |
|---|---|---|---|---|
|  |  |  |  | Lecture / écriture |

## Contrats Pydantic / JSON Schema

| Contrat | Version | Validation |
|---|---|---|
|  |  |  |

## Compatibilité

```text
Compatibilité conservée / rupture documentée / migration requise.
```

---

# 9. Tests

## Tests unitaires

| Test | Résultat | Preuve |
|---|---|---|
|  |  |  |

## Tests d’intégration

| Scénario | Environnement | Résultat |
|---|---|---|
|  | DB temporaire / Paper |  |

## Tests fonctionnels de bout en bout

| Scénario utilisateur | Résultat attendu | Résultat observé |
|---|---|---|
|  |  |  |

## Tests de non-régression

- [ ] Workflow Paper V3.3.
- [ ] Approval séparée de l’exécution.
- [ ] Fill unique.
- [ ] Cash, position et NAV cohérents.
- [ ] Audit présent.
- [ ] LIMIT non atteint sans fill.
- [ ] Double appel sans doublon.
- [ ] Rollback en cas d’erreur.
- [ ] Live refusé.
- [ ] Shadow non appelé.
- [ ] Constitution par tranches, si applicable.
- [ ] Cash réservé, si applicable.
- [ ] Écarts réel/cible recalculés, si applicable.

## Tests adversariaux

```text
Scénario, attaque ou donnée incohérente : résultat.
```

## Tests non exécutés

```text
Test : raison, risque, action future.
```

---

# 10. Sécurité et gouvernance

| Contrôle | Statut | Preuve |
|---|---|---|
| `BROKER_LIVE_ENABLED = False` |  |  |
| Aucun appel Live |  |  |
| Shadow isolé |  |  |
| RUNE fail-closed |  |  |
| Confirmation manager |  |  |
| Idempotence |  |  |
| Transaction / rollback |  |  |
| Aucun secret dans Git |  |  |
| Données sensibles restées locales |  |  |
| Modèles externes hors runtime |  |  |

## Recherche de secrets avant commit

```text
Commande exécutée :
Résultat :
```

---

# 11. Validation Git

## Commits

| Hash | Message | Fichiers principaux |
|---|---|---|
|  |  |  |

## Contrôles

- [ ] `git diff --check` réussi.
- [ ] Diff revu fichier par fichier.
- [ ] Fichiers ajoutés sélectivement.
- [ ] Aucun `.bak.*`, DB, secret, log ou artefact temporaire ajouté.
- [ ] Push distant réussi.
- [ ] Branche distante vérifiée.
- [ ] PR créée ou décision de non-merge documentée.

## État Git final

```text
Coller git status --short et git log pertinent.
```

---

# 12. Rollback

## Point de retour

```text
Branche, tag, commit ou backup :
```

## Procédure

```text
Étapes exactes de rollback code, configuration et DB.
```

## Test du rollback

```text
Testé / Non testé — résultat et justification.
```

---

# 13. Observabilité et exploitation

## Logs et audits

| Source | Événement attendu | Vérifié ? |
|---|---|---:|
| `event_log` |  | Oui / Non |
| `pplx_audit` runtime, si applicable |  | Oui / Non |
| Logs applicatifs |  | Oui / Non |
| Traçabilité de développement |  | Oui / Non |

## Runbooks

| Document | Créé / mis à jour | Version |
|---|---|---|
|  |  |  |

## Alertes

```text
Alertes ajoutées, testées ou restant à faire.
```

---

# 14. Documentation

## Documents mis à jour

| Document | Ancienne version | Nouvelle version | Motif |
|---|---|---|---|
| Architecture |  |  |  |
| Templates P0–P10 |  |  |  |
| Spécification |  |  |  |
| Runbook |  |  |  |
| Workflow Git |  |  |  |

## État validé à reporter

Texte à intégrer dans la section `État déjà validé` des priorités dépendantes :

```text
- 
```

## Hypothèses devenues obsolètes

- Hypothèse : remplacement ou suppression.

---

# 15. Dette et risques résiduels

| Dette / risque | Sévérité | Impact | Traitement prévu | Priorité cible |
|---|---|---|---|---|
|  | Faible / Moyenne / Haute / Critique |  |  | P… |

## Blocages

```text
Aucun / Description, propriétaire et condition de levée.
```

---

# 16. Décision suivante

| Champ | Valeur |
|---|---|
| Priorité suivante | P… |
| Décision | Ouvrir / Bloquer / Reporter |
| Conditions d’ouverture |  |
| Documents à charger |  |
| Branche envisagée |  |
| Premier livrable |  |

## Prompt suivant actualisé

- [ ] L’état validé est mis à jour.
- [ ] Les nouveaux commits sont référencés.
- [ ] Les nouvelles dettes sont mentionnées.
- [ ] Les dépendances sont vérifiées.
- [ ] Les contraintes communes sont conservées.
- [ ] Aucun patch ne sera proposé avant validation du plan.

---

# 17. Approbation de clôture

```text
Je confirme que :
- les résultats ci-dessus correspondent aux faits observés ;
- les critères non atteints sont explicitement indiqués ;
- le Live reste désactivé sauf décision formelle ultérieure ;
- les documents et prompts dépendants ont été actualisés ;
- la priorité suivante peut être ouverte uniquement selon la décision consignée.

Manager :
Date :
Décision finale :
```
