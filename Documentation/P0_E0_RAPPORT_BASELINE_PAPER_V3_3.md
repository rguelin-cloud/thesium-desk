# P0 / E0 — Rapport de baseline Paper Execution V3.3

- Date : 6 septembre 2026
- Étape : E0 — gel et baseline
- Méthode : inventaire SQLite **lecture seule** (`mode=ro` + `PRAGMA query_only=ON`), aucune écriture
- Branche de travail au moment du gel : `feature/paper-execution-v3-3`, HEAD `e538ecc`
- Commits de référence confirmés : `920e7b2`, `2e08bbc`, `e538ecc` (plus `4e56fab` intercalé, non listé au prompt)
- Verdict technique : **aucun blocage** — sous réserve des contrôles Git de propreté du dépôt
- Note de confidentialité : les valeurs de cash, NAV, P&L et positions relevées pendant l'inventaire sont volontairement **exclues** de ce document, qui a vocation à être versionné

---

## 1. Invariants déjà garantis par le schéma

| Invariant | Mécanisme constaté | Portée |
|---|---|---|
| I2 — un fill unique par ordre | `CREATE UNIQUE INDEX uq_fills_order_id ON fills(order_id)` | Garantie **base**, pas seulement applicative |
| Une seule approval active par ordre | `CREATE UNIQUE INDEX uq_paper_approvals_order_active ON paper_approvals(order_id) WHERE order_id IS NOT NULL AND status IN ('pending','approved')` | Index partiel : empêche deux gouvernances concurrentes sur un même ordre |
| Intégrité référentielle des fills | `fills.order_id INTEGER NOT NULL REFERENCES orders(id)` | Un fill orphelin est impossible |
| Champs de fill obligatoires | `fill_price` et `fill_quantity` en `NOT NULL` | Un fill vide est impossible |
| Vocabulaire des ordres | `CHECK(side IN ('buy','sell'))`, `CHECK(order_type IN ('market','limit'))`, `CHECK(status IN ('pending','pending_validation','approved','filled','rejected','cancelled'))` | Vocabulaire contraint en base |

**Conséquence sur le plan P0** : la décision n° 2 (« autoriser la création conditionnelle de `uq_fills_order_id` après preflight ») devient **sans objet**. Aucune migration de schéma n'est nécessaire en P0. Les tests valideront le comportement applicatif face à la contrainte, notamment que la violation produit un refus propre et non une erreur 500.

---

## 2. Vocabulaire non contraint en base

`paper_approvals.status` et `paper_approvals.paper_execution_status` sont de simples `TEXT NOT NULL` avec valeurs par défaut `'pending'` et `'not_executed'`, **sans clause CHECK**.

Valeurs observées :

```text
status                 : pending | approved | rejected
paper_execution_status : not_executed | approved_not_executed | paper_executed
```

`not_executed` n'apparaît pas dans le modèle opérationnel v2.4, qui ne décrit que `approved_not_executed` et `paper_executed`. Il correspond à l'état initial et à l'état terminal d'une approval rejetée.

Action P0 : documenter la machine à états complète dans le runbook, et ajouter un test de vocabulaire qui échoue si une valeur inconnue apparaît. Une contrainte CHECK est envisageable mais relève de P2, pas de P0.

---

## 3. Piège de test identifié : trigger de déduplication

```sql
CREATE TRIGGER trg_orders_dedup
BEFORE INSERT ON orders
FOR EACH ROW
WHEN NEW.status = 'pending_validation'
 AND EXISTS (
    SELECT 1 FROM orders
    WHERE instrument_id = NEW.instrument_id
      AND side = NEW.side
      AND status = 'pending_validation'
      AND datetime(created_at) > datetime('now', '-10 minutes')
 )
BEGIN
  SELECT RAISE(IGNORE);
END
```

Un `INSERT` d'ordre `pending_validation` sur le même instrument et le même sens dans une fenêtre de 10 minutes est **silencieusement ignoré** : aucune erreur, aucune ligne créée, `lastrowid` trompeur.

Impacts directs sur E1 :

- les fixtures doivent créer les ordres avec le statut cible (`approved`) ou vérifier systématiquement le nombre de lignes réellement insérées ;
- tout test de constitution multi-tranches sur un même instrument doit contourner ou neutraliser explicitement la fenêtre de 10 minutes ;
- un test dédié doit documenter ce comportement, car un IGNORE silencieux peut masquer une régression fonctionnelle.

---

## 4. Cohérence de l'état gelé

