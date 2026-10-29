# Site Dourous Abou Sirine

Le site est généré à partir des dossiers de MP3 de votre FTP : un dossier correspond à une rubrique
ou une série, et un nom de fichier correspond au titre de l'audio. Aucun logiciel à installer :
il suffit de Python 3, déjà présent sur votre machine.

## Première fois

1. Ouvrez `config.ini` et remplissez la partie `[ftp]` (hôte, identifiant, mot de passe :
   espace client OVH > Hébergements > FTP - SSH).
2. Vérifiez la connexion et les dossiers :

       python3 outil.py verifier

## Publier un nouvel audio

1. Déposez le MP3 dans le bon dossier du FTP, comme d'habitude.
   Pour qu'il soit bien classé, nommez-le comme les autres, par exemple
   `Tafsir - Fatiha - 31 - Titre du cours.mp3` (le numéro sert à l'ordre des épisodes).
2. Lancez :

       python3 outil.py publier

   L'outil relit le FTP, reconstruit le site et envoie uniquement ce qui a changé.

## Voir le site sur votre ordinateur

    python3 outil.py apercu

puis ouvrez http://localhost:8000.

## Réglages d'affichage (`affichage.json`)

- `renommer` : nom affiché d'un dossier (ex. « Fiqh » au lieu de « Fiqh - Jurisprudence »).
- `fusionner` : dossiers dont les audios sont rangés dans le dossier parent.
- `masquer` : dossiers à ne pas afficher.
- `ordre` : ordre des rubriques.
- `descriptions` : petit texte sous le titre d'une rubrique.

## Mise en ligne

Par défaut, le site est envoyé dans `www/nouveau` (adresse `/nouveau/`) pour le tester sans
toucher au site actuel. Le remplacement du site Joomla se fera dans un second temps.
