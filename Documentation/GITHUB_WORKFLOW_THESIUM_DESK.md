# Procédure GitHub — ThesiumDesk

Ce document définit une méthode de travail Git/GitHub simple, sûre et adaptée au projet ThesiumDesk. Son objectif est de versionner le code, isoler chaque évolution, éviter l’exposition de secrets ou de bases de données, et permettre un retour arrière rapide.

## 1. Principes

- Le dépôt GitHub `rguelin-cloud/thesium-desk` doit rester **privé**.
- Git versionne le code source, la documentation source, les migrations, les schémas et les tests.
- Git ne versionne jamais la base SQLite active, les secrets, les clés, les tokens, les logs, les caches ou les backups.
- Toute évolution fonctionnelle est développée dans une branche `feature/...`.
- Toute correction urgente est développée dans une branche `hotfix/...`.
- La branche `main` représente un état stable, testé et restaurable.
- L’installation d’un patch et l’exécution d’un ordre Paper sont deux actes distincts. Un commit ne doit jamais exécuter une opération de trading.

## 2. Branches

| Branche | Usage | Règle |
|---|---|---|
| `main` | Référence stable | Ne pas développer directement dessus |
| `backup/pre-v3-3-20260905` | Point de restauration avant V3.3 | À conserver en lecture seule |
| `feature/paper-execution-v3-3` | Développement V3.3 | Branche active pour l’exécution Paper explicite |
| `feature/<sujet>` | Nouvelle fonctionnalité | Une fonctionnalité isolée par branche |
| `hotfix/<sujet>` | Correction ciblée et urgente | Petit diff, tests obligatoires |

### Nommage recommandé

```text
feature/paper-execution-v3-3
feature/zephr-liquidity-v1
feature/weighted-consensus-shadow-v1
hotfix/approval-auth-header
hotfix/sqlite-transaction-commit
chore/repository-hygiene
```

## 3. Répertoire de travail

Le dépôt local se trouve actuellement ici :

```text
C:\Users\RichardGUELIN\Prod\ThesiumDesk
```

Avant tout travail, vérifier le dossier et la branche :

```powershell
cd C:\Users\RichardGUELIN\Prod\ThesiumDesk

git branch --show-current
git status --short
git remote -v
```

Le remote attendu est :

```text
origin  https://github.com/rguelin-cloud/thesium-desk.git (fetch)
origin  https://github.com/rguelin-cloud/thesium-desk.git (push)
```

Si l’URL contient par erreur une syntaxe Markdown, la corriger :

```powershell
git remote set-url origin https://github.com/rguelin-cloud/thesium-desk.git
git remote -v
```

## 4. Ce qui est versionné

Les fichiers suivants sont typiquement versionnés :

```text
api_server.py
api_server_with_static.py
app.js
index.html
execution_engine.py
models.py
auth.py
risk_pretrade.py
risk_policy.py
market_regime_v1.py
backtest_engine.py
memo_generator.py
inference_router.py
weighted_vote.py
consensus_v2.py
agent_prompts_v2.py
approval_service.py
legacy_cycle_adapter.py
sizing.py
portfolio_state.py
Documentation/*.md
schemas/
migrations/
tests/
```

Avant d’ajouter un fichier de configuration comme `bridge_config.py`, vérifier qu’il ne contient aucune clé ou aucun identifiant. Si nécessaire, créer plutôt :

```text
bridge_config.example.py
.env.example
```

avec des valeurs factices, et conserver les vraies valeurs dans un fichier local ignoré.

## 5. Ce qui ne doit jamais être versionné

Les éléments suivants doivent rester locaux :

```text
thesium.db
*.db
*.sqlite
*.sqlite3
*.db-*
*.bak
backup_*/
backups*/
_backups*/
logs/
router_logs/
starvation_logs/
differentiation_logs/
.geo_cache.json
.env
.env.*
*.pem
*.key
*.p12
*.pfx
secrets/
credentials/
*.zip
*.jsonl
```

Les backups, diagnostics et scripts ponctuels peuvent être conservés localement ou archivés dans un dossier Drive privé, mais ne doivent pas être ajoutés sans revue explicite.

## 6. `.gitignore` et `.gitattributes`

Le fichier `.gitignore` est une barrière de sécurité, mais il ne protège pas les fichiers déjà suivis. Pour cesser de suivre un fichier tout en le gardant localement :

```powershell
git rm --cached .geo_cache.json
```

Vérifier que le fichier local existe toujours :

```powershell
Test-Path .\.geo_cache.json
```

Une configuration de fin de ligne recommandée est :

