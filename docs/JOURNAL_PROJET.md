# LD06 Atelier — journal et mémoire du projet

Mise à jour : 2 novembre 2026. Version Python : v0.2.0.

Ce fichier sert de point de reprise du projet. Le mettre à jour après chaque
modification importante et le conserver dans Git. Il fournit un contexte lisible
à une prochaine conversation ; il ne constitue pas une promesse de mémoire
personnelle automatique entre toutes les conversations.

## Objectif et préférences

TP EIGSI Jour 1 : acquérir ses propres scans polaires réels, afficher plusieurs
nuages en couleurs et régler chaque pose, construire et mettre à jour une grille,
extraire et manipuler des segments, construire une carte vectorielle et expliquer
la démarche. L'utilisateur voulait d'abord être guidé, puis a demandé la création
de l'application en gardant le code clair et compréhensible.

Une version web a été construite, avec un rapport Word. Le choix final confirmé
est de poursuivre **l'application Python locale**. Ne pas reprendre le travail
sur le site web par défaut. Les évolutions Python ne modifient pas le site ni la
trame Word déjà livrée, qui reflète une étape précédente.

## Ressources fournies

- ESP32_LD06_Test.zip : sketch Arduino et bibliothèque LD06.
- LD06 Communication Protocol.pdf : manuel LDROBOT v1.0.
- LD06 datasheet.pdf.
- Acquisition des données issues du Lidar LD06.md.
- Quatre captures d'écran des résultats réels Python.
- Les deux documents de cours sur les constructions des cartes ne sont pas fournis.
- Les CSV/JSON de la session réelle à quatre acquisitions ne sont pas encore reçus.

## Ce qui a été réalisé

- Lecture du sketch et de la bibliothèque ; compréhension trame contre scan.
- Confirmation de la réception des données sur ESP32.
- Passage de printScanTeleplot à printScanCSV.
- Explication angle-distance, degrés/radians, sin/cos, indexation NumPy et baud.
- Application Tkinter/Matplotlib avec import CSV et capture USB PySerial.
- Affichage de plusieurs scans, couleurs et poses indépendantes.
- Filtrage des mesures sans modifier les données brutes.
- Grille d'occupation : rayons, cellules libres, impacts et masque inconnu.
- Extraction de segments, angle, proximité, fusion, intersection et découpage.
- Carte vectorielle : extraction globale puis fusion des voisins.
- Exports polaires, session JSON, grille NPZ et segments CSV.
- Guide en français, exemples explicitement simulés et tests automatisés.
- Version web alternative : 29 tests ; elle reste une piste non retenue.
- Trame Word de sept pages avec comparaisons et résultats réels à compléter.
- Git local préparé : baseline v0.1.0 et évolution v0.2.0.
- Nouveau zéro angulaire demandé : ancien 90° devient 0° pour nouveaux scans.

## Convention angulaire actuelle

La dernière précision de l'utilisateur remplace sa première formulation
« orientation par défaut à 90° » : **le nouveau zéro doit être l'ancien 90°**.

On garde les angles polaires originaux et on applique :

```text
angle_local = angle_mesure - angle_reference
angle_reference = 90 degres pour tout nouveau CSV ou scan USB
angle_carte = angle_local + orientation_pose_robot
```

À pose robot (0,0,0) et distance 1 m :

| Angle original | Angle local | x robot | y robot |
|---:|---:|---:|---:|
| 90° | 0° | 1 m | 0 m |
| 0° | -90° | 0 m | -1 m |
| 180° | 90° | 0 m | 1 m |

La référence est désormais **fixe à 90° pour les scans réels**, sans champ
supplémentaire dans l'interface, conformément à la demande du 2 novembre.
Seule l'orientation règle la pose du robot. Les anciennes sessions réelles
adoptent également cette référence lors de leur ouverture ; recalculer les cartes.
Les démonstrations conservent leur repère synthétique à 0°.
Le CSV exporté conserve l'angle original ; utiliser la session JSON pour conserver
la calibration et les poses. Vérifier physiquement la convention sur le robot.

## Résultats réels observés et faits confirmés

- L'utilisateur confirme que les quatre acquisitions ont été faites **sans déplacer
  le lidar**. Ne pas attribuer les écarts à un changement volontaire de pose.
- Les grands murs se superposent visuellement assez bien.
- Les petits groupes centraux diffèrent ; mouvements de personnes possibles,
  mais non confirmés. Ne pas présenter cette hypothèse comme un fait.
- La grille a des zones inconnues et des traces de rayons ; cela peut venir des
  occultations et de la discrétisation, pas forcément d'une mauvaise pose.
- Capture : 984, 456, 982 et 456 points ; les quatre scans portent le nom USB 1.
- Le scan sélectionné affiche 719,4° : presque deux tours dans un même bloc.
- Extraction affichée : 52 segments pour le scan sélectionné ; carte fusionnée :
  43 segments pour l'ensemble. Ces deux nombres ne décrivent pas le même périmètre.

## Anomalie prioritaire encore ouverte

L'acquisition Python rejette une étendue inférieure à 340°, mais ne borne pas
l'étendue supérieure. Un bloc proche de 720° peut donc être accepté à tort comme
un scan unique. L'origine précise doit être recherchée dans la session et dans
la chaîne ESP32/bibliothèque/CSV. Ce problème **n'est pas corrigé en v0.2.0**.
Ne pas supprimer arbitrairement la moitié des points et ne pas seulement augmenter
les seuils de fusion pour masquer les conséquences.

## Choix techniques et solutions à privilégier

| Sujet | Choix retenu ou recommandé | Pourquoi et limites |
|---|---|---|
| Référence robot | Calibration distincte de la pose | Ancien 90° = zéro, sans altérer les mesures |
| Unités | Mètres en interne, degrés dans l'interface | Conversion unique à l'entrée ; radians pour trigonométrie |
| Source polaire | Recalculer x/y depuis angle et distance | Le y du code fourni utilise un signe moins malgré les angles corrigés |
| Acquisition | Indice 0, continuité, fin de bloc, CRC en amont | Ajouter un vrai contrôle du nombre de tours ; CSV seul ne prouve pas l'absence de pertes en amont |
| Grille | Rayons libres + impacts occupés + inconnu séparé | Ne jamais déclarer libres les zones masquées |
| Probabilités | Log-odds -0,4/+0,85, bornées [-4,4] | Poids pédagogiques non calibrés ; une preuve/cellule/scan |
| Mise à jour | Recalcul depuis les scans choisis après changement | Évite de recompter les mêmes scans ou de garder les anciennes poses |
| Extraction | Ruptures, split-and-fit, ajustement orthogonal | Simple et explicable ; sensible au bruit et aux seuils |
| Fusion | Angle non orienté ET distance | L'angle seul confond des murs parallèles éloignés |
| Découpage | Intersection sur A et B et strictement intérieure à A | Colinéaires et extrémités inchangés ; égalité : côté de A[0] |
| Carte vectorielle | Fusion progressive des segments globaux | Heuristique, ordre dépendant ; ne pas couper tous les croisements automatiquement |
| Versionnement | Commits courts et versions identifiées | Conserver les mesures réelles séparément et les réglages reproductibles |

Les réglages 0,20 m rupture, 0,04 m erreur, 8° fusion et 0,12 m distance sont des
points de départ. Les améliorer un par un après contrôle de la séparation des tours.

## Reste à faire par priorité

### P0 — Fiabilité des acquisitions

- [ ] Récupérer la session JSON réelle à quatre acquisitions.
- [ ] Examiner les angles, les retours à zéro et les indices dans les blocs à 720°.
- [ ] Vérifier la bibliothèque ESP32 et ses frontières de tours.
- [ ] Définir puis tester un découpage fiable en scans d'un seul tour.
- [ ] Avertir ou rejeter clairement les blocs partiels ou multiples.
- [ ] Donner un nom unique à chaque acquisition entre plusieurs captures.

### P1 — Repère et qualité des cartes

- [ ] Vérifier sur le robot qu'un obstacle à l'ancien 90° apparaît bien sur +x.
- [ ] Adapter explicitement les anciennes sessions au repère retenu, si souhaité.
- [ ] Vérifier l'absence de mouvement pendant chaque tour et les objets mobiles.
- [ ] Comparer deux résolutions et mesurer le compromis détail/mémoire/temps.
- [ ] Comparer les seuils de segmentation et relever les fragments perdus.
- [ ] Mesurer les effets de la fusion, sans boucher les ouvertures réelles.

### P2 — Rapport et GitHub

- [ ] Lire les deux documents du cours encore manquants.
- [ ] Adapter le rapport à la version Python et au zéro angulaire actuel.
- [ ] Ajouter scans réels, conditions, paramètres et figures aux résultats.
- [ ] Distinguer tests artificiels, observations réelles et hypothèses.
- [ ] Créer ou fournir un dépôt GitHub vide et son URL.
- [ ] Publier main et les tags ; vérifier le dépôt distant.
- [ ] Configurer l'identité Git réelle pour les prochains commits.

### Plus tard seulement

- [ ] Filtrage spatial prudent, pondération des segments par leur support.
- [ ] Durée de vie des cellules si objets mobiles réellement problématiques.
- [ ] Recalage automatique uniquement si plusieurs poses différentes sont acquises.
- [ ] Amélioration visuelle de l'interface sans cacher les paramètres du TP.

## Fichiers et validation

- app.py : interface et sessions v1/v2.
- cartographie.py : géométrie, calibration, grille et segments.
- acquisition.py : capture série CSV.
- LISEZ_MOI.md : guide de fonctionnement ; GUIDE_GITHUB.md : versionnement.
- tests/ : calculs, coordonnées, géométrie et compatibilité des sessions.

Commande : `python -m unittest discover -s tests -v`.
Version v0.2.0 : **24 tests réussis**, dont nouveau zéro 90°, pose séparée et
compatibilité v1. Pas de vérification visuelle Windows ni de nouvel essai matériel
pour cette modification. La version initiale avait 21 tests ; la web 29.
Les commits de préparation sont attribués à Codex (codex@localhost), pas à
l'utilisateur. Aucun dépôt distant GitHub n'est encore configuré ni publié.


## Publication GitHub — 2 novembre 2026

La v0.2.0 est appliquée sur la branche `main` du dépôt
`nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation`, à la suite de
l’import initial existant. La session réelle `session_ld06.json` est conservée.
Les 24 tests locaux passent. Le zéro lidar des nouveaux scans vaut 90° ;
les anciennes sessions gardent leur référence pour préserver leur affichage.
Le problème des acquisitions proches de 720° reste à traiter séparément.


## Simplification après retour utilisateur — 2 novembre 2026

Suppression du champ « Zéro lidar » : le décalage de 90° est automatique et fixe
pour les données réelles, y compris les anciennes sessions. Aucun angle brut
n'est modifié. Prochaines priorités : diagnostiquer les scans à 720°, vérifier
l'acquisition, améliorer les segments, puis documenter les résultats réels.


## Orientation fixe portée à 180° — 2 novembre 2026

Sur demande utilisateur, le décalage fixe de 90° est remplacé par 180° :
`angle_local = angle_mesure - 180°`. L'ancien 180° est donc sur +x lorsque
la pose du robot est nulle. La règle s'applique aux imports, à l'USB et aux
sessions réelles rouvertes. Aucun champ supplémentaire ; angles bruts conservés.
Les paragraphes précédents décrivent l'historique des réglages, cette décision
est la référence actuelle. Les 25 tests locaux passent.


## Correction : ajouter 180° aux 90° initiaux — 2 novembre 2026

La demande était une rotation supplémentaire de 180° par rapport au repère
initial déjà décalé de 90°. La référence fixe correcte est donc 270°,
et non 180° : `angle_local = angle_mesure - 270°`. Un test vérifie que
les points locaux sont les opposés de ceux du réglage initial à 90°.
Cette correction remplace la décision précédente. Les 26 tests passent.


## Visibilité individuelle — 2 novembre 2026

Ajout de la colonne Visible : masquer/réafficher les nuages et leurs poses
indépendamment de la colonne Carte. Aucun scan supprimé, aucune pose modifiée.
État conservé en JSON ; les anciennes sessions reprennent leur affichage initial.
Les cartes calculées restent indépendantes de la visibilité des nuages.


## Acquisitions à plusieurs positions et souris — 2 novembre 2026

Session analysée : « Test plusieur scans pas la meme position.json », 13 blocs.
Onze ont 304–306 points et 357,79–359,78° d'étendue. Les blocs 11 et 13
ont respectivement 766 points/1079,54° et 545 points/643,04° : plusieurs tours
ou bloc partiel multiple, et non un scan unique.

Ajouts : modes souris Déplacer/Tourner, coordonnées synchronisées, rotation
autour de la pose, conservation du zoom, Échap annule. Contrôle de tour
plausible affiché et appliqué aux prochaines captures USB (340–380°, saut <=10°).
Les sessions existantes restent intactes et consultables. La référence reste 270°.

Difficultés : conflits avec Pan/Zoom, sélection de nuages superposés, instabilité
près du pivot, discontinuité ±180°, cartes périmées après déplacement.
Solutions et limites décrites dans [ANALYSE_SCANS_ET_SOURIS.md](methodes/ANALYSE_SCANS_ET_SOURIS.md).

Pistes matérielles non résolues : vitesse réelle absente du JSON, interpolation
ESP32 différente du manuel (diviseur 12 au lieu de 11 et demi-pas), pertes
possibles pendant l'impression CSV bloquante. Aucun changement du firmware
dans cette livraison ; ne pas attribuer avec certitude les 305 points à une cause.
Le problème des tours multiples est désormais détecté côté Python, sa cause
amont reste à corriger. L'ancienne tâche de diagnostic 720° devient donc
partiellement traitée, sans prétendre avoir réparé le firmware.

Validation : 38 tests automatisés passent, dont événements Matplotlib de
translation, rotation, Échap, passage ±180°, garde Pan/Zoom et diagnostics.
La fenêtre Tkinter sous Windows et la capture sur ESP32 restent à essayer.


## Supports du cours et premier rapport illustré — 2 novembre 2026

Archives reçues : Cartographie-20261102.zip et Localisation-20261102.zip.
Les deux méthodes de construction précédemment manquantes sont maintenant
disponibles et lues, ainsi que les notes sur la pose et le scan matching.
Les anciennes mentions « documents manquants » sont donc historiques.

Grid map : rapprochement avec le cours effectué pour le repère global,
l'état initial inconnu, les cellules traversées via Bresenham, les impacts
et les observations successives. L'implémentation utilise des log-odds.
Le nettoyage temporel demeure une extension non implémentée.

Carte vectorielle : extraction et fusion présentes, mais le traitement des
anciennes features traversées par les nouveaux rayons n'est pas intégré.
La fonction de découpage testée au laboratoire ne signifie pas que cette
étape de mise à jour de carte est réalisée. C'est une tâche restante prioritaire
après la fiabilisation de l'acquisition.

