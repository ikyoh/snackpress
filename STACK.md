# Stack proposée pour Snackpress

Date : 14 octobre 2026. Proposition pour la V1 web d’imposition répétitive. L’utilisateur n’a pas de préférence technologique préalable. Socle applicatif installé le 15 octobre 2026 ; versions reproductibles dans pnpm-lock.yaml et uv.lock. pikepdf 9.11.0 et Playwright 1.56.1 fixés pour la compatibilité Mac Intel/macOS 13. Voir README.md.

## Choix recommandé

| Couche | Choix | Usage |
|---|---|---|
| Interface | React + TypeScript + Vite | Application interactive de réglage et d’aperçu. |
| Composants | Tailwind CSS + shadcn/ui | Formulaires, panneaux, dialogues et états d’erreur, avec styles adaptés à Snackpress. |
| Affichage PDF | PDF.js, paquet pdfjs-dist | Rendu des fichiers source et du PDF imposé dans le navigateur. |
| API | Python + FastAPI + Pydantic | Import, validation des paramètres, calcul des placements, export et suivi des traitements. |
| Moteur PDF | pikepdf, construit sur QPDF | Import des pages comme objets PDF, transformations et composition des feuilles. Choix conditionné au prototype de fidélité. |
| Données du prototype | SQLite + SQLAlchemy + Alembic | Statut des travaux et modèles côté serveur, sur une seule instance. |
| Fichiers | Répertoire temporaire privé sur volume dédié | Sources et exports séparés des données structurées ; purge automatique et quotas. |
| Développement | pnpm pour TypeScript ; uv pour Python | Installation reproductible et fichiers de verrouillage. |
| Vérification | pytest, Vitest et Playwright | Géométrie et API, logique d’interface, parcours d’import et d’export. |
| Déploiement bêta | Docker Compose + Caddy, sur une machine Linux en région UE | Interface et API derrière une même origine HTTPS, avec processus PDF séparés. |

Les versions exactes seront fixées au démarrage du code après vérification de leur compatibilité. La base SQLite n’est pas un stockage de PDF et ne sert pas de courtier de messages.

## Répartition des responsabilités

React affiche les paramètres, permet la manipulation de la vue et présente les placements. PDF.js affiche le résultat ; il n’est pas le moteur de génération des planches.

Python détient le calcul géométrique de référence et la génération PDF. Un schéma Pydantic versionné décrit les paramètres : feuille, zone imprimable, format fini, fond perdu, espaces, grille, rotation, retournement et quantité. Le client TypeScript utilise des types générés depuis OpenAPI.

L’API retourne un plan explicite de placements avec les transformations de chaque pose et les repères. L’interface dessine un schéma SVG de ce plan. L’export utilise exactement le même plan. Après stabilisation des réglages, une prévisualisation du PDF généré confirme le résultat avec PDF.js. Cela évite de maintenir deux algorithmes d’imposition indépendants.

L’aperçu peut utiliser des images pour rester fluide ; l’export est composé à partir des objets PDF d’origine. Une capture du canvas ne doit jamais servir de fichier d’impression.

## Organisation du dépôt

```text
apps/
  web/                  # React, formulaires, aperçu, client API
  api/                  # FastAPI, travaux, fichiers et modèles
packages/
  imposition/           # Calculs Python purs et composition PDF
  api-client/           # Types TypeScript générés depuis OpenAPI
tests/
  fixtures/             # Corpus synthétique, ou fichiers autorisés
  e2e/                  # Parcours Playwright
infra/                  # Dockerfiles, Compose, Caddy
```

Le paquet d’imposition ne dépend pas de FastAPI. Il doit pouvoir être exécuté en ligne de commande pour tester un fichier sans l’interface. Un éventuel passage à une application locale pourra réutiliser cette séparation, mais demandera un travail de packaging spécifique.

## Traitements PDF

