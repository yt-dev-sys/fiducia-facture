# Fiducia Facture

Application de bureau Windows de gestion de clients, services, factures et paiements.

## Installation

La version destinée à l'utilisateur final est autonome : Python, CustomTkinter, ReportLab et les autres dépendances Python sont inclus dans l'application construite avec PyInstaller. L'utilisateur final n'a pas besoin d'installer Python, pip, Git ou un terminal.

L'application est destinée à Windows 10/11 64 bits.

Les fichiers de l'application sont installés sous `Program Files`, tandis que les données métier restent dans :

`Documents\\Fiducia Facture\\`

Les journaux, l'état technique, le token Telegram et les téléchargements temporaires sont stockés sous `%LOCALAPPDATA%\\FiduciaFacture\\`.

## Sauvegardes Telegram

Google Drive a été retiré. Fiducia Facture utilise un bot Telegram pour conserver une copie hors machine.

Le token du bot est volontairement absent du dépôt et vide par défaut. Au premier lancement, l'application crée :

`%LOCALAPPDATA%\\FiduciaFacture\\config\\telegram_bot_token.txt`

Ajoutez votre token BotFather sur une seule ligne dans ce fichier. Le fichier est en dehors de `Program Files` et n'est donc pas remplacé par les mises à jour.

Pour associer le bot au compte de votre père :

1. Ouvrez le bot dans Telegram avec le compte de votre père.
2. Envoyez `/start`.
3. Dans Fiducia Facture, ouvrez le profil de l'entreprise et cliquez sur **Connecter Telegram** (facultatif si la connexion automatique au démarrage détecte déjà le /start).

Chaque sauvegarde crée un snapshot SQLite sûr, puis une archive ZIP avec la base et les métadonnées. L'archive est envoyée à Telegram et supprimée du dossier temporaire local après succès. Les sauvegardes locales quotidiennes sont conservées selon la politique de rétention de l'application.

Une panne Internet ou Telegram ne bloque pas l'application : la sauvegarde locale continue et l'envoi Telegram est retenté lors d'un prochain démarrage.

**Ne commitez jamais le token du bot dans GitHub.**

## Mises à jour

L'application ne nécessite pas Git. Elle interroge les GitHub Releases via HTTPS. Une vérification automatique est faite au maximum une fois par 24 heures, avec une vérification manuelle disponible dans l'application.

Lorsqu'une nouvelle version stable est publiée, l'application :

1. détecte la release ;
2. propose la mise à jour ;
3. télécharge l'installateur dans `%LOCALAPPDATA%\\FiduciaFacture\\update\\` ;
4. vérifie le SHA-256 lorsqu'il est publié avec la release ;
5. lance l'installateur ;
6. se ferme ;
7. Inno Setup remplace les fichiers de l'application ;
8. les données utilisateur et la configuration Telegram restent en place.

## Build via GitHub Actions

Le dépôt utilise GitHub Actions et un runner Windows hébergé par GitHub. Le workflow installe Python, les dépendances, PyInstaller et Inno Setup sur la machine de build, puis produit l'installateur Windows. GitHub documente les runners Windows hébergés et le fonctionnement des workflows. 

### Build de test

Dans GitHub : **Actions → Build Windows installer → Run workflow**.

Le workflow publie un artefact téléchargeable nommé selon la branche ou le tag.

### Release officielle

La version est définie dans `app/version.py`. Pour publier une version, mettez à jour `APP_VERSION`, poussez les changements, puis créez un tag correspondant, par exemple :

```text
v1.0.0
```

Le workflow construit alors l'installateur et publie automatiquement l'EXE et son fichier `.sha256` dans la GitHub Release.

## Structure utilisateur

```text
Documents\\Fiducia Facture\\
├── facture_app.db
├── backups\\
└── exports\\

%LOCALAPPDATA%\\FiduciaFacture\\
├── config\\
│   ├── telegram_bot_token.txt
│   └── telegram_chat_id.txt
├── logs\\
├── update\\
├── cache\\
└── state\\
```
