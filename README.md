# LD06 Atelier

Application Python locale pour le TP EIGSI de cartographie et localisation lidar.

- Acquisition USB, import CSV LD06 / MapTool et import direct des ZIP de CSV.
- Nuages multiscans en couleurs et poses indépendantes.
- Grille d'occupation, segments et carte vectorielle.
- Superposition automatique entre deux scans par ICP, aperçu avant/après et application de la pose.
- Mesures originales conservées et exports reproductibles.
- Pilotage clavier en Wi-Fi via hotspot ESP32, scans continus et carte vectorielle incrémentale.

## Démarrer

Python 3.10 ou plus récent. Sous Windows : `installer_windows.bat`, puis
`lancer_windows.bat`. Le guide complet est dans [LISEZ_MOI.md](LISEZ_MOI.md).

## Jour 2

L'onglet **Localisation** propose **Recherche large + ICP** (±1 m / ±30° par
défaut, réglables) et **ICP local** pour recaler un mobile sur un scan fixe. Les filtres communs sont utilisés. Vérifier l'aperçu avant
d'appliquer la pose, puis enregistrer la session. Guide, méthode et limites dans
[LOCALISATION_JOUR2.md](LOCALISATION_JOUR2.md). L'évaluation reproductible
`python evaluer_localisation.py` exporte les erreurs vraies et les temps.
L'onglet **TP Localisation** ajoute aussi les références grille et carte
vectorielle ; résultats dans [TP_JOUR2_RESULTATS.md](TP_JOUR2_RESULTATS.md).

## Repère lidar actuel

Le dernier choix utilisateur dans le dépôt fixe `ANGLE_REFERENCE_DEFAUT = 0°`.
`angle_local = angle_mesure - ANGLE_REFERENCE_DEFAUT`. La pose reste séparée.
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
repère de simulation neutre (aucune correction propre au LD06). Les poses fournies
sont chargées et conservées séparément dans `pose_connue` pour l’évaluation ;
ICP ne lit jamais cette métadonnée. Sans commentaire de pose, le départ est zéro.
Pour évaluer un recalage, perturber volontairement la pose de départ : une
superposition grâce à l’en-tête n’est pas un résultat de localisation.

MapTool ne fournit pas d’intensité : le filtre d’intensité est ignoré pour ces
scans et l’information est affichée. Les filtres de distance restent actifs.
Les acquisitions LD06 utilisent leur intensité et la référence fixe configurée dans le code (actuellement 0°).
Les sessions conservent ces distinctions et l’export d’un scan MapTool conserve
le format sans intensité. La pose exportée est la pose actuelle du scan ;
la pose de référence d’origine est conservée séparément dans la session JSON.

Validation de l’archive ScanJules fournie : 15 scans de 450 points, 6750 points
au total, bornes globales proches de [0,2] × [0,3] m à l’arrondi près. Les
coordonnées relatives sont vérifiées puis recalculées depuis angle et portée.
82 tests passent, dont ZIP, pose non nulle, intensité absente et sessions.


## Recalage automatique après acquisition USB

Dans **Acquisition USB**, cocher **Recaler automatiquement chaque nouveau scan
sur le précédent (ICP)**, puis Capturer. Option désactivée initialement. La
méthode, les fenêtres et la distance d’appariement viennent de Localisation ;
les filtres communs sont utilisés sans les modifier. Le dernier scan de la
liste est la référence, même s’il est masqué ou décoché Carte. Aucun scan chargé :
le premier scan reçu ancre le repère à sa pose (zéro pour une nouvelle capture).
Le départ du suivant est la pose de son prédécesseur, pas zéro.

La série est d’abord lue et le port fermé, puis le lot est recalé dans le thread
pour ne pas bloquer la réception série par ICP. Dans un lot de plusieurs scans,
chaque scan accepté devient la référence du suivant. En pratique, capturer un
scan à chaque arrêt du robot, puis le déplacer avant la capture suivante.
Les poses acceptées sont appliquées automatiquement, sans le bouton Appliquer.

Acceptation automatique : **exactement les mêmes critères que le bouton
Localiser**, sans seuil supplémentaire de 60 % ou 0,10 m. Le solveur exige
notamment convergence et correspondances suffisantes. Ces critères ne
garantissent pas une pose vraie correcte.
Sur échec, exception ou annulation du recalage, les données sont conservées ;
la pose du scan concerné n’est pas remplacée, la chaîne est interrompue et les
scans non recalés sont décochés Carte. Ils restent visibles, avec le motif dans
leur fiche. Corriger manuellement ou dans Localisation, puis recocher Carte.
Le dernier scan non validé bloque le démarrage d’un nouvel auto-recalage jusqu’à
correction explicite de sa pose.

