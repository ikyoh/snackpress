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

Mode Operate. Réglages à gauche et résultat à droite ; empilement sur mobile. Sur ordinateur, le panneau d’aperçu reste sticky dans l’atelier et sa hauteur suit la fenêtre. Pizza sert de modèle pour les formulaires longs : colonne de préparation légèrement élargie, défilement interne des réglages, action de génération accessible en bas, sections Format / Zone de sécurité / Zone inexploitable repliables avec résumés, et gestion des configurations à la demande. Sur mobile, Pizza propose deux onglets Réglages / Aperçu qui conservent les saisies. Les illustrations, typographies et commandes héritent de la nouvelle identité. Les feuilles PDF restent blanches, leurs proportions et couleurs ne sont pas teintées par l’interface. Les limites métier, mesures et avertissements restent visibles.

## Interactions et accessibilité

Commandes bombées qui s’enfoncent au clic, cartes légèrement soulevées au survol, confirmation ponctuelle par une transition jaune/verte après un vrai traitement réussi. Focus clavier violet visible, contrastes élevés pour les textes utiles, cibles tactiles larges, mouvements désactivés lorsque l’utilisateur demande une réduction des animations. Les pictogrammes de snacks sont décoratifs ; les noms d’outils restent du texte accessible.

## Illustrations

Génération intégrée image_gen, fichiers WebP avec transparence conservée dans `apps/web/public/candy`. La planche de 16 snacks est affichée par cellules CSS ; les 14 premières correspondent aux outils. Le héros et les prompts sont documentés dans `apps/web/public/candy/ASSETS.md`.

Le hero choisi le 17 octobre 2026 est « La fabrique à PDF » : presse miniature rose et violette imprimant une planche de snacks avec repères de coupe, burger et donut autour. Fichier `hero-printshop.webp`, affiché entièrement sans recadrage. La mention « Prototype local » est retirée des en-têtes.
