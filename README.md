# Snackpress

Atelier web local réunissant **14 outils prépresse** : Burger, Chili Dog, Donut, Tiramisu, Taco, Pizza, Burrito, Club Sandwich, Fortune Cookie, Poké, Sushi, Kebab, Layer Cake et Bento.

La page d’accueil présente le catalogue avec recherche et filtres. Chaque outil dispose de ses réglages, d’un aperçu PDF/image actualisé automatiquement, d’un traitement final et de fichiers téléchargeables. Les fonctions et limites sont détaillées dans [TOOLS.md](TOOLS.md).

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

L’atelier d’imposition détaillé reste accessible depuis Layer Cake ou directement à http://127.0.0.1:5173/?tool=imposition. Réglages et aperçu côte à côte, grille manuelle, fonds perdus, repères et configurations personnelles y sont disponibles.

## Sushi : découpe et rainage

Sushi propose un fond perdu réglable par côté (0 mm par défaut) et un contour facultatif : Aucun par défaut, Rectangle ou Cercle. Le contour carré ou rectangulaire accepte un rayon des coins en mm (0 par défaut, au maximum la moitié du plus petit côté). « Ajouter un tracé » permet de créer autant de lignes que nécessaire, chacune avec son type Coupe / Rainage, son orientation Horizontal / Vertical et sa position en mm. Les positions sont mesurées depuis le bord gauche pour les verticales et depuis le haut pour les horizontales, sur le format fini, bords inclus. Les tracés ne se prolongent pas dans le fond perdu. Le PDF conserve les tons directs et la surimpression ; la TrimBox définit le format fini, la BleedBox le fond perdu. Le format du PDF est exactement (largeur + 2 × fond perdu) × (hauteur + 2 × fond perdu). Les anciens rainages enregistrés sont repris comme tracés verticaux. Ces réglages sont aussi disponibles dans Burger et dans les composants du catalogue.

## Vérifier

