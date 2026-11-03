# Pilotage Wi-Fi et carte vectorielle en direct

Cette version ajoute un point d'accès sur l'ESP32, un onglet **Robot Wi-Fi**
et une carte vectorielle incrémentale. Le PC pilote manuellement le robot.
La navigation autonome, l'évitement d'obstacles et la fermeture de boucle ne
sont pas encore intégrés. La carte ne commande aucun mouvement automatique.

## Installer le firmware

1. Installer Arduino IDE et le paquet **esp32 by Espressif Systems 2.0.17**.
   URL du gestionnaire de cartes :
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`.
2. Ouvrir `firmware/ScanAtlas_WiFi/ScanAtlas_WiFi.ino`. Garder tous les fichiers
   du dossier ensemble : `protocol.h`, `MecanumCar_v2.cpp` et `MecanumCar_v2.h`.
   La bibliothèque moteur fournie est incluse, sans autre installation.
3. Sélectionner **ESP32 Dev Module**, le port USB de l'ESP32, puis Téléverser.
   Cette cible suppose l'ESP32 classique du montage fourni, pas un C3/S3.
4. Le moniteur série à 115200 bauds doit afficher `ScanAtlas AP : 192.168.4.1`.
   Le nouveau firmware démarre à l'arrêt ; aucune séquence de démonstration moteur.

| Élément | Connexion conservée du projet fourni |
| --- | --- |
| Carte moteur SDA | GPIO 19 |
| Carte moteur SCL | GPIO 21 |
| LD06 TX vers ESP32 RX2 | GPIO 33, 230400 bauds |
| LD06 activation | GPIO 32 au niveau haut |
| Masse | Commune aux alimentations et à l'ESP32 |

Les broches viennent du README et des sources de `MecanumCarV2` et
`ESP32_LD06_Test` ; ces dossiers d'origine ne sont pas remplacés. Les moteurs
et le lidar doivent disposer de leur alimentation habituelle. Le niveau haut
sur GPIO32 reproduit le test fourni ; ce n'est pas une régulation PWM du lidar.

## Connecter le PC et conduire

1. Sur le PC, rejoindre le Wi-Fi **ScanAtlas**, mot de passe **ScanAtlas2026**.
   Accepter de rester connecté même si Windows indique « pas d'Internet ».
   Le SSID et le mot de passe sont modifiables au début du sketch.
2. Installer les dépendances avec `installer_windows.bat`, puis lancer
   `lancer_windows.bat` (ou `python app.py`).
3. Dans **Robot Wi-Fi**, laisser `192.168.4.1`, puis **Connecter**.
   Le premier tour valide fixe l'origine de la nouvelle carte.
4. Cocher **Pilotage manuel au clavier**. Cliquer dans la bande bleue de pilotage.
5. Maintenir une touche : ↑ avance, ↓ recule, ← tourne à gauche,
   → tourne à droite ; A / D déplacent latéralement le châssis Mecanum.
   Une seule direction à la fois ; plusieurs touches donnent STOP.
6. Relâcher arrête le mouvement. Espace, Échap, perte de focus ou changement
   d'onglet désactivent le clavier. Pour repartir, réactiver explicitement.

La puissance est un **PWM brut**, pas une vitesse mesurée : 65 par défaut,
plage limitée à 0–100 sur les 255 pas de la bibliothèque. Le sens des roues,
la puissance nécessaire et la vitesse réelle restent à mesurer sur le robot.
Premier essai roues levées pour confirmer avance, recul, rotations et arrêt,
puis trajet lent au sol avec visibilité directe. Aucun capteur de collision
n'arrête automatiquement le robot dans cette version.

## Carte en direct

Les mesures brutes restent en mètres/degrés/intensité. Le repère lidar actuel
reste à 0°. Les filtres communs sont copiés à la création d'une nouvelle carte ;
les changements ultérieurs ne mélangent pas plusieurs filtrages dans la carte.
Une reconnexion conserve la carte et demande un recalage près de sa dernière
pose ; **Nouvelle carte** remplace explicitement cette référence et prend les
nouveaux filtres. Laisser finir un calcul après Déconnecter avant de reconnecter.

Le suivi compare chaque tour à une sous-carte issue des **huit derniers scans
clés acceptés**. Une prédiction SE(2) extrapole les deux dernières poses lidar
valides en tenant compte du temps. Aucune odométrie n’est déduite des touches.
Un ICP robuste point-vers-droite utilise des normales locales par PCA, un
Jacobien analytique et un système 3 × 3. L’index et les normales sont conservés
entre les scans clés. La recherche multi-résolution est un secours, validé
ensuite par le même contrôle de géométrie point-vers-droite.

La rotation peut s’accumuler sur 360° au fil des tours. Un déplacement soudain
hors du voisinage de suivi demande un arrêt et une reprise près de la dernière
pose acceptée. L’onglet unique **Localisation** sert aux trois références du TP ;
il n’y a plus un second panneau de recalage manuel. Les routines globales
historiques restent disponibles dans les scripts et l’acquisition USB.

Insertion seulement si : solveur validé, géométrie contrainte, au moins **75 %
des points distincts filtrés à moins de 12 cm** de la référence, RMSE ≤ 10 cm
sur les correspondances à moins de 50 cm, déplacement ≤ `0,20 + 1,2 × dt` m
et rotation ≤ `10 + 150 × dt` degrés. `dt` est l'intervalle des tours acceptés ;
un trou supérieur à 1,5 s suspend le suivi. Ces limites sont des garde-fous de
suivi lent, pas des vitesses étalonnées. Le pourcentage est une mesure d'accord
géométrique, **pas une probabilité que la pose soit correcte**. Le premier tour
affiche 100 % par convention d'ancrage, sans comparaison à une carte préexistante.

Les scans clés sont insérés à partir de 15 cm, 5° ou 2 s. Les segments sont
extraits par groupes ordonnés et ajustement orthogonal PCA/SVD : rupture 25 cm,
erreur 5 cm, au moins 6 points, longueur 15 cm. Fusion sous 6° et 10 cm,
avec nouvel ajustement des points supports et erreur maximale 5 cm.
Le dessin affiche la carte de points, les segments verts et la trajectoire.
Il est limité à environ 4 rafraîchissements/s ; tous les tours ne deviennent
pas des scans clés.

Les ressources sont bornées : derniers scans réseau/calcul uniquement,
40 000 points voxelisés à 5 cm, 2 000 scans clés, 2 000 segments et 160 appuis
par segment fusionné. Une limite atteinte suspend l'insertion avec message.
Un échec conserve la dernière carte et suspend son enrichissement. Le pilotage manuel reste disponible avec connexion et lidar récents. Une reprise automatique est essayée près de la dernière pose (25 cm / 8°), au maximum deux fois par seconde. **Reprendre le suivi** autorise un essai explicite jusqu’à 1,2 m / 35°, avec les mêmes contrôles géométriques. Voir [Acquisition et dépannage](ACQUISITION_ET_DEPANNAGE.md).

**Ajouter les scans clés à la session** permet de conserver les mesures et les
poses dans la session JSON habituelle, puis de reconstruire une grille ou une
carte avec les outils du TP. **Exporter les segments CSV** exporte les lignes
`x1_m,y1_m,x2_m,y2_m`. Enregistrer avant de quitter ou de remplacer la carte.

## Protocole et arrêt

Deux voies indépendantes : UDP 4210 pour les commandes, TCP 4211 pour les
tours lidar. Une seule session de pilotage, identifiée par un jeton de 32
caractères et l'adresse/port UDP. L'ouverture exige une première commande STOP.
Les numéros croissants empêchent l'application de commandes anciennes. Pas de
reconnexion ni de réarmement moteur automatique.

Le PC renouvelle son intention toutes les 75 ms environ. Après 250 ms sans
activité de l'interface, le thread réseau transmet STOP. L'ESP32 arrête et
libère le pilote après 300 ms sans commande acceptée. Au-delà de 600 ms sans
flux lidar, les commandes de mouvement sont aussi inhibées. Les délais sont
des réglages logiciels ; le délai mécanique réel doit être mesuré. Un arrêt
logiciel ne remplace pas la coupure matérielle de l'alimentation moteur.

Le firmware lit l'UART sans attendre un transfert TCP et vérifie le CRC8 LD06
(polynôme 0x4D). Il coupe à la frontière de tour et abandonne le premier fragment
ainsi que les débordements, sans filtrer les intensités à la source. Un tour
utilise au maximum 1 200 points ; les anciens CSV multitours restent importables.
Les trames TCP vérifient aussi un CRC32 ; un mauvais CRC, un numéro répété ou
un redémarrage ESP32 impose une reconnexion et ne modifie pas la carte.

SA06 version 1, little endian : en-tête `<4sBBHIQIH>` (26 octets) = magic,
version, flags zéro, nombre de points, séquence, fin du tour en µs monotones
64 bits, durée du tour en µs, longueur utile. Points `<HHB>` : angle CCW en
centi-degrés, distance mm, intensité brute. CRC32 IEEE de l'en-tête et des
points, stocké sur 4 octets. Les horodatages sont ceux du robot, pas l'heure PC.
Leur précision reste limitée par le découpage en paquets UART.

## Vérifications et limites

Firmware compilé pour `esp32:esp32:esp32`, core **2.0.17** : 766 453 octets de
programme (58 %) et 63 296 octets de variables globales (19 %). Les allocations
FreeRTOS, buffers Wi-Fi et piles consomment aussi de la RAM au fonctionnement.
La compilation ne prouve pas le fonctionnement du câblage et des moteurs.

Tests : protocole fragmenté/concaténé, CRC, tailles et horodatages, dernière
valeur seulement, bail d'interface, trames répétées, faux robot UDP/TCP en
boucle locale, parseur et watchdog compilés en C++, trajectoire connue,
préservation de l'origine et absence d'insertion sur échec.

`python evaluer_wifi.py` reproduit 60 tours d'une salle synthétique, occultations
par murs et obstacle, 450 points/tour, bruit gaussien σ = 3 mm, graine 2026.
Trajet simultané x = 0,012i m, y = 0,004i m, angle = 0,6i°, intervalle 100 ms.
Résultat de la première version Wi-Fi : **60/60 acceptés**, erreur maximale de position
**5,03 mm**, erreur angulaire maximale **0,400°**, calcul médian **52,2 ms**,
P95 **119,6 ms**, **7 scans clés et 5 segments finaux**. CSV :
`exemples/evaluation_wifi_simulation.csv`. Ces chiffres dépendent de cette
simulation et du PC d'essai ; ils ne garantissent pas 10 Hz sur ton PC.

Pour essayer l'interface sans robot : `python simuler_robot_wifi.py`, puis
adresse `127.0.0.1` dans Robot Wi-Fi. Il s'agit uniquement d'une salle simulée ;
fermer le simulateur avec Ctrl+C.

Il reste à mesurer sur le matériel : portée et pertes Wi-Fi, réception réelle
des tours, sens/vitesse des roues, délai d'arrêt, suivi à vitesse lente et
qualité de la carte. Le lidar acquiert un tour pendant que le robot bouge :
pas encore de compensation intra-tour, faute d'odométrie/IMU mesurée. Les
objets mobiles et les scènes répétitives peuvent donner un faux recalage.
Pas de fermeture de boucle, ni d'optimisation globale des poses. La fusion
incrémentale ne supprime pas encore les anciens segments selon l'espace libre ;
l'outil vectoriel du TP peut être reconstruit depuis les scans clés enregistrés.

## Sources et attribution

- [Espressif Wi-Fi AP](https://docs.espressif.com/projects/arduino-esp32/en/latest/api/wifi.html) : configuration du hotspot.
- [Code officiel du core 2.0.17](https://github.com/espressif/arduino-esp32/tree/2.0.17) : API WiFi, UDP, serveur TCP, UART et FreeRTOS utilisés.
- Bibliothèque `MecanumCar_v2` fournie par l'utilisateur, auteur 邓飞 (Keyestudio, en-têtes 2021/2022) : fichiers repris sans modification depuis le ZIP fourni.
- Test LD06 du dépôt et [Robot-Maker-SAS/LD06](https://github.com/Robot-Maker-SAS/LD06) : format des paquets, CRC8 et conversion CW vers CCW. Le parseur Wi-Fi est réécrit pour éviter les envois série bloquants.
- [Cartographer](https://google-cartographer-ros.readthedocs.io/en/latest/algo_walkthrough.html) : inspiration pour séparer suivi local, cartes accumulées et sélection des scans clés. Ce programme ne réimplémente pas Cartographer complet.
- [SciPy least_squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html) et [cKDTree](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html) : primitives du solveur robuste et de l'index spatial.

## Interface et suivi actualisés

Les indicateurs de pose, orientation, concordance, durée de calcul et nombre
de segments sont regroupés en haut de Robot Wi-Fi. Le curseur de puissance
conserve la même plage PWM. Les cases Points de carte, Scan courant et Segments
ne modifient que l’affichage ; Suivre le robot déplace la caméra sans changer
les poses. Centrer la carte rétablit une vue d’ensemble. Le zoom est conservé
entre les tours, avec des objets graphiques réutilisés.

Les curseurs de filtrage complètent la saisie numérique dans le panneau gauche.
Appliquer les filtres garde son rôle habituel ; en mode direct, les filtres
restent figés jusqu’à Nouvelle carte pour éviter de mélanger les références.
Les mesures originales ne sont pas supprimées. Aucun nouveau firmware à flasher.

La comparaison chiffrée avec la première version et les limites sont décrites
dans [SUIVI_CONTINU.md](SUIVI_CONTINU.md).

