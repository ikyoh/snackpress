# Les outils Snackpress

Périmètre demandé le 15 octobre 2026. Les 14 outils ont un formulaire, un traitement réel, des fichiers téléchargeables et un aperçu PDF/image. Les résultats incluent leurs réglages et leurs limites en JSON. Le catalogue est la page d’accueil ; la recherche et les filtres servent à retrouver les outils.

| Outil | Entrée et résultat | Contrat et limites |
|---|---|---|
| Burger | PDF visuels + un PDF par finition + gabarit facultatif → BAT A4 et fiche technique PDF | Nombre de fichiers réglable ; carte recto verso : 2 PDF d’une page ; brochure : 4 pages de couverture et intérieur contrôlé. Jusqu’à 200 pages source, rendu à 120 dpi maximum ajusté sur A4 ; couleurs non contractuelles. |
| Chili Dog | PDF → rapport PDF et inventaire JSON des formats, boîtes, polices, images et couleurs | Inspection des déclarations et ressources référencées ; pas de certificat PDF/X, de mesure de résolution effective ni de garantie sur les ressources inline. |
| Donut | PDF de 1 à 20 pages ou PNG/JPEG → PDF ou PNG avec bords prolongés/miroir | Raster RGB à 72–300 dpi. La zone visible devient le format fini ; anciennes boîtes de coupe ignorées explicitement. Largeur physique déclarée pour une image. Sortie PNG pour une page seulement. Chaque bord doit être relu. |
| Tiramisu | Deux PDF → superposition, carte des différences, rapport et JSON page par page | Raster RGB à 72–150 dpi, aligné en haut à gauche, sans recalage. Tolérance sur le maximum des écarts RGB. Les pages absentes et les écarts de dimensions sont signalés. |
| Taco | Format à plat et type de pli → schéma 1:1 et fiche des panneaux | Accordéon : panneaux égaux. Roulé : retrait progressif selon l’emboîtement. Portefeuille : 4 panneaux, volets extérieurs réduits. Aucun ordre de lecture automatique ; validation du façonnier requise. |
| Pizza | Forme rectangulaire, ronde ou ovale, format fini, fond perdu et sécurité → gabarit 1:1 et légende | L’ovale conserve une largeur et une hauteur indépendantes ; le cercle utilise un diamètre unique. TrimBox et BleedBox définies. Guides visibles et fond perdu coloré ; gabarit technique à retirer du visuel final. |
| Burrito | Format, ourlet, fourreau et entraxe → plan 1:1 et coordonnées des œillets | Ourlet intérieur sur 4 côtés ; fourreau ajouté au-dessus ; entraxe ajusté pour ne pas dépasser le maximum demandé ; centres dédoublonnés aux coins. Aucun visuel modifié. |
| Club Sandwich | Pages intérieures, grammage/main ou calibre → estimation du dos et PDF | Feuilles = pages / 2 ; calibre en µm = grammage × main, ou calibre mesuré ; bloc en mm = feuilles × calibre / 1 000 ; marge de colle ajoutée. Hors couverture et compression ; confirmer au relieur. |
| Fortune Cookie | Réglages et fond PDF facultatif d’une page → série PDF de 1 à 100 exemplaires | Texte, numérotations multiples sans plafond de placements et QR ou Code 128. Chaque numérotation partage la séquence et possède ses coordonnées X/Y en mm, sa couleur, sa taille en points, sa police et sa rotation en degrés. Placement à la souris dans l’aperçu ou par coordonnées depuis le coin supérieur gauche (point de départ sur la ligne de base). `{n}` dans le contenu du code est remplacé par le numéro avec préfixe. Une page par exemplaire ; numérotations sur fond transparent ; surfaces blanches réservées au texte et aux codes. Fond utilisé sans redimensionnement, au format de sa TrimBox. Codes à tester sur une épreuve. |
| Poké | PDF → espaces couleur, tons directs et estimation CMJN par page | Estimation écran après rendu RGB, avec K = 1 − max(R,G,B), puis retrait du noir. Moyennes par canal et somme maximale estimée. Ni séparation RIP, ni TAC certifié, ni consommation d’encre réelle. |
| Sushi | Format, contour et positions des rainages → PDF vectoriel et convention | Rectangle/cercle, traits de 0,1 mm, sans remplissage, surimpression activée. Deux tons directs nommés, par défaut `CutContour` et `Crease`. Marge technique de 5 mm autour du contour. Convention à confirmer à l’atelier. |
| Kebab | Papier, quantité, couleurs, finitions et notes → fiche PDF | Déclarations et instructions ; aucun choix de fabrication validé automatiquement. |
| Layer Cake | PDF → répétition ou livret piqué, plus fiche de tirage | Répétition : moteur géométrique natif existant, PDF de 1 ou 2 pages, sans changement d’échelle ; atelier détaillé conservé. Livret : 4–80 pages, multiple de 4, pages ajustées proportionnellement aux demi-feuilles, sans chasse. Ordre des feuilles documenté ; retournement et pliage à éprouver sur presse. |
| Bento | De 1 à 8 PDF → fusion, extraction, réordre ou rotation | Jusqu’à 80 pages par source et 200 en sortie. Fusion selon l’ordre des fichiers, modifiable dans l’écran. Autres opérations sur un seul fichier. Pages et plages à partir de 1 ; le réordre doit contenir chaque page une fois. PDF non chiffrés ; signatures, formulaires, annotations et métadonnées de document non conservés. |