```sh
uv run pytest
uv run ruff check .
pnpm test
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
pnpm test:e2e:accounts  # Comptes et e-mails locaux, serveurs et données de test isolés
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

## Aperçus automatiques

Les ateliers recalculent l’aperçu après une pause de 500 ms dans la saisie, dès que les fichiers requis sont présents. L’aperçu utilise les réglages actuels, conserve le dernier PDF affiché pendant le calcul et ignore les réponses devenues obsolètes. Les réglages invalides sont signalés sans effacer le dernier aperçu. « Actualiser l’aperçu » permet de recréer une session expirée. L’imposition propose l’aperçu PDF dès l’import, avec les commandes Recto/Verso, et conserve son mode Plan interactif. Fortune Cookie conserve aussi l’éditeur de placement des numérotations.

**Les aperçus ne sont pas des fichiers finaux.** Donut, Tiramisu et Poké utilisent au maximum les deux premières pages et 96 dpi ; les mesures et comparaisons de l’aperçu sont donc partielles. Fortune Cookie montre au maximum deux exemplaires. Les autres outils utilisent leur moteur habituel. Le bouton « Générer le fichier final » réalise le traitement complet avec la résolution, les pages et la quantité demandées. L’atelier d’imposition conserve son bouton « Générer le PDF » et sa confirmation du format fini.

Les fichiers sont importés une fois dans une session d’aperçu, puis les requêtes d’actualisation transmettent seulement les réglages. Les calculs interrompus sont annulés côté serveur. Chaque session conserve au maximum trois générations d’aperçu ; les rendus échoués sont supprimés. Les sessions sont supprimées à leur libération par le navigateur et expirent après 30 minutes d’inactivité, indépendamment des fichiers finaux conservés 24 h. La purge périodique et les limites de travaux, de taille, de processus et de temps restent actives. L’import autorise le traitement sur le serveur pour produire l’aperçu.

## Produits d’impression et BAT

Le lien **Produits d’impression** ouvre le catalogue personnel : catégories, supports matières, façonnages et finitions, produits et déclinaisons. Six produits pilotes sont fournis, dont les billets détachables numérotés. Dans Burger, choisir le catalogue ou un mode libre configurable ; la composition classique reste disponible. Les composants définissent leurs formats, fichiers PDF, pagination et tracés Pizza, Taco, Burrito, Sushi ou perforations. Les billets proposent des numéros répétés, un recto verso facultatif, les codes et un manifeste des carnets ; l’aperçu montre le premier et le dernier, l’export final génère la série (100 billets maximum).

Le catalogue est enregistré dans le compte avec contrôle des modifications concurrentes. Chaque BAT conserve une copie de ses spécifications dans les réglages, indépendamment des changements ultérieurs du catalogue. Documentation et limites : [catalogue des produits](docs/PRINT-CATALOG.md).

## Comptes et configurations personnelles

Les outils sont utilisables sans compte. Le bouton **Se connecter** permet de créer un compte : saisie de l’adresse e-mail, réception d’un lien valable 30 minutes, choix d’un mot de passe d’au moins 15 caractères, puis connexion. Le même compte retrouve ses configurations sur tous les appareils. Les liens sont à usage unique. « Mot de passe oublié ? » envoie un nouveau lien et invalide toutes les sessions après modification du mot de passe.

Chaque outil, y compris l’atelier d’imposition, propose **Mes configurations** : enregistrer sous un nom, charger, mettre à jour, renommer, dupliquer, supprimer et définir une configuration par défaut. Pour dupliquer, saisir un autre nom puis cliquer sur Dupliquer. La configuration par défaut se charge à l’ouverture, si aucun réglage n’a été modifié pendant le chargement. Une modification concurrente sur un autre appareil est refusée : actualiser la liste puis charger la version voulue. Limite : 200 configurations par compte et noms uniques par outil. Les paramètres sont validés par les mêmes modèles que les traitements ; les numérotations Fortune Cookie sont incluses. Charger des réglages ne lance aucun traitement et ne transfère aucun PDF. L’imposition conserve les dimensions du document déjà importé et demande une nouvelle confirmation du format.

Les anciens modèles d’imposition du navigateur peuvent être **importés explicitement dans le compte connecté**. Les originaux locaux sont conservés ; les collisions de noms reçoivent un suffixe. La liste, la sélection et les messages personnels sont effacés à la déconnexion ou au changement de compte ; les réglages en cours restent dans l’atelier.

Comptes, configurations, sessions et liens sont conservés dans `jobs.db`, dans le même volume que les travaux. La purge des travaux après 24 h ne supprime pas les comptes ni les configurations ; les sessions expirent après sept jours. Sauvegarder le volume complet, y compris `jobs.db`. Au démarrage, les tables nouvelles sont créées automatiquement sans modifier les travaux existants ; la migration Alembic `0002` est aussi disponible.

### Configurer les e-mails

Copier `.env.example` en `.env` pour Docker Compose et renseigner :

- `SNACKPRESS_PUBLIC_URL` : origine exacte du site, sans chemin ni slash final. HTTPS obligatoire hors `localhost` / `127.0.0.1`. Le port fait partie de l’origine. En développement Vite : `http://127.0.0.1:5173` ; Docker local : `http://127.0.0.1:8080` ; Jelastic : `https://snackpress.jcloud.ik-server.com`.
- `SNACKPRESS_MAIL_FROM` : adresse d’expédition autorisée par le fournisseur.
- `SNACKPRESS_SMTP_HOST`, `SNACKPRESS_SMTP_PORT`, `SNACKPRESS_SMTP_USERNAME`, `SNACKPRESS_SMTP_PASSWORD` : paramètres du fournisseur SMTP.
- `SNACKPRESS_SMTP_SECURITY` : `starttls` (port 587) ou `ssl` (port 465). La connexion vérifie le certificat TLS.

Le démarrage natif ne lit pas automatiquement `.env` : exporter les variables avant de lancer `scripts/serve.py`. Aucun secret n’est transmis au frontend. Sans SMTP configuré, l’inscription signale une indisponibilité ; les outils restent utilisables. Aucun compte n’est activé sans vérification de l’adresse.

Pour le développement local uniquement : exporter `SNACKPRESS_MAIL_MODE=file` et `SNACKPRESS_PUBLIC_URL=http://127.0.0.1:5173`. Les messages sont écrits avec des permissions privées dans `.data/mail-outbox/*.eml` (ou `/data/mail-outbox` dans Docker) ; ouvrir le lien contenu dans le fichier. Ce mode refuse les origines distantes et n’est pas adapté à un serveur public. Les messages locaux sont purgés après une heure.

Les sessions utilisent un cookie HttpOnly, SameSite Strict, Secure sous HTTPS. Les mots de passe utilisent scrypt avec sel aléatoire ; seuls les condensats des sessions et des liens sont stockés. Les écritures de compte et de configuration exigent un en-tête dédié et contrôlent l’origine. Les réponses personnelles ne sont pas mises en cache. Les demandes d’authentification sont limitées par adresse e-mail et IP dans le processus API ; garder une instance API et configurer le proxy de confiance Uvicorn pour que l’IP client soit transmise correctement. Ces limites se réinitialisent au redémarrage du processus.

