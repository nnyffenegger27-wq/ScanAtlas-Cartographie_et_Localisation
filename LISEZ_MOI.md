# LD06 Atelier — ton application Python de TP

Application locale en français pour acquérir, comprendre et cartographier les scans LD06.
Elle fonctionne sans compte et sans serveur. Une connexion Internet sert uniquement
à installer les bibliothèques Python la première fois.

## Démarrer sur Windows

1. Décompresse **tout** le dossier ZIP. Ne lance pas les fichiers depuis le ZIP.
2. Il faut Python **3.10 ou plus récent**, avec Tkinter (inclus dans l'installation
   Windows standard). Si nécessaire, installe Python depuis https://www.python.org/.
3. Double-clique sur `installer_windows.bat` et attends « Installation terminee ».
4. Double-clique sur `lancer_windows.bat`.
5. Clique sur **Démonstration simulée (2 scans)** pour découvrir l'application.

L'installateur utilise un environnement `.venv` propre au dossier ; il ne remplace
pas les bibliothèques d'autres projets. Laisse la console ouverte en cas d'erreur.
Si la commande `py` manque, utilise les commandes manuelles ci-dessous avec `python`.

Sous macOS/Linux, depuis ce dossier :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Tkinter peut nécessiter un paquet système sous Linux (`python3-tk`).
Sous Windows, les commandes manuelles équivalentes sont :

