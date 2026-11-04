# Reprise du projet — état, architecture, décisions, suite

Document écrit pour qu'un nouvel intervenant (personne ou assistant) reprenne le travail sans l'historique des conversations. À lire en premier ; le détail daté des essais est dans [JOURNAL_PROJET.md](JOURNAL_PROJET.md), l'usage dans [GUIDE_SCANATLAS_V3.md](GUIDE_SCANATLAS_V3.md).

Mis à jour le 4 novembre 2026. Ce qui n'a pas été essayé sur le vrai robot est signalé comme tel : aucun test matériel n'a pu être fait par l'assistant, seulement des tests sur ordinateur.

## 1. Le projet en une page

ScanAtlas : application Python (Tkinter + Matplotlib) qui reçoit en direct les tours d'un lidar LD06 monté sur un robot Keyestudio Mecanum Car V2 (carte ESP32), pilote le robot au clavier ou à la manette Xbox, et construit une carte 2D tout en localisant le robot dessus (SLAM 2D par recalage de scans).

- Dépôt : `nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation`, branche de travail `claude/commandes-combinees`.
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
README.md, DEMARRER.txt, *.bat   démarrage Windows (installer_windows.bat puis lancer_windows.bat)
app.py                           fenêtre principale (3 espaces) ; lance interface_tp / interface_wifi
interface_wifi.py                espace « Robot » : connexion Wi-Fi ou USB, pilotage, carte en direct
interface_tp.py, evaluer_tp_jour2.py   comparaison TP (grille / segments / scan)
robot_wifi.py                    transport Wi-Fi (UDP commandes + TCP scans), bail de commande, état
robot_usb.py                     transport filaire (poignée de main LIVE, démultiplexage SA06 / texte)
cartographie_direct.py           CarteDirecte : suivi ICP, scans clés, carte incrémentale
suivi_lidar.py, localisation*.py ICP, localisation globale 360°, localisation TP
cartographie.py, acquisition.py, recalage_capture.py, manipulation.py, assemblage_global.py   outils du TP
journal_direct.py                tours.jsonl, session_secours.json, evenements.log
encart_commandes.py, apparence.py, manette.py   pavé de commandes, palette, manette XInput
simuler_robot_wifi.py            robot simulé sur le PC (sans matériel)
firmware/ScanAtlas_WiFi/         firmware ESP32 (voir §5)
tests/                           206 tests, voir §8
docs/                            documentation (ce fichier, guide, journal, etc.)
outils/                          scripts d'évaluation reproductibles (python outils/<nom>.py)
materiel/                        firmware de démonstration d'origine du châssis, test lidar, CAO
```

Les modules Python sont à plat à la racine (imports simples, tests sans installation). Ne pas les déplacer sans adapter les tests et les lanceurs.

## 4. Chaîne de traitement

1. Le firmware lit le LD06, découpe en tours, envoie des trames SA06 (angle 1/100°, distance mm, intensité ; fin de tour en µs ESP32).
2. `robot_wifi.RobotWifi` (ou `robot_usb.RobotUsb`, même interface) reçoit dans des threads, valide (CRC, séquence, durée) et dépose le dernier tour dans une file. **Aucun thread ne touche Tk.**
3. `interface_wifi.wifi_poll` (tâche Tk, boucle régulière) prend le dernier tour, le confie à un calcul hors thread UI (`CarteDirecte.traiter`), dessine la carte (Matplotlib) et envoie la commande de pilotage.
4. `CarteDirecte.traiter` : prédiction SE(2), ICP robuste point-vers-droite (`suivi_lidar`), contrôle d'acceptation (erreur résiduelle, recouvrement), création de scans clés (déplacement ≥ 0,15 m, 5° ou 2 s), carte vectorielle et grille. Modes : Cartographie + localisation, Localisation seule (carte figée), localisation globale 360° si position inconnue.
5. `journal_direct` enregistre chaque tour (`tours.jsonl`), une session de secours et les événements (`evenements.log` : suivi actif / perdu, états de liaison).

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
- Clavier AZERTY : Z/S avance / recule, Q/D déplacement latéral, A/E rotation (flèches équivalentes). Plus de bouton LB : le pilotage s'active à l'écran. B (manette) ou Espace désarme le pilotage sans toucher au lidar ni à la localisation. RB bascule la cartographie. Le pilotage continue même si la localisation est perdue. Perte de focus de la fenêtre : arrêt.
- Pavé de commandes (flèches) : le carré vert dynamique est derrière chaque flèche avec le pourcentage ; pas de barres Surge / Sway / Yaw (double information, refusé par l'utilisateur).
- Sécurité : tout arrêt d'urgence est fait par le **bail de 300 ms du firmware**, indépendant du PC.
- Aucun nom de projet extérieur ne doit apparaître dans les fichiers du dépôt comme source d'inspiration.

## 7. Limites et inconnues

- Rien du firmware n'a été vérifié sur ESP32 réel : seulement tests C++ sur ordinateur et compilation syntaxique contre de faux en-têtes. Mode filaire, vraie manette et rendu Windows non essayés.
- Cause des « suspensions » (flux qui s'arrête) non démontrée ; hypothèse BROWNOUT. Pour trancher : ouvrir le moniteur série à 115200 au démarrage et lire la raison du dernier reset (`resetName`), lire `evenements.log` de la session, tester avec les 18650 branchées et chargées.
- Les sens des roues I2C et PWM sont à valider avec `MOTOR_DIAGNOSTIC=true` (roues levées).
- Pas d'odométrie : aucun codeur confirmé.
- Une exécution complète des tests a échoué une seule fois sans reproduction (non identifiée).

## 8. Tester

```
python -m unittest discover -s tests          # 206 tests, ~45 s
```

Tk est nécessaire pour les tests d'interface (Linux sans écran : `xvfb-run -a python -m unittest discover -s tests`). Le test `tests/test_usb_direct.py` contient de faux en-têtes Arduino pour vérifier la syntaxe du `.ino` avec g++. Les tests moteurs compilent les vrais en-têtes du firmware avec g++ (`tests/test_motor_*.py`). Banc de suivi : `python outils/evaluer_wifi.py`. Robot simulé : `python simuler_robot_wifi.py`.

## 9. Suite prévue (par ordre)

1. **Valider sur le robot** : piles 18650, firmware à jour, sens du sway, vitesse, Localisation seule, filaire. Lire `evenements.log` et le moniteur série en cas de coupure.
2. **Refonte du design** : interface sobre, élégante, ergonomique (palette neutre, hiérarchie claire, un panneau de contrôle clair, carte au centre). Fichiers concernés : `apparence.py`, `interface_wifi.py`, `app.py`, `encart_commandes.py`.
3. **Prédiction par commandes** : utiliser les commandes envoyées pour initialiser le recalage lidar (modèle de mouvement), avec recherche élargie si le lidar contredit la prédiction. Idée demandée par l'utilisateur pour plus tard.
4. **Capture directe dans Localisation** et SLAM « en direct » plus poussé (fermeture de boucle, optimisation de graphe de poses) selon la vidéo de référence, une fois ses attentes précisées.
5. Pas de rapport Word pour l'instant (demande de l'utilisateur) ; tenir `JOURNAL_PROJET.md` à jour avec les difficultés rencontrées.

## 10. Conventions de travail

- Branche `claude/commandes-combinees` ; un commit par lot cohérent avec un message en français.
- Ne pas versionner `__pycache__`, `*.npz`, `*.log`, sessions et exports (voir `.gitignore`).
- Toute fonction qui change le comportement du robot ou du protocole reçoit un test sur ordinateur ; ce qui n'a pas pu être essayé sur le matériel est écrit comme tel dans le journal.
