# LD06 Atelier

Application Python locale pour le TP EIGSI de cartographie et localisation lidar.

- Acquisition USB, import CSV LD06 / MapTool et import direct des ZIP de CSV.
- Nuages multiscans en couleurs et poses indépendantes.
- Grille d'occupation, segments et carte vectorielle.
- Superposition automatique entre deux scans par ICP, aperçu avant/après et application de la pose.
- Mesures originales conservées et exports reproductibles.

## Démarrer

Python 3.10 ou plus récent. Sous Windows : `installer_windows.bat`, puis
`lancer_windows.bat`. Le guide complet est dans [LISEZ_MOI.md](LISEZ_MOI.md).

## Jour 2

L'onglet **Localisation** propose **Recherche large + ICP** (±1 m / ±30° par
défaut, réglables) et **ICP local** pour recaler un mobile sur un scan fixe. Les filtres communs sont utilisés. Vérifier l'aperçu avant
d'appliquer la pose, puis enregistrer la session. Guide, méthode et limites dans
[LOCALISATION_JOUR2.md](LOCALISATION_JOUR2.md). L'évaluation reproductible
`python evaluer_localisation.py` exporte les erreurs vraies et les temps.
La localisation sur grille et carte vectorielle reste à développer.

## Repère robot depuis v0.2.0

Pour les nouveaux imports/USB, **l'ancien 270° devient 0°** :
`angle_local = angle_mesure - 270°`. La pose du robot reste un réglage séparé.
Cette référence est fixe, sans champ supplémentaire dans l'interface. Elle
s'applique aussi aux scans réels des anciennes sessions ; les mesures restent
intactes et les cartes doivent être recalculées. Les simulations gardent leur
repère de démonstration.

## Suivi du projet

- [JOURNAL_PROJET.md](JOURNAL_PROJET.md) : contexte, décisions, observations et tâches.
- [GUIDE_GITHUB.md](GUIDE_GITHUB.md) : envoyer le dépôt et travailler avec GitHub.

## Tests

```bash
python -m unittest discover -s tests -v
```

Limite connue prioritaire : un bloc proche de 720° peut encore être accepté comme
un seul scan. La correction nécessite de vérifier les frontières de tours dans
les mesures réelles. Les captures d'écran ne suffisent pas à localiser sa cause.


## Masquer un scan

Dans « Mes scans », cliquer sur la case de la colonne **Visible** pour masquer
ou réafficher un scan dans l'onglet Nuages, avec ses points et sa flèche de pose.
La colonne **Carte** choisit indépendamment les scans utilisés pour les calculs
de cartographie. La visibilité est sauvegardée dans la session JSON.


## Déplacer et tourner un scan à la souris

Dans Nuages : sélectionner un scan visible dans la liste, désactiver Pan/Zoom,
puis choisir **Déplacer le scan** ou **Tourner le scan**. Maintenir le clic
gauche et glisser dans le graphique. La rotation pivote autour du lidar.
Les coordonnées sont actualisées ; Échap annule le geste avant validation.
Recalculer ensuite les cartes et enregistrer la session.

