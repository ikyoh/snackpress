# Snackpress — plan de réalisation

Statut initial : proposition du 14 octobre 2026.

Avancement au 15 octobre 2026 : premier prototype local implémenté (import, géométrie, aperçu, export natif, modèles locaux, purge et tests). Voir README.md pour le lancement et les limites. La validation sur corpus professionnel, les épreuves physiques et la bêta multiutilisateur restent à réaliser.

## Hypothèses et estimation

Prévoir 8 à 10 semaines pour une bêta de l’imposition répétitive, avec un développeur expérimenté à temps plein et des professionnels disponibles chaque semaine. Estimation de planification, à revoir après le prototype du moteur. L’ajout des livrets ou du préflight complet change ce périmètre.

Support proposé pour la bêta : application web pour valider rapidement le parcours. Importer un PDF vers un serveur impose un consentement clair sur son traitement et une suppression automatique. Si les pilotes exigent un fonctionnement entièrement hors ligne, prendre cette décision dès la découverte et réestimer une application locale.

## Étapes et critères de sortie

| Étape | Durée indicative | Livrable et critère de sortie |
|---|---|---|
| 1. Observer les usages | Semaine 1 | 3 à 5 entretiens, corpus de fichiers, contraintes de presses, parcours retenu et mesures du temps actuel. |
| 2. Valider le moteur | Semaine 2 | Génération de planches recto/verso ; comparaison des ressources PDF et épreuves imprimées ; choix du moteur et vérification des conditions de licence et d’intégration. |
| 3. Construire le cœur | Semaines 3–4 | Modèle géométrique, répétition, rotations, marges, espaces, repères, quantité et export ; cas de référence vérifiés. |
| 4. Construire l’interface | Semaines 5–6 | Import, paramètres en mm, aperçu des deux faces, schéma de retournement, erreurs compréhensibles, modèles enregistrés et fiche de réglages. |
| 5. Fiabiliser | Semaine 7 | Corpus complet, limites de fichiers, isolation des traitements, suppression des fichiers et épreuves physiques sur les presses pilotes. |
| 6. Piloter et ajuster | Semaines 8–10 | Bêta utilisée sur des travaux réels ; corrections ; mesures de temps, de réutilisation et d’intérêt commercial ; décision de lancement. |

Ne pas poursuivre avec un moteur dont la fidélité reste incertaine : réduire les fichiers pris en charge ou tester un SDK spécialisé, puis revoir calendrier et coûts.

## Architecture proposée

La proposition détaillée des technologies, de leurs responsabilités et de leur évolution est décrite dans [STACK.md](STACK.md). Le moteur PDF reste conditionné aux résultats du prototype.

- Interface TypeScript/React, avec lecteur PDF pour l’aperçu. Choisir et figer les versions au démarrage de l’implémentation.
- Service de traitement PDF séparé de l’interface. Piste pour le prototype : Python et pikepdf pour importer les pages comme objets PDF natifs, calculer les transformations et produire les planches. Comparer avec callas si le corpus révèle des difficultés ou si une garantie prépresse plus large devient indispensable.
- Contrat d’imposition unique : format feuille, zone imprimable, format fini, zone source, rotations, grille, fond perdu, repères, quantité et convention de retournement. Ce contrat alimente l’export et l’aperçu pour limiter les divergences.
- Travaux de traitement exécutés dans un processus isolé, avec plafonds de taille, de temps et de mémoire. Ajouter une file de travaux seulement si les mesures le justifient.
- Modèles stockés localement au début ; stockage temporaire des PDF et résultats, suppression après téléchargement ou au plus tard sous 24 heures. L’expiration doit être mise en œuvre et vérifiée avant l’ouverture de la bêta.

Un aperçu d’écran sert à contrôler la disposition ; il ne constitue pas une épreuve couleur contractuelle. L’export doit conserver les objets PDF sans rasterisation générale ni conversion couleur implicite.

## Contrat de qualité PDF

Le prototype doit vérifier ce qui survit à l’importation et à la composition : polices intégrées, images, espaces CMJN, tons directs, transparences, surimpressions et informations colorimétriques pertinentes. L’import de pages comme objets natifs ne suffit pas à prouver cette conservation.

Traiter explicitement les rotations de page, origines de coordonnées non nulles, unités PDF inhabituelles, dimensions incohérentes entre recto et verso et absence de TrimBox. Les éléments interactifs, annotations et fichiers signés doivent être refusés ou faire l’objet d’un comportement documenté ; aucune transformation silencieuse.

Ne pas annoncer la conformité PDF/X sans validation du document exporté par un outil approprié. Le changement de structure du document peut affecter ses métadonnées et sa conformité même lorsque les éléments graphiques restent identiques.

## Vérifications nécessaires

1. Géométrie : résultats connus pour cartes, flyers et étiquettes ; orientation, centrage, absence de chevauchement et de débordement ; cas où aucune pose ne tient.
2. Quantité : arrondi au nombre de feuilles, nombre de copies produites et consigne de répétition du PDF exporté cohérents.
3. Recto verso : fichiers asymétriques comportant des numéros dans les coins, test des deux conventions de retournement, vérification sur une presse réelle à 100 %.
4. Fidélité : inspection des ressources, comparaison visuelle des zones utiles et contrôle externe des couleurs, transparences et surimpressions sur le corpus. Aucune tolérance pour une erreur d’échelle ou de correspondance des faces ; fixer les tolérances physiques de repérage avec les pilotes.
5. Parcours : un utilisateur importe, configure, contrôle et exporte sans aide ; les erreurs proposent une action concrète.
6. Exploitation : fichiers protégés, corrompus et hors limites ; échec de traitement récupérable ; suppression effectivement vérifiée ; aucun contenu client dans les journaux.

## Décisions à prendre au premier jalon

- Confirmer que les premiers pilotes travaillent surtout sur cartes, flyers et étiquettes plutôt que sur livrets.
- Choisir web ou local selon leurs contraintes de confidentialité et de connexion.
- Définir les limites de poids et de complexité à partir du corpus et des mesures.
- Choisir le moteur après comparaison des exports, du coût et des conditions de licence.
- Confirmer le temps de développement disponible et recalibrer l’estimation.

## Première action concrète

Trouver trois imprimeurs pilotes et réunir dix travaux récents avec leurs réglages de presse et leurs PDF. Livrer ensuite un prototype qui impose une carte recto verso sur SRA3 et imprimer une épreuve. Ce jalon teste simultanément le besoin, la géométrie, le retournement et la fidélité du moteur.

## Sources

- [pikepdf — placement de pages et objets PDF](https://pikepdf.readthedocs.io/en/stable/topics/overlays.html).
- [callas — intégration du moteur](https://oem.callassoftware.com/integration/).
- [Adobe — repères et boîtes de page](https://helpx.adobe.com/acrobat/using/printer-marks-hairlines-acrobat-pro.html).

## Extension demandée le 15 octobre 2026

Les 14 outils du tableau utilisateur sont implémentés dans le prototype local, avec catalogue, paramètres, fichiers produits, aperçu et limites déclarées. Les outils ne sont plus limités à la seule imposition répétitive ; lire TOOLS.md pour leurs contrats et README.md pour le lancement. Cette extension n’équivaut pas à une validation du corpus professionnel ni à une bêta publique.