## Fichiers et limites

Stockage privé dans `.data` (ou `SNACKPRESS_DATA`), jamais dans le dépôt. Suppression immédiate depuis les ateliers ; purge automatique au démarrage puis chaque minute pour les travaux de plus de 24 h. Limites : 25 Mo par fichier, 50 Mo par traitement, 100 travaux, 2 processus PDF simultanés et 30 secondes par traitement. Les travaux interrompus doivent être relancés.

**Accès aux documents :** les comptes protègent les configurations personnelles. Les outils et les liens de travaux restent accessibles sans connexion ; les identifiants aléatoires des fichiers ne constituent pas une autorisation par utilisateur. Protéger l’accès au service au niveau du proxy ou du réseau avant de traiter des documents privés sur un hébergement partagé.

Les exports natifs d’imposition ne sont pas rasterisés. Les corrections de Donut, les comparaisons Tiramisu, les visuels des BAT Burger et les estimations Poké utilisent un rendu raster explicitement annoncé. Les repères superposés dans les BAT conservent les objets PDF natifs du gabarit. Aucun outil ne certifie PDF/X ou le TAC ; les contrôles atelier indiqués restent nécessaires. Lire les limites propres à chaque outil dans [TOOLS.md](TOOLS.md).

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

## HTTPS géré par Caddy sur Jelastic (IP publique dédiée)

Avec Docker Compose **2.24.4 ou ultérieur**, utiliser `compose.https.yaml` **seul** pour que Caddy obtienne et renouvelle le certificat de `snackpress.app`, puis redirige automatiquement HTTP vers HTTPS. Ce mode exige une IP publique dédiée au nœud Docker Engine et un accès direct à Caddy sur les ports publics 80 et 443.

1. Chez le registrar, créer un enregistrement DNS **A** pour `@` vers l’IP publique du nœud. Ne conserver un enregistrement AAAA que si cette adresse IPv6 atteint aussi ce nœud.
2. Dans le pare-feu Jelastic, autoriser TCP **80 et 443** vers le nœud ; UDP 443 permet également HTTP/3. Le trafic de ce domaine doit atteindre directement Docker, sans terminaison TLS sur le répartiteur partagé Jelastic. Le routage `JELASTIC_EXPOSE=8080` du mode précédent ne remplace pas cet accès direct.
3. Dans le `.env` à la racine du projet, conserver les paramètres SMTP et renseigner :

```dotenv
SNACKPRESS_DOMAIN=snackpress.app
SNACKPRESS_PUBLIC_URL=https://snackpress.app
SNACKPRESS_ACME_EMAIL=votre-adresse@example.com
```

Remplacer l’adresse d’exemple par une adresse de contact réelle pour le compte ACME ; elle peut être différente de l’expéditeur SMTP. `SNACKPRESS_DOMAIN` contient uniquement le nom d’hôte. `SNACKPRESS_PUBLIC_URL` sert aux liens des comptes et aux contrôles d’origine ; vide, cette variable est déduite du domaine. `SNACKPRESS_ACME_CA` vide utilise Let’s Encrypt en production. Aucun certificat n’est à installer manuellement. Seul le domaine indiqué est configuré : ajouter un DNS `www` ne suffit pas à activer son HTTPS.

Après publication des DNS, lancer sur le nœud Jelastic :

```sh
docker compose -f compose.https.yaml config --quiet
docker compose -f compose.https.yaml up --build -d --wait
docker compose -f compose.https.yaml logs --tail=100 web
curl --fail https://snackpress.app/api/health
```

La dernière commande doit réussir sans désactiver la vérification du certificat. Le contrôle de santé Docker vérifie Caddy et l’API sur une interface interne ; il ne garantit pas que l’émission du certificat public est terminée. En cas d’échec ACME, vérifier les DNS, les ports entrants et les journaux du service `web`.

Les ports publics 80/443 sont publiés vers les ports internes 8080/8443 : Caddy reste exécuté sans root, avec les privilèges supprimés et le système de fichiers en lecture seule. Les certificats, clés et comptes ACME sont conservés dans le volume **`snackpress_caddy-data`**, à sauvegarder et à préserver lors des mises à jour. Le volume **`snackpress_pdf-data`** existant est réutilisé pour les comptes, configurations et documents. Ne pas utiliser `down --volumes`, qui supprimerait ces données.