Nouvelle capture de superposition manuelle : les murs se recouvrent visuellement
sur plusieurs zones, sans évaluation chiffrée de précision. Le bloc de 766 points
est encore inclus dans Carte ; le bloc de 545 points est exclu. Exclure aussi
le bloc 766 avant une carte de validation. Les poses corrigées sur cette capture
ne sont pas assimilées à celles du JSON précédemment reçu.

Premier rapport Word illustré produit : Rapport_ScanAtlas_Jour1_Avancement.docx,
avec les cinq captures des nuages, grille, segments, carte vectorielle et
superposition récente. Textes courts, paramètres visibles, solutions retenues,
limites et suites à vérifier. Les captures anciennes restent identifiées comme
telles ; les tests logiciels ne sont pas présentés comme une validation matérielle.
Aucun changement de l'application ni du firmware dans cette étape.


## Mise à jour de la grid map pour le TP — 2 novembre 2026

Comparaison avec les cinq étapes du document de cours. Le noyau disposait déjà
de l'état inconnu, de la conversion par pose, de Bresenham et des preuves
libres/occupées. L'interface ne proposait qu'une reconstruction de tous les
scans cochés, et le noyau ignorait les rayons hors des anciennes bornes.

Ajouts : Grille.depuis_scan(scan, resolution, filtres) pour créer une carte
à partir d'un scan et sa pose ; Grille.mettre_a_jour pour conserver et
actualiser cette même carte avec agrandissement automatique. Trois boutons
séparent création depuis la sélection, ajout incrémental et reconstruction.
Validation des scans avant intégration et prévention du double compte dans
l'interface. Les paramètres et poses restent explicites et les données brutes
sont intactes. La référence lidar reste 270°.

Difficultés traitées : conserver les indices monde pendant l'agrandissement
vers les coordonnées négatives ; laisser inconnues les cellules nouvelles ;
ne pas effacer une carte lorsqu'un nouveau scan est importé ou que sa pose
non encore intégrée est corrigée ; invalider si la pose d'un scan déjà intégré
change ; ne pas mélanger des filtres/résolutions différents dans une carte.
La carte est limitée à quatre millions de cellules et un échec de croissance
ne modifie pas les anciennes observations.

Validation : 46 tests passent. Ils couvrent l'extension, la conservation
des probabilités et du masque observé, les poses, l'impact prioritaire, les
observations contradictoires, les mesures invalides, le double compte et
les tours multiples. Essai sur les 11 scans angulairement plausibles du JSON :
l'ajout incrémental et la reconstruction complète donnent exactement les
mêmes valeurs et le même masque (331 × 363 cellules à 0,05 m). Les deux
blocs multiples sont exclus. Ce contrôle ne prouve pas zéro perte de mesures.

Limites : scan matching automatique non implémenté ; pas de vieillissement
ni de lissage spatial ; grille calculée exportable en NPZ mais non conservée
dans la session JSON. Le rapport Word sera complété avec une capture du
nouveau parcours ; la documentation texte décrit dès maintenant les changements.


## Conservation des blocs multiples et comparaison de grille — 2 novembre 2026

Décision explicite utilisateur : conserver les acquisitions de 766 et 545 points.
Les anciennes recommandations d'exclusion sont abandonnées. Le problème n'est
pas « trop de points » ; plusieurs tours peuvent être cartographiés sous une
même pose si le lidar reste immobile. Les poses internes à un bloc ne sont
pas connues : un éventuel mouvement ne peut pas être corrigé automatiquement.

Modification : vérification angulaire informative et non bloquante pour les
trois actions de grille ; captures USB autorisées au-delà d'un tour. Le seuil
minimal de capture de 340° reste en place ; pas de seuil maximal ni de quota
de points ajouté. Les erreurs de format, indices CSV manquants et filtres de
mesure restent contrôlés. Le texte « bloc anormal » devient « bloc de plusieurs
tours ». Une preuve au plus par cellule et par bloc évite que répéter les mêmes
rayons à pose fixe augmente artificiellement leur poids dans un seul bloc.

49 tests passent, dont création, ajout, reconstruction et capture simulée
d'un bloc de deux tours. Une répétition identique de deux tours produit les
mêmes preuves par cellule qu'un seul tour dans ce bloc.

Captures reçues : à 0,05 m, grille 290 × 267 ; à 0,10 m, grille 146 × 134.
Les deux blocs étaient décochés sur ces images ; ce sont des résultats avant
réintégration. Le Word est corrigé et complété par ces deux figures, avec
comparaison visuelle de la résolution et sans prétendre mesurer la précision.
Aucun changement des cases dans la session locale de l'utilisateur n'est
possible ici : il doit recocher les blocs dans Carte après mise à jour.


## Correction des segments et de la carte vectorielle — 2 novembre 2026

Demande : extraire les segments de tous les scans cochés Carte et corriger
la carte vectorielle. Les blocs de plusieurs tours restent conservés.
Question posée sur les anciens segments traversés : l'utilisateur choisit
de les raccourcir prudemment après plusieurs rayons concordants.

L'extraction est désormais globale mais chaque scan reste séparé, avec sa pose
et sa couleur. Une frontière de tour coupe le groupe de points sans supprimer
les tours. Changer la sélection ne vide plus l'affichage des segments.
La carte vectorielle utilisait déjà tous les scans cochés : sa fusion est
corrigée par contrôle des droites supports et de l'erreur sur tous les points
originaux, au lieu de réajuster uniquement les extrémités déjà moyennées.

La gestion des absences, précédemment non intégrée, est maintenant appliquée
pendant la construction successive : au moins trois directions de rayons
valides distinctes, marge à l'impact, coupe médiane et conservation du côté
le plus long. Les doublons de rayons d'un bloc multiple ne votent pas plusieurs
fois dans le même bin angulaire. Les coupes et les fusions sont comptées.

Difficultés : seuils très larges des captures (rupture 1 m, erreur 0,5 m,
fusion 1 m), dérive des fusions en chaîne, extrémités faussement proches,
répétitions de tours, confusion sélection/Carte, coût des intersections.
Solutions et limites dans SEGMENTS_MULTISCANS_ET_VECTORIELLE.md. Un bouton
rétablit des seuils prudents sans changer silencieusement les paramètres.

60 tests passent. Trois réglages ont été calculés sur les 13 scans de l'ancien
JSON, tous conservés : 138/63, 160/65 et 222/88 segments extraits/finaux.
Ces nombres ne mesurent pas la précision ; les poses actuelles recalées
à la souris ne sont pas disponibles dans ce fichier. Sur deux scans simulés
à poses connues : aucune coupe. Un essai réel sur la dernière session est
encore nécessaire pour confirmer le résultat visuel.

Le rapport est corrigé pour distinguer l'ancienne extraction sélectionnée
de l'extraction multiscans, et la fusion initiale de la nouvelle méthode.
Les nouvelles captures sont conservées comme résultats avant correction.


## 3 novembre 2026 — Jour 2 — Superposition automatique ICP

Ajout de Localisation : choix explicite d'une référence fixe et d'un mobile,
pose initiale actuelle, ICP point à point, aperçu avant/après, durée, RMSE,
recouvrement et application explicite de la pose. Annulation, calcul en thread,
refus des résultats périmés ou non convergés. Les données brutes et la référence
restent intactes ; les cartes concernées sont invalidées après application.
Les filtres communs sont utilisés, sans exclure les blocs de plusieurs tours.

71 tests passent. Évaluation à pose connue sur les deux scans simulés : 4/6
réussites avec seuils 0,10 m et 2°. Une initialisation décalée de 1 m, 0,5 m,
15° converge vers une mauvaise pose ; un départ de 3 m, 3 m, 70° manque de
recouvrement. Le RMSE des paires n'est pas une erreur de localisation vraie.
Détails et CSV reproductible dans LOCALISATION_JOUR2.md et exemples/resultats_icp.csv.
Interface testée par actions/tracés sans écran ; Windows et acquisition réelle
restent à vérifier. Localisation grille et vectorielle non encore implémentées.

Essais manuels de filtrage transmis ce matin : distances 1,8–6 m, intensité
220, rupture 0,5 m, erreur de droite 0,2 m, fusion 6°/1 m ; captures à 78
segments extraits et 24 de carte, 54 fusions, une coupe. Résultat plus lisible
mais pertes de surfaces proches/faibles et risque de combler les ouvertures.
Aucun réglage utilisateur n'est changé silencieusement par cette livraison.


## 3 novembre 2026 — Correction des mouvements combinés

Retour utilisateur : ICP local peu fiable vers 50 cm et en translation +
rotation, malgré de bons résultats sur rotations seules et petits déplacements.
Filtres confirmés par capture : 0,05–12 m, intensité 0. La précédente hypothèse
de filtrage fort était erronée pour cette série. Aucune modification silencieuse
des filtres. Ajout par défaut de Recherche large + ICP, fenêtres ±1 m / ±30°,
réglables. Champ de distances à 5 cm pour la recherche, plusieurs candidats
diversifiés, deux affinements et ICP sur les points complets échantillonnés.
Score borné incluant les points non appariés, contrôle des limites et annulation.
ICP local conservé pour la comparaison.

75 tests passent. Comparaison à poses connues sur 9 initialisations identiques :
local 7/9 contre recherche large 8/9 aux seuils 10 cm et 2°. Temps médians
environ 0,154 s / 0,892 s sur l’environnement de test. Le cas décalé de
1 m, 0,5 m et 15° est récupéré ; le cas hors fenêtre de 3 m, 3 m, 70° reste
en échec. CSV et protocole conservés. Le résultat sur le robot reste à vérifier,
avec une incertitude des poses de référence à mesurer.


## 3 novembre 2026 — Import des CSV MapTool

Prise en charge de l’archive ScanJules du professeur : 15 CSV, chacun de 450
points, colonnes angle_deg,r_m,x_rel_m,y_rel_m et commentaire de pose. Les
distances sont déjà en mètres et le repère est neutre : ne pas appliquer les
270° du LD06. Les coordonnées relatives redondantes sont vérifiées à 1 mm
puis les points sont recalculés. La pose de l’en-tête initialise le scan et
reste conservée séparément dans pose_connue. ICP n’utilise pas pose_connue.

Absence d’intensité : ajout d’un indicateur explicite ; stockage interne à 0
sans prétendre à une mesure, filtre d’intensité ignoré pour MapTool uniquement.
Propagation aux copies de localisation, sessions et export. L’import ZIP lit
les CSV sans extraction sur disque. Les formats ESP32 à six colonnes et nos
anciens CSV à trois colonnes restent acceptés.

82 tests passent. Lecture des 6750 points réels de l’archive fournie : bornes
globales environ (−0,000096, −0,000091) à (2,000096, 3,000081) m, cohérentes
avec un domaine de 2 × 3 m et les arrondis. Aucun point supprimé par un seuil
d’intensité 220 (car non disponible), filtres de distance par défaut inchangés.
La pose du fichier est fournie par le simulateur : pour mesurer la localisation,
il faut perturber la pose initiale et comparer au champ pose_connue.


## 3 novembre 2026 — Option ICP après capture USB

Ajout d’une case à cocher dans Acquisition USB, désactivée initialement :
recaler automatiquement chaque nouveau scan sur le dernier scan de la liste.
Réutilisation de la méthode et des fenêtres de Localisation et des filtres
communs. Capture du lot puis fermeture du port avant calcul afin de ne pas
ralentir la réception série. Sans référence, le premier scan ancre le repère ;
les suivants partent de la pose précédente. Application automatique autorisée
par l’option, avec convergence, recouvrement ≥60 % et RMSE ≤0,10 m.

Après un échec ou annulation de recalage, les mesures restent conservées, la
chaîne s’arrête et les nouveaux scans non recalés sont décochés Carte, visibles
pour correction. Les résultats périmés après modification de référence/filtres
sont écartés sans perdre les données. Suivi numérique sauvegardé par scan.
Une correction explicite de pose enlève le blocage de référence non validée.

90 tests passent. Cas vérifiés : ancrage, référence du prédécesseur, absence
de mutation des entrées, exception, qualité insuffisante, annulation, option
désactivée/activée et rejet de résultat périmé. Sur deux acquisitions simulées,
un mobile à pose inconnue initialisée à zéro retrouve sa vraie pose à environ
2,9 mm et 0,049° près. Essai matériel USB toujours nécessaire. Une bonne RMSE
ne prouve pas la pose correcte ; accumulation de dérive et faux alignements
restent possibles. Aucun pilotage moteur ni mise à jour cartographique auto.


## 3 novembre 2026 — Correction du retour et des critères de capture automatique

Retour utilisateur : case cochée mais aucune superposition automatique visible.
Le comportement attendu est confirmé : dernier scan déjà chargé comme référence,
application de la pose au nouveau scan, message explicite si cela échoue.
L’inspection trouve des seuils d’acceptation additionnels (60 % / 0,10 m) qui
pouvaient rejeter un résultat pourtant applicable dans Localisation, ainsi qu’un
retour limité à des compteurs. Sans la session de l’essai réel, la cause précise
de cet échec n’est pas confirmée.

Suppression des seuils propres à la capture : mêmes critères que Localiser.
Affichage de la référence et des étapes réception/recalage ; succès avec pose
appliquée et ouverture de Nuages, ou fenêtre d’échec avec motif. Premier scan
explicitement présenté comme ancrage. Une exception du module ne perd plus les
scans déjà reçus. Les scans non recalés restent visibles et décochés Carte.

95 tests passent, dont un parcours complet depuis un flux série simulé, via
le vrai décodeur CSV, la recherche large ICP, la file de messages et l’application
de la pose. Simulation : erreur <1 cm et <0,1°, référence inchangée, passage
à Nuages vérifié. Tests additionnels du motif d’échec, premier scan, exception
et harmonisation des critères. L’essai sur le matériel réel reste nécessaire.

Le dépôt avait évolué avant cette correction : ANGLE_REFERENCE_DEFAUT = 0°,
modification utilisateur conservée. Les tests d’import/session suivent désormais
la constante configurée ; la géométrie d’une référence explicite à 270° reste
testée séparément. Pas de changement de filtrage ni d’algorithme multi-références.

## 3 novembre 2026 — Fiabilité et superposition d’un lot

Retour utilisateur : le recalage automatique reste peu fiable, besoin de superposer beaucoup de scans et remise en question du précédent scan seul. Ajout d’une sous-carte glissante de cinq références acceptées, moyennées par cellule de 5 cm ; contrôle d’accord fin à 65 %, contrôle des normales des surfaces et refus des solutions concurrentes dans la recherche large. Acquisition conserve une ancre précédente et des références antérieures portant un statut accepté ; elle ne fusionne pas aveuglément tous les imports.

