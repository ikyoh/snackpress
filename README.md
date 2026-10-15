# Snackpress

Atelier web local réunissant **14 outils prépresse** : Burger, Chili Dog, Donut, Tiramisu, Taco, Pizza, Burrito, Club Sandwich, Fortune Cookie, Poké, Sushi, Kebab, Layer Cake et Bento.

La page d’accueil présente le catalogue avec recherche et filtres. Chaque outil dispose de ses réglages, de son traitement réel, d’un aperçu paginé et de fichiers téléchargeables. Les fonctions et limites sont détaillées dans [TOOLS.md](TOOLS.md).

## Démarrer

Prérequis : Node 22.12+ (Node 24 conseillé), pnpm 9.11, uv et Python 3.12. pikepdf 9.11.0 et Playwright 1.56.1 sont fixés pour le Mac Intel/macOS 13 utilisé pour le développement.

```sh
pnpm install --frozen-lockfile
uv sync --frozen
uv run python scripts/serve.py
# Dans un second terminal :
pnpm dev
```

Atelier : http://127.0.0.1:5173. API : http://127.0.0.1:8000/docs. Les services écoutent uniquement sur l’interface locale ; Vite relaie `/api` vers FastAPI.

L’atelier d’imposition détaillé reste accessible depuis Layer Cake ou directement à http://127.0.0.1:5173/?tool=imposition. Réglages et aperçu côte à côte, grille manuelle, fonds perdus, repères et modèles locaux y sont conservés.

## Vérifier

```sh
uv run pytest
uv run ruff check .
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
# Ou avec Google Chrome déjà installé :
SNACKPRESS_BROWSER_CHANNEL=chrome pnpm test:e2e
```

Les types TypeScript proviennent du contrat OpenAPI :

```sh
pnpm types:generate
```

Le catalogue et ses champs sont définis par l’API, avec validation Pydantic côté serveur. Chaque résultat inclut une fiche JSON des paramètres, métriques et limites.

## Organisation

- `apps/web` : React/TypeScript/Vite, Tailwind, PDF.js, catalogue et ateliers.
- `apps/api` : FastAPI/Pydantic, travaux SQLite/SQLAlchemy, imports et processus PDF bornés.
- `packages/imposition` : calcul géométrique partagé par l’aperçu SVG et l’export natif.
- `packages/prepress` : catalogue, génération ReportLab, composition pikepdf, rendu PDFium et calculs raster NumPy/Pillow.
- `packages/api-client` : OpenAPI et types générés.
- `tests` : géométrie, moteur PDF, outils, API et parcours navigateur.
- `infra` : conteneurs locaux, Caddy et migration Alembic initiale.

## Fichiers et limites

Stockage privé dans `.data` (ou `SNACKPRESS_DATA`), jamais dans le dépôt. Suppression immédiate depuis les ateliers ; purge automatique au démarrage puis chaque minute pour les travaux de plus de 24 h. Limites : 25 Mo par fichier, 50 Mo par traitement, 100 travaux, 2 processus PDF simultanés et 30 secondes par traitement. Les travaux interrompus doivent être relancés.

**Usage local individuel.** Il n’existe pas encore de comptes, d’authentification ni d’autorisation multiutilisateur. Ne pas exposer publiquement. Les identifiants aléatoires servent à accéder aux fichiers pendant la session, pas à sécuriser un service partagé.

Les exports natifs d’imposition ne sont pas rasterisés. Les corrections de Donut, les comparaisons Tiramisu, les BAT Burger et les estimations Poké utilisent un rendu raster explicitement annoncé. Aucun outil ne certifie PDF/X ou le TAC ; les contrôles atelier indiqués restent nécessaires. Lire les limites propres à chaque outil dans [TOOLS.md](TOOLS.md).

## Conteneurs locaux

Prérequis : un moteur Docker démarré (par exemple Docker Desktop) et Docker Compose 2.20.3 ou ultérieur. Node, pnpm, Python et uv ne sont pas nécessaires sur l’hôte pour ce mode.

Depuis la racine du dépôt :

```sh
docker compose up --build -d --wait
```

Atelier sur http://127.0.0.1:8080. L’interface React est compilée puis servie par Caddy, qui relaie `/api` vers FastAPI. Seul le port web est publié, sur l’interface locale. Compose attend que l’API soit prête avant de démarrer le web ; les deux services disposent d’un contrôle de santé. Ce mode exécute une version compilée, sans rechargement automatique des sources.

```sh
docker compose ps                       # État et santé des services
docker compose logs -f                  # Journaux (Ctrl-C pour quitter)
curl --fail http://127.0.0.1:8080/api/health
docker compose down                    # Arrêter, en conservant les données
docker compose up --build -d --wait     # Reconstruire après modification
```

Pour utiliser un autre port : `SNACKPRESS_PORT=8090 docker compose up -d --wait`, puis ouvrir http://127.0.0.1:8090. Garder la même variable pour les commandes suivantes. Si Docker signale une connexion impossible au daemon, démarrer le moteur Docker avant de relancer la commande.

SQLite et les fichiers traités restent dans le volume Docker `snackpress_pdf-data`, monté dans `/data`. Le dossier `.data` du démarrage natif n’est pas importé automatiquement. `docker compose down` conserve ce volume ; `docker compose down --volumes` **supprime définitivement ses données**. La purge applicative après 24 h reste active. Les conteneurs s’exécutent sans root, avec un système de fichiers en lecture seule et des répertoires temporaires dédiés. Les données locales et fichiers `.env` sont exclus du contexte de construction.

