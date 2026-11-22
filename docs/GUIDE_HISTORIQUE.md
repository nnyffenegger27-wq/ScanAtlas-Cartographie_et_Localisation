# Consulter l’historique Git du rendu

Le dépôt GitHub est privé. Son lien reste dans le README, mais il nécessite un accès autorisé. Le ZIP du rendu contient donc aussi un dossier `historique_git/` avec une copie portable de l’historique (`ScanAtlas_historique.bundle`). Ce fichier est propre à l’archive de livraison ; il n’est pas une dépendance de l’application.

Avec Git installé, depuis le dossier `ScanAtlas/` extrait du ZIP :

```
git clone historique_git/ScanAtlas_historique.bundle ScanAtlas_historique
git -C ScanAtlas_historique log --all --date=iso --oneline
git -C ScanAtlas_historique log origin/jours-1-2 --date=iso
```

Les quatre branches utiles sont conservées : `main`, `jours-1-2`, `version-2-refonte-tkinter` et `version-3-tkinter-avancee`. Le bundle se lit hors ligne et ne contient pas les réglages d’accès GitHub ni les sauvegardes de travail personnelles.

Le dossier principal du ZIP est la version du rendu, avec les corrections documentaires et le nouveau classement des cartes. Le bundle sert à consulter les commits enregistrés pendant le développement ; les dernières corrections locales du rendu ne constituent pas de nouveaux commits dans cet historique.