Ajout du recalage des scans cochés Carte dans l’ordre de la liste : premier scan fixe, suivants localisés progressivement, échecs non propagés dans la référence, mesures conservées, échecs décochés Carte et signalés. Annuler le calcul écarte les poses ; annuler le dernier lot appliqué restaure poses, statuts et états Carte. Protection contre les changements de données, poses ou filtres pendant les calculs.

Difficultés : convergence ICP fausse malgré un score acceptable, vues ne partageant pas les mêmes obstacles, glissement le long de murs parallèles, ambiguïté d’une salle carrée, densité excessive des points répétés, ordre ZIP non chronologique. Les contrôles limitent les faux positifs mais augmentent les refus. Seuil d’accord fin réglé sur le même jeu MapTool : ne pas confondre calibration et validation indépendante. Dérive et fermeture de boucle non résolues.

Évaluation documentée dans FIABILITE_LOCALISATION.md : 42 essais MapTool, ICP local 5 corrects acceptés / 26 faux acceptés / 11 refus ; recherche large contrôlée 15 / 0 / 27. Trajectoire simulée bruitée : 7 recalages sur 7 après l’ancre, erreur maximale 1,18 cm et 0,222°. Les en-têtes MapTool et les poses vraies simulées ne servent qu’à l’évaluation. Aucun nouvel essai matériel réalisé. Rapport Word complété avec ces résultats et leurs limites.

## 3 novembre 2026 — Recherche globale sur 360 degrés et groupes secondaires

L’utilisateur précise que les fenêtres ±1 m / ±90° sont trop contraignantes, demande de partir du premier scan, de comparer les suivants à la carte cumulée, d’afficher la concordance et de mettre les scans non raccordés à part pour les fusionner plus tard. Il accepte un coût supérieur. Choix : recherche corrélative globale hiérarchique NumPy, contrôle des espaces libres, ICP multi-départ et assemblage de groupes dans des repères séparés.

Nouveau mode par défaut, champs de fenêtre cachés et inutilisés. Toute la carte et 360° sont explorés ; domaine de translation déduit des bornes de la carte et de la portée du mobile. Pas grossier 40 cm/4°, affinements jusqu’à 5 cm/0,5°, jusqu’à seize départs ICP. Tous les scans raccordés contribuent, avec moyenne spatiale sans troncature aux cinq derniers. Les scans bruts restent inchangés. Les limites d’allocation mémoire restent explicites ; cette recherche à candidats finis n’est pas une garantie d’optimum global.

Difficulté identifiée sur une grande salle presque symétrique : une mauvaise pose pouvait encore avoir 77,5 % de concordance. Ajout d’une carte interne des zones libres traversées par les rayons ; coût augmenté et rejet si plus de 8 % des impacts contredisent une zone libre, hors marge de 18 cm autour des impacts connus. La scène doit rester essentiellement statique. La concordance seule ne suffit pas ; les solutions concurrentes et la géométrie restent contrôlées.

Assemblage de tous les scans de la liste, y compris ceux en attente. Premier scan fixe ; sinon raccordement à la carte principale, à un groupe secondaire ou création d’un nouveau groupe. Pont partiel : au moins 35 % sur chaque carte et 85 % sur leur union, plus les autres contrôles. Transformation rigide de toutes les poses d’un groupe lors de la fusion. Les groupes locaux sont masqués et décochés Carte, mais conservés et persistés en session. Les anciennes vues sont retentées à l’extension et à la reprise. Une ancre déplacée invalide la reprise. Le dernier scan refusé ne bloque plus l’acquisition globale.

Évaluation : demi-tour retrouvé avec erreur 2,90 mm / 0,0491° ; déplacement 4,47 m + demi-tour dans une salle convexe asymétrique : 0,83 mm / 0,0298°. Poses initiales volontairement erronées, sans recours à la vérité terrain pendant la recherche. MapTool : 14 scans contre première référence, cinq corrects acceptés, neuf refus et aucun faux accepté sur ce jeu de développement ; médiane 6,82 s. Les tests isolés de fusion utilisent des correspondances simulées ; une validation physique de la fusion reste nécessaire. Il ne s’agit pas encore d’une optimisation globale de graphe ni d’une fermeture de boucle. Aucun filtre ni zéro lidar changé. Documentation détaillée dans LOCALISATION_GLOBALE.md ; rapport Word complété avec les résultats et réserves.

### Lot bruité sur la carte cumulée

Le banc de huit scans (graine 20261103, bruit de distance 15 mm, environ 20 % de pertes et 5 % d’aberrants) accepte correctement les sept scans après l’ancre. Erreurs maximales : 0.01239 m et 0.1982°, temps cumulé 93.74 s dans cet environnement chargé. Tous les scans raccordés participent à la référence. Détails : exemples/localisation_globale_lot.csv. Ce résultat en simulation ne remplace pas l’essai matériel.

## 3 novembre 2026 — Objectif de SLAM vectoriel temps réel en Wi-Fi

L’utilisateur confirme le besoin final : déplacement pendant les scans, commande clavier depuis l’application, transmission Wi-Fi, carte vectorielle construite en temps réel, puis navigation autonome. La recherche globale améliore certains raccordements mais reste lourde. Recherche de projets existants et étude documentée dans ARCHITECTURE_TEMPS_REEL_WIFI.md : CSM, KISS-ICP, Cartographer, Line Segment Mapping/CAE-RLSM, SLAM Toolbox, BreezySLAM, Espressif et Nav2. Les références et les idées retenues sont attribuées ; aucun code externe n’est copié ou installé dans cette étape.

Audit du dépôt main : pas de firmware ESP32 présent au commit 2f9ba1f8783afb26808372aafb335914ec6e238c. L’utilisateur précise ensuite que seul le test LD06 est disponible. La copie fournie reçoit sur GPIO33 à 230400 bauds et utilise GPIO32 pour le lidar ; elle affiche Teleplot en USB à 115200 bauds et ne contient ni Wi-Fi ni moteurs. Le câblage moteur, le châssis, les encodeurs et l’IMU ne sont pas confirmés.

Décision d’architecture : suivi local rapide et carte locale bornée, images clés et segments mis à jour progressivement ; conserver le repère global du premier scan. Réserver le recalage global, les groupes et les futures corrections de boucle à une tâche de fond. Séparer acquisition, enregistrement, pilotage et rendu. Le suivi point vers droite et les voisins indexés sont à évaluer, pas déjà intégrés. Les objectifs proposés sont 5 Hz/P95 <200 ms puis 10 Hz/100 ms ; la médiane actuelle du banc global est 12,13 s par recalage. Le temps réel n’est donc pas acquis.

Wi-Fi proposé : canaux TCP distincts pour commandes et scans compacts horodatés, en conservant l’acquisition UART non bloquante. Le robot bouge pendant un tour ; prévoir la compensation du mouvement et ne pas assimiler une commande moteur à une odométrie réelle. Prévoir expiration de commande sur ESP32, arrêt au relâchement/perte de focus et vérification de la perte de réseau. Pour l’autonomie, conserver une carte d’occupation interne, l’empreinte du robot et les obstacles récents, en complément des murs vectoriels. Première étape visée : trajet manuel cartographié ; ensuite destination choisie, puis exploration automatique.

Cette livraison est une étude et un plan de développement, ajoutés au rapport. Le solveur, le firmware et le pilotage moteur existants ne sont pas modifiés et aucun essai matériel nouveau n’est revendiqué.

## 3 novembre 2026 — Minimum du TP Jour 2 sur les trois références

La consigne est recentrée sur une méthode fonctionnelle par type de référence et une évaluation commune. Implémentation de trois modèles distincts : champ de distances des cellules occupées d’une vraie grille probabiliste, projections sur les segments finis d’une vraie carte vectorielle, et voisins indexés des points d’un scan fixe. Ajout de deux stratégies par modèle : moindres carrés robustes locaux et recherche multi-résolution suivie du même affinement, soit six combinaisons évaluées. SciPy fournit EDT, interpolation, cKDTree et least_squares ; aucune reprise silencieuse d’un projet complet.

Nouvel onglet TP Localisation avec aperçu, sélection du mobile à gauche, application explicite de la pose et annulation. Le mobile ne peut pas entrer dans sa propre grille ou carte vectorielle de référence. Les résultats sont écartés si les références, les données ou les filtres changent pendant le calcul. Ajout de SciPy dans requirements et message du lanceur Windows demandant la mise à jour des dépendances.

Banc commun : mêmes deux scans simulés, références issues du seul scan fixe, sept perturbations de départ et seuils 0,10 m / 2°. Export de 42 essais et synthèse avec erreurs, médiane/P95, taux de réussite et faux acceptés. Les modes multi-résolution font 6/7 réussites pour chaque référence (six départs dans le voisinage et un échec volontairement éloigné). Les modes locaux font 5/7 ; une mauvaise convergence vectorielle du cas 6 reste acceptée malgré 72,5 % de concordance, explicitement documentée. Les poses connues ne sont utilisées que pour l’évaluation. Pas de chiffre physique inventé : l’incertitude des références mesurées sur le robot reste non renseignée.

Tests ciblés : distances aux extrémités des segments, champ de grille, six combinaisons, géométrie dégénérée, annulation, absence de mutation, prévention de l’auto-référence, invalidation et application réelle depuis le contrôleur d’interface. Une annulation précoce a révélé une variable de graines non initialisée, corrigée. Les tests de durée sous charge ont été remplacés par des vérifications fonctionnelles ; les durées se mesurent dans le banc, sans borne arbitraire susceptible de rendre les tests instables.

Le code moteur annoncé par l’utilisateur a été recherché dans le dépôt et sa branche main. À ce stade de la vérification, le dernier commit accessible est encore 2f9ba1f ; aucun dossier moteur/ESP32 n’y est visible. L’intégration moteur n’est donc pas annoncée comme réalisée. Le plan Wi-Fi/temps réel et ses sources sont conservés ; ce travail de localisation TP est une étape concrète vers cette architecture, pas le système autonome complet.

### Mise à jour après disponibilité du programme moteur

Le commit utilisateur f6fd482 ajoute ESP32_LD06_Test et MecanumCarV2. Le programme ESP32MecanumCar.ino a été lu : bibliothèque MecanumCar_v2, I2C SDA 19 / SCL 21, avance, recul, déplacements latéraux, rotations et arrêt dans une séquence temporisée non bloquante. Le README confirme le châssis Keyestudio Mecanum Car V2. La version GitHub du test lidar active le CSV. Cette disponibilité remplace le constat d’absence précédent ; les dossiers importés par l’utilisateur seront conservés lors de la publication. Le code actuel n’a pas encore de Wi-Fi ni d’intégration au PC.

## 3 novembre 2026 — Pilotage Wi-Fi et carte vectorielle en direct

À la demande utilisateur, ajout d'un firmware hotspot ESP32 et d'un onglet Robot Wi-Fi. SSID ScanAtlas, mot de passe ScanAtlas2026, IP 192.168.4.1. Broches confirmées dans le projet fourni : moteur SDA19/SCL21, lidar RX33 à 230400 bauds, activation GPIO32. La bibliothèque MecanumCar_v2 du ZIP fourni est incluse sans modification ; le programme de démonstration et les autres dossiers utilisateur sont conservés. Aucune séquence de mouvement au démarrage.

Deux canaux : commandes UDP4210 avec session, séquence, STOP initial et bail de 300 ms sur l'ESP32 ; tours lidar TCP4211 avec frontière de tour, durée/fin horodatées, CRC8 UART puis CRC32 réseau. Tâche moteur indépendante du transfert et de l'UART ; files du dernier scan uniquement. Le PC transmet STOP après 250 ms sans renouvellement UI. Perte de focus, relâchement, Espace/Échap, changement d'onglet, perte réseau ou échec de suivi désactivent le mouvement. Le flux lidar périmé bloque aussi la conduite. Ces contrôles logiciels ne sont pas un système d'évitement d'obstacles.

La carte part du premier scan fixe. Suivi local robuste indexé sur une sous-carte de points validés, secours multi-résolution et reprise explicite. Contrôles supplémentaires : 75 % à 12 cm, RMSE ≤ 10 cm, évolution de pose plausible et délai entre scans. La concordance affichée utilise bien accord_fin à 12 cm, et non le recouvrement large à 50 cm du solveur. Les scans refusés ne contaminent pas la carte. Scans clés à 15 cm / 5° / 2 s. Extraction PCA/SVD et fusion incrémentale des segments avec appuis bornés. Export segments et transfert des scans clés vers la session habituelle ; reconnexion conservant la carte. Aucun déplacement commandé n'est présenté comme une odométrie mesurée.

Vérification : 137 tests de la suite initiale avec les 10 premiers tests Wi-Fi ont passé. Un test supplémentaire couvre les acquittements UDP retardés ; un test Tk réel couvre connexion, flèches, relâchement, focus, onglet et déconnexion. Le test UI a révélé un rejet trop strict des acquittements dès que le paquet suivant était parti : correction pour accepter un acquittement antérieur, nouveau et encore récent, sans accepter les répétitions. Les numéros et la fenêtre temporelle limitent le rejeu. Le parseur et le watchdog firmware sont compilés en C++ hôte et leurs trames sont décodées par le client Python.

Compilation réelle du sketch avec Arduino-ESP32 2.0.17 et cible esp32:esp32:esp32 : 766453 octets programme / 1310720 et 63296 octets variables globales / 327680. Le téléchargement automatique du compilateur ne fonctionnait pas dans l'environnement ; installation locale des archives officielles, vérification SHA256, puis compilation aboutie. Les dépendances de compilation ne sont pas ajoutées au dépôt. La compilation ne prouve ni le câblage ni le fonctionnement physique.

Banc reproductible outils/evaluer_wifi.py : 60 tours simulés à 100 ms, 450 points par tour, murs et obstacle avec occultations, bruit gaussien σ3 mm, graine 2026, translation et rotation simultanées. 60/60 acceptés ; erreurs maximales 5,03 mm et 0,400°, médiane calcul 52,2 ms et P95 119,6 ms ; 7 scans clés, 5 segments. Les résultats CSV sont conservés. Ce banc ne simule pas le mouvement pendant le tour et n'évalue pas les pertes radio. Simulateur interactif fourni : python simuler_robot_wifi.py puis adresse127.0.0.1.

Limites restantes : essais matériels, compensation intra-tour et odométrie/IMU, dérive et scènes ambiguës, fermeture de boucle, suppression des segments anciens par preuves d'espace libre dans le mode direct, relocalisation globale en arrière-plan, collision et navigation autonome. Le mode global existant reste séparé pour les acquisitions enregistrées. Guide complet et attribution des inspirations Espressif, Robot-Maker/LD06, Cartographer et SciPy dans PILOTAGE_WIFI.md. Le rapport Word reçoit la capture du nouvel onglet, les résultats simulés et les essais physiques restant à effectuer.