```bat
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

## Pourquoi Python plutôt qu'une application web ?

Pour ce TP, le port série de l'ESP32 et les calculs géométriques sont centraux.
Python permet de les réunir dans une application locale dont les fichiers sont
faciles à lire, modifier et expliquer. Une version web serait intéressante pour
partager l'interface ; l'accès USB demanderait une API série du navigateur ou un
service local. Ici, on garde un seul programme et trois petites dépendances.

## Un premier essai en cinq minutes

1. Ajoute les deux scans simulés. Leur source est explicitement marquée SIMULATION.
2. Observe les nuages : ils représentent une salle de 6 × 4 m avec un obstacle.
3. Sélectionne SIMULÉ 2. Modifie sa position x, puis applique la pose.
   Seul ce scan se déplace. Rétablis x = -0.8, y = 0.4, orientation = 15°.
4. Dans Grille, clique **Construire / actualiser**. Les impacts sont sombres,
   l'espace libre clair, l'inconnu bleu-gris.
5. Dans Segments, extrais les segments. Leurs numéros servent au laboratoire.
6. Dans Carte vectorielle, construis la carte avec les scans cochés.
7. Enregistre une session JSON, ferme puis rouvre-la. Les cartes sont à recalculer.

Les fichiers `exemples/SIMULE_1.csv`, `SIMULE_2.csv` et `session_demo.json`
permettent aussi un essai par import. Le JSON contient les poses correctes ;
les CSV seuls démarrent chacun à la pose (0, 0, 0).

**La démonstration ne remplace pas les relevés réels demandés au TP.**

## 1. Obtenir tes propres scans réels

Sur l'ESP32, conserve la configuration qui fonctionne. Dans le `if (ld06.readScan())`,
la seule sortie de mesures doit être :

```cpp
ld06.printScanCSV(Serial);
```

Commente la sortie Teleplot et les affichages de diagnostic. Le fichier d'exemple
utilise `Serial.begin(115200)` vers le PC et 230400 bauds vers le lidar.
Ce sont deux liaisons différentes.

Dans l'application :

1. Ferme le moniteur série Arduino et tout autre programme utilisant le port.
2. Ouvre Acquisition USB et actualise les ports. Choisis le port de l'ESP32.
3. Laisse 115200 si c'est la valeur de `Serial.begin`.
4. Pose le lidar immobile ; capture d'abord **un** scan.
5. Sélectionne ce scan puis exporte-le en CSV. Enregistre aussi la session.
6. Déplace le lidar à une autre position stable et recommence ; note sa pose
   relative ou ajuste-la manuellement avec le nuage de points.

L'application attend l'indice 0, vérifie la continuité des indices CSV et attend
la fin du bloc. Un premier fragment est abandonné. Une couverture angulaire de
340° au minimum est requise. Un scan valide côté CSV peut toutefois contenir des
pertes de trames en amont de l'ESP32 ; observe toujours sa cohérence visuelle.
La capture s'arrête après 40 secondes ou via Annuler et ferme le port.

Le CSV texte est volumineux : à 115200 bauds, l'impression peut ralentir la lecture
du lidar et provoquer des pertes en amont. Si tes scans sont troués, vérifie cela.
Tu peux augmenter la vitesse de `Serial.begin` (par exemple 460800), puis régler
**la même vitesse** dans l'application ; garde la liaison lidar à 230400.
Cette modification nécessite de retéléverser le programme et dépend de ta carte.

Sans capture USB, tu peux importer le CSV copié depuis le moniteur série.
Garde les lignes numériques complètes et les lignes vides entre les scans.
Un retour de l'indice à zéro sépare aussi les scans. Les fragments sont acceptés
à l'import : vérifie toi-même qu'il s'agit bien de scans complets.

## 2. Comprendre les coordonnées et les poses

Le CSV ESP32 contient :

```text
indice,angle_deg,distance_mm,intensite,x_mm,y_mm
```

L'application lit les 4 premières colonnes et ignore les x/y déjà calculés.
Elle convertit les millimètres en mètres. L'angle fourni par cette bibliothèque
est déjà mathématique (antihoraire) : **ne pas l'inverser une seconde fois**.
La décroissance des angles dans le temps est normale pour une rotation horaire.

Dans le repère du lidar :

```text
x_local = distance * cos(angle)
y_local = distance * sin(angle)
```

On convertit d'abord les degrés en radians. Puis, pour une pose (tx, ty, alpha) :

```text
x_carte = tx + cos(alpha)*x_local - sin(alpha)*y_local
y_carte = ty + sin(alpha)*x_local + cos(alpha)*y_local
```

La pose représente celle du **lidar**, pas celle d'un châssis décalé. L'application
ne calcule pas les poses automatiquement. L'origine globale est libre : tu peux
choisir le premier lidar comme origine (0,0,0).

Le code ESP32 fourni utilise un signe moins pour sa coordonnée y malgré ses
angles corrigés. Notre calcul utilise explicitement la convention mathématique
ci-dessus ; les valeurs y peuvent donc avoir le signe opposé à celles du CSV.

Chaque scan garde une couleur et une pose indépendantes. La colonne **Carte**
permet de l'exclure de l'affichage commun et des deux cartes sans le supprimer.
Les filtres n'effacent jamais les mesures originales. Les paramètres sont des
valeurs de départ, pas des caractéristiques imposées au capteur.

## 3. Grille d'occupation : démarche proposée

1. Convertir les scans valides dans le repère global en utilisant leur pose.
2. Définir les bornes de la grille autour des points et des origines des scans.
3. Convertir les coordonnées en cellules : floor((position - origine)/résolution).
4. Pour chaque retour valide, parcourir le rayon avec Bresenham.
5. Marquer les cellules avant l'impact libres ; l'impact occupé.
6. Accumuler les preuves avec des log-odds, puis afficher les probabilités.

Une résolution de 0.05 signifie **5 cm par cellule**, pas 5 cellules par mètre.
Diviser la résolution par deux multiplie approximativement par quatre le nombre
 de cellules pour une même surface. Une limite de 4 millions de cellules évite
les allocations excessives.

Probabilité initiale = 0.5. Chaque scan apporte -0.4 pour une cellule libre et
+0.85 pour une cellule d'impact, avec saturation des log-odds entre -4 et +4.
`p = 1 / (1 + exp(-log_odds))`. Une cellule inconnue a un masque séparé : elle ne
doit pas être confondue avec une cellule observée mais incertaine.
Une même cellule ne reçoit qu'une preuve par scan, et un impact a priorité sur
un passage libre dans ce scan. Ce choix réduit l'effet de la densité des rayons.
Ces poids sont pédagogiques, sans calibration probabiliste expérimentale.

Le calcul est volontairement réexécuté depuis les scans cochés : déplacer une
pose ne laisse pas de traces anciennes et recliquer ne recompte pas les scans.
La fonction `Grille.mettre_a_jour` peut aussi mettre à jour une grille existante.
Elle ignore les rayons hors de ses bornes ; l'interface recalcule les bornes pour
tous les scans inclus avant d'y ajouter chaque scan.

Bresenham est une approximation discrète et n'inclut pas forcément chaque cellule
que le faisceau géométrique effleure. Les retours rejetés ou à portée maximale
ne libèrent pas de rayon. Pas de durée de vie des cellules dans cette version.

## 4. Segments : démarche proposée et cas limites

L'ordre des points du scan est conservé. Les trous de mesures et les écarts
supérieurs à 0.20 m séparent des groupes. Un groupe est découpé à son point le
plus éloigné de la droite reliant ses extrémités tant que l'erreur dépasse 0.04 m.
Une fois accepté, le groupe est ajusté par moindres carrés orthogonaux (SVD/PCA).
Il faut au moins 6 points et une longueur de 0.15 m. Un groupe insuffisant est
rejeté. Ces réglages sont à adapter au bruit et à la taille des objets.
Le premier et le dernier point du tour ne sont pas reliés : un mur peut rester
en deux morceaux au niveau de la couture du scan, puis être fusionné.

Dans le laboratoire, deux segments peuvent être comparés :

- Angle **non orienté** entre 0 et 90° : deux directions opposées décrivent la
  même droite. Un segment nul n'a pas d'angle défini.
- Proximité : écart angulaire ≤8° ET distance minimale entre segments ≤0.12 m.
- Fusion : ajuste les quatre extrémités par SVD et projette les extrêmes.
- Intersection : une intersection unique doit appartenir aux deux segments.
- Découpage de A par B : l'intersection doit en plus être strictement intérieure
  à A. On conserve le plus long côté. À égalité, on conserve le côté de A[0].

Tolérance numérique `EPS = 1e-8 m`. Pour le parallélisme, la comparaison normalisée
utilise le seuil numérique 1e-8 sur le sinus de l'angle. Les segments colinéaires
ne possèdent pas d'intersection unique dans cette opération et ne sont pas coupés.
Une intersection à une extrémité de A (à la tolérance près) laisse A inchangé.
Une extrémité de B située à l'intérieur de A peut en revanche couper A.

Le laboratoire affiche la proposition sans modifier la carte. Il permet de
comprendre l'opération ; les tests automatiques couvrent les cas limites imposés.

## 5. Carte vectorielle : démarche proposée

On extrait les segments de chaque scan dans sa pose globale, puis on accumule
les segments. À chaque ajout, les segments proches sont fusionnés jusqu'à ce
qu'aucune fusion supplémentaire ne soit possible.

La fusion reste heuristique et dépend de l'ordre d'insertion. Deux segments
légèrement inclinés qui se croisent peuvent fusionner si les seuils l'autorisent.
La fusion ne conserve pas le nombre de points d'origine comme poids. La carte
n'est ni un plan d'architecte ni un graphe topologique. On n'applique pas le
« garder le plus long côté » automatiquement à chaque croisement : cela pourrait
supprimer des portions de murs réels. L'opération reste disponible et testée.

Les deux documents « Construction d'une grid map… » et « Construction d'une carte
vectorielle… » ne faisaient pas partie des pièces jointes. Cette implémentation
est une proposition simple à comparer à ces documents, pas leur reproduction.

## Où lire le code ?

| Fichier | Contenu |
|---|---|
| `app.py` | Interface, boutons, affichage, import/export et session |
| `cartographie.py` | Coordonnées, pose, grille, extraction et opérations de segments |
| `acquisition.py` | Réception des lignes CSV et reconstruction de scans USB |
| `tests/test_calculs.py` | Tests des calculs et cas limites |

Commence par `Scan.points()`, puis `Grille.mettre_a_jour()`, puis
`intersection()` et `decouper()`. Les calculs sont séparés des boutons pour
pouvoir les étudier et les appeler seuls dans un petit script.

## Exports

- **Scan CSV** : angle_deg, distance_m, intensite. Un fichier par scan ; pas de pose.
- **Session JSON** : mesures, source réelle/simulée, poses, inclusion et paramètres.
  C'est le format à utiliser pour reprendre le travail complet. Les cartes sont
  reconstruites ensuite. L'ouverture remplace la session après confirmation.
- **Grille NPZ** : origine, resolution, log_odds, observe, probabilite. Ouvrir avec
  `np.load('carte.npz')` ; conserver le masque `observe` avec les probabilités.
- **Vecteurs CSV** : x1_m,y1_m,x2_m,y2_m dans le repère global.
- La barre Matplotlib sous chaque vue permet de sauvegarder son graphique.

## Vérification et limites matérielles

Depuis le dossier :

```bash
python -m unittest discover -s tests -v
```

Les tests utilisent des données simulées. Ils couvrent coordonnées, poses,
formats CSV, reconstruction de blocs série, rayons de grille et géométrie.
Le fonctionnement avec ton ESP32 et son port USB doit être vérifié sur ton PC :
aucun matériel réel n'est connecté dans l'environnement de préparation.
Le contrôle visuel de l'interface Windows reste également à effectuer sur ton PC.

Ne présente pas les résultats simulés comme tes relevés de salle. Pour expliquer
ta démarche, distingue les choix de cette application, tes propres réglages et
ce que tu as réellement observé sur tes acquisitions.

## Repère robot — référence fixe

L'ancien angle 180° devient automatiquement le nouveau 0° :
`angle_local = angle_mesure - 180°`, puis la pose du robot est appliquée.
Il n'y a aucun paramètre de calibration dans l'interface. Seuls x, y et
l'orientation règlent la pose. Les mesures polaires originales restent intactes.

Les scans réels des anciennes sessions adoptent aussi ce repère lors de leur
ouverture : leur affichage peut donc tourner par rapport à la version précédente.
Recalculer les cartes après chargement. Les exemples simulés gardent leur repère
propre. La session JSON conserve les poses ; le CSV conserve les angles originaux.
