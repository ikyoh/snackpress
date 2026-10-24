# Catalogue des produits d’impression

Accès : **Produits d’impression** dans l’en-tête (`/?view=products`). Le catalogue est personnel, enregistré dans le compte et retrouvé sur les autres appareils. Sans connexion, la gamme de départ peut être consultée et modifiée temporairement ; l’enregistrement exige un compte. Les produits pilotes ne sont pas une copie du catalogue ni des prescriptions de Realisaprint.

## Bibliothèques et produits

**Ajouter un produit** ouvre un assistant en quatre étapes : nom et catégorie, format et papier, fichiers et tracés, puis vérification. Le format est personnalisé par défaut ; un gabarit Pizza enregistré peut aussi être choisi. Les fichiers attendus se définissent en un choix : recto seul, recto verso dans deux PDF ou recto verso dans un PDF de deux pages. Sushi et les autres tracés restent accessibles dans la troisième étape.

Les boutons Précédent et Modifier conservent les saisies. Annuler revient au catalogue sans ajouter de produit. **Créer le produit** l’enregistre directement dans le compte connecté ; sans compte, il est ajouté au catalogue temporaire. En cas d’échec, le récapitulatif et les réglages sont conservés pour réessayer. Une déclinaison Standard et un composant portant le nom du produit sont créés automatiquement. Les finitions, les autres déclinaisons et les composants supplémentaires se règlent ensuite dans la fiche détaillée. Les éventuelles autres modifications du catalogue sont également enregistrées, ce qui est annoncé dans le récapitulatif.

- Catégories et sous-catégories modifiables ; suppression refusée tant qu’une catégorie est utilisée.
- Supports matières réutilisables : famille, grammage et épaisseur facultatifs.
- Façonnages et finitions : supports compatibles, exclusions entre finitions et PDF de masque facultatif. Une finition sans masque reste une instruction de fabrication.
- Produits : catégorie, description, supports et finitions autorisés, une ou plusieurs déclinaisons. Duplication et retrait des produits et des déclinaisons.
- Composants : nom, format fini, fond perdu, matière, règle de pagination, emplacements PDF et tracés. Par exemple, une brochure distingue couverture et intérieur.

La gamme de départ comprend carte recto verso, dépliant pli roulé, brochure agrafée, bâche à œillets, étiquette découpée et billet détachable numéroté. Les catégories incluent aussi packaging, textile et PLV pour créer d’autres produits avec les composants et tracés disponibles.

Un emplacement correspond à un PDF avec un nom, un rôle (visuel ou masque technique) et un nombre exact de pages. Pour accepter un PDF recto verso au lieu de deux PDF, créer une déclinaison avec un emplacement de deux pages. Une finition demandant un masque ajoute un fichier par composant, contenant autant de pages que ses visuels. Les finitions sélectionnées s’appliquent à l’ensemble des composants : leur support doit être compatible. Un masque propre à un seul composant peut être défini directement dans ses emplacements.

Dans les produits, les gabarits sont enregistrés sous forme de paramètres. Pizza, Taco, Burrito et Sushi peuvent être combinés par composant. « Perforations — parties détachables » n’est plus proposé dans Ajouter un tracé ; les perforations déjà enregistrées restent conservées et modifiables. Les dimensions proviennent du composant ; les autres réglages restent modifiables. Le BAT superpose les tracés en alignant leur origine au format fini. Un PDF vectoriel des tracés à l’échelle 1:1 est téléchargeable par composant. Le gabarit PDF fourni par un façonnier reste disponible dans la composition classique de Burger.

Pour compléter un gabarit Pizza, choisir **Sushi — découpe et rainage** dans **Ajouter un tracé**, dans les produits, l’assistant ou le mode libre du BAT. Le gabarit Pizza, ses dimensions, son fond perdu et son contour sont conservés. Sushi ajoute des lignes de coupe et de rainage dans ce même format ; il ne crée pas de second contour. Changer de gabarit Pizza conserve les lignes Sushi, dont les positions doivent rester dans le nouveau format. Le PDF des tracés et le BAT comprennent les deux couches vectorielles. Le contour du BAT reste celui de Pizza, quel que soit l’ordre d’ajout des tracés.

Sans Pizza, Sushi peut aussi définir un contour facultatif (rectangle avec coins arrondis ou cercle), les tons directs et les tracés de coupe ou de rainage. Le cercle conserve un format carré quand son diamètre change. Choisir ensuite un gabarit Pizza conserve les lignes Sushi et confie le contour à Pizza. Les réglages sont enregistrés avec la déclinaison et repris dans le BAT.

## Création du BAT

Dans Burger, **Mode du BAT** propose :

1. **Composition classique** : fonctionnement précédent, y compris les configurations personnelles existantes. Sushi est désormais aussi disponible directement comme gabarit.
2. **Depuis le catalogue** : catégorie, produit, déclinaison, puis options. « Adapter les spécifications pour ce BAT » permet de changer les dimensions, supports, emplacements et tracés sans modifier le produit enregistré.
3. **Mode libre configurable** : mêmes composants, fichiers et tracés, sans produit préalable. « Enregistrer comme nouveau produit » ajoute la configuration au catalogue du compte. La catégorie sélectionnée, ou la première catégorie disponible, est utilisée ; elle peut être modifiée dans le catalogue.

