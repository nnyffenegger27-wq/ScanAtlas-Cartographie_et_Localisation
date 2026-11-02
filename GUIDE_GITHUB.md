# Versionner LD06 Atelier avec Git et GitHub

## Ce qui est déjà prêt

Le dossier contient un dépôt Git local et son dossier `.git` avec deux versions :

- `v0.1.0` : application Python initiale.
- `v0.2.0` : ancien 90° comme nouveau zéro, référence séparée de la pose,
  compatibilité des anciennes sessions et documentation du projet.

Les commits de préparation sont attribués à Codex, pas à toi. Configure ton identité
pour les prochains commits. Le dépôt n'est pas encore envoyé sur GitHub.

**Git** garde l'historique sur ton PC. **GitHub** en garde une copie distante.
Un commit est un point de sauvegarde du code. Un tag nomme une version précise.

## 1 Installer Git et ouvrir le bon dossier

Installe Git depuis https://git-scm.com/downloads si nécessaire. Décompresse
entièrement le ZIP dans un nouveau dossier. Conserve le dossier `.git` inclus.
Ouvre le dossier `LD06_Atelier` dans VS Code puis Terminal > Nouveau terminal.
Toutes les commandes ci-dessous s'exécutent dans ce dossier, à côté de `app.py`.

```bash
git --version
git status
git log --oneline --decorate
git tag
```

Si Git signale « not a git repository », vérifie que tu es bien dans le dossier
qui contient `.git`. Ne remplace pas ton ancienne installation sans avoir
sauvegardé tes sessions et tes CSV.

## 2 Choisir ton identité pour ce projet

Remplace les deux valeurs par ton nom et une adresse associée à ton compte GitHub
(ou l'adresse noreply indiquée dans les paramètres de ton compte).

```bash
git config user.name "Ton nom"
git config user.email "TON_ADRESSE_ASSOCIEE_A_GITHUB"
```

Ces réglages sont locaux au projet. Ils n'authentifient pas une connexion GitHub.

## 3 Créer un dépôt GitHub vide

Sur https://github.com/new, crée un dépôt nommé par exemple `ld06-atelier`.
Un dépôt privé convient pour commencer. Laisse décochées les options d'ajout d'un
README, d'un .gitignore et d'une licence : ces fichiers/historique locaux existent
déjà et le dépôt distant doit être vide pour ce premier envoi.

Copie ensuite l'URL HTTPS affichée par GitHub. Dans les commandes suivantes,
remplace `URL_HTTPS_DE_TON_DEPOT` par cette URL, sans y ajouter de mot de passe.

```bash
git remote add origin URL_HTTPS_DE_TON_DEPOT
git remote -v
git push -u origin main
git push origin --tags
```

La connexion demandée par Git/GitHub se fait sur ton PC ; ne colle pas de secret
dans le code ou dans une conversation. Si `origin` existe déjà, vérifie `git remote -v`
avant toute modification. Si le dépôt distant contient déjà des fichiers,
n'utilise pas `--force` : il faut traiter les deux historiques proprement.

Actualise ensuite GitHub : vérifie la branche main, les commits et les deux tags.

## 4 Sauvegarder chaque amélioration

Exemple après une modification de l'acquisition :

```bash
git status
git diff
python -m unittest discover -s tests -v
git add acquisition.py tests JOURNAL_PROJET.md
git commit -m "Corriger la séparation des tours lidar"
git push
```

Ajoute seulement les fichiers que tu as réellement modifiés. Un commit doit
correspondre à un changement clair. Mets le journal à jour en même temps.

Quand une prochaine version est validée, tu peux lui donner un tag :

```bash
git tag -a v0.3.0 -m "Séparation fiable des tours lidar"
git push origin v0.3.0
```

C'est un exemple futur : ne crée pas ce tag tant que la correction n'est pas faite.

## 5 Conserver tes acquisitions

Utilise ces dossiers pour tes fichiers de travail :

```text
donnees_reelles/   CSV bruts de la salle
sessions/         sessions JSON avec poses et référence angulaire
exports/          cartes, images et autres exports
```

Ils sont exclus de Git par `.gitignore`, ainsi que `.venv`, les caches et les
fichiers temporaires. Sauvegarde ces données séparément : Git ne protège pas les
fichiers qu'il ignore. Les exemples simulés fournis restent versionnés.
Ne déplace pas un fichier déjà suivi dans un dossier ignoré sans vérifier l'état Git.

## Commandes utiles sans risque pour le travail

```bash
git status                         # fichiers modifiés
git diff                           # changements non enregistrés
git log --oneline --decorate        # historique
git show v0.1.0:acquisition.py       # lire l'ancienne acquisition sans changer le dossier
```

Référence officielle :
https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github