```gitattributes
* text=auto
*.py text eol=lf
*.js text eol=lf
*.html text eol=lf
*.json text eol=lf
*.md text eol=lf
*.ps1 text eol=crlf
```

Sous Windows :

```powershell
git config core.autocrlf true
```

Les avertissements `LF will be replaced by CRLF` sont des avertissements de normalisation et non des erreurs.

## 7. Cycle de développement

### 7.1 Démarrer une évolution

Toujours partir de la branche stable :

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/<nom-fonctionnalite>
```

Exemple :

```powershell
git switch main
git pull --ff-only origin main
git switch -c feature/paper-execution-v3-3
```

Si la branche existe déjà :

```powershell
git switch feature/paper-execution-v3-3
git pull --ff-only origin feature/paper-execution-v3-3
```

### 7.2 Travailler localement

Avant un patch :

```powershell
git status --short
git diff
```

Après un patch :

```powershell
py -3.13 -m py_compile .\api_server.py .\execution_engine.py

git diff -- api_server.py app.js execution_engine.py
```

Les scripts d’installation doivent créer eux-mêmes un backup local et exécuter des validations. Ils sont utiles localement, mais ne doivent être ajoutés au dépôt que s’ils sont maintenus comme outils officiels sous `scripts/`.

### 7.3 Ajouter sélectivement

Ne jamais faire `git add .` sans revue préalable.

Ajouter les fichiers explicitement :

```powershell
git add api_server.py app.js
git add execution_engine.py
git add Documentation/<document>.md
```

Voir ce qui est préparé :

```powershell
git diff --cached --name-status
git diff --cached
```

### 7.4 Chercher des secrets avant commit

Avant chaque commit, exécuter :

```powershell
git diff --cached | Select-String `
  -Pattern 'api[_-]?key|secret|password|token|bearer|private[_-]?key|client[_-]?secret|sk-[a-z0-9]' `
  -CaseSensitive:$false
```

Une occurrence n’est pas automatiquement un secret : elle peut être un nom de variable, un commentaire ou du code d’authentification. Vérifier visuellement toute valeur affichée.

Si une valeur sensible est détectée :

```powershell
git restore --staged <fichier>
```

Puis déplacer la valeur vers une variable d’environnement ou un fichier local ignoré avant de reprendre.

### 7.5 Committer

Les messages doivent être courts et descriptifs :

```powershell
git commit -m "feat: add ready-to-execute paper order queue"
git commit -m "fix: enforce unique fill per paper order"
git commit -m "docs: update swarm operating model v2.2"
git commit -m "test: add paper execution idempotence checks"
```

Préfixes recommandés :

| Préfixe | Usage |
|---|---|
| `feat:` | Fonctionnalité nouvelle |
| `fix:` | Correction de bug |
| `docs:` | Documentation |
| `test:` | Tests |
| `refactor:` | Réorganisation sans changement fonctionnel |
| `chore:` | Outillage, hygiène, maintenance |
| `security:` | Garde-fou ou correction de sécurité |

### 7.6 Pousser

```powershell
git push -u origin feature/<nom-fonctionnalite>
```

Puis vérifier :

```powershell
git status
git log -3 --oneline
```

## 8. Pull request et revue

Pour une évolution fonctionnelle :

1. Pousser la branche feature.
2. Ouvrir une Pull Request vers `main` sur GitHub.
3. Décrire précisément le comportement, les fichiers modifiés, les migrations, les tests et le rollback.
4. Vérifier le diff GitHub avant merge.
5. Merger uniquement après test local et validation fonctionnelle.

Template de description de PR :

```markdown
## Objectif

## Périmètre

## Fichiers modifiés

## Migration base de données

## Tests réalisés

## Garanties de sécurité

## Plan de rollback

