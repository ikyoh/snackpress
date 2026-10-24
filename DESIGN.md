# Snackpress — le royaume des snacks

Direction demandée explicitement par l’utilisateur le 15 octobre 2026 : un univers à la Candy Crush, très coloré, qui donne l’impression que la suite est un jeu d’enfant. Cette demande remplace l’ancienne identité de nuancier prépresse.

## Identité

Univers original de confiserie et de snacks de jeu : rose framboise, violet cassis, bleu soda, vert pomme, orange et jaune citron. Fonds clairs teintés, illustrations gourmandes en volume, reflets et bords bombés sur les commandes. Aucun personnage, logo ou élément graphique de Candy Crush repris.

Lilita One donne la voix ronde des titres et du nom ; Nunito variable porte les textes et les mesures. Polices auto-hébergées. Texte principal prune foncé sur les surfaces pâles ; texte blanc réservé aux commandes suffisamment foncées. Les couleurs des cartes varient par outil, pas par statut de validation.

Typographie d’interface agrandie : base navigateur conservée à 100 %, textes courants et champs à 1,0625 rem (17 px par défaut), informations secondaires à 0,9375 rem (15 px), légendes à 0,875 rem (14 px). Les titres gardent leur hiérarchie avec des tailles en rem. Les tailles mobiles ne descendent pas sous cette échelle ; les cartes passent sur une colonne jusqu’à 600 px et les commandes peuvent revenir à la ligne.

Le logo est un « S feuilleté » : ruban rose framboise vers violet, avec un coin jaune replié évoquant une feuille d’impression. Source vectorielle : `apps/web/public/snackpress.svg`. Dans les en-têtes, il apparaît à 32 px dans une pastille pâle `#fff5fc`. Les favicons SVG/ICO/PNG et l’icône Apple reprennent le même dessin sur ce fond pâle.

## Catalogue

Titre « Les PDF ? Un jeu d’enfant. », illustration gourmande, lien réel vers le catalogue et trois gestes qui décrivent le parcours : choisir l’outil, ajouter ses réglages, récupérer le fichier. Les 14 cartes portent une illustration correspondant à leur nom, une description métier et une action clairement identifiable. Recherche, filtres et liens fonctionnent comme auparavant. Aucun score, vie, récompense ou indicateur de progression inventé.

## Ateliers

Mode Operate. Réglages à gauche et résultat à droite ; empilement sur mobile. Sur ordinateur, le panneau d’aperçu reste sticky dans l’atelier, sans défilement interne. Le PDF intégré s’ajuste à la zone disponible ; le zoom détaillé est disponible en plein écran. Les ateliers partagent une colonne de préparation légèrement élargie, le défilement interne des réglages, une action de génération accessible en bas, des sections repliables par sujet avec résumés, et la gestion des configurations à la demande. Pizza conserve ses sections Format / Zone de sécurité / Zone inexploitable, qui peuvent rester ouvertes ensemble. Les retraits utilisent une valeur commune par défaut, avec dissociation des côtés et conservation des configurations asymétriques. Les bornes de dimensions se trouvent dans « Limites de dimensions », ouvert automatiquement lorsqu’un gabarit chargé les utilise. Les contraintes géométriques sont expliquées près des champs ; le dernier réglage actif est surligné dans l’aperçu à jour du gabarit, sans ajout au PDF exporté ; les autres outils utilisent leurs sujets métier (pliage, ourlets, numérotation, fabrication, etc.). Sur mobile, chaque atelier propose deux onglets Réglages / Aperçu qui conservent les saisies. Taco propose un choix explicite de retournement et de face au recto ; les boutons Recto / Verso remplacent la navigation numérique pour le plan de pliage, dans l’aperçu automatique et le résultat final. La face sélectionnée reste active pendant les recalculs. Le PDF conserve des identifiants de panneaux physiques, un coin commun A et des plis pointillés visibles sur les deux faces. Les illustrations, typographies et commandes héritent de la nouvelle identité. Les feuilles PDF restent blanches, leurs proportions et couleurs ne sont pas teintées par l’interface. Les limites métier, mesures et avertissements restent visibles.

## Interactions et accessibilité

La création d’un produit suit un assistant intégré à la page, en quatre étapes : Produit, Format et papier, Fichiers et tracés, Vérification. Une seule étape apparaît à la fois ; les retours conservent les saisies et les liens Modifier du récapitulatif ramènent à la bonne étape. Les noms techniques de déclinaison et de composant ne sont pas demandés pendant la création. Les PDF attendus se choisissent par usage (recto, recto verso), les tracés se configurent à la demande, et le récapitulatif précède l’enregistrement. La fiche détaillée conserve les réglages avancés. Le focus suit le titre de l’étape, les champs utilisent la validation native et le parcours s’empile sur mobile.

L’en-tête commun au catalogue, aux outils et à l’imposition regroupe « Tous les outils », « Produits d’impression » et l’accès au compte. Les trois commandes utilisent une hauteur de 48 px, la même typographie et les mêmes espacements. La destination active est indiquée visuellement et par `aria-current`. Les accès restent visibles sur mobile, sur deux colonnes puis une seule sur les écrans les plus étroits.

Commandes bombées qui s’enfoncent au clic, cartes légèrement soulevées au survol, confirmation ponctuelle par une transition jaune/verte après un vrai traitement réussi. Focus clavier violet visible, contrastes élevés pour les textes utiles, cibles tactiles larges, mouvements désactivés lorsque l’utilisateur demande une réduction des animations. Les pictogrammes de snacks sont décoratifs ; les noms d’outils restent du texte accessible.

## Illustrations

Génération intégrée image_gen, fichiers WebP avec transparence conservée dans `apps/web/public/candy`. La planche de 16 snacks est affichée par cellules CSS ; les 14 premières correspondent aux outils. Le héros et les prompts sont documentés dans `apps/web/public/candy/ASSETS.md`.

Le hero choisi le 17 octobre 2026 est « La fabrique à PDF » : presse miniature rose et violette imprimant une planche de snacks avec repères de coupe, burger et donut autour. Fichier `hero-printshop.webp`, affiché entièrement sans recadrage. La mention « Prototype local » est retirée des en-têtes.