Les fichiers sont contrôlés côté serveur : PDF non chiffré, pagination exacte, dimensions physiques de la TrimBox (tolérance 0,1 mm), fonds perdus disponibles dans la BleedBox (tolérance 0,1 mm), unités et rotation normalisées. La règle « pagination par multiple de » contrôle le total des pages visuelles du composant ; elle vaut 4 pour les composants de la brochure pilote. Les fichiers de production ne sont pas redimensionnés pour satisfaire ces contrôles.

Le BAT contient une présentation seule et une présentation avec tracés pour chaque page visuelle, ainsi que les masques séparés. La fiche technique liste les spécifications. `reglages.json` conserve une copie complète des spécifications utilisées : les modifications ou suppressions ultérieures du catalogue ne modifient pas ces résultats. Les visuels du BAT restent rasterisés pour la présentation ; les repères superposés conservent leurs tracés vectoriels et leurs hachures dans le PDF final. Le BAT ne constitue pas une épreuve couleur contractuelle. Les travaux et leurs réglages restent soumis à la conservation actuelle de 24 heures : télécharger les résultats à conserver.

## Billets détachables numérotés

L’option « Billets ou coupons numérotés » n’est plus proposée dans la fiche produit ni dans le mode libre du BAT. Les produits déjà configurés avec une numérotation conservent leurs réglages et leur génération de série.

Le produit pilote comporte une souche et un billet dans un même visuel, une perforation verticale à 30 mm et deux positions portant le même numéro. Les coordonnées partent du coin supérieur gauche du format fini.

Réglages : premier numéro, quantité de 1 à 100, chiffres, préfixe, suffixe, une à vingt positions, taille et face pour chaque position. Un décalage permet une séquence différente sur une position. Pour un verso, ajouter un second emplacement visuel d’une page. Les billets utilisent un recto et un verso facultatif dans deux fichiers distincts.

Le QR code ou Code 128 optionnel est placé au recto. `{n}` dans son contenu devient le numéro complet avec préfixe et suffixe. Tester les codes sur une épreuve ; les contenus trop denses ou trop longs sont refusés.

Le BAT montre le premier et le dernier billet. L’aperçu ne génère que ces échantillons. **Générer le fichier final** produit toute la série PDF, dans l’ordre des numéros, recto puis verso pour chaque billet. Les visuels vectoriels et les fonds perdus sont conservés ; les annotations et champs interactifs des sources ne sont pas repris. Les tracés restent dans un PDF séparé et ne sont pas imprimés sur la série.

L’assemblage en billets séparés, carnets agrafés ou carnets encollés est une instruction. Le manifeste donne les plages de numéros par carnet et signale le dernier carnet partiel. L’imposition en piles, les perforations physiques et la reliure restent des opérations de fabrication.

## Stockage et limites

Une ligne `print_libraries` par compte dans `jobs.db`, indépendante de la purge des travaux. Les sauvegardes du volume incluent le catalogue. Les écritures sont authentifiées, protégées par les mêmes contrôles d’origine que les configurations et portent une révision : une modification concurrente est refusée. Recharger le catalogue pour récupérer la dernière version ; cette action abandonne les modifications locales non enregistrées.

Limites : 200 produits, 30 déclinaisons par produit, 12 composants par déclinaison, 100 catégories, 100 matières, 30 finitions, catalogue de 250 Ko. Un BAT accepte 80 fichiers et 200 pages source, masques compris. Les plafonds existants de fichiers, temps, processus, rendu et taille de sortie s’appliquent. Les géométries disponibles restent celles des outils : le catalogue peut décrire d’autres produits, mais ne génère pas automatiquement de nouvelles formes de packaging ni de visualisation 3D.

Les nouvelles tables sont créées au démarrage sans modifier les tables existantes. La migration Alembic `0003` est fournie et peut être répétée sur une base déjà initialisée.

## Vérification

```sh
.venv/bin/python -m pytest
.venv/bin/ruff check .
pnpm test
pnpm build
SNACKPRESS_BROWSER_CHANNEL=chrome pnpm test:e2e:products
```

Les tests navigateur du catalogue utilisent des serveurs, une base et une boîte e-mail locale temporaires (ports 8015 et 5175), sans envoyer de vrais e-mails. Ils couvrent aussi les parcours classiques Burger.

Validation locale du 17 octobre 2026 : 131 tests Python, 2 tests Vitest, compilation TypeScript/Vite, Ruff et vérification des diffs réussis. Les 6 parcours Playwright dédiés passent dans Google Chrome : Burger classique, catalogue et masques, billets et série, compte et sauvegarde, mode libre et affichage mobile. La migration `0002` → `0003` et sa répétition sont vérifiées. Les écrans ordinateur/mobile ont été inspectés. La validation sur documents professionnels, les épreuves couleur et les essais de fabrication restent distincts de ces vérifications logicielles.