## Hors périmètre
```

Pour V3.3, la PR doit notamment déclarer :

```text
- Aucun fill n’est créé par l’installation.
- Le Live broker est explicitement refusé.
- L’index unique fills(order_id) est créé seulement après contrôle de doublons.
- L’exécution nécessite une confirmation UI explicite.
- Les ordres limit non atteints restent approved et non exécutés.
- Le chemin d’exécution humain n’appelle pas le runner de cycle ou Shadow.
```

## 9. Procédure V3.3

### 9.1 État requis avant installation

```text
BROKER_LIVE_ENABLED = False
Aucun doublon fills.order_id
Approval = approved
Order lié = approved
paper_execution_status = approved_not_executed
```

L’ordre annulé et les smoke tests sans `order_id` ne sont jamais candidats à l’exécution.

### 9.2 Installation

Le script V3.3 doit :

1. Créer une sauvegarde horodatée de `api_server.py`, `app.js` et `thesium.db`.
2. Exécuter un preflight de schéma SQLite et de doublons sur `fills.order_id`.
3. Créer l’index `uq_fills_order_id` de façon idempotente.
4. Ajouter/mettre à jour la route lecture seule `GET /api/approvals/ready-to-execute`.
5. Durcir la route `POST /api/approvals/{approval_id}/execute-paper`.
6. Ajouter la queue UI `Approved Paper Orders` et une modal de confirmation.
7. Compiler Python, valider les marqueurs et restaurer automatiquement en cas d’échec.
8. Ne jamais créer de fill au moment de l’installation.

### 9.3 Exécution Paper

L’exécution est une opération distincte :

```text
Manager ouvre Approved Paper Orders
→ sélectionne Execute Paper Order
→ consulte close de référence, fill estimé, slippage et frais
→ confirme explicitement
→ API vérifie tous les prérequis
→ écrit un fill unique
→ met à jour l’ordre, l’approval, le portefeuille et l’audit
```

Convention Paper actuelle :

```text
Source de prix : dernier prices.close
Slippage : 0.001 = 10 bps
Frais : 0.005 par unité
BUY : close × 1.001
SELL : close × 0.999
```

Pour un limit non atteint :

```text
Order remain approved
Approval remain approved_not_executed
No fill
No cash or position change
HTTP 409 with clear reason
```

### 9.4 Vérifications post-exécution

```powershell
py -3.13 -c "import sqlite3; c=sqlite3.connect('thesium.db'); c.row_factory=sqlite3.Row; print(*[dict(r) for r in c.execute('SELECT * FROM fills WHERE order_id = ?', (674,)).fetchall()], sep='\n')"
```

Puis vérifier :

```text
- Une seule ligne fills pour order_id.
- orders.status = filled.
- paper_execution_status = paper_executed.
- portfolio_positions et portfolio_state mis à jour.
- event_log contient l’audit d’exécution.
- Un second clic retourne 409 et ne crée aucun second fill.
```

## 10. Rollback

### 10.1 Rollback Git avant commit

Annuler une modification locale de fichier suivi :

```powershell
git restore api_server.py app.js
```

Annuler ce qui a été ajouté à l’index mais pas encore commité :

```powershell
git restore --staged api_server.py app.js
```

### 10.2 Revenir à un commit

Voir l’historique :

```powershell
git log --oneline --decorate -10
```

Créer une branche de secours sur l’état courant :

```powershell
git switch -c backup/before-rollback-YYYYMMDD
```

Revenir temporairement au baseline V3.3 :

```powershell
git switch backup/pre-v3-3-20260905
```

### 10.3 Rollback d’un patch installé

Les scripts de patch officiels doivent créer des backups locaux. Restaurer d’abord les fichiers sources depuis leur backup horodaté, puis redémarrer l’API.

Si le patch comprend une migration SQLite qui modifie le schéma, restaurer aussi le snapshot de `thesium.db` créé avant installation. Ne jamais remplacer une base active sans arrêter proprement l’API et vérifier le backup.

## 11. Règles d’exploitation

- Toujours arrêter ou stabiliser les processus qui écrivent dans SQLite avant une migration de schéma.
- Toujours vérifier `git status` avant de changer de branche.
- Ne jamais lancer un second Decision Cycle pour tester une UI si un ordre équivalent est déjà en attente ou approuvé.
- Ne jamais utiliser les boutons legacy `PASS / REJETER` pour un ordre déjà gouverné par `paper_approvals`.
- Ne jamais exécuter une action Paper à partir d’un smoke test sans `order_id`.
- Ne jamais activer Live pour tester V3.3.
- Toujours conserver un log de test et l’état avant/après toute première exécution Paper.

## 12. Checklist quotidienne

Avant de coder :

```powershell
git switch feature/<branche>
git pull --ff-only
git status --short
```

Avant de committer :

```powershell
git diff
git diff --cached --name-status
git diff --cached | Select-String -Pattern 'api[_-]?key|secret|password|token|bearer|private[_-]?key|client[_-]?secret' -CaseSensitive:$false
```

Après le commit :

```powershell
git status
git log -1 --oneline
git push
```

## 13. Contacts et références

- Dépôt privé : `https://github.com/rguelin-cloud/thesium-desk.git`
- Branche baseline V3.3 : `backup/pre-v3-3-20260905`
- Branche V3.3 : `feature/paper-execution-v3-3`
- Application locale : `C:\Users\RichardGUELIN\Prod\ThesiumDesk`
- Lancement API : `py -3.13 -m uvicorn api_server_with_static:app --host 0.0.0.0 --port 8000 --reload`