## Exploitation locale

Dans Burger, choisissez la composition avant l’import : nombre de fichiers visuels, puis finitions nommées (vernis, dorure, blanc de soutien ou autre). Importez les PDF dans l’ordre indiqué ; les flèches permettent de corriger leur affectation. Pour une brochure, les premiers fichiers de couverture doivent totaliser 4 pages et les fichiers suivants le nombre de pages intérieures annoncé. Les finitions viennent ensuite, avec un PDF distinct pour chacune.

Le gabarit Burger peut reprendre les réglages et configurations personnelles de Pizza, Taco, Burrito ou Sushi, ou provenir de leur PDF exporté (une page). La TrimBox sert à placer un visuel au format fini ; un visuel au format complet du gabarit est également accepté. Chaque visuel reçoit une page de présentation et une page supplémentaire avec les repères. Les dimensions incompatibles sont refusées. Les pages de finition sont présentées séparément dans le BAT.

- 25 Mo par fichier, 50 Mo par traitement, 100 travaux conservés au maximum.
- Processus PDF séparés : 2 simultanés, 30 secondes murales et 25 secondes CPU ; fichier de sortie individuel limité à 150 Mo. Mémoire virtuelle limitée à 1 Gio sur Linux, threads de calcul limités à 1.
- Rendus limités en pixels : 20 millions pour Donut, 8 millions par page pour Tiramisu, 4 millions pour l’estimation Poké. Un fichier trop grand est refusé avec une action proposée ; il n’est pas rééchantillonné silencieusement.
- PDF non chiffrés. Jusqu’à 80 pages pour l’inspection, la comparaison et les outils généraux ; limites plus étroites indiquées ci-dessus.
- Sources et résultats stockés dans le répertoire privé `.data`, purge au démarrage puis chaque minute après 24 heures. Suppression immédiate d’un résultat depuis son écran.
- Usage local individuel ; les identifiants aléatoires de travaux ne remplacent pas une authentification pour un déploiement public.

Les exemples fournis sont synthétiques : carte recto verso, version modifiée, fond d’une page et livret de huit pages. Aucun fichier client n’est inclus.

## Validation avant production

Les tests automatisés couvrent les exports des 14 outils et des cas connus de géométrie, pixels, pagination, numérotation et ressources PDF. Ils ne remplacent pas un corpus professionnel ni les essais du façonnier, du relieur et de la presse. Les résultats raster ne constituent pas une épreuve couleur contractuelle.


Les aperçus se mettent à jour automatiquement après 500 ms sans saisie et dès que les fichiers requis sont présents. Donut, Tiramisu et Poké sont limités à deux pages et 96 dpi dans l’aperçu ; Fortune Cookie affiche deux exemplaires maximum. Le bouton de génération réalise toujours le fichier complet avec les paramètres demandés. Les limites de l’aperçu sont indiquées dans chaque atelier. Voir le README pour la conservation des sessions temporaires.

## Catalogue des produits d’impression

Le lien **Produits d’impression** permet de gérer catégories, matières, finitions et produits à déclinaisons dans le compte. Burger propose le catalogue et un mode libre avec composants, emplacements PDF nommés, pagination, formats et fonds perdus contrôlés. Les tracés Pizza, Taco, Burrito, Sushi et les perforations sont associés aux composants ; Pizza et Sushi sont des références de découpe alternatives. Les spécifications sont copiées dans les réglages du BAT.

Les **billets détachables numérotés** proposent souche et coupons, perforations, numéros répétés ou décalés, préfixe/suffixe, recto verso et codes facultatifs. Le BAT et l’aperçu montrent le premier et le dernier billet ; l’export final contient toute la série vectorielle (100 billets maximum) et le manifeste des carnets. L’assemblage et les perforations physiques restent des opérations de fabrication. Voir les [modalités et limites](docs/PRINT-CATALOG.md).