Validation finale de cette livraison : découverte de 139 tests, 138 exécutés avec succès et un test Tk ignoré en mode sans écran ; ce test Tk a été exécuté séparément avec succès sur un écran virtuel. Les tests réseau attendent des événements plutôt qu'une réponse à un instant arbitraire ; le délai déterministe du bail reste testé séparément. Sous forte charge, la connexion PC tolère jusqu'à 2 s sans acquittement, tandis que l'intention UI expire à 250 ms et le watchdog indépendant ESP32 reste à 300 ms. Le rapport est complété de quatre pages, avec la capture de l'onglet et le banc chiffré.

## 3 novembre 2026 — Suivi point-vers-droite et interface unifiée

À la demande utilisateur, suppression du doublon visible Localisation / TP Localisation. Un seul onglet Localisation présente les trois références du TP, les deux stratégies comparables et l'évaluation commune. Le suivi embarqué dans Robot Wi-Fi garde un rôle distinct de cartographie pendant la conduite. Les fonctions historiques restent dans les scripts et dans l'acquisition USB ; elles ne créent pas un deuxième panneau.

Ajout d'une prédiction SE(2) fondée exclusivement sur les deux dernières poses lidar acceptées et leurs horodatages. Référence locale des huit derniers scans clés fiables, index et normales conservés entre les insertions. Normales issues de la covariance de sept voisins, sélection des voisinages linéaires. ICP robuste point-vers-droite avec Jacobien analytique et système 3x3, associations resserrées et contrôle d'observabilité. Le secours multi-résolution repasse par cette validation pour ne pas contourner une géométrie insuffisante. Concordance toujours mesurée sur les impacts réels à 12 cm, mesures originales et première ancre conservées.

Interface : palette claire avec accent bleu-vert, boutons hiérarchisés, liste et onglets harmonisés. Curseurs ajoutés aux champs numériques de filtrage et de segmentation, ainsi qu'au PWM. Robot Wi-Fi affiche pose, orientation, concordance, durée et nombre de segments ; couches et suivi de caméra activables. Les objets graphiques sont réutilisés et le zoom n'est plus réinitialisé à chaque tour. Les filtres restent figés pendant une carte directe et les arrêts logiciels sont conservés.

Comparaison sur les mêmes 60 tours, mêmes mesures et poses initiales, avec la version b28f7c9 : 60/60 acceptés dans chaque cas. Médiane de calcul 33,33 -> 3,73 ms ; P95 58,46 -> 13,63 ms ; erreur maximale 5,03 -> 0,64 mm et 0,400 -> 0,0144 degré. Ces valeurs sont simulées et excluent UI, radio et déformation intra-tour. Les 120 lignes sont dans exemples/comparaison_suivi_continu.csv et le protocole dans SUIVI_CONTINU.md.

Validation : 144 tests découverts, 143 exécutés avec succès sans écran et un test Tk exécuté séparément avec succès. Nouveau test sur 105 tours avec translation et rotation au-delà de 180 degrés, test de composition SE(2), cas du mur unique, points isolés et cache. Le test UI contrôle aussi le seul onglet Localisation, le curseur et la conservation du zoom. La vérification visuelle a nécessité l'installation de polices pour l'écran virtuel de test ; le thème choisit la famille disponible plutôt que supposer Segoe UI partout.

Le firmware et le protocole de conduite ne sont pas modifiés dans cette livraison, afin de conserver la compatibilité avec les essais en cours. Il faut seulement actualiser et redémarrer l'application PC ensuite. La fermeture de boucle, l'odométrie/IMU, la compensation intra-tour et la navigation autonome restent à développer. Les principes méthodologiques et leurs sources publiques CSM, PCL, Cartographer et SciPy sont détaillés, sans annoncer une reprise de leurs logiciels complets.


## 3 novembre 2026 — Reprise du suivi et acquisition USB ou Wi-Fi

Retour utilisateur : les touches changent bien l’indication, mais le robot ne bouge pas ; l’exemple moteur fourni ne fonctionne pas non plus sur le robot essayé. Un essai sur un autre robot est prévu. Le suivi peut se suspendre même à l’arrêt, clavier décoché. Aucun essai physique supplémentaire n’a été réalisé ici.

Cause logicielle identifiée : après un premier recalage refusé, le drapeau perdu empêchait toute nouvelle tentative. Correction : nouvelle tentative au maximum deux fois par seconde, près de la dernière pose (25 cm / 8°), sans insertion de scans refusés. Une reprise explicite autorise 1,2 m / 35° et resynchronise le temps après reconnexion. Les seuils de concordance et de géométrie ne sont pas relâchés. La cause du premier refus réel reste à identifier.

Le clavier manuel dépend de la connexion et de la fraîcheur du lidar, plus du succès du recalage. Les arrêts au relâchement, changement d’onglet, perte de focus et perte de transport sont conservés. Le tableau distingue commande PC et acquittement effectif ESP32. L’attente de reprise affiche -- ; le motif précédent reste visible. Les refus répétés ne déclenchent plus de dessin continu de la carte figée.

Acquisition propose USB et Wi-Fi, 1 à 20 scans bruts, avec localisation automatique facultative déjà existante. La capture Wi-Fi envoie seulement STOP. Les imports, exports, sessions et trois références de localisation du TP sont conservés. Firmware inchangé : USB nécessite le programme CSV historique, Wi-Fi le programme ScanAtlas_WiFi. La sortie USB à la demande dans le même firmware reste à intégrer.

Validation : 148 tests découverts ; après restauration du fichier d’exemple session_demo.json absent de la copie de travail, les 147 tests sans écran passent (dont le test initialement bloqué, revérifié avec son groupe de cinq tests). Le test Tk a ensuite réussi sur écran virtuel : pilotage pendant refus de suivi, récupération automatique, relâchement, focus, changement d’onglet et conservation du zoom. Les 148 tests ont donc été exécutés avec succès. Les quatre nouveaux tests couvrent récupération automatique sans contamination, reprise après redémarrage d’horloge, capture brute Wi-Fi sans géométrie et acquittement STOP distinct d’un FORWARD envoyé. Le simulateur réseau ne valide pas le mouvement physique.

Difficulté de reprise : les modifications non publiées de la session interrompue n’étaient plus présentes localement. Reconstruction depuis le commit publié a1c13d8, sans écraser les dossiers moteurs ni les données utilisateur. Les instructions sont dans ACQUISITION_ET_DEPANNAGE.md.

## 4 novembre 2026 — Interface en trois espaces et reprise des cartes

Choix validés avec l'utilisateur : thème clair sobre bleu pétrole, logo ScanAtlas, trois espaces principaux, grande carte et panneaux repliables. Cartographie garde ses outils historiques, dont la carte vectorielle. Localisation conserve les trois références du TP et l'évaluation ; le mobile se choisit dans son panneau propre. Robot en direct masque la liste globale des scans et propose Points, Grille et Vectorielle. Le panneau de commandes est redimensionnable, défilant et masquable ; l'arrêt reste accessible en tête. La navigation Matplotlib reste visible en bas. Ajout d'une annulation des poses manuelles et des poses appliquées après recalage.

La référence directe peut provenir des scans cochés Carte de la session, copiés avec leurs poses. Les segments existants sont préservés quand leurs scans sources correspondent exactement. Au démarrage sur une carte existante et après reconnexion, recherche globale 360° puis confirmation point-vers-droite ; un résultat ambigu ou insuffisant n'est pas inséré. Les tentatives globales sont espacées de cinq secondes. Test d'une pose initiale inconnue avec translation et rotation de 145°. L'ICP courant, les critères d'acceptation et l'ancrage restent protégés. La carte de référence conserve sa couverture après enrichissement.

Le mode Localisation seule poursuit les poses tout en figeant les points, les segments et les cellules de grille. La grille d'occupation est mise à jour uniquement aux insertions validées, avec copie publiée atomiquement ; l'image et les références sont conservées entre les mises à jour. Tous les tours réseau complets reçus sont journalisés avant la file de calcul. Les décisions et une session JSON de secours sont enregistrées séparément. La sauvegarde directe est compatible avec les sessions version 2. Les tours non traités restent analysables dans le journal, sans prétendre avoir été localisés.

Manette Xbox : lecture XInput Windows sans dépendance ajoutée, maintien LB, zone morte de 22 %, axe dominant et puissance proportionnelle plafonnée. Relâchement, B, perte de focus ou de transport donnent STOP ; déconnexion de la manette désarme l'option. Les essais ont porté sur les conversions et les contrôles simulés, pas sur une manette physique.

Correction du pilote moteur après retour de câblage : le programme utilise huit sorties PWM directes plutôt que l'ancien pilote à deux fils. Profil proposé M1=5/18, M2=19/21, M3=2/4, M4=16/17. GPIO, affectation des roues et inversions sont séparés dans motor_config.h. Ce relevé et l'emplacement des roues ne sont pas vérifiés physiquement. Mode de diagnostic série par impulsions de 250 ms à PWM 50, sans Wi-Fi ni lidar. Le même firmware propose désormais le CSV USB sur requête SCAN N, en tâche séparée ; les anciennes captures CSV et le protocole réseau restent compatibles.

Validation : 156 tests découverts, 155 réussis sans écran et le test Tk exécuté séparément avec succès. Contrôles ajoutés pour carte figée, copie indépendante, recherche initiale inconnue, journal, annulation de pose, axes Xbox, USB à la demande et PWM sur API simulée 2.x/3.x. Compilation réelle ESP32 classique avec Arduino-ESP32 2.0.17 : 778261 octets de programme (59 %), 69488 octets de variables globales (21 %). La branche Arduino 3.x est testée sur API simulée, sans compilation cible 3.x revendiquée.

Difficultés : reprise des modifications depuis le dernier commit publié ; adaptation des sélections après regroupement des onglets ; respect du zoom malgré imshow ; widgets bas masqués si le canvas était empaqueté avant la barre de navigation ; polices de l'écran virtuel à réindexer. La chaîne Arduino a dû être reconstituée et ses dépendances téléchargées par un autre chemin que son client réseau. Les erreurs d'outillage ont été résolues jusqu'à production du binaire. Aucun essai moteur, radio ou manette physique n'a été réalisé. Fermeture de boucle, compensation du mouvement intra-tour et navigation autonome restent hors livraison. Le guide courant est GUIDE_SCANATLAS_V3.md ; sources publiques LEDC et XInput citées dans ce guide.

## 4 novembre 2026 — Commandes combinées, encart de pilotage, capture dans Localisation

Reprise de la conversation « Plan du TP lidar » au point validé : manette avec stick gauche en surge + sway, stick droit en yaw, RB pour la cartographie, encart visuel des commandes en pourcentage utilisable sans robot, et capture directe dans Localisation par rapport au dernier scan. Le rapport Word n'est pas touché (demande utilisateur : plus tard).

