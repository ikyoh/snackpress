# Feuille de style — Gestion des remontées

Le fichier `realisaprint-remontees.css` cible les classes et identifiants de la page fournie : navigation, filtres, export, traitements, quatre blocs et tableaux. Il conserve les couleurs de statut et les éléments masqués utilisés par l’application.

## Installer sur la page réelle

Copier le CSS à côté du HTML ou dans le dossier des styles, puis ajouter cette ligne **en dernier dans `<head>`**, après les feuilles de style existantes :

```html
<link rel="stylesheet" href="realisaprint-remontees.css">
```

Adapter le chemin si le CSS se trouve dans un autre dossier. Aucun changement des classes ni des identifiants de la page n’est nécessaire. Les variables `--rp-*` en début de fichier permettent de modifier les couleurs et les arrondis.

Le style utilise `:has()`, pris en charge par les navigateurs récents (Chrome/Edge 105+, Safari 15.4+, Firefox 121+). Les scripts, Bootstrap, les icônes et les ressources d’origine restent nécessaires aux fonctionnalités de l’extranet.

## Voir le résultat hors ligne

Ouvrir `apercu.html` en conservant le CSS dans le même dossier. Cet aperçu reprend le contenu du fichier fourni ; il contient donc ses données métier. Il ne charge aucune ressource externe. Ses formulaires et ses actions serveur sont désactivés. Quelques icônes SVG et une base de navigation sont incluses uniquement pour rendre l’aperçu lisible sans les ressources de l’extranet.

Le fichier fourni est une sauvegarde de l’affichage « code source » du navigateur, avec des balises `span` et des caractères échappés. Son HTML utile a été extrait pour l’aperçu. Ajouter simplement le CSS à cette sauvegarde afficherait toujours le code source : pour l’installation, utiliser le véritable HTML de la page.

Sur petit écran, les filtres passent en deux colonnes puis une seule, et les tableaux conservent toutes leurs colonnes avec défilement horizontal dans chaque panneau. Le fichier source n’a pas été modifié.

## Version confort de lecture

Fond gris chaud, surfaces blanc cassé, texte principal agrandi à 16 px et tableaux à 15 px. Les lignes sont plus espacées ; les en-têtes des panneaux sont neutres et les couleurs de statut restent discrètes. Le focus clavier demeure visible et aucune animation supplémentaire n’est ajoutée. Les contrastes de texte sont conservés pour la lisibilité.