Le diagnostic du scan sélectionné signale les tours multiples et les grandes
lacunes. Les blocs de plusieurs tours sont conservés ; leur étendue est indiquée à titre informatif. Un scan de 305 points
couvrant 360° ne prouve pas que toutes les mesures ont été reçues.
Voir [l'analyse des acquisitions et des difficultés](ANALYSE_SCANS_ET_SOURIS.md).


## Rapport et supports du cours

Le premier rapport Word illustré reprend les cinq captures utilisateur.
Le suivi du rapport et la comparaison aux méthodes du cours sont consignés
dans [SUIVI_RAPPORT_ET_COURS.md](SUIVI_RAPPORT_ET_COURS.md).
La grid map est rapprochée de la méthode fournie ; la gestion des anciennes
formes traversées par les nouveaux rayons reste à intégrer à la carte vectorielle.


## Grille conforme au parcours du TP

Dans l'onglet Grille, trois actions sont distinguées :

1. **Créer depuis le scan sélectionné** : repart d'une grille inconnue et intègre
   ce scan dans sa pose actuelle. Cette action remplace la grille affichée.
2. **Ajouter le scan sélectionné à la grille** : met à jour la grille existante
   et étend ses bornes si nécessaire, en conservant les anciennes observations.
   Cette action porte sur la sélection, indépendamment de la case Carte.
3. **Reconstruire depuis les scans cochés Carte** : recalcule tout depuis les
   poses actuelles des scans inclus, sans cumuler avec la grille précédente.

Avant chaque intégration : diagnostic angulaire informatif et filtrage distance/
intensité. Les cellules traversées avant l'impact reçoivent une preuve libre
(log-odds -0,4) ; la cellule d'impact reçoit une preuve occupée (+0,85).
Une même cellule ne reçoit qu'une preuve par scan, l'impact étant prioritaire.
Les preuves sont bornées à [-4,+4]. Le masque observe conserve la différence
entre une cellule jamais vue et une cellule observée de probabilité neutre.

Un double clic sur Ajouter ne recompte pas le même objet scan. Le noyau de
calcul autorise des observations répétées pour les expériences probabilistes ;
la protection contre le double compte se situe dans l'interface. Importer
plusieurs fois un même fichier crée en revanche des scans distincts.

Importer ou acquérir un nouveau scan conserve la grille. Le déplacement d'un
scan qui n'a pas encore été intégré conserve aussi la grille. Modifier la pose
d'un scan déjà intégré l'invalide : il faut reconstruire, car ses anciennes
preuves ne peuvent pas être simplement déplacées. Les changements de filtres
ou de résolution nécessitent également une reconstruction. Changer les cases
Carte ou supprimer un scan invalide actuellement les cartes.

La résolution reste fixe pendant l'agrandissement ; les cellules ajoutées sont
inconnues. La limite de quatre millions de cellules protège la mémoire.
L'export NPZ conserve l'origine, la résolution, les log-odds, les probabilités
et le masque observé. Les sessions JSON conservent les scans et leurs poses,
pas la grille calculée : la reconstruire après réouverture.

Alignement utilisé : poses manuelles, sans scan matching automatique.
Le vieillissement temporel et le lissage spatial décrits comme extensions dans
le cours restent à développer ; ils ne sont pas nécessaires au parcours de base.


## Décision actuelle sur les blocs de plusieurs tours

Les acquisitions de 766 et 545 points sont conservées et peuvent être cochées
dans Carte. Le nombre de points et une étendue supérieure à un tour ne bloquent
plus la grille ni les captures USB. Une information signale l'étendue, sans
demander de confirmation. La pose choisie s'applique à l'ensemble du bloc :
elle suppose le lidar immobile pendant ses mesures. Les points invalides ou
hors filtres restent exclus ; les données originales ne sont pas modifiées.
Une cellule reçoit au plus une preuve par bloc, même si plusieurs tours la
mesurent. Cette décision remplace les anciennes recommandations d'exclusion.


## Segments de tous les scans et carte vectorielle

Dans Segments, cliquer sur **Extraire les segments des scans cochés Carte**.
L'extraction utilise chaque pose indépendamment, y compris pour un scan masqué
mais coché Carte. Sélectionner un scan dans la liste ne limite plus l'extraction.
Le bouton **Rétablir des seuils prudents** permet de repartir d'un réglage
explicite sans réécrire les paramètres des anciennes sessions.

La carte vectorielle fusionne sur les points d'origine avec contrôle de l'erreur
de droite, puis traite prudemment les anciennes formes traversées par au moins
trois nouveaux rayons de directions distinctes. Voir les méthodes, limites
et trois essais dans [SEGMENTS_MULTISCANS_ET_VECTORIELLE.md](SEGMENTS_MULTISCANS_ET_VECTORIELLE.md).


## Import MapTool du professeur

Le bouton **Importer des CSV ou un ZIP** accepte les exports
`angle_deg,r_m,x_rel_m,y_rel_m`, avec pose optionnelle
`# Robot position: x=...m, y=...m, theta=...deg`. Distances en mètres,
repère de simulation neutre (aucun décalage LD06 de 270°). Les poses fournies
sont chargées et conservées séparément dans `pose_connue` pour l’évaluation ;
ICP ne lit jamais cette métadonnée. Sans commentaire de pose, le départ est zéro.
Pour évaluer un recalage, perturber volontairement la pose de départ : une
superposition grâce à l’en-tête n’est pas un résultat de localisation.

MapTool ne fournit pas d’intensité : le filtre d’intensité est ignoré pour ces
scans et l’information est affichée. Les filtres de distance restent actifs.
Les acquisitions LD06 continuent à utiliser leur intensité et la référence 270°.
Les sessions conservent ces distinctions et l’export d’un scan MapTool conserve
le format sans intensité. La pose exportée est la pose actuelle du scan ;
la pose de référence d’origine est conservée séparément dans la session JSON.

Validation de l’archive ScanJules fournie : 15 scans de 450 points, 6750 points
au total, bornes globales proches de [0,2] × [0,3] m à l’arrondi près. Les
coordonnées relatives sont vérifiées puis recalculées depuis angle et portée.
82 tests passent, dont ZIP, pose non nulle, intensité absente et sessions.