| Contrôle | Résultat | Lecture |
|---|---|---|
| Doublons `fills.order_id` | 0 | Conforme |
| Fills sans `order_id` | 0 | Conforme |
| Orders `filled` sans fill | 0 | Conforme |
| Fills sur ordre non `filled` | 0 | Conforme |
| Approvals `approved_not_executed` possédant déjà un fill | 0 | Conforme |
| Approvals sans `order_id` | 2 | Smoke tests historiques, jamais exécutables par conception |
| Fills sans approval | 317 | Héritage du chemin cycle antérieur à V3.3 |
| Candidats réellement exécutables | 0 | Aucun ordre en attente d'exécution au moment du gel |
| `integrity_check` | ok | Conforme |
| Violations de clé étrangère | 0 | Conforme |

L'arithmétique des fills se referme exactement : `order_filled` (171) + `order_filled_human` (146) = 317 fills hérités, plus le fill V3.3 gouverné (#318) = 318 fills au total, égal au nombre d'ordres `filled`.

**Règle de test qui en découle** : un fill n'implique jamais une approval. Aucun test ne doit poser cette hypothèse.

### Ancrage numérique de non-régression

```text
Order  #674  instrument_id 24  side 'sell'  quantity 4  order_type 'market'  limit_price NULL
Fill   #318  fill_price 1011.1878  fill_quantity 4  slippage 4.0488  fees 0.02
Audit  event_log : order_filled_human_v33
```

Conforme à la convention documentée : `SELL fill = close × 0.999`, `frais = quantité × 0.005`.

---

## 5. Dettes qualifiées à l'issue de E0

| # | Constat | Sévérité | Traitement |
|---|---|---|---|
| D1 | `orders.validated_at` et `fills.filled_at` portent une valeur strictement identique (`2026-09-05T10:57:22.037597`) : la séparation temporelle approve/execute n'est pas prouvable depuis `orders` | Moyenne | Vérifier `paper_approvals.decided_at` ; test E4 exigeant `decided_at < filled_at` ; correction éventuelle reportée à P1/P2 |
| D2 | Le `risk_check_result` de l'order #674 contient `risk_v2.passed = 0`, `blocked_by = broker_mapping_ok`, `reason = not_tradable_strict_refusal`, `policy = A_strict_refuse`, mais `mode = warn` : un refus strict a été dégradé en avertissement | Haute | Test adversarial P0 documentant le comportement observé ; décision manager requise ; toute modification de politique de risque est hors périmètre P0 |
| D3 | Vocabulaire des statuts d'approval non contraint en base | Faible | Documenté au runbook ; CHECK éventuel en P2 |
| D4 | `trg_orders_dedup` ignore silencieusement des insertions | Moyenne | Neutralisé et documenté dans les fixtures E1 ; test dédié |
| D5 | Base en mode `wal` : une copie fichier simple de `thesium.db` est incomplète | Moyenne | Snapshot uniquement via l'API `backup()` de SQLite, ou arrêt de l'API puis copie de `.db`, `.db-wal` et `.db-shm` |
| D6 | `portfolio_state` expose `total_value`, pas `nav` | Faible | Les tests et le runbook doivent employer les noms de colonnes réels |

---

## 6. Décisions du plan mises à jour

| Décision initiale | Statut après E0 |
|---|---|
| 1. Surcharge du chemin DB par variable d'environnement | Toujours requise pour E1 |
| 2. Création conditionnelle de `uq_fills_order_id` | **Sans objet** — l'index existe déjà |
| 3. Traitement des tests de constitution non implémentés | Toujours ouverte — `xfail(strict=True)` recommandé |
| 4. Tolérance d'arrondi cash/NAV | Toujours ouverte |
| 5. Nom de branche et tag de gel | `feature/p0-paper-stabilization` depuis `feature/paper-execution-v3-3` ; tag `paper-v3.3-frozen` sur `e538ecc` |

---

## 7. Conditions de clôture de E0

- [ ] `git status --porcelain` vide, ou artefacts locaux écartés du suivi Git
- [ ] Aucun `.bak`, `.db`, `.sqlite`, `.env`, `logs/`, `.pem`, `.key` suivi par Git
- [ ] Tag `paper-v3.3-frozen` posé sur `e538ecc` et poussé
- [ ] Branche `feature/p0-paper-stabilization` créée
- [ ] Snapshot de la base réalisé via l'API `backup()`, stocké hors dépôt
- [ ] `paper_approvals.decided_at` de l'approval #4 relevé pour trancher D1