Si référence ou filtres changent pendant la capture, les poses calculées sont
écartées et les nouveaux scans sont conservés à zéro, décochés Carte. L’option
et les bilans par scan sont sauvegardés dans les sessions. Il ne s’agit pas
encore d’un SLAM avec fermeture de boucle ; les erreurs successives peuvent
s’accumuler. Les cartes se construisent avec leurs boutons habituels.


### Résultat visible après capture

Un état indique la référence choisie dès le lancement, puis « Capture terminée,
localisation automatique en cours ». Si le calcul est accepté, la pose du nouveau
scan est appliquée, le dernier scan est sélectionné et l’onglet Nuages affiche
la superposition. Si le calcul échoue, une fenêtre **Échec de localisation
automatique** donne le motif ; le scan reste disponible pour correction.
Le premier scan d’une session vide affiche explicitement qu’il devient la
référence et qu’aucune localisation n’est à effectuer. Les exceptions du module
de recalage conservent également les scans déjà reçus.

### Recalage fiable et lots de scans

Localisation propose **Superposer le lot coché Carte**, dans l’ordre d’acquisition : première pose fixe, sous-carte des cinq derniers scans acceptés, poses refusées signalées, restauration possible du dernier lot. Acquisition USB utilise également une sous-carte des dernières références acceptées. Recherche large vérifie l’accord fin, la géométrie et les solutions concurrentes avant application. Lire [FIABILITE_LOCALISATION.md](FIABILITE_LOCALISATION.md) pour les critères, les limites et les évaluations chiffrées (simulation et MapTool, sans nouvelle validation matérielle).

### Mode global 360° et groupes en attente — version actuelle

Le mode par défaut est maintenant **Carte cumulée · recherche globale 360°** : premier scan fixe, recherche sur toute la carte connue, aucune fenêtre obligatoire de déplacement ou d’orientation. Dans Localisation, **Assembler tous les scans** recale la collection et garde les groupes non raccordés séparément. Acquisition USB utilise la même carte cumulée et peut reprendre après un scan refusé. La concordance est affichée avec le motif de refus éventuel. Lire [LOCALISATION_GLOBALE.md](LOCALISATION_GLOBALE.md) pour le fonctionnement, les tests et les limites. Les sections antérieures décrivent les étapes précédentes.

### Pilotage Wi-Fi et cartographie pendant le déplacement

L'onglet **Robot Wi-Fi** et le firmware `firmware/ScanAtlas_WiFi` implémentent
maintenant le hotspot **ScanAtlas** (mot de passe **ScanAtlas2026**, adresse
**192.168.4.1**), les commandes clavier et la carte vectorielle incrémentale.
Guide de flash, connexion, tests et limites : [PILOTAGE_WIFI.md](PILOTAGE_WIFI.md).
Le firmware a été compilé pour ESP32 classique, core Arduino **2.0.17**.
Les essais matériels restent à réaliser ; pas encore de navigation autonome.
Pour essayer sans matériel : `python simuler_robot_wifi.py`, puis adresse
`127.0.0.1` dans Robot Wi-Fi. Les dossiers moteur et lidar d'origine sont conservés.
L'étude [ARCHITECTURE_TEMPS_REEL_WIFI.md](ARCHITECTURE_TEMPS_REEL_WIFI.md)
reste la référence pour les étapes suivantes, notamment odométrie,
relocalisation globale en arrière-plan et autonomie.

### TP Jour 2 — les trois références et leur évaluation

Un nouvel onglet **TP Localisation** propose la grille d’occupation, la carte vectorielle et un scan de référence. Deux stratégies par type : affinement local robuste, ou multi-résolution puis affinement. La carte doit être construite sans le scan mobile ; l’application contrôle cette exclusion. Le bouton d’évaluation exporte 42 essais simulés sur les mêmes scans et les mêmes poses initiales, avec erreurs vraies, temps, taux de réussite et faux acceptés. Lire [TP_JOUR2_RESULTATS.md](TP_JOUR2_RESULTATS.md).

**Après mise à jour, relancer installer_windows.bat** pour installer SciPy, puis redémarrer l’application. Les nouvelles méthodes TP supposent une pose approchée ; le mode global 360° reste disponible séparément. Les essais réels avec incertitudes mesurées restent à réaliser.
