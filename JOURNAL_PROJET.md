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
Solutions et limites décrites dans [ANALYSE_SCANS_ET_SOURIS.md](ANALYSE_SCANS_ET_SOURIS.md).

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
