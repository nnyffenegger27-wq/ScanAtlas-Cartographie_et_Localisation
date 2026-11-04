# Reprise du projet — état, architecture, décisions, suite

Document écrit pour qu'un nouvel intervenant (personne ou assistant) reprenne le travail sans l'historique des conversations. À lire en premier ; le détail daté des essais est dans [JOURNAL_PROJET.md](JOURNAL_PROJET.md), l'usage dans [GUIDE_WEB.md](GUIDE_WEB.md).

Mis à jour le 4 novembre 2026 (interface web, branche `claude/interface-web`). Ce qui n'a pas été essayé sur le vrai robot est signalé comme tel : aucun test matériel n'a pu être fait par l'assistant, seulement des tests sur ordinateur.

## 1. Le projet en une page

ScanAtlas : application (serveur Python local + interface web dans le navigateur) qui reçoit en direct les tours d'un lidar LD06 monté sur un robot Keyestudio Mecanum Car V2 (carte ESP32), pilote le robot au clavier ou à la manette Xbox, et construit une carte 2D tout en localisant le robot dessus (SLAM 2D par recalage de scans).

- Dépôt : `nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation`, branches : `main` (première version, interface Tkinter), `claude/commandes-combinees` (dernière version avec l'interface Tkinter) et `claude/interface-web` (**version finale**, interface web, sans Tkinter ni Matplotlib) ; le « qui est quoi » est dans le README.
- Poste de l'utilisateur : Windows ; dossier `C:\Users\nyffe\Documents\GitHub\LD06-Cartographie_et_Localisation`. Journaux de l'application : `C:\Users\nyffe\AppData\Local\ScanAtlas\journaux\`.
- Langue du projet, des messages et des échanges : français.
- But final demandé par l'utilisateur : un SLAM temps réel sur le robot, « comme dans la vidéo » https://www.youtube.com/watch?v=Pq5y7eDiReU (titre : solution SLAM exécutée sur un microcontrôleur de type Arduino). **La vidéo n'a pas pu être regardée** ; seule la notion « cartographie et localisation en direct pendant que le robot roule » est retenue. À préciser avec l'utilisateur (2 ou 3 comportements attendus) avant d'investir dans une grosse refonte.

## 2. Matériel et liaison

| Élément | Valeur |
| --- | --- |
| Carte | ESP32 classique, Arduino-ESP32 **2.0.17** |
| Lidar LD06 | UART 230400 bauds sur Serial2, RX **GPIO33**, enable/PWM **GPIO32**, tampon RX 4096 |
| Moteurs | carte Keyestudio, au choix **I2C** (SDA 19 / SCL 21, adresse 0x30) ou **PWM** (8 GPIO), choisi à la compilation |
| Wi-Fi | l'ESP32 crée le réseau **ScanAtlas**, IP 192.168.4.1 |
| Commandes | UDP 4210, protocole SA1 / SA2, bail de 300 ms |
| Scans | TCP 4211, trames binaires SA06 + CRC32 |
| Filaire | USB-série, mode `LIVE` à 921600 bauds (même contenu que le Wi-Fi) |

Alimentation : les moteurs doivent être alimentés par les piles 18650 (interrupteur de la carte sur ON). Sur l'USB seul, la tension chute au démarrage des moteurs : lenteur, redémarrage de l'ESP32 (reset `BROWNOUT`), coupures de flux. C'est l'hypothèse principale des « suspensions » constatées, **non encore confirmée**.

## 3. Organisation du dépôt

```
README.md                        présentation, démarrage, qui est quoi (branches)
lancer_windows.bat, lancer_mac_linux.sh   lanceurs : installent les dépendances au premier lancement
scanatlas.py, serveur.py         point d'entrée ; serveur HTTP local (127.0.0.1, jeton, REST + flux SSE)
web/                             interface : index.html, style.css, modules JS (main, direct, carte, vue, pilotage, api)
session_directe.py               connexion, pilotage, reconnexion, démo, suivi en direct (sans interface)
document_carte.py                carte partagée : scans, filtres, import/export, recalage, assemblage
robot_wifi.py, robot_usb.py      transports Wi-Fi (UDP commandes + TCP scans) et USB-série ; bail de commande
cartographie_direct.py           CarteDirecte : suivi ICP, scans clés, carte incrémentale, replacement guidé (replacer)
exploration.py                   exploration autonome : frontières, chemin (Dijkstra), commande avec évitement, détections
simulation.py                    salles simulées (registre SALLES : appartement, deux pièces, salle simple ; constructeurs rectangle / polygone / cloison avec portes), lidar, collisions, cinématique
suivi_lidar.py, localisation*.py ICP, localisation globale 360°, localisation TP
cartographie.py, recalage_capture.py, assemblage_global.py   outils de carte (CSV, grille, segments, assemblage)
evaluer_tp_jour2.py              comparaison TP des trois références (script, voir outils/)
journal_direct.py                tours.jsonl, session_secours.json, evenements.log
simuler_robot_wifi.py            robot simulé sur le PC (sans matériel) ; --salle appartement | deux_pieces | salle
firmware/ScanAtlas_WiFi/         firmware ESP32 (voir §5)
tests/                           voir §8
docs/                            documentation : voir docs/README.md (guide, reprise, journal, methodes/, archives_tkinter/)
Cartes/, exemples/               données réelles et résultats d'évaluation (un README dans chaque dossier)
outils/                          scripts d'évaluation reproductibles (python outils/<nom>.py)
materiel/                        firmware de démonstration d'origine du châssis, test lidar, CAO
```

Les modules Python sont à plat à la racine (imports simples, tests sans installation). Ne pas les déplacer sans adapter les tests et les lanceurs.

## 4. Chaîne de traitement

1. Le firmware lit le LD06, découpe en tours, envoie des trames SA06 (angle 1/100°, distance mm, intensité ; fin de tour en µs ESP32).
2. `robot_wifi.RobotWifi` (ou `robot_usb.RobotUsb`, même interface) reçoit dans des threads, valide (CRC, séquence, durée) et dépose le dernier tour dans une file. L'interface ne touche jamais ces threads.
3. `session_directe.SessionDirecte` : un fil de calcul prend le dernier tour (`CarteDirecte.traiter`) et publie `scan` / `carte` vers le navigateur (flux SSE) ; une boucle de sécurité à 50 ms envoie la commande de pilotage (consigne valable 0,35 s) ; le navigateur dessine sur un canvas.
4. `CarteDirecte.traiter` : prédiction SE(2), ICP robuste point-vers-droite (`suivi_lidar`), contrôle d'acceptation (erreur résiduelle, recouvrement), création de scans clés (déplacement ≥ 0,15 m ou 5°, ou 3 s en mouvement lent, jamais à l'arrêt ; constantes `CLE_*` de `cartographie_direct.py`), retrait des points et segments périmés (`SEUIL_PERIME`, lu sur la grille d'occupation), carte vectorielle et grille. Le coût d'un scan clé est constant (≈ 40 ms) : ne rien y ajouter qui grandisse avec la carte. Modes : Cartographie + localisation, Localisation seule (carte figée), localisation globale 360° si position inconnue.
5. `journal_direct` enregistre chaque tour (`tours.jsonl`), une session de secours et les événements (`evenements.log` : suivi actif / perdu, états de liaison). **Toute son écriture se fait dans un fil à part** (les appels ne font que déposer une tâche) et la session de secours n'est réécrite que toutes les 20 s au plus (espacée quand la carte grossit) : sérialiser la carte dans le fil de calcul gelait le PC et faisait expirer le bail du robot.

Rotation rapide : `suivi_lidar.corriger_mouvement` redresse le tour (rotation + translation par instant de mesure) avec la vitesse estimée par l'historique de poses, deux passes ; plafond de rotation de 60 % dans l'interface (`wifi_yaw_max`).

Perte de suivi (`CarteDirecte.traiter`, `_recuperer`) : refus d'un recalage → état perdu ; fenêtre de retour proportionnelle au temps écoulé ; après 1 s recherche élargie autour de la dernière pose (`localisation_globale(centre, rayon)`), après 6 s recherche sur toute la carte toutes les 3 s. Cache du champ de distances et de la grille libre sur la sous-carte. Reconnexion automatique dans `session_directe.py` (`_perte`, `_tour`) et nouvel essai d'ouverture du port dans `robot_usb.py`.

Localisation seule avec carte vide : le premier scan sert de référence (origine fixe), les suivants sont localisés sans enrichir la carte. Un scan non accepté est dessiné en rouge à la dernière pose connue (ne rien afficher était le défaut constaté).

## 5. Firmware `firmware/ScanAtlas_WiFi`

Un sketch (`ScanAtlas_WiFi.ino`) et des en-têtes testables sur ordinateur :

- `protocol.h` : CRC32, énumération des mouvements, analyse des commandes SA1 / SA2, `mecanumMix` (FL = vx−vy−w, FR = vx+vy+w, RL = vx+vy−w, RR = vx−vy+w, réduction proportionnelle si une roue dépasse 100). Convention : +vx avant, +vy gauche, +w rotation à gauche.
- `motor_config.h` : **tous les réglages moteurs** (pilote, broches `PIN_M1A…PIN_M4B`, associations roues / moteurs, signes, fréquence PWM, signes d'axes `AXIS_*_SIGN`, échelle `MOTOR_DUTY_MIN/MAX`, `MOTOR_DIAGNOSTIC`).
- `motor_common.h` (mélange commun, `powerToDuty`), `motor_pwm.h` (LEDC), `motor_i2c.h` + `MecanumCar_v2.cpp/.h` (I2C logiciel), `motor_driver.h` (sélection à la compilation).
- `usb_live.h` : session filaire (`LIVE jeton débit`, `READY jeton SA2`, `LIVE_STOP`).
- `.ino` : tâches commande (UDP) et scan (TCP), lidar, bail de sécurité (moteurs coupés après 300 ms sans commande), journal série (cause du dernier reset, appareils Wi-Fi, silence du lidar). Sur la liaison filaire, seul `loop()` écrit sur le port ; les journaux sont coupés pendant la liaison.

Compilation : Arduino IDE, carte « ESP32 Dev Module », Arduino-ESP32 2.0.17, ouvrir le dossier `ScanAtlas_WiFi`. Fichiers en UTF-8 sans BOM (un BOM a déjà fait échouer la compilation de `MecanumCar_v2.cpp`).

## 6. Décisions à conserver

- Choix PWM / I2C **à la compilation**, jamais à chaud (une mauvaise sélection enverrait des signaux sur les broches de l'autre carte).
- Sens et vitesse réglés dans `motor_config.h` (`AXIS_SWAY_SIGN = -1` par défaut : sway inversé constaté sur le robot ; pourcentage converti en PWM 0..255 par `powerToDuty`, ce qui corrige la lenteur due à un pourcentage envoyé tel quel comme PWM).
- Clavier AZERTY : Z/S avance / recule, Q/D déplacement latéral, A/E rotation (flèches équivalentes). Plus de bouton LB : le pilotage s'active à l'écran. Clavier et manette sont cochés d'emblée et ne sont jamais décochés par un arrêt (B tenu / Espace / perte de focus = STOP seulement). RB bascule la cartographie. Le pilotage continue même si la localisation est perdue. Perte de focus de la fenêtre : arrêt.
- Pavé de commandes (flèches) : le carré vert dynamique est derrière chaque flèche avec le pourcentage ; pas de barres Surge / Sway / Yaw (double information, refusé par l'utilisateur).
- Sécurité : tout arrêt d'urgence est fait par le **bail de 300 ms du firmware**, indépendant du PC.
- Aucun nom de projet extérieur ne doit apparaître dans les fichiers du dépôt comme source d'inspiration.

## 7. Limites et inconnues

- Rien du firmware n'a été vérifié sur ESP32 réel : seulement tests C++ sur ordinateur et compilation syntaxique contre de faux en-têtes. Mode filaire, vraie manette et rendu Windows non essayés.
- Les coupures (ESP32 qui redémarre, port USB qui disparaît : `GetOverlappedResult failed` dans `evenements.log`) viennent très probablement de l'alimentation : les 18650 ne semblent pas fournir le courant, la carte vit sur l'USB. Non confirmé par la raison de reset ; hypothèse BROWNOUT. Pour trancher : ouvrir le moniteur série à 115200 au démarrage et lire la raison du dernier reset (`resetName`), lire `evenements.log` de la session, tester avec les 18650 branchées et chargées.
- Les sens des roues I2C et PWM sont à valider avec `MOTOR_DIAGNOSTIC=true` (roues levées).
- Pas d'odométrie : aucun codeur confirmé.
- Une exécution complète des tests a échoué une seule fois sans reproduction (non identifiée).

## 8. Tester

```
python -m unittest discover -s tests          # 190 tests, ~80 s
```

Plus besoin de Tk ni d'écran virtuel. `tests/test_navigateur.py` pilote un vrai Chromium et est ignoré sans Playwright (`pip install playwright && playwright install chromium`). Le test `tests/test_usb_direct.py` contient de faux en-têtes Arduino pour vérifier la syntaxe du `.ino` avec g++. Les tests moteurs compilent les vrais en-têtes du firmware avec g++ (`tests/test_motor_*.py`). Banc de suivi : `python outils/evaluer_wifi.py`. Robot simulé : `python simuler_robot_wifi.py`.

## 9. Suite prévue (par ordre)

1. **Valider sur le robot** : exploration autonome (sens des axes, `RAYON_ROBOT`, puissance minimale pour avancer), replacement par indice, piles 18650, firmware à jour, sens du sway, vitesse, Localisation seule, filaire. Lire `evenements.log` et le moniteur série en cas de coupure.
2. **Interface web** : valider sur Windows (rendu, manette dans le navigateur, port occupé), puis fusionner `claude/interface-web` si elle convient ; retours d'usage à noter dans le journal.
3. **Prédiction par commandes** : utiliser les commandes envoyées pour initialiser le recalage lidar (modèle de mouvement), avec recherche élargie si le lidar contredit la prédiction. Idée demandée par l'utilisateur pour plus tard.
4. SLAM « en direct » plus poussé (fermeture de boucle, optimisation de graphe de poses) selon la vidéo de référence, une fois ses attentes précisées.
5. Pas de rapport Word pour l'instant (demande de l'utilisateur) ; tenir `JOURNAL_PROJET.md` à jour avec les difficultés rencontrées.

## 10. Conventions de travail

- Branche `claude/commandes-combinees` ; un commit par lot cohérent avec un message en français.
- Ne pas versionner `__pycache__`, `*.npz`, `*.log`, sessions et exports (voir `.gitignore`).
- Toute fonction qui change le comportement du robot ou du protocole reçoit un test sur ordinateur ; ce qui n'a pas pu être essayé sur le matériel est écrit comme tel dans le journal.