La base est initialisée automatiquement au démarrage de l’API. Les migrations Alembic restent disponibles via `docker compose exec api alembic upgrade head`. La configuration détaillée reste dans `infra/compose.yaml`, incluse par le fichier racine.

Les parcours navigateur existants peuvent cibler les conteneurs démarrés, avec les dépendances de test installées sur l’hôte :

```sh
SNACKPRESS_BASE_URL=http://127.0.0.1:8080 pnpm test:e2e
# Ajouter SNACKPRESS_BROWSER_CHANNEL=chrome pour utiliser Chrome déjà installé.
```

Références de configuration : [ordre de démarrage Compose](https://docs.docker.com/compose/how-tos/startup-order/) et [intégration Docker de uv](https://docs.astral.sh/uv/guides/integration/docker/).

Validation Docker du 15 octobre 2026 : images construites et exécutées sous Linux amd64 via Docker Desktop, deux services sains, import/export PDF et BAT vérifiés, téléversement de 50 Mio accepté, migration Alembic exécutée et données conservées après recréation des conteneurs. Les 19 parcours navigateur ont été validés : 17 au premier passage, puis les 2 parcours ayant dépassé leur délai au chargement initial ont réussi lors d’une reprise avec un seul worker.

## Déploiement Jelastic avec Docker Compose

Le fichier `compose.prod.yaml` est destiné à Docker Engine dans Jelastic. Il reprend les images, les contrôles de santé, les limites de ressources et les protections des conteneurs locaux. Le port web est publié sur `0.0.0.0:8080` pour être accessible au proxy Jelastic ; l’API n’a aucun port publié. Les journaux Docker sont limités à trois fichiers de 10 Mo par service. Docker Compose **2.24.4 ou ultérieur** est nécessaire pour remplacer le port local avec `!override`.

Sur le nœud Jelastic, depuis la racine du dépôt :

```sh
docker compose version
docker compose -f compose.prod.yaml config --quiet
docker compose -f compose.prod.yaml up --build -d --wait
curl --fail http://127.0.0.1:8080/api/health
```

Ce fichier s’utilise seul avec `-f compose.prod.yaml`, sans ajouter `-f compose.yaml`. Le nom de projet reste `snackpress` : il réutilise les services et le volume `snackpress_pdf-data` d’un déploiement effectué auparavant avec `docker compose up` depuis la racine. Ne pas arrêter les anciens services avec `down --volumes`. Si l’ancien lancement utilisait `-p`, `COMPOSE_PROJECT_NAME` ou directement `-f infra/compose.yaml`, reprendre son nom de projet avec `-p` pour réutiliser son volume. Vérifier le nom avec `docker compose ls` avant de basculer.

Dans le tableau de bord Jelastic :

1. Ajouter **sur le nœud Docker Engine**, dans les variables Jelastic, `JELASTIC_EXPOSE=8080`. Cette variable concerne le routage de la plateforme ; l’ajouter uniquement dans les services Compose ne configure pas Jelastic.
2. Redémarrer le nœud pour appliquer le routage.
3. Activer le **SSL intégré** dans la topologie de l’environnement si l’accès utilise le répartiteur partagé, sans IP publique directe. Jelastic termine HTTPS ; Caddy sert le trafic interne en HTTP.
4. Ouvrir https://snackpress.jcloud.ik-server.com/ puis https://snackpress.jcloud.ik-server.com/api/health. Aucun DNS personnel ni nom de domaine dans Caddy n’est nécessaire pour cette adresse.

Commandes d’exploitation :

```sh
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs --tail=100 -f
docker compose -f compose.prod.yaml up --build -d --wait  # Mise à jour
docker compose -f compose.prod.yaml down                 # Arrêt, données conservées
```

Le port hôte est configurable avec `SNACKPRESS_PORT` ; adapter aussi `JELASTIC_EXPOSE` si sa valeur change. `SNACKPRESS_BIND_HOST` permet de choisir l’interface publiée (par défaut `0.0.0.0`). Les valeurs peuvent être définies dans le fichier `.env` à la racine du dépôt. Conserver une seule instance de l’API avec son volume SQLite et prévoir une sauvegarde de ce volume. La purge des travaux après 24 h reste active.

**Limite applicative :** ce fichier prépare l’hébergement, mais Snackpress ne possède pas encore d’authentification. Protéger l’accès au niveau du proxy ou du réseau avant d’y déposer des documents privés ou d’ouvrir le service à plusieurs utilisateurs.

Références : [ports et variable JELASTIC_EXPOSE](https://www.virtuozzo.com/application-management-docs/container-ports/), [SSL intégré Jelastic](https://www.virtuozzo.com/application-management-docs/built-in-ssl/), [remplacement des ports Compose](https://docs.docker.com/reference/compose-file/merge/).

## Moteur d’imposition en CLI

```sh
PYTHONPATH=packages/imposition uv run python -m snackpress_imposition source.pdf sortie.pdf
# Ajouter --settings reglages.json pour des paramètres personnalisés.
# Sans sortie : afficher le diagnostic JSON.
```

Les cas d’imposition avancés, la validation d’un corpus professionnel, les épreuves sur presse et le contrôle d’accès avant bêta distante restent des jalons distincts.

## Validation du 15 octobre 2026

58 tests Python, 2 tests Vitest et 19 parcours Playwright réussis (Google Chrome installé). Chaque outil est testé jusqu’au rendu et au téléchargement ; le catalogue, le mobile, les modèles locaux et le livret de huit pages sont couverts. Compilation TypeScript/Vite, Ruff et configuration Compose vérifiés. Les écrans ordinateur/mobile et des résultats PDF synthétiques ont été contrôlés visuellement. Ces contrôles restent distincts de la validation d’un corpus professionnel et des épreuves sur presse.