Protocole : nouvelle commande UDP `SA2 jeton séquence vx vy w` (pourcentages signés, -100 à 100). Un mouvement à un seul axe part toujours en `SA1`, donc l'ancien firmware reste utilisable. Le firmware annonce `READY jeton SA2` ; le PC se rabat sur l'axe dominant avec un message « Reflasher ScanAtlas_WiFi » si l'annonce manque. Mixage mécanum dans protocol.h (fonction pure, testée sur l'hôte), saturation proportionnelle, un vecteur nul vaut STOP, un mouvement ne peut pas ouvrir le bail (STOP d'abord).

Interface : encart Surge / Sway / Yaw (deux cases par axe, remplissage vert depuis le centre en % du PWM, fixe au clavier, proportionnel à la manette), fond beige hors connexion et vert pâle connecté. Le pilotage fonctionne sans robot (mode test, rien d'envoyé). Clavier combinable, touches opposées annulées. Manette : LB reste l'homme mort, B arrête, RB bascule cartographie / localisation seule sur front montant. Localisation : section Capture directe (source, méthode, nombre de scans), réglages ICP exposés avec curseurs et partagés avec Acquisition, colonne défilante, superposition tracée dans l'onglet. Variables de capture et d'ICP créées une seule fois pour tous les onglets.

Difficultés : (1) un nouveau PC avec un ancien firmware aurait perdu la liaison au premier mouvement combiné, car `SA2` n'est pas acquitté : d'où la négociation dans READY et le repli. (2) Les réglages ICP n'avaient plus de champ visible depuis le regroupement des onglets ; ils n'existaient que comme variables de l'onglet Acquisition, recréées à sa construction, ce qui aurait désynchronisé des champs placés ailleurs : création unique avant les onglets, `champ()` réutilise une variable existante. (3) `focus_get()` de Tk peut lever `KeyError` ; le pilotage tournant désormais à chaque cycle, l'exception est rattrapée pour ne pas arrêter la boucle d'interface. (4) Les symboles ↺ ↻ ne s'affichaient pas dans toutes les polices : retirés. (5) Les tests de capture existants utilisaient des faux objets sans les nouvelles méthodes : complétés.

Validation : 161 tests existants et 16 nouveaux passent sous Python 3.13 avec Tk et écran virtuel, dont l'encart dessiné réellement, le mode test sans robot, RB, la liaison avec un faux robot et l'ancien firmware, la capture depuis Localisation et la compilation hôte du firmware. Captures de contrôle de l'écran virtuel relues. **Non vérifié sur le matériel** : le mixage sur les vraies roues (signes et emplacement des moteurs toujours à confirmer), la manette physique (lecture XInput simulée), le Wi-Fi radio, et la nouvelle disposition sous Windows. À tester roues levées d'abord, puis au sol à faible PWM.

## 4 novembre 2026 — Choix du pilote moteur PWM ou I2C

Demande : les robots n'étant pas câblés de la même façon, pouvoir choisir entre la carte moteur pilotée en PWM direct et en I2C, et savoir où régler les broches. Tous les réglages sont regroupés dans `firmware/ScanAtlas_WiFi/motor_config.h` : `MOTOR_DRIVER` (PWM par défaut, surchargeable par `-DMOTOR_DRIVER=2`), le profil PWM (`MOTOR_PINS`, `WHEEL_MOTOR`, `WHEEL_SIGN`, `MOTOR_PWM_HZ`) et le profil I2C (`I2C_SDA_PIN`, `I2C_SCL_PIN`, `I2C_WHEEL_MOTOR`, `I2C_WHEEL_SIGN`).

Structure : `motor_common.h` (validation des broches et du plan de roues, mélange commun `drive` / `apply` en classe modèle), `motor_pwm.h` (pilote PWM, comportement inchangé), `motor_i2c.h` (nouveau pilote par `mecanumCar::PWM_OUT`, canaux 1..8) et `motor_driver.h` (sélection à la compilation, erreur si la valeur est inconnue). Le sketch n'utilise plus qu'un type `MotorDriver` ; protocole, bail de sécurité et mode diagnostic sont inchangés. Le démarrage affiche le pilote actif.

Choix : la sélection est faite à la compilation et non à l'exécution, car une mauvaise sélection à chaud pourrait envoyer des signaux sur des broches utilisées par l'autre carte. Le pilote I2C met le canal opposé à zéro avant d'activer un sens, comme le PWM. L'association par défaut des roues I2C reprend celle du firmware de démonstration d'origine.

Validation : tests hôte sur la vraie classe `mecanumCar` (canaux, sens, ordre d'écriture, arrêt, plafond), sélection des deux pilotes avec les API 2.x et 3.x simulées, refus d'un pilote inconnu, validation des broches. Limites : le .ino n'a pas été compilé pour un ESP32 ici, et rien n'a été essayé sur un robot réel (sens des roues I2C à vérifier avec le mode diagnostic).

## 4 novembre 2026 — Alignement sur les derniers échanges : AZERTY, plus de LB, pavé de commandes

Les derniers échanges avec ChatGPT, transmis ensuite, fixaient des choix que le code ne suivait pas encore : clavier AZERTY (Z/S surge, Q/D sway, A/E yaw), plus de LB à maintenir (activation à l'écran), B ou Espace coupant le pilotage jusqu'à sa réactivation sans toucher au lidar ni à la localisation, pilotage conservé même si la localisation est perdue, arrêt si le focus de l'application est perdu. Les images jointes montraient aussi le pavé visuel (flèches, rotations, croix d'arrêt, case verte active).

Modifications : `manette.py` (plus de LB ; `EtatManette` sans champ `lb`), `interface_wifi.py` (touches AZERTY, flèches conservées comme équivalents, B désarme le pilotage avec message, textes d'aide), `encart_commandes.py` (pavé 3 × 3 dessiné en polygones et polylignes, sans glyphes de police ; croix verte à l'arrêt ; barres en pourcentage conservées à droite), aide intégrée et guide.

Difficulté : les anciennes touches A/D (sway) changent de sens : A devient le yaw gauche. Les flèches restent donc la voie la plus sûre pour qui a l'habitude de l'ancienne disposition. Une exécution complète de la suite a échoué une fois sans qu'on puisse le reproduire (quatre exécutions suivantes propres) ; le test concerné n'a pas été identifié.

Validation : 185 tests réussis sous Python 3.13 avec Tk et écran virtuel, dont l'encart dessiné (pavé et barres), les touches AZERTY, B qui désarme, RB qui bascule la cartographie. Non essayé avec une vraie manette ni sur Windows. Idée gardée pour plus tard, comme convenu : prédire le mouvement à partir des commandes pour initialiser le recalage lidar, avec recherche élargie si le lidar contredit la prédiction.

Correctif de compilation Arduino IDE (même jour) : `MecanumCar_v2.cpp` était enregistré avec un BOM UTF-8 et `MecanumCar_v2.h` en GBK ; le compilateur de l'ESP32 refusait le BOM (`stray '#'`, `'\U0000feff' does not name a type`). Les deux fichiers sont convertis en UTF-8 sans BOM, et le `.cpp` est entouré de `#if MOTOR_DRIVER == MOTOR_DRIVER_I2C` : en mode PWM, ce fichier n'est plus compilé du tout, donc une erreur dans la bibliothèque I2C ne peut plus bloquer le PWM. Vérifié par une compilation syntaxique g++ des deux modes avec un faux `Arduino.h` ; pas de compilation ESP32 réelle ici.

## 4 novembre 2026 — Encart simplifié, direct filaire USB, journal série du robot

Encart : les barres Surge / Sway / Yaw sont supprimées (double information). Le carré vert dynamique est désormais directement derrière chaque flèche du pavé, avec le pourcentage dans la case ; la croix centrale est pleine à l'arrêt.

Coupures de scans : les journaux de l'application (dossier `AppData\Local\ScanAtlas\journaux`, lus avec l'accord de l'utilisateur) montrent une liaison saine pendant plus de 30 s (environ 9 tours par seconde, aucun trou supérieur à 150 ms, tous les suivis acceptés) qui s'arrête net, puis plusieurs reconnexions sans aucun tour reçu. Ces traces ne permettent pas de désigner la cause (Wi-Fi, alimentation, lidar). Un défaut de la bibliothèque I2C a été écarté : aucune attente sans limite dans le code. Le firmware journalise donc maintenant sur la console série la cause du dernier redémarrage (dont BROWNOUT), les appareils Wi-Fi, le bail, les flux de scans et le silence du lidar.

Direct filaire : nouvelle liaison USB qui porte les mêmes trames SA06 et les mêmes commandes SA1 / SA2, négociée par `LIVE jeton débit` à 115200 puis passée à 921 600 bauds, avec bail de 300 ms et retour automatique à 115200. Fichiers : `firmware/ScanAtlas_WiFi/usb_live.h` (analyse et état de session), gestion dans `ScanAtlas_WiFi.ino`, client `robot_usb.py` (démultiplexage trames / acquittements texte, resynchronisation après octets abîmés, DTR/RTS non activés pour ne pas redémarrer la carte), choix Wi-Fi / USB filaire dans l'interface. Difficulté : la console porte à la fois des données binaires et du texte ; les journaux série sont donc coupés pendant la liaison filaire, et seul `loop()` écrit sur le port pour éviter tout mélange à l'intérieur d'une trame.

Validation : 14 tests dédiés (démultiplexeur, client contre un faux firmware qui simule le changement de débit, mauvais débit, firmware muet, robot occupé, flux interrompu, interface, logique C++ de session compilée sur l'hôte) ; le sketch est en outre vérifié par g++ (syntaxe seule) contre de faux en-têtes ESP32 avec les deux pilotes moteur. Non essayé : câble, robot et compilation ESP32 réels.

## 4 novembre 2026 — Sway inversé, lenteur, Localisation seule vide

Constats de l'utilisateur : le sway est inversé ; le robot, même filaire, se « suspend » vite ; en Localisation seule, rien ne se passe et aucun point ne s'affiche ; le robot avance très lentement (soupçon : alimenté par l'USB seul, pas par les 18650).

Causes et corrections :
- Sway : constantes `AXIS_SURGE_SIGN` / `AXIS_SWAY_SIGN` / `AXIS_YAW_SIGN` dans `motor_config.h`, appliquées dans `drive` et `apply` (sway à -1 par défaut). Tests hôte avec et sans inversion.
- Lenteur : le pourcentage 0..100 de l'application était écrit directement comme PWM sur 0..255, soit au plus 39 % de la puissance. Nouvelle conversion `powerToDuty` avec `MOTOR_DUTY_MIN` / `MOTOR_DUTY_MAX`. L'alimentation USB seule reste un second suspect (chute de tension).
- Localisation seule : avec une carte vide, l'application refusait chaque scan (message d'erreur) donc rien n'était calculé ni dessiné. Le premier scan sert maintenant de référence (origine fixe) et les suivants sont localisés sans enrichir la carte. De plus, un scan non accepté est dessiné en rouge à la dernière pose connue, et les passages suivi actif / suivi perdu sont écrits dans `evenements.log` du dossier de journal.
- « Suspendu » : cause non démontrée. Hypothèse principale : chute de tension (BROWNOUT) quand les moteurs démarrent sur l'USB seul. À confirmer avec le moniteur série à 115200 (la raison du dernier redémarrage est affichée au démarrage) et avec `evenements.log`.

Validation : 205 tests réussis. Non essayé sur le robot.

## 4 novembre 2026 — Rangement du dépôt, document de reprise, refonte visuelle

Rangement : la documentation passe dans `docs/`, les scripts d'évaluation reproductibles dans `outils/` (ils ajoutent eux-mêmes la racine au chemin d'import ; commande `python outils/<nom>.py`), le firmware de démonstration d'origine du châssis, le test lidar et la CAO dans `materiel/`. Les modules Python restent à plat à la racine pour ne pas casser les imports ni les tests. Les deux fichiers `.pyc` qui étaient suivis par Git sont retirés. `docs/REPRISE_PROJET.md` et `AGENTS.md` résument l'état, l'architecture, les décisions et la suite pour un nouvel intervenant.

Refonte visuelle (sobre, ergonomique) : palette neutre (fond gris clair, cartes blanches à bordure fine, un accent bleu-vert foncé, vert / rouge réservés à l'état), boutons secondaires grisés pour se distinguer des cartes, onglets soulignés, curseurs et barres de défilement discrets, graphiques Matplotlib harmonisés (cadre léger, grille claire, titres sobres) via `apparence.py` (`appliquer_theme`, `style_matplotlib`, `carte_ui`, `habiller_barre`). Espace Robot : connexion et état dans l'en-tête, bandeau d'instruments (position, orientation, concordance, calcul, carte) au-dessus de la carte, colonne de droite en blocs, **bloc Pilotage fixé en bas** pour que le pavé et l'arrêt restent visibles sans défilement (vérifié par un test à 1366 × 768). Zone de focus clavier entourée d'un liseré visible. Le pavé garde ses fonctionnalités ; ses couleurs sont adoucies.

Difficulté : la colonne de droite dépassait la hauteur de l'écran et cachait le pavé derrière un ascenseur ; la connexion a donc été déplacée dans l'en-tête et le bloc de pilotage compacté. Validation : 208 tests réussis, captures d'écran faites sous Linux avec écran virtuel ; rendu Windows (police Segoe UI, DPI) non vérifié.

## 4 novembre 2026 — Robot perdu pour de bon, reconnexion, import lent

Constat (journaux `evenements.log` de la session de 10 h 30) : le suivi se perdait puis ne revenait jamais, 25 s jusqu'à la coupure. Les refus étaient du type « 99 % à 12 cm, RMSE 4 cm, déplacement 1 cm » : des recalages excellents refusés. Deux causes dans le code :
- `icp_droites` exigeait une convergence stricte (pas < 0,2 mm) en 30 itérations ; un robot en mouvement n'y arrive pas toujours. Critère assoupli (dernier pas < 3 mm et < 0,05°) et raison du refus écrite dans le message (trop peu de points, géométrie insuffisante, non stabilisé, concordance).
- Une fois perdu, le suivi n'acceptait un retour qu'à 25 cm et 8° de la **dernière pose gelée**, alors que le robot continue de rouler et de tourner : il ne pouvait plus jamais revenir. Fenêtre désormais proportionnelle au temps écoulé, puis récupération automatique : recherche élargie autour de la dernière pose (tous angles, rayon croissant) après 1 s, recherche sur toute la carte après 6 s, relancée toutes les 3 s. Durées mesurées sur l'horloge du PC (celle du lidar repart à zéro si l'ESP32 redémarre). Simulation : saut de 1,3 m et 70° retrouvé en 1,3 s à 2,5 cm.

Reconnexion : à 10 h 40, `GetOverlappedResult failed (Accès refusé)` puis `could not open port 'COM8'` : l'ESP32 redémarre (coupure d'alimentation) et Windows rend le port avec quelques secondes de retard. L'ouverture est maintenant réessayée pendant 8 s ; reconnexion automatique (3 s, 8 essais, carte conservée) avec reprise près de la dernière pose au lieu d'une recherche globale systématique. Un clic sur Déconnecter annule la relance. Piège rencontré : lire une variable Tk depuis le thread de calcul le tue en silence ; les options sont lues avant le démarrage du thread.

Import des scans cochés : 150 scans = 1,7 s de chargement mais surtout 5 s de première recherche globale (champ de distances et grille de zones libres recalculés à chaque appel). Ces deux objets sont maintenant gardés sur la sous-carte, et l'interface indique le chargement. La recherche globale reste proportionnelle à la taille de la carte.

Interface : bouton **Me retrouver** près de la carte (les anciens boutons étaient cachés derrière le bloc Pilotage sur un écran à échelle 125-150 %), deux cases d'options.

Vidéo de référence (Robot Maker, 2018) : robot mecanum à 4 roues avec lidar RPLIDAR A2 qui cartographie un appartement de 80 m² avec un SLAM exécuté sur un microcontrôleur 32 bits. Le but retenu : cartographier une grande surface en roulant, sans se perdre. Pas de détail technique exploitable dans la description.

Validation : 215 tests réussis. Non essayé sur le robot (coupures d'alimentation toujours en cause : batteries à vérifier).

## 4 novembre 2026 — Perte de localisation en tournant vite

Remarque de l'utilisateur : en tournant trop vite, le robot perd la localisation. Cause : un tour du LD06 dure 0,1 s ; à 90°/s le robot tourne de 9° pendant un seul tour, le tour est donc déformé (≈45 cm à 3 m) et le recalage point-vers-droite le refuse. Reproduit en simulation (`tests/test_recuperation.py`, tour généré rayon par rayon avec le robot en rotation) : à 150°/s l'orientation dérive de 21° sans correction.

Corrections : `suivi_lidar.corriger_mouvement` (chaque point est ramené à l'instant de fin de tour avec la vitesse estimée par l'historique de poses, puis une seconde passe avec la vitesse mesurée par le premier recalage) appelée par `CarteDirecte.traiter` ; curseur « Rotation maximale » (60 % par défaut) dans le Pilotage. Résultat simulé : erreur d'orientation maximale 1,5° à 150°/s. Difficulté : les tours simulés des anciens bancs de test sont instantanés (sans déformation), donc le redressement les dégrade légèrement (1,26° au lieu de moins de 1° sur le demi-tour continu) ; le seuil du test a été relevé à 1,5° avec un commentaire. Limites : redressement valable si l'ordre des points est celui de la mesure et la vitesse à peu près constante ; non essayé sur le robot réel (l'angle réel de rotation par pourcentage de puissance n'est pas calibré).

Validation : 218 tests réussis.

## 4 novembre 2026 — Déconnexions en boucle, scans douteux, Position 360°

Constat (journaux de l'utilisateur, Wi-Fi comme USB) : le robot se déconnecte et se reconnecte en boucle. Le firmware n'a pas redémarré (les numéros de séquence continuent d'une session à l'autre) et le flux est sain jusqu'à l'arrêt brusque. Cause : le « bail » de 300 ms. Un seul trou de 300 ms dans les commandes (Wi-Fi qui cale 0,6 à 1,8 s, port USB occupé) fermait **toute la session** : flux de scans coupé, propriétaire libéré, et en USB retour à 115200 alors que le PC parlait encore à 921600, donc plus aucun dialogue possible. Une nouvelle session d'un autre jeton recevait « BUSY » tant que l'ancienne vivait, et l'envoi d'une trame TCP abandonnait après 300 ms.

Corrections (firmware `protocol.h`, `ScanAtlas_WiFi.ino`, `usb_live.h`) : 300 ms coupent seulement les moteurs, la session vit 6 s ; première commande après un trou appliquée comme STOP ; une session muette depuis plus d'une seconde est remplacée par une nouvelle demande ; envoi TCP jusqu'à 2 s ; en USB le débit n'est plus remis à 115200 à chaque remplacement. PC : attente jusqu'à 5 s (au lieu de 2 s), poignée de main USB qui essaie 115200 puis le débit rapide, pauses notées dans `evenements.log`. La reconnexion automatique est reprogrammée si le calcul précédent finit encore (avant, elle était abandonnée sans message, d'où certaines reconnexions qui ne partaient pas ; un test intermittent l'a révélé).

Scans qu'il ne faudrait pas prendre, autour des reconnexions : après une position retrouvée, une reprise ou un trou de plus de 0,6 s, la carte n'est enrichie qu'après 3 tours suivis normalement (`PROBATION_SCANS`).

« Position 360° » : après une recherche globale, le suivi continuait avec la référence locale de l'ancien endroit (14 m autour du dernier scan clé) et reperdait le robot, et le bouton décochait en plus clavier et manette. La confirmation et le suivi se font maintenant sur la carte autour de la position trouvée, et les cases ne sont plus décochées par aucun arrêt (clavier et manette actifs d'emblée ; B n'arrête que tant qu'il est tenu).

Difficulté : plusieurs tests d'interface intermittents sous écran virtuel (lecture du focus Tk qui lève `KeyError`, calcul précédent encore vivant) ; la lecture de l'onglet est séparée de celle du focus et la reconnexion retentée. Validation : 224 tests réussis (14 exécutions successives des tests de pilotage et de reconnexion). **Non essayé sur le robot** : il faut reflasher le firmware ; la machine d'analyse n'atteint pas 192.168.4.1.

## 4 novembre 2026 — Démonstration impossible à quitter, onglets lents

Démonstration : le bouton lançait un robot simulé et réglait l'adresse sur 127.0.0.1, mais rien ne permettait d'en sortir : le processus restait actif, l'adresse du vrai robot était perdue et la carte simulée restait en place (un vrai robot connecté ensuite était localisé dans la carte de la démonstration). Désormais le bouton devient « Quitter la démo » ; « Déconnecter » en sort aussi. La sortie arrête le robot simulé, rend la liaison, l'adresse et la carte d'avant. Une connexion différée de 0,8 s est ignorée si on a déjà quitté.

Lenteur : mesures sous Linux avec écran virtuel. Démarrage ≈ 2,4 s (imports 1,3 s, construction de la fenêtre 1 s) ; ouverture d'un onglet ≤ 0,3 s à vide. Avec 150 scans chargés, l'onglet Cartographie coûtait 1,2 s à chaque affichage et l'ajout des scans 1,4 s : un nuage, une flèche et une ligne de légende par scan (600 dessins de collections, 300 éléments de légende). Au-delà de 25 scans visibles, le nuage est dessiné en un bloc (une case de 3 cm par point, une seule série de flèches, pas de légende) : 0,27 s et 0,35 s. Le plus gros du coût était donc le dessin Matplotlib, pas Python. Non mesuré sous Windows (antivirus, premier lancement avec construction du cache de polices Matplotlib).

Validation : 225 tests réussis.

## 4 novembre 2026 — Passage à une interface web (branche `claude/interface-web`)

Demande de l'utilisateur : une application plus finie, plus facile à prendre en main, sobre et avec une direction artistique, sans doublons ; passer sur le web si c'est plus performant. Décision : le calcul reste en Python (numpy / scipy : ICP, localisation globale) et l'interface devient une page servie en local ; Tkinter et Matplotlib disparaissent. Raisons : démarrage et changement d'écran instantanés (plus de figures Matplotlib reconstruites), dessin sur canvas 2D (milliers de points sans coût par scan), manette lue par le navigateur (Gamepad API), et une seule interface à maintenir.

Direction artistique « relevé » : papier chaud, encre bleu-nuit, un seul accent vert d'eau, chiffres en police à chasse fixe, thème sombre automatique, aucune dépendance externe. Deux écrans seulement (Direct, Carte) contre cinq onglets. Doublons supprimés : un seul réglage de connexion, un seul arrêt, un seul « Me retrouver », une seule carte (Acquisition et Capture directe = Direct ; Nuages, Grille, Segments, Carte vectorielle = couches de Carte ; Localisation = recalage dans l'inspecteur + assemblage).

Architecture : `serveur.py` (HTTP 127.0.0.1, vérification de `Host`, jeton aléatoire, flux SSE), `session_directe.py` (ex-logique de l'espace Robot, sans interface), `document_carte.py` (carte unique partagée par le direct et l'atelier). Voir `docs/GUIDE_WEB.md`.

Difficultés et défauts trouvés par les nouveaux tests :
- Une consigne `NaN` envoyée au pilotage était « bornée » par `min(1, nan)` à +1, soit pleine vitesse avant : refus des valeurs non finies avant de borner (serveur et conversion en pourcentages).
- Course entre `connecter` et le lancement du calcul si on se déconnecte aussitôt (thread de calcul avec `robot = None`) : le lancement est abandonné si le robot a disparu.
- Processus du robot simulé non attendu à la sortie de la démonstration (zombie) : attente dans un fil.
- Interface : valeurs de position qui passaient à la ligne, texte de manette trop long, échelle recouverte par la barre d'outils, champ vide sans fond sur la grille : corrigés après captures d'écran dans Chromium (clair, sombre, mobile).

Tests : suppression des tests Tk (interface, apparence, pilotage combiné, manipulation à la souris, acquisition USB par onglet) ; conservation de tous les tests de calcul, de protocole, de firmware et de récupération ; ajout de `test_serveur.py` (sécurité, API carte, import, tâches, verrou, flux), `test_session_directe.py` (reconnexion, démo quittable, pilotage périmé = arrêt), `test_navigateur.py` (clavier, carte dessinée, démo depuis l'interface). Le clavier est maintenant testé dans le navigateur, plus en Python.

Limites : **non essayé sur Windows ni avec le vrai robot** ; la manette via le navigateur n'a pas été essayée avec une vraie manette (la logique de zone morte et de boutons suit l'ancien module) ; le rendu a été vérifié sous Chromium Linux seulement. Le firmware (délai de bail, session de 6 s) doit toujours être reflashé.

## 4 novembre 2026 — SLAM automatique, replacement guidé, couches dans le direct

Demande : le plus important est le SLAM manuel **et automatique** (le robot se déplace seul pour scanner la pièce), avec vues points / grille / carte vectorielle, de l'optimisation, et la possibilité de **donner un point et une direction approximatifs** quand le robot est perdu.

Optimisation d'abord : le plus proche voisin (`localisation.plus_proches`) était un calcul brut par blocs. Remplacé par un arbre k-d (SciPy) dont l'arbre est gardé pour la dernière référence : la recherche de position sur la carte (« Me retrouver », replacement) passe de 5 à 10 s à environ 0,6 s ; la suite de tests passe de 60 à 50 s. Défaut trouvé au passage : dans `localisation_globale`, le rayon de la recherche élargie était écrasé par la portée du lidar, si bien que la « recherche près de la dernière pose » cherchait en réalité partout ; corrigé, et le quadrillage des positions est maintenant centré sur le point donné (le point lui-même est toujours testé).

Replacement guidé : `CarteDirecte.replacer(x, y, cap)` limite la recherche à 1 m et ±50° autour de l'indice, confirme par la géométrie locale (75 % à 12 cm, RMSE 10 cm), passe en vérification de 3 tours comme les autres récupérations, et abandonne l'indice après 5 essais ou 12 s (la récupération habituelle reprend). Interface : bouton *Replacer*, clic + glisser pour la direction, proposé automatiquement quand la position est perdue. Simulation : indice faux de 64 cm et 30° → position exacte retrouvée à 1,3 cm / 0,1° ; cap faux de 170° ou point à l'autre bout de la salle → refusé, la carte n'est pas faussée.

Exploration autonome (`exploration.py`) : frontières sur la grille d'occupation de la carte directe, plus court chemin (Dijkstra SciPy, coût qui préfère le milieu des passages, distance de sécurité de 26 cm), raccourcis en ligne droite, pilotage holonome sans rotation, vitesse réduite près des obstacles et de la destination, repoussement latéral, couloir d'arrêt devant le robot lu directement dans le lidar. Quand plus aucune frontière n'est atteignable : « Exploration terminée ». Surveillances : robot immobile (autre destination, puis arrêt après 3 essais) et robot qui va dans une autre direction que celle commandée (arrêt avec message : sens des moteurs ou orientation du lidar). Toute commande manuelle, Espace, Arrêt, déconnexion ou nouvelle carte arrête l'exploration. Position perdue : le robot s'arrête et cherche ; 45 s sans retrouver → arrêt.

Banc d'essai (`simulation.py`, temps simulé, glissement aléatoire des roues, collisions) : deux pièces reliées par une porte de 1 m avec un meuble — exploration complète en 47 s à 60 % de puissance (18 s à 100 %), écart de suivi maximal 2,6 cm (4,5 cm à 100 %), jamais plus près d'un mur que 23 cm ; salle de 20 m × 12 m en 58 s, planification 10 ms en moyenne ; salle simple avec mur en L en 16 s ; départ presque dans un coin possible. Chaque tour est traité en 4 ms en moyenne (29 ms au pire).

Difficultés : (1) la première salle de test avait un mur plein à la place de la porte (le robot concluait à juste titre que la pièce était fermée) ; (2) le premier évitement regardait un cône de ±50° et ralentissait le robot le long d'un mur à 25 cm : remplacé par le couloir balayé (largeur du robot) ; (3) une exploration terminée immédiatement dans la salle de démonstration était un faux « bloqué » dans un test, qui demandait une salle où il reste des zones à voir ; (4) une consigne NaN (corrigée plus haut) aurait été lue comme pleine vitesse.

Interface : couches Points / Occupation / Plan dans le direct (grille demandée au serveur seulement si affichée et si la carte a changé, réponses compressées), chemin, destination et zones à voir tracés pendant l'exploration.

Limites : **exploration et replacement non essayés sur le vrai robot** ; la puissance minimale pour avancer, le rayon réel du châssis (`RAYON_ROBOT`, `DISTANCE_ARRET`), le sens du sway et l'orientation du lidar sont à vérifier ; pas de fermeture de boucle (la carte est stabilisée par le recalage sur la carte entière, pas par un graphe de poses) ; les portes vitrées et les surfaces que le lidar traverse ne sont pas gérées ; l'exploration ne cherche pas le chemin de retour au point de départ.

Validation : 190 tests réussis.

## 4 novembre 2026 (après-midi) — grande salle simulée

Demande : pas de robot sous la main, donc une pièce simulée plus grande, avec meubles, tables, couloir.

`simulation.py` : trois constructeurs (`rectangle`, `polygone` pour les meubles ronds, `cloison` avec ouvertures pour les portes) et un registre `SALLES`. Nouvelle salle **appartement** de 16 m × 10 m : salon, cuisine, couloir de 16 m, bureau, chambre et salle de réunion ; trois portes sur le couloir, une porte bureau/chambre (donc une boucle), une ouverture salon/cuisine ; canapé, tables, chaises, bibliothèque, îlot, plan de travail, armoires, lit, plantes, deux piliers, une table ronde ; passages de 90 cm au plus étroit, interstices de 40 cm infranchissables (le robot les voit sans pouvoir y entrer). `simuler_robot_wifi.py --salle ...`, `/api/demo {salle}` et une liste de salles dans l'interface (écran d'accueil et menu de connexion, synchronisées, mémorisées dans le navigateur) ; l'appartement est la salle par défaut. `distance_aux_murs` est vectorisée (118 segments dans l'appartement) ; un tour de lidar simulé coûte 2,7 ms.

