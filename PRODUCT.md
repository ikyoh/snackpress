# Snackpress
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
React, TypeScript, Vite, Tailwind, composants shadcn/ui, PDF.js ; FastAPI/Pydantic, pikepdf, SQLite/SQLAlchemy/Alembic. Choix validé par la demande de démarrage selon STACK.md.

## Users
Imprimeurs numériques et graphistes préparant des cartes, flyers et étiquettes.

## Product Purpose
Réunir 14 outils prépresse pour contrôler, préparer, présenter, tracer, personnaliser et assembler les documents d’impression. Périmètre élargi explicitement par l’utilisateur le 15 octobre 2026 ; contrats détaillés dans TOOLS.md.

## Operating Context
Réglages en millimètres, contrôle des deux faces, export de feuilles types et consignes de tirage. L’utilisateur a choisi les réglages et l’aperçu côte à côte pour travailler rapidement. Les aperçus PDF/image se recalculent après une pause de 500 ms, avec une version réduite pour les traitements lourds et une génération finale explicite. Pizza prend en charge les rectangles, cercles et ovales.

## Capabilities and Constraints
Catalogue complet : Burger, Chili Dog, Donut, Tiramisu, Taco, Pizza, Burrito, Club Sandwich, Fortune Cookie, Poké, Sushi, Kebab, Layer Cake et Bento. Sorties et limites conformes au tableau de l’utilisateur, documentées dans TOOLS.md. La rasterisation est autorisée pour les corrections Donut, les comparaisons Tiramisu et les présentations/estimations écran ; elle est annoncée dans chaque parcours.

Grille régulière, rotation 0/90°, feuilles et marges personnalisables, fonds perdus disponibles, repères, quantité et configurations personnelles liées à un compte vérifié par e-mail, avec import des anciens profils locaux. Les outils restent accessibles sans compte ; les travaux PDF ne sont pas encore isolés par utilisateur. Prototype ; validation de fidélité et épreuves physiques requises avant bêta. Voir PRODUCT-BRIEF.md et STACK.md.

## Brand Commitments
Nom Snackpress, langue française. Direction visuelle explicitement choisie le 15 octobre 2026 : inspiration Candy Crush, très colorée, ludique et gourmande, pour rendre la prise en main accueillante. L’interface utilise ses propres illustrations, conserve la précision des réglages et annonce les limites des traitements.

## Evidence on Hand
Cadrage et plan présents dans le dépôt ; aucun corpus pilote ni référence visuelle fourni.

## Product Principles
- Un seul plan géométrique pour l’aperçu et l’export.
- Les traitements natifs et raster sont distingués ; tout ajustement de taille est annoncé.
- Les limites du prototype sont explicites.