Pour une mise à jour, répéter `docker compose -f compose.https.yaml up --build -d --wait`. Pour un changement de domaine ou de variables, modifier `.env` puis recréer les conteneurs avec `up -d --wait` ; `restart` ne recharge pas les variables Compose. Le mode local reste disponible avec `docker compose up --build -d --wait`.

Validation locale : image construite, configuration Compose résolue, redirection HTTP vers HTTPS, service web et proxy API en TLS testés avec un certificat interne temporaire, exécution sans root et certificat conservé après recréation du conteneur. L’émission du certificat public nécessite le déploiement, les DNS et les ports ouverts sur Jelastic.

Références : [HTTPS automatique de Caddy](https://caddyserver.com/docs/automatic-https), [prérequis HTTPS](https://caddyserver.com/docs/quick-starts/https) et [IP publique Jelastic](https://www.virtuozzo.com/application-management-docs/public-ip/).

## Déploiement Jelastic avec terminaison HTTPS sur la plateforme

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

### Domaine personnalisé : snackpress.app

Pour l’hébergement Jelastic actuel, Caddy reste en HTTP sur le port interne 8080 et Jelastic termine HTTPS. Le domaine se configure au démarrage des conteneurs : aucune recompilation du frontend n’est nécessaire pour changer de domaine. La première installation du Caddyfile modifié nécessite toutefois de reconstruire l’image web.

Sur le nœud Jelastic, dans le fichier `.env` à la racine du projet :

```dotenv
SNACKPRESS_DOMAIN=snackpress.app
SNACKPRESS_PUBLIC_URL=
```

`SNACKPRESS_DOMAIN` contient uniquement le nom d’hôte, sans `https://`, chemin ni port. Le Compose production transmet cette variable à Caddy et déduit automatiquement `SNACKPRESS_PUBLIC_URL=https://snackpress.app` pour les comptes, les contrôles d’origine et les liens d’activation/récupération envoyés par e-mail. Si un ancien `.env` contient `SNACKPRESS_PUBLIC_URL=http://127.0.0.1:8080` ou l’URL Jelastic, supprimer cette valeur ou la remplacer par `https://snackpress.app` : une valeur explicite reste prioritaire et doit correspondre à l’origine publique.

Avec un domaine configuré, Caddy redirige les autres noms d’hôte vers `https://snackpress.app` en 308, en conservant chemin et paramètres. Cela inclut l’ancien nom de l’environnement et `www.snackpress.app`, si leurs DNS/certificats permettent d’atteindre le service. Le point de santé `/api/health` reste accessible quel que soit l’hôte pour les sondes Docker et Jelastic. Sans domaine, le mode local continue de fonctionner comme auparavant et le Compose production utilise l’URL Jelastic historique pour les comptes.

**DNS et rattachement à Jelastic :**

1. Sans IP publique dédiée, créer à la racine `@` un enregistrement ALIAS/ANAME (ou un CNAME aplati, si le fournisseur le prend en charge) vers `snackpress.jcloud.ik-server.com`. Un CNAME classique est adapté à un sous-domaine comme `www`, mais pas à la racine d’une zone DNS standard. Si le fournisseur ne propose pas cette fonction pour la racine, utiliser une IP publique et un enregistrement A, ou choisir un sous-domaine comme adresse publique.
2. Dans les paramètres de l’environnement Jelastic, **Custom Domains / Domain Binding**, rattacher `snackpress.app`. Ajouter aussi `www.snackpress.app` si ce nom doit rediriger vers la racine. Ce rattachement est nécessaire lorsque le trafic passe par le répartiteur partagé. Avec une IP publique dédiée, un enregistrement A vers l’IP du point d’entrée suffit pour le routage DNS.
3. Configurer un certificat couvrant **snackpress.app** sur le point d’entrée Jelastic et y activer la redirection HTTP vers HTTPS. Le SSL intégré du domaine `*.jcloud.ik-server.com` ne couvre pas le domaine acheté. Avec un répartiteur partagé, utiliser **Custom SSL via SLB**, selon les fonctions proposées par l’hébergeur (API/support si nécessaire) ; avec une IP publique et un point d’entrée TLS Jelastic, utiliser son option Let’s Encrypt ou un certificat personnalisé. Pour rediriger `www` en HTTPS, son certificat doit aussi être valide avant que Caddy puisse recevoir la requête.
4. Conserver `JELASTIC_EXPOSE=8080` sur le nœud Docker Engine. Les variables de domaine dans `.env` ne remplacent pas le rattachement DNS, le routage et le certificat de la plateforme.

Après récupération de la version du dépôt contenant ces changements :

```sh
docker compose -f compose.prod.yaml config --quiet
docker compose -f compose.prod.yaml up --build -d --wait
curl --fail https://snackpress.app/api/health
```

Pour un changement ultérieur de domaine, modifier `.env` puis lancer `docker compose -f compose.prod.yaml up -d --wait` afin de recréer les conteneurs concernés. Un simple `restart` ne relit pas les variables Compose. Prévoir une reconnexion après un changement de domaine, car les cookies ne sont pas partagés entre domaines.

Validation locale : Caddy validé avec domaine renseigné et vide ; requêtes HTTP testées dans des conteneurs temporaires pour le site, le proxy API, le point de santé, la redirection 308 avec chemin/paramètres et l’absence de boucle derrière la terminaison TLS de Jelastic. Résolution Compose vérifiée avec et sans domaine ainsi qu’avec une URL publique explicite. Les DNS, le certificat et le rattachement distants restent à effectuer dans les comptes de l’hébergeur et du registrar.

Références : [domaines personnalisés Jelastic](https://www.virtuozzo.com/application-management-docs/custom-domains/), [SSL personnalisé via le répartiteur partagé](https://www.virtuozzo.com/application-management-docs/custom-ssl-via-slb/) et [variables du Caddyfile](https://caddyserver.com/docs/caddyfile/concepts#environment-variables).

Commandes d’exploitation :

```sh
docker compose -f compose.prod.yaml ps
docker compose -f compose.prod.yaml logs --tail=100 -f
docker compose -f compose.prod.yaml up --build -d --wait  # Mise à jour
docker compose -f compose.prod.yaml down                 # Arrêt, données conservées
```

Le port hôte est configurable avec `SNACKPRESS_PORT` ; adapter aussi `JELASTIC_EXPOSE` si sa valeur change. `SNACKPRESS_BIND_HOST` permet de choisir l’interface publiée (par défaut `0.0.0.0`). Les valeurs peuvent être définies dans le fichier `.env` à la racine du dépôt. Conserver une seule instance de l’API avec son volume SQLite et prévoir une sauvegarde de ce volume. La purge des travaux après 24 h reste active.

**Limite applicative :** les comptes isolent les configurations, mais les travaux PDF ne sont pas rattachés à leur propriétaire. Protéger leur accès au niveau du proxy ou du réseau avant d’y déposer des documents privés.

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


## Validation des comptes du 17 octobre 2026

80 tests Python, 2 tests Vitest, compilation TypeScript/Vite et Ruff réussis. Les 23 parcours existants passent : 21 au premier passage, puis Donut et l’export d’imposition lors d’une reprise avec un seul worker après dépassement du délai initial. Les 2 nouveaux parcours Playwright dédiés couvrent l’inscription par lien e-mail local, l’activation, la connexion, le CRUD des configurations, le choix par défaut, un autre navigateur, les conflits de version, la déconnexion, l’import des anciens modèles et la récupération du compte. Les écrans de connexion et de configurations ont été vérifiés sur ordinateur et mobile. Les tests de comptes démarrent deux serveurs et une base temporaires isolés, sans envoyer de vrais e-mails ; ils nécessitent les ports 8015 et 5175 libres. La migration Alembic `0001` → `0002`, sa répétition et la configuration Compose production sont vérifiées. L’envoi SMTP réel reste à valider après configuration du fournisseur.

Références pour les mécanismes d’authentification : [stockage des mots de passe](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [sessions](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) et [récupération de compte](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html) de l’OWASP.


## Validation des aperçus et de l’ovale du 17 octobre 2026

100 tests Python réussis (99 dans la suite complète, puis le test ajouté d’annulation sur déconnexion), 2 tests Vitest, compilation TypeScript/Vite, Ruff et vérification des diffs. Les 27 parcours Playwright principaux et les 2 parcours comptes passent : aperçu automatique sans export implicite, regroupement des saisies rapides, réponse obsolète ignorée, conservation du dernier PDF sur réglage invalide, import unique des fichiers, aperçu réduit de Fortune Cookie avec série finale complète, recto-verso d’imposition et parcours existants. Les tests serveur couvrent les aperçus des 14 outils, les fichiers publiables, le stockage borné à trois générations, l’expiration, les limites et l’indépendance des exports finaux. L’ovale de Pizza est contrôlé en géométrie PDF, rendu raster et interface ordinateur/mobile.