Résultat en boucle fermée, 60 % de puissance, glissement aléatoire des roues : exploration complète en 353 s simulées (47 s de calcul pour les 3 500 tours), « Exploration terminée » de lui-même, erreur de suivi maximale 3,2 cm, jamais plus près d'un mur que 22 cm, 90 % des points à plus de 20 cm d'un mur observés (le reste est l'intérieur des meubles). À 100 % de puissance l'exploration complète dure environ 3 min simulées et l'erreur de suivi monte à 9 cm en pointe (virage près de la grande table), puis revient à 3 cm : pas de dérive cumulée, mais c'est une raison de plus de rester à 40–60 % sur le vrai robot. Comparée au vrai plan, la carte colle à quelques centimètres près. Dans l'application, en temps réel, le robot a traversé le couloir et atteint la cuisine (x = 12 m) en 75 s.

Difficultés : les tests de la session et du navigateur qui explorent « la salle de démonstration » dépendaient de la petite salle ; ils la demandent maintenant par son nom (l'appartement ne tiendrait pas en temps réel dans un test). Deux valeurs attendues fausses dans mon test du lidar (rayon qui rase le bord d'un pilier ; table basse sur la trajectoire) : c'était le test qui avait tort, pas la simulation.

Tests : `tests/test_exploration.py` (sortie du salon par la porte ; exploration complète de l'appartement avec `SCANATLAS_LENT=1`, 36 s), `tests/test_simulation.py` (constructeurs, départ dégagé de chaque salle, **toutes les pièces atteignables depuis le départ** avec la marge de sécurité de l'exploration, collisions, distances lidar), choix de salle dans la session et le navigateur.

## 4 novembre 2026 (soir) — gel après ~100 scans, déconnexions, segments superposés, points périmés, carte unique

Retour d'essai : à partir de ~100 scans clés ça commence à freezer, vers 230 le robot se déconnecte (« même en simulation »), beaucoup de segments se superposent dans la carte vectorielle, il faut retirer les points rendus obsolètes par un nouveau scan, et une seule carte doit être ouverte dans tous les onglets.

Diagnostic (reproduit en temps réel : application complète, processus du robot simulé, sockets ; échantillonneur d'arrêts côté PC, traces côté robot) :
- Le traitement d'un scan ne prenait que 3 à 6 ms et il n'y avait aucun retard de file : ce n'était pas une surcharge de calcul au sens habituel. Le PC *s'arrêtait* 100 à 320 ms par moments (82 arrêts de plus de 100 ms en 8 minutes), la boucle de commande n'envoyait plus rien pendant plus de 300 ms, et le robot simulé coupait alors toute la session (« Flux lidar fermé ») : 3 à 5 déconnexions en 8 minutes.
- Cause principale : le journal réécrivait **toute** la session de secours (tous les scans clés, `json.dumps` qui tient le GIL) à chaque scan clé, dans le fil de calcul : 59 des 82 arrêts. Coût proportionnel au nombre de scans, donc l'apparition du gel vers 100 scans et des coupures vers 230.
- Cause secondaire : un scan clé coûtait 97 ms en moyenne et jusqu'à 230 ms en fin d'exploration (plus que la période du lidar de 100 ms), dominé par la fusion des segments (≈ 1000 appels du test `proches` par scan clé, en Python) et par `np.unique(axis=0)` sur la carte de points.
- Aggravant : un scan clé toutes les 2 s même robot immobile (65 scans clés en 140 s à l'arrêt).
- Défaut du simulateur : il coupait la session à 300 ms de silence, alors que le firmware ne coupe que les moteurs à 300 ms et la session à 6 s (`protocol.h`). Le simulateur suit maintenant le firmware (reprise de session possible après 1 s de silence).

Corrections : journal entièrement dans un fil d'écriture, session de secours écrite scan par scan, au plus toutes les 20 s et à la fermeture ; préfiltre vectorisé des segments voisins (le test exact ne passe plus que sur quelques candidats) ; `reduire` sur clé entière ; plus de scan clé à l'arrêt ; intervalle de commutation des fils réduit à 2 ms dans le serveur ; carte et segments retirés quand ils sont traversés par de nouveaux rayons.

Mesures : coût d'un scan clé 97 → 38 ms en moyenne et **constant** quelle que soit la taille de la carte (il montait à 230 ms) ; application réelle en temps réel dans l'appartement, 8 minutes, 426 scans clés : **0 déconnexion** (3 à 5 avant), 0 arrêt du PC de plus de 100 ms (82 avant, jusqu'à 320 ms), retard de file au plus 1 scan. Exploration complète équivalente (quatre départs : 1296 s avant, 1337 s après avec des scans clés tous les 25 cm, puis 1338 s avec les seuils de 15 cm / 5° réadoptés ; 4 à 6 cm d'erreur de suivi, même qualité).

Segments superposés : l'onglet Carte recalculait le plan depuis **tous** les scans clés (`carte_vectorielle`, 18 s pour 250 scans, sur le fil du serveur) et, avec un bruit de 1,2 cm comme un vrai LD06, doublait 159 m de segments sur 232 m ; la carte fusionnée du direct n'en double que 16 m sur 151 m. L'écran Carte affiche maintenant la carte fusionnée du direct (nuage, segments, grille) tant que le document n'est pas modifié : une seule carte pour tous les onglets, rien à recalculer, plus de traits épais. Le rechargement de l'écran Carte est limité à une fois par seconde pendant qu'une carte se construit.

Points périmés : un point de la carte dont la cellule de grille est repassée sous le seuil libre (−0,8 de log-odds) après de nouveaux rayons est retiré ; même règle pour un segment dont la moitié des mesures sources est périmée. Test : un meuble ajouté puis retiré disparaît de la carte (31 points restaient sans cette règle, 0 avec), les murs ne sont pas grignotés.

Limites : mesures faites sur ce PC de développement (2 cœurs) ; la machine de l'utilisateur, plus lente, n'est pas mesurée mais le coût est maintenant constant. Le simulateur de bruit (1,2 cm) est un réglage, pas une mesure du vrai LD06. Le seuil de péremption peut effacer un vrai mur vu une seule fois en rasant puis traversé par des rayons voisins ; il est réécrit au scan suivant qui le voit.

Retours du même essai, **notés mais pas traités** (à reprendre ensuite) :
1. Déconnexions encore présentes sur le vrai robot : `[WinError 10051]` (réseau inaccessible) pendant la reconnexion, essai 6/8. À investiguer côté Windows et Wi-Fi (changement de réseau, adaptateur) avec un nouvel `evenements.log`.
2. Message « Le robot ne va pas dans la direction commandée (écart de 89°) » : sens des axes du châssis ou orientation du lidar (la détection d'exploration a fonctionné comme prévu).
3. Yaw pur : seuls les moteurs d'une diagonale devraient tourner ; actuellement les quatre tournent et le robot pivote sur un cercle d'environ 50 cm de diamètre au lieu de sur place (firmware / cinématique à revoir).
4. Exploration : le robot va trop vite ; envisager des étapes de 50 cm avec scan, en gardant la localisation pendant le déplacement. Précision de l'utilisateur : la carte peut être construite en continu si le coût est maîtrisé (c'est le cas maintenant : scans clés tous les 15 cm / 5°).

Validation : 216 tests réussis (nouveaux : `tests/test_charge_carte.py` — `reduire`, préfiltre, scans clés à l'arrêt et en mouvement, points périmés, journal hors du chemin critique, carte unique).

## 4 novembre 2026 (16 h) — le suivi se perdait tout le temps sur le vrai robot : régression de ma correction du gel

**Constat (journaux du robot).** Jusqu'à 15 h 51 presque toutes les sessions étaient à ~100 % de scans acceptés. Après l'installation de la correction du gel (fb74c77), plusieurs sessions tombent à 13–53 % : « Suivi actif » / « Suivi perdu » en boucle, `Recalage refusé : 88 % à 12 cm, RMSE 0.101 m, déplacement 0.00 m`, robot immobile.

**Méthode.** Les journaux contiennent les tours bruts : je les rejoue dans `CarteDirecte` avec l'horloge du lidar (`perf_counter` remplacé par `fin_us`), ancien code (5deb327) contre nouveau. Résultat identique à ce que l'utilisateur voit : ancien 93–96 %, nouveau 14–27 %. Sans cette horloge, le rejeu est faux (les attentes de 0,5 s entre essais ne passent jamais).

**Cause.** Le lidar en câble ne donne que ~261 points par tour (1,4°, 58 ms). Ma correction supprimait les scans clés à l'arrêt (pour ne pas gonfler la carte). La référence du suivi restait alors un seul tour clairsemé ; or la validation du recalage mesure la distance de chaque point au *point de référence le plus proche* : un point exact du mur, tombé entre deux points de référence (20 cm et plus à 8–12 m, ou en rasant un mur), paraît à plus de 12 cm. 11–15 % de points hors tolérance suffisent à faire dépasser RMSE 0,10 m, et le suivi est refusé à l'arrêt. Ma simulation (450 points, bruit 3 mm) ne pouvait pas montrer ce défaut.

**Correctifs.**
1. `cartographie_direct.py` : à l'arrêt, jusqu'à `STATIQUES_MAX = 12` scans clés espacés d'1 s (densification), puis plus aucun tant que le robot ne bouge pas. La carte ne grossit donc pas pendant une pause (le gel venait de la croissance sans fin), mais la référence est assez dense. Compteur remis à zéro par un scan clé en mouvement.
2. `suivi_lidar.py` : `ecart_a_la_reference` : l'écart d'un point est le minimum de la distance au point le plus proche (diminuée de la moitié de l'espacement local au-delà de 5 cm) et de la distance à la droite locale du mur. Une carte dense n'est pas touchée.
3. Les points périmés (SEUIL_PERIME) ne sont pas en cause : taux d'acceptation identique avec ou sans sur les vraies données.

**Mesures (rejeu des vraies sessions).** 15 h 56 : 35 % → 96 % ; 15 h 59 : 14 % → 96 % ; 16 h 01 : 21 % → 99 % ; 15 h 59 (démarrage seul, 9 s) : 6 % → 75 % ; longues sessions qui marchaient : 93–100 % conservés avec 5 fois moins de scans clés (2309 tours : 140 → 30).

**Tests.** `tests/donnees/lidar_cable_arret.jsonl.gz` (330 vrais tours) + `ToursReels` (échoue à 39 % sur fb74c77), `LidarClairseme` (simulation 261 points), `SalleVirtuelle(points=, duree_tour=)`. 219 tests OK.

**Leçon.** Valider sur les vrais journaux avant de pousser : une simulation propre ne remplace pas le rejeu de tours réels. Le rejeu est maintenant un outil du dépôt : `python outils/rejouer_journal.py <tours.jsonl>`.

**Reste à traiter.** Démarrage à froid : les 5–10 premières secondes restent fragiles (75 %) ; déconnexions Wi-Fi (`WinError 10051`, « Pause de 1–2 s sans scan »), écart de 89°, dérive du sway, vitesse d'exploration.

## 4 novembre 2026 (17 h) — gel toutes les 5 s, vecteurs superposés, TP intégrés à la version web

**Retour de l'utilisateur** (scan `scanenautonomie.json`) : « beaucoup mieux » ; reste un gel environ toutes les 5 s (le robot s'arrête, il faut relâcher puis réappuyer la commande ; après le gel il est un peu perdu mais se retrouve vite) ; carte vectorielle avec beaucoup de vecteurs superposés ; demande d'intégrer aussi les TP précédents dans la version web.

**Gel : le lien Wi-Fi est coupé 0,5 à 4 s.** Dans les vrais journaux, les acquittements UDP et les scans TCP s'arrêtent *ensemble* pendant 0,5 à 4 s, aussi bien à l'arrêt qu'en mouvement ; avec le câble USB il n'y en a aucune. Cause probable : balayage / itinérance de la carte Wi-Fi de Windows, ou coexistence radio. Ce n'est pas corrigeable côté logiciel. Ce qui l'est : le comportement après la coupure. (1) Le suivi tolère maintenant un trou jusqu'à `TROU_MAX = 8 s` et lance tout de suite une recherche large au retour du lien au lieu de se déclarer perdu. (2) Critère d'acceptation du suivi corrigé : accord à 12 cm ≥ 75 % **et** RMSE des points concordants ≤ 6 cm (`rmse_fin`), au lieu du RMSE global qui refusait de bons recalages à cause de quelques points isolés. (3) Diagnostics dans le journal : PC réactif ou bloqué pendant la pause, signal et canal Wi-Fi. (4) Simulateur : option `--coupures` qui reproduit ces coupures.

**À tester sur le robot :** `ping -t 192.168.4.1` pendant un gel (pertes ou pas) ; carte Wi-Fi de Windows : agressivité d'itinérance au minimum, économie d'énergie désactivée ; essai en USB ; autre canal. Le reflash du firmware n'est pas nécessaire pour ces changements.

**Non expliqué :** pourquoi il faut relâcher puis réappuyer la touche. Le firmware traite volontairement la première commande après une coupure comme un STOP (`resumed`), ce qui explique un arrêt ; dans le simulateur et Chromium le clavier reprend tout seul, donc le cas réel (focus, manette, comportement de l'ESP) reste à décrire précisément.

**Vecteurs superposés.** Les segments sont fusionnés quand angle < 8°, distance < 25 cm, résidu p90 < 8 cm (`FUSION_*`) ; sur la carte de l'utilisateur 416 / 808 segments → 144–169. L'onglet Carte d'une session importée de plus de 30 scans affiche la vue fusionnée (reconstruction 92 s → ~16 s) jusqu'à la première modification.

**TP intégrés.** Écran Carte : menu *Recalage sur…* (toute la carte, ou grille / plan / scan × locale / multi-résolution, point de départ = pose actuelle) et bouton *Évaluer les méthodes (TP)* (42 essais, tableau de synthèse, CSV). Backend : `DocumentCarte.localiser_tp` et `evaluer_tp`, points d'accès `/api/carte/localiser`, `/api/carte/evaluer_tp`, `/api/carte/evaluation_{synthese,essais}.csv`. Le banc ne modifie pas la carte. Tests : `tests/test_tp_web.py` et un parcours navigateur.

**Reste à traiter.** `WinError 10051` / reconnexion, écart de 89° (orientation du lidar), dérive du sway, vitesse d'exploration / pas de 50 cm, démarrage à froid (~75 % les premières secondes), perte longue après coupure avec forte rotation (~120°/s). Rien de tout cela n'est validé sur mouvement réel du robot.

## 4 novembre 2026 (18 h) — rangement du dépôt, README, versions expliquées, onglet « Le projet » complété

**Demande de l'utilisateur :** ranger le dossier ; un README qui explique comment utiliser le projet et quel fichier lance l'application ; donner accès à la version `main` d'avant le web (le professeur a accès au dépôt et pourra la télécharger) en expliquant clairement ce qui est quoi ; dans l'onglet « Le projet » (écrit en premier jet par ChatGPT), expliquer le fil de la réflexion, les buts, les problèmes et les solutions.

**Rangement.** `docs/` : guides actuels à la racine (`GUIDE_WEB`, `REPRISE_PROJET`, `JOURNAL_PROJET`, `GUIDE_GITHUB`), méthodes du TP dans `docs/methodes/`, anciens modes d'emploi Tkinter dans `docs/archives_tkinter/`, `docs/README.md` comme index ; tous les liens internes recalculés et vérifiés (aucun lien cassé). `Cartes/README.md` et `exemples/README.md` décrivent chaque fichier. Voir plus bas (18 h 15) pour le rangement du code Python.

**Lancement.** `lancer_windows.bat` crée l'environnement et installe les dépendances au premier lancement (il remplace `installer_windows.bat` et `DEMARRER.txt`, supprimés) ; `lancer_mac_linux.sh` fait la même chose ailleurs (testé : le serveur démarre et répond). `.gitattributes` impose les fins de ligne CRLF aux `.bat` et LF aux `.sh` : un ZIP téléchargé depuis GitHub gardait sinon des `.bat` en LF, qui peuvent mal gérer les étiquettes `goto`. Le `.bat` n'a pas pu être essayé sous Windows.

**README et versions.** Le README décrit les trois branches : `main` (première version complète, Tkinter, TP Jour 1 et 2), `claude/commandes-combinees` (Tkinter la plus avancée) et `claude/interface-web` (version finale), avec liens, ZIP, commandes `git`, démarrage sans robot en 2 minutes et avec robot. Les README de `main` et `commandes-combinees` reçoivent un encadré qui renvoie vers la version finale.

**Onglet « Le projet ».** Ajouts : les buts (TP, but personnel, critères de réussite, ordre de travail), les trois versions du dépôt, l'exploration autonome et le replacement, un tableau problème → cause → solution → résultat pour tout ce qui a été trouvé sur le vrai robot (suivi perdu, rotation rapide, déconnexions, gel, vecteurs superposés, régression du suivi, coupures Wi-Fi), le « cas à retenir » (une simulation propre ne remplace pas de vraies données), la suite, le bilan mis à jour. Retiré : le lien « Principes Cartographer » (consigne du dépôt : pas de projet extérieur comme source d'inspiration) et la référence à un commit. Les chiffres reprennent ceux de ce journal ; rien de nouveau n'a été mesuré.

**Limites.** Le gel Wi-Fi de 5 s n'est toujours pas corrigé ; le `.bat` n'est pas essayé sous Windows ; la page n'a été vérifiée que sous Chromium (bureau et téléphone, sans erreur JS).

## 4 novembre 2026 (18 h 15) — code Python rangé dans le paquet `atlas/`

**Demande :** ne pas laisser vingt-cinq fichiers Python à plat à la racine. **Fait :** paquet `atlas/` en quatre dossiers (`application/` serveur et carte partagée ; `robot/` liaisons, session, journaux, exploration ; `calcul/` SLAM, localisation, TP ; `simulation/` salles et robot simulé). Déplacement par `git mv` (l'historique de chaque fichier est conservé), imports réécrits en absolu (`from atlas.calcul import cartographie`), y compris dans les tests et `outils/`, et dans les chaînes de `patch('atlas.calcul.cartographie.…')`.

**Trois points qui dépendaient de l'emplacement des fichiers :** le dossier `web/` est retrouvé depuis la racine du dépôt (`serveur.py`) ; le robot simulé de la démonstration est lancé par `python -m atlas.simulation.simuler_robot_wifi` avec la racine comme dossier de travail (il était lancé comme un script à côté de `session_directe.py`) ; le test d'évasion hors du dossier web vise maintenant `scanatlas.py`. Commandes changées : `python -m atlas.calcul.evaluer_tp_jour2` et `python -m atlas.simulation.simuler_robot_wifi` (les scripts de `outils/` ne changent pas). Les anciennes entrées de ce journal citent les anciens emplacements des fichiers.

**Validation :** 231 tests réussis (dont le navigateur et la démonstration, qui lance le sous-processus), scripts d'`outils/` importés sans erreur, serveur lancé depuis `scanatlas.py` (HTTP 200). Les résultats d'`exemples/` régénérés par ces essais ont été remis tels quels.

## 4 novembre 2026 (19 h 15) — Connecter, Espace, scan manuel, import de scan

**Remarques de l'utilisateur après ses essais (« ça marche plutôt bien ») :** le bouton *Connecter* de l'accueil ne faisait rien (il fallait passer par le menu), *Espace* ne servait à rien, il voulait pouvoir prendre des scans à la main depuis le web, puis : un scan importé s'importe mais ne s'affiche pas (ou clignote).

**Connecter.** Le clic sur le bouton de l'accueil remontait jusqu'à l'écouteur qui referme le menu de connexion ; le bouton ne se connecte plus via le menu mais directement (`connecter()`), affiche la liaison actuelle et « régler la liaison » ouvre le menu.

**Espace.** Deux causes : l'événement était ignoré dès que le focus était sur un curseur (Puissance, Rotation max), et la répétition automatique d'une touche tenue (Z) relançait la consigne juste après l'arrêt. `arretUrgence()` coupe tout, verrouille les touches encore tenues jusqu'à leur relâchement et prévient le serveur ; le bouton Arrêt passe par la même fonction ; le serveur confirme l'arrêt dans le bandeau (sauf lors d'un simple changement d'écran, `silencieux`).

**Scan manuel.** Bouton *Prendre un scan* (`POST /api/scan`) : `CarteDirecte.demander_scan_manuel()` fait du prochain tour un scan clé à la position suivie, quel que soit le mode ; refusé si le robot n'est pas connecté ou la position pas suivie, abandonné après 4 s sans suivi. Nommé « Manuel n / séquence ». Dans la simulation parfaite, un robot immobile n'est pas « suivi » (trop peu de points de droite communs avec une carte d'un seul scan) : les tests le font rouler un peu. Sur le vrai lidar bruité, ça n'a pas été constaté.

**Import de scan.** Reproduit en test : l'événement « document » (SSE) arrive avant la fin de la requête d'import et recharge la carte pendant que la vue n'était pas encore à recadrer ; le recadrage n'avait lieu que si la version de la carte changeait, donc jamais après. Le scan était bien dans la carte mais hors écran. Corrigé : le recadrage ne dépend plus du changement de version, et les rechargements qui se croisent sont ordonnés (seul le dernier compte). La barre d'outils du bas se replie maintenant sous le pavé de pilotage au lieu de passer dessous. Tests : session (scan manuel en Localiser, refus sans robot, abandon), navigateur (Connecter, Espace avec focus sur un curseur et touche tenue, bouton Prendre un scan, import lointain avec réponse retardée).


## 4 novembre 2026 (20 h 55) — Espace retiré, historique des jours 1-2 restauré, l'énoncé dans le compte rendu

**Espace retiré.** Le robot s'arrête de lui-même dès qu'il n'y a plus de commande (la consigne n'est valable que 0,35 s), donc la touche Espace ne servait à rien. Il reste *Échap* et le bouton **Arrêt** (`arretUrgence()`, inchangé). README, guide web et tests mis à jour.

**Historique des jours 1 et 2.** Le vrai historique (34 commits, 2 et 3 novembre) n'était plus sur GitHub : `main` y avait été remplacée par la refonte du 4 novembre (branche sans parent). Il est restauré tel quel dans la branche **`jours-1-2`**, avec un README ajouté qui donne un tableau « étape de l'énoncé → fichiers → commits » et situe les quatre branches. Aucun commit d'origine n'a été modifié ; seul le README est ajouté par-dessus.

**Compte rendu (`web/presentation.html`).** Nouveau chapitre « L'énoncé » : les 12 étapes du TP (Jour 1, Jour 2, Jour 3 et bonus) avec ce qui a été fait, où le trouver dans `jours-1-2` et où c'est dans la version finale. Le bloc des versions passe à quatre cartes. Sections renumérotées (02 à 06).

**Captures de la version Tkinter.** Faites sur le PC de l'utilisateur (Tkinter n'existe pas dans l'environnement de travail) avec le dossier `commandes-combinees` : nuages, grille, segments, carte vectorielle, localisation, direct. Cinq sont dans le compte rendu (`web/presentation-assets/tk-*.webp`), étiquetées réel ou simulation. Le dossier de travail `captures_tk` est resté sur le PC (exclu de git en local).

**Limites à dire.** La carte de la salle de classe (Jour 3) n'a pas de mesure de précision indépendante. La capture de localisation est recadrée. Les tests de la branche `jours-1-2` n'ont pas été relancés ici.

## 4 novembre 2026 (21 h 30) — dépôt remis au clair : `main` = version web

Demande de l'utilisateur : que le dépôt soit lisible et qu'on ne puisse pas se tromper. `main` (branche par défaut) devient la **version finale web**. Les anciennes versions Tkinter ne sont pas perdues : l'ancienne `main` devient l'branche `version-2-refonte-tkinter`, la branche `claude/commandes-combinees` l'branche `version-3-tkinter-avancee`. La branche `jours-1-2` (historique réel des jours 1 et 2) reste une branche. Les branches `claude/interface-web` et `claude/commandes-combinees` sont supprimées. README, compte rendu et documents mis à jour avec ces noms.

## 17 novembre 2026 — les deux versions réunies dans `main`

Demande : que le professeur ait accès aux deux versions (web et Python) et que tout soit clair. La version Python (Tkinter, état de `version-3-tkinter-avancee`) est copiée dans le dossier `version_python_tkinter/` de `main` : elle s'y lance toute seule (`installer_windows.bat`, `lancer_windows.bat`), sans changer de branche. Le README de `main` s'ouvre par un tableau « Pour le professeur » (A : web à la racine, B : Python dans son dossier, historique des jours 1 et 2 dans la branche `jours-1-2`). Un encadré en tête du README du dossier renvoie vers la version web. Le compte rendu (« Le projet ») cite le dossier au lieu de la branche. Vérifié : les 75 tests de ce dossier qui n'ont pas besoin de Tkinter passent ; 18 fichiers de tests n'ont pas pu être chargés ici parce que Tkinter n'est pas installé dans l'environnement de travail (donc ni l'interface ni ces tests n'ont tourné ici ; l'interface a été lancée sur le PC de l'utilisateur pour les captures).

## 22 novembre 2026 (21 h 30) — captures Tkinter refaites

Les captures « nuages, grille, segments, carte vectorielle » du compte rendu venaient de `scanmultiposition_ld06.json`, dont presque tous les scans avaient la pose (0, 0, 0) alors qu'ils avaient été pris à des endroits différents : tout se superposait à l'origine, d'où une carte illisible. Refaites avec `Cartes/session_ld06.json` (4 scans USB réels de la même pièce, pris au même endroit : la superposition au centre est correcte et on lit la pièce). Les légendes et le PDF sont mis à jour ; les chiffres cités sont ceux affichés par l'application (grille 260 × 289 cellules ; 48 segments de carte, 94 fusions, 19 coupes). Les captures « localisation » et « direct » n'ont pas changé.


## 22 novembre 2026 — relecture du rendu et rangement

L’utilisateur précise que `scanenautonomie.json` est le relevé de toutes les pièces et qu’il n’a plus accès au robot. Le compte rendu a été corrigé en conséquence : 736 scans, distincts de l’autre session semi-autonome de 578 scans. Les mentions « plusieurs pièces à valider » sont remplacées par une distinction entre résultat obtenu, précision non mesurée et répétabilité non évaluée.

Ajout d’une figure des 736 scans et de leurs poses enregistrées, sans recalage supplémentaire : 332 856 mesures après les filtres de session, affichage allégé à 39 442 points (carrés de 3 cm). La figure conserve les murs doublés et les points dispersés. La ligne relie des poses estimées ; ce n’est pas une mesure indépendante de la trajectoire. Script reproductible : `outils/produire_carte_finale.py`. Aucun fichier de mesure ni pose n’a été modifié.

Relecture du bilan dans un ton personnel, sans annoncer de nouveaux tests matériels. Clarification du banc simulé (deux scans, une seule géométrie, sans bruit ajouté), correction de l’ancienne numérotation des versions. README et index de données mis à jour. Les chiffres des temps publiés sont conservés ; la reproduction des 42 essais retrouve les mêmes réussites/refus/faux positifs.

Rangement : préparations locales `captures_tk/` déplacées dans `outils/captures_tk/`, chemin du script adapté, dossier ignoré par Git. Tentative de retrait des dossiers matériel vides restés à la racine (certains sont protégés par Windows et peuvent rester présents) ; les sources de référence restent dans `materiel/`. Ajout des index `outils/README.md` et `tests/README.md`. Les sessions et anciennes versions sont conservées à leur emplacement pour préserver les liens.

Validation avant modification : 238 tests exécutés, 15 échecs, 30 erreurs, 12 ignorés (222,8 s). Compilateur `g++` absent et refus réseau Windows 10013 dans l’environnement de relecture ; les tests de connexion expirent aussi. Les 45 tests du cœur du TP passent et les 42 essais sont reproduits. Ces limites ne sont pas présentées comme une validation du robot.


Finalisation : les dossiers matériel vides ont finalement pu être retirés avec les outils Windows après vérification qu’ils ne contenaient aucun fichier. Les explications repliées sont développées à l’impression. Tableaux ajustés au format A4, notes regroupées et pages numérotées ; PDF régénéré et contrôlé visuellement (26 pages). Le titre et les ajouts restent descriptifs, sans inventer de mesures ni de nouveaux essais.

Validation après modification : 238 tests en 224,7 s, avec les mêmes 15 échecs, 30 erreurs et 12 ignorés qu’avant. Les 45 tests ciblés du cœur du TP passent à nouveau ; syntaxe du JavaScript de présentation et liens locaux vérifiés. Aucun changement dans les acquisitions, le firmware ou les modules de calcul existants. Une archive du rendu est préparée à partir des fichiers suivis et des nouveaux fichiers utiles, sans environnements Python, caches ni captures de préparation ; l’historique Git reste accessible par le lien du README.


## 22 novembre 2026 — mieux expliquer les améliorations du SLAM

À la demande de l’utilisateur, le compte rendu détaille le nettoyage des anciens points contredits par des rayons libres, les segments périmés, la réduction de densité, les scans clés, les sauvegardes espacées dans un fil séparé et la densification limitée à l’arrêt. Les chiffres historiques (97 → 38 ms) restent identifiés comme des mesures de développement consignées dans le journal. Ajout des précautions après une récupération et de la correction des mesures pendant un tour en mouvement.

Le replacement guidé est expliqué depuis le geste à la souris : point approximatif, glissement pour donner le cap, recherche de 1 m / ±50°, confirmation géométrique puis trois scans de suivi avant réenrichissement automatique. Distinction avec la recherche globale « Me retrouver ». Aucun nouveau résultat matériel n’est annoncé ; ces changements concernent uniquement les explications et leur mise en page.

La suite complète exécutée avant ce lot avait les mêmes limites environnementales documentées (238 tests : 15 échecs, 30 erreurs, 12 ignorés) ; les 45 tests du cœur du TP passaient.

Le PDF enrichi tient en 28 pages. Les nouveaux passages ont été contrôlés visuellement. Les tests dédiés au replacement (4 tests) et à la charge/nettoyage de carte (20 tests) passent. Les observations décrites sont celles du code et des journaux conservés, sans nouvel essai physique.

Validation après ce lot documentaire : suite complète terminée en 237,1 s, avec les mêmes 238 tests, 15 échecs, 30 erreurs et 12 ignorés qu'avant (limites de compilateur et réseau déjà documentées). PDF et archive du rendu actualisés.


## 22 novembre 2026 — classement et noms des cartes pour le rendu

À la demande de l’utilisateur, les cartes de la version finale sont réparties en quatre dossiers numérotés : résultats SLAM, acquisitions USB, essais de recalage et données simulées MapTool. `scanenautonomie.json` devient `Cartes/01_resultats_slam/toutes_les_pieces_autonomie.json`. Les anciens noms sont conservés dans `Cartes/correspondance_noms.csv` et dans le tableau de l’index. La copie de la version Tkinter et les entrées historiques du journal gardent leur organisation d’origine.

Les déplacements ont été vérifiés par empreintes SHA-256 avant et après : aucune acquisition, pose ou archive n’a été modifiée. Les liens actuels du README, du compte rendu, du document de reprise et du script de figure sont mis à jour. Les variantes d’essais restent conservées et ne sont pas présentées comme un classement de qualité. Deux descriptions alternatives d’images ont aussi été corrigées (quatre scans USB et 48 segments, conformément aux légendes existantes).

État avant ce lot : la suite complète précédente avait 238 tests, avec les mêmes 15 échecs, 30 erreurs et 12 ignorés liés à l’environnement ; les tests dédiés au replacement et à la charge de carte passaient. Le classement ne modifie aucun algorithme.

Validation du classement : les 11 sessions JSON s’ouvrent avec l’importeur de l’application ; les deux archives ZIP donnent 15 et 5 scans ; les 29 CSV MapTool se lisent. Le script de figure retrouve 736 scans, 332 856 mesures filtrées et 39 442 points dessinés. Le PDF de 28 pages est régénéré et contrôlé visuellement.

Suite complète après classement : 238 tests en 235,1 s, 16 échecs, 30 erreurs, 12 ignorés. Aux limites de compilateur et réseau déjà constatées s’ajoute un échec de temporisation dans le test de reconnexion ; relancé seul, ce test passe (1 test, 0,25 s). Aucun calcul, transport ou test n’a été modifié pour masquer ces résultats.

Vérification de livraison : le dépôt GitHub est privé. Le ZIP final contient donc une copie Git portable des quatre branches utiles dans historique_git/ et un guide pour l’évaluateur. Cette copie a été vérifiée et clonée hors ligne ; origin/jours-1-2 est bien consultable. Le dossier principal du ZIP contient les corrections locales du rendu ; le bundle conserve les commits enregistrés auparavant. L’archive ne contient ni environnements Python, ni caches, ni sauvegardes de travail personnelles.
