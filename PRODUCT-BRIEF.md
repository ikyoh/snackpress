# Snackpress — cadrage de la première version

Statut : cadrage initial du 14 octobre 2026.

Évolution demandée le 15 octobre 2026 : ajout des 14 outils prépresse détaillés dans TOOLS.md. Ce document conserve le cadrage initial de l’imposition ; le catalogue complet est désormais implémenté dans le prototype local.
Priorité confirmée : imposer les pages sur des feuilles d’impression.

## Positionnement

Snackpress transforme un PDF de carte, flyer ou étiquette en planches d’impression, avec un aperçu compréhensible, des paramètres en millimètres et des modèles réutilisables.

Cible initiale proposée : opérateurs de petites imprimeries numériques et graphistes qui préparent régulièrement des planches pour un imprimeur. Le premier utilisateur pilote à recruter est un opérateur réalisant plusieurs de ces travaux par semaine.

Hypothèse à tester : préparer une planche répétitive dans un outil de mise en page ou un logiciel trop complexe prend assez de temps et présente assez de risques pour justifier un outil spécialisé. Ni la fréquence, ni le temps perdu, ni la volonté de payer ne sont encore établis.

## Première version proposée

Un seul mode d’imposition : répétition d’un même produit sur une grille régulière, en recto seul ou recto verso. Entrée : PDF d’une page, ou PDF de deux pages dont la première est le recto et la seconde le verso. Les documents plus longs sont explicitement refusés dans cette version.

| Fonction | Comportement attendu |
|---|---|
| Import | Lecture du PDF, dimensions, rotation et boîtes de page ; message explicite pour un fichier protégé, endommagé ou non pris en charge. |
| Format fini | Utiliser la TrimBox lorsqu’elle existe ; sinon demander de confirmer le format et la zone de coupe. |
| Feuille | A4, A3, SRA3 et dimensions personnalisées ; orientation et marges non imprimables réglables. |
| Placement | Grille régulière centrée ; comparer les orientations 0° et 90°, afficher le nombre de poses ; permettre lignes et colonnes manuelles. |
| Fond perdu | Utiliser le contenu disponible autour du format fini ; prévenir lorsque l’espace déclaré est insuffisant. Ne pas inventer les pixels ou objets manquants. |
| Espacement | Distance entre formats finis, avec vérification des débordements et du chevauchement des fonds perdus. |
| Repères | Traits de coupe réglables, placés hors du contenu utile et dans la zone disponible ; aperçu de leur emplacement. |
| Recto verso | Aperçus séparés et schéma de retournement ; positions du verso calculées selon le retournement choisi. |
| Quantité | Calcul du nombre de feuilles et des exemplaires produits ; export d’une feuille type recto ou d’une paire recto/verso, avec quantité de répétitions indiquée. |
| Export | PDF imposé à l’échelle 100 %, fiche des réglages et avertissements. |
| Modèles | Sauvegarde locale de profils de feuille et de placement, réutilisables sur un autre PDF. |

Le nombre de poses et le nombre de feuilles sont des résultats du calcul, jamais des constantes marketing. Les marges réelles et le retournement doivent être vérifiés sur la machine utilisée.

Le diagnostic initial vérifie la géométrie et la possibilité de traiter le fichier. Il ne certifie pas que le document est conforme à toutes les exigences prépresse. Une BleedBox correcte ne prouve pas que du contenu existe effectivement dans toute la zone de fond perdu.

## Parcours principal

1. Déposer le PDF et confirmer les pages recto et verso.
2. Confirmer le format fini et le fond perdu disponible.
3. Choisir la feuille, les marges machine, l’espacement et la quantité.
4. Vérifier la grille, les repères et le schéma recto verso dans l’aperçu.
5. Exporter le PDF et la fiche de réglages pour lancer l’impression à 100 %.

Exemple de scénario pilote : une carte recto verso de 85 × 55 mm à répéter sur une feuille SRA3. L’opérateur confirme les marges de sa presse, contrôle le retournement, exporte une paire de feuilles et réalise une épreuve avant le tirage.

## Suite du produit

Après validation de la répétition : livrets piqués, puis assemblage séquentiel et découpe en piles (« cut and stack »). Les livrets ajoutent notamment l’ordre des pages, les pages blanches, le pliage et la compensation liée à l’épaisseur du papier ; ils méritent un parcours et des tests propres.

L’imposition de plusieurs commandes sur une même feuille, les données variables, l’optimisation de découpes irrégulières, les corrections colorimétriques, la conversion PDF/X, les dossiers surveillés et les intégrations avec les presses restent des extensions ultérieures.

## Validation produit et commerciale

Avant de stabiliser la V1 : observer 3 à 5 professionnels, récupérer avec leur accord 20 à 30 PDF représentatifs, relever les outils employés et chronométrer leur préparation actuelle. Comprendre également pourquoi leurs outils actuels ne suffisent pas.

Objectifs proposés pour le pilote, à ajuster après mesure :

- Au moins 4 utilisateurs sur 5 exportent une première planche sans assistance.
- Temps médian de préparation inférieur à 2 minutes sur les cas simples et réduction d’au moins 50 % par rapport à leur méthode habituelle.
- Aucune erreur d’échelle, d’orientation ou de correspondance recto verso dans le corpus de validation et les épreuves physiques.
- Au moins 3 pilotes réutilisent Snackpress chaque semaine pendant quatre semaines.
- Au moins 2 pilotes acceptent un engagement payant à un prix discuté après usage.

Modèle commercial à tester : abonnement professionnel par utilisateur, avec essai limité. Fixer le prix après les pilotes et le choix du moteur, dont la licence et le coût de traitement peuvent modifier l’économie du produit. La facturation automatisée n’est pas nécessaire pour la première bêta.

## Décision

Feu vert pour la découverte et un prototype d’imposition. Lancement commercial conditionné à la fidélité des exports, aux épreuves physiques et à l’usage récurrent observé. La différenciation proposée repose sur la simplicité du parcours et les modèles métier ; elle reste à valider auprès des professionnels.

## Références techniques

- [callas : moteur d’imposition](https://callassoftware.com/use-cases/impose-pdf-files/) et [intégration OEM](https://oem.callassoftware.com/integration/) : solution spécialisée à évaluer.
- [pikepdf : overlays et placement de pages](https://pikepdf.readthedocs.io/en/stable/topics/overlays.html) : piste technique pour un prototype par objets PDF natifs.
- [Adobe : repères et boîtes PDF](https://helpx.adobe.com/acrobat/using/printer-marks-hairlines-acrobat-pro.html).
- [Adobe : compensation d’épaisseur des livrets](https://helpx.adobe.com/indesign/desktop/print/print-booklets/adjust-creep-settings-in-booklets.html).