Pour le prototype mono-instance, utiliser des processus enfants bornés, supervisés par le service, avec limite de concurrence, délai maximal et plafonds de ressources. Les calculs PDF ne doivent pas bloquer la boucle asynchrone de l’API. Une tâche interrompue au redémarrage est marquée en échec et peut être relancée ; ne pas promettre une file durable à ce stade.

Lorsque la charge ou les exigences de reprise le justifient, passer à un worker dédié avec une file durable. Celery et Redis sont une piste à évaluer à ce jalon, sans les imposer au prototype.

Avant la bêta distante : contrôle d’accès par invitations, autorisation par propriétaire de travail, isolation du traitement, limites d’import, suppression automatique et absence de contenu PDF dans les journaux. Choisir le fournisseur d’identité au moment du passage au service multiutilisateur, selon le mode de commercialisation retenu.

## Évolution vers le SaaS

- PostgreSQL pour les comptes, modèles synchronisés, travaux et abonnement ; migrer avant de multiplier les instances.
- Stockage objet compatible S3, en région UE, pour les fichiers temporaires lorsque plusieurs workers doivent y accéder ; accès privé et expiration vérifiée.
- Worker et file de travaux pour gérer concurrence, reprises et traitements longs.
- Fournisseur d’identité et paiement lorsque le modèle commercial est validé.
- Moteur spécialisé tel que callas si le corpus ou les futures exigences de préflight/PDF-X dépassent les capacités validées du moteur initial.

## Pourquoi ces choix

Vite convient à l’atelier interactif envisagé, dont le besoin principal n’est pas le rendu serveur de pages publiques. Si un site marketing devient nécessaire, il peut être ajouté séparément. FastAPI permet de définir et documenter le contrat API avec Pydantic et OpenAPI. pikepdf fournit des primitives de placement de pages par objets PDF ; la géométrie d’imposition et les vérifications métier restent à développer.

Une stack intégralement TypeScript avec pdf-lib est une alternative possible : la bibliothèque expose l’intégration de pages PDF. Je recommande néanmoins de commencer par le prototype Python/pikepdf pour évaluer directement la composition et l’inspection des objets PDF. Ce choix est une préférence d’architecture, pas la preuve d’une meilleure fidélité sur tous les fichiers.

## Critère de validation du moteur

Avant de considérer pikepdf comme le moteur définitif, exporter des planches issues du corpus pilote et vérifier : géométrie, polices, CMJN, tons directs, transparences, surimpressions, boîtes de page et informations colorimétriques. Contrôler le retournement avec des épreuves physiques. Une bibliothèque de composition ne certifie pas la conformité PDF/X.

## Documentation de référence

- [Vite — démarrage et modèles React/TypeScript](https://vite.dev/guide/).
- [shadcn/ui — installation](https://ui.shadcn.com/docs/installation/manual).
- [PDF.js — exemples de rendu](https://mozilla.github.io/pdf.js/examples/index.html).
- [FastAPI — fonctionnalités Pydantic et OpenAPI](https://fastapi.tiangolo.com/features/).
- [FastAPI — limites des tâches de fond simples](https://fastapi.tiangolo.com/tutorial/background-tasks/).
- [pikepdf — composition et placement de pages](https://pikepdf.readthedocs.io/en/stable/topics/overlays.html).
- [pikepdf — dépôt, QPDF et licence MPL-2.0](https://github.com/pikepdf/pikepdf).
- [pdf-lib — intégration de pages PDF](https://pdf-lib.js.org/docs/api/classes/pdfdocument).

## Extension des outils — 15 octobre 2026

Le catalogue demandé élargit le prototype : ReportLab génère les fiches, plans vectoriels, codes et BAT ; pypdfium2 rend les pages pour Donut, Tiramisu, Burger et Poké ; NumPy/Pillow traitent les pixels. pikepdf conserve son rôle de composition native et d’inspection structurelle. Tous les traitements PDF restent dans des processus enfants bornés. Les outils sont séparés dans `packages/prepress`. Les nouvelles versions sont verrouillées dans uv.lock. Les types du catalogue, des champs et des résultats viennent d’OpenAPI. Voir TOOLS.md pour le contrat de chaque outil.
