# ScanAtlas — cartographie et localisation avec un robot lidar

TP EIGSI « Cartographie et localisation » (SLAM 2D). Un robot Keyestudio Mecanum Car V2 (ESP32) porte un lidar LD06 : il roule, la carte se dessine sur le PC, et le robot s'y retrouve. Le robot peut aussi **explorer seul** une pièce, et on peut le **replacer** sur la carte s'il se perd. Tout le calcul est en Python ; l'application s'utilise dans le navigateur, **sans robot** grâce à des salles simulées.

> **Où suis-je ?** Cette page est le README de la branche **`claude/interface-web`** : la **version finale**, celle à lancer et à présenter.
> Les deux autres branches (`main`, `claude/commandes-combinees`) sont les versions précédentes, avec l'ancienne interface Tkinter : voir [Qui est quoi](#1-qui-est-quoi--les-trois-branches).

## Sommaire

1. [Qui est quoi : les trois branches](#1-qui-est-quoi--les-trois-branches)
2. [Lancer la version finale](#2-lancer-la-version-finale)
3. [Ce qu'on peut faire dans l'application](#3-ce-quon-peut-faire-dans-lapplication)
4. [L'onglet « Le projet »](#4-longlet--le-projet-)
5. [Lancer la première version (`main`, Tkinter)](#5-lancer-la-première-version-main-tkinter)
6. [Plan du dépôt](#6-plan-du-dépôt)
7. [Le robot et son firmware](#7-le-robot-et-son-firmware)
8. [Tests et documentation](#8-tests-et-documentation)

---

## 1. Qui est quoi : les trois branches

Le dépôt contient trois versions du même projet, dans l'ordre où elles ont été écrites. Elles sont toutes complètes et se téléchargent séparément (bouton vert **Code ▸ Download ZIP** sur GitHub après avoir choisi la branche, ou les liens ci-dessous).

| | Branche | C'est… | Interface | À utiliser pour |
| --- | --- | --- | --- | --- |
| **3** | **`claude/interface-web`** ← *vous êtes ici* | **La version finale.** Mêmes calculs que les versions précédentes, plus : interface web (écrans Direct et Carte, onglet « Le projet »), SLAM en direct, **exploration autonome**, **replacement guidé**, grandes salles simulées, suivi corrigé d'après les vraies sessions du robot, TP Jour 2 intégré à l'écran Carte. | Navigateur | La démonstration, l'évaluation, le travail actuel |
| **2** | [`claude/commandes-combinees`](https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation/tree/claude/commandes-combinees) · [ZIP](https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation/archive/refs/heads/claude/commandes-combinees.zip) | **La version Tkinter la plus avancée** (16 commits du 4 novembre) : commandes combinées (avancer + côté + tourner), choix du pilote moteur PWM ou I2C, acquisition USB directe, reprise automatique du suivi et reconnexion, redressement du tour lidar en rotation. | Fenêtres Tkinter | Voir l'étape intermédiaire, comparer avec le web |
| **1** | [`main`](https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation/tree/main) · [ZIP](https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation/archive/refs/heads/main.zip) | **La première version complète** (« LD06 Atelier ») : acquisition USB, import CSV / MapTool, nuages, grille d'occupation, segments, carte vectorielle, recalage ICP, **TP Jour 1 et Jour 2** (trois références × deux stratégies, 42 essais), premier pilotage Wi-Fi. C'est la base de tout le reste ; ses documents (guides, résultats du Jour 2, journal) y sont à la racine, tels que remis. | Fenêtres Tkinter | Les rendus du TP tels qu'ils étaient, les premiers choix |

**Pourquoi trois versions ?** `main` est la version du TP : elle marchait, mais l'interface Tkinter / Matplotlib était trop lourde pour piloter le robot et cartographier en même temps. La branche 2 améliore le pilotage et la liaison. La branche 3 change d'interface (web) pour la fluidité et ajoute l'autonomie. Le détail du raisonnement est dans l'onglet **Le projet** (§4) et dans [`docs/JOURNAL_PROJET.md`](docs/JOURNAL_PROJET.md).

**Ce qui ne change pas d'une branche à l'autre :** les méthodes de calcul du TP (grille d'occupation, segments, carte vectorielle, ICP, localisation sur trois références) et le firmware de base. **Ce qui change :** l'interface, le pilotage, le suivi en direct, l'exploration autonome.

**Récupérer une branche en ligne de commande**

```
git clone https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation.git
cd ScanAtlas-Cartographie_et_Localisation
git checkout main                          # version 1 (Tkinter)
git checkout claude/commandes-combinees    # version 2 (Tkinter, avancée)
git checkout claude/interface-web          # version 3 (finale, web)
```

---

## 2. Lancer la version finale

Il faut **Python 3.10 ou plus récent** ([python.org](https://www.python.org/downloads/) ; sous Windows, cocher « Add python.exe to PATH »). Rien d'autre : le premier lancement crée un environnement `.venv` et installe numpy, scipy et pyserial (connexion Internet nécessaire cette seule fois). L'application elle-même fonctionne hors ligne.

| Système | Lancer |
| --- | --- |
| **Windows** | double-clic sur **`lancer_windows.bat`** |
| **macOS / Linux** | `./lancer_mac_linux.sh` (ou `bash lancer_mac_linux.sh`) |
| À la main | `pip install -r requirements.txt` puis `python scanatlas.py` |

Le navigateur s'ouvre sur `http://127.0.0.1:8765/`. La fenêtre noire (ou le terminal) est le serveur : la fermer, ou Ctrl+C, quitte l'application et arrête les moteurs. Options : `python scanatlas.py --port 9000 --sans-navigateur`.

### Essayer sans robot (2 minutes)

1. Sur l'écran d'accueil du **Direct**, choisir une salle (appartement de 16 m × 10 m, deux pièces, salle simple) puis **Essayer sans robot**.
2. Piloter au clavier : **Z / S** avancer, reculer · **Q / D** déplacement latéral · **A / E** tourner · **Espace** arrêt. La carte se dessine pendant que le « robot » roule.
3. Cliquer **Explorer seul** : le robot simulé parcourt toute la salle et s'arrête avec « Exploration terminée ».
4. Onglet **Carte** : *Importer* → `Cartes/scanenautonomie.json` (un vrai scan fait par le robot en autonomie), ou *Importer* des scans réels de `Cartes/`. Changer de couche : Points, Occupation (grille), Plan (carte vectorielle).
5. Écran Carte → **Évaluer les méthodes (TP)** : lance les 42 essais du TP Jour 2 (3 références × 2 stratégies × 7 départs) et propose les exports CSV.

### Avec le robot

1. Flasher le firmware une fois (§7), allumer le robot (piles 18650 chargées, interrupteur de la carte moteur sur ON).
2. Se connecter au Wi-Fi **ScanAtlas** créé par l'ESP32 (ou brancher le câble USB après avoir fermé le moniteur série Arduino).
3. Dans l'application : bouton **Connexion** en haut à droite, puis **Connecter**. Pilotage au clavier ou à la manette Xbox (RB change de mode, B arrête).
4. Modes : *Cartographier* (ajoute des scans), *Localiser* (se positionne sans modifier la carte), *Me retrouver* (recherche sur toute la carte), **Replacer** (cliquer la position sur la carte puis glisser la direction), **Explorer seul**.

Guide complet : [`docs/GUIDE_WEB.md`](docs/GUIDE_WEB.md).

---

## 3. Ce qu'on peut faire dans l'application

- **Direct** : connexion Wi-Fi ou USB, pilotage clavier / manette / pavé à l'écran, carte et position en temps réel (couches Points, Occupation, Plan), exploration autonome, replacement guidé, nouvelle carte.
- **Carte** (hors connexion) : importer des CSV, ZIP ou sessions, afficher / exclure / déplacer / tourner des scans, **recaler** un scan (sur toute la carte, ou sur grille / carte vectorielle / autre scan comme au TP Jour 2, en affinement local ou multi-résolution), assembler tous les scans, régler les filtres (distance, intensité, taille de cellule), exporter.
- **Une seule carte** alimente tous les écrans ; elle n'est modifiable que robot déconnecté.
- **Le projet** : le compte rendu (voir §4).

---

## 4. L'onglet « Le projet »

Dans l'application, dans la barre du haut, à côté de *Direct* et *Carte* (ou directement `http://127.0.0.1:8765/static/presentation.html`) : le compte rendu du projet, écrit à la première personne. Il explique **les buts**, **le fil de la réflexion**, **les problèmes rencontrés et les solutions**, les outils, les essais chiffrés du TP Jour 2 et le bilan, et il reprend le « qui est quoi » des branches. À imprimer en PDF depuis le navigateur si besoin (bouton *Imprimer*).

---

## 5. Lancer la première version (`main`, Tkinter)

Cette version est indépendante : on la télécharge séparément.

```
git clone -b main https://github.com/nnyffenegger27-wq/ScanAtlas-Cartographie_et_Localisation.git ScanAtlas-main
```

Windows : `installer_windows.bat`, puis `lancer_windows.bat` (dans le dossier téléchargé). Ailleurs : `pip install -r requirements.txt` (numpy, scipy, matplotlib, pyserial ; Tkinter est fourni avec Python) puis `python app.py`. Le mode d'emploi est dans `LISEZ_MOI.md` à la racine de `main`. La version 2 (`claude/commandes-combinees`) se lance de la même façon. Les guides correspondants sont aussi copiés ici dans [`docs/archives_tkinter/`](docs/archives_tkinter/).

---

## 6. Plan du dépôt

Le code Python est dans le paquet **`atlas/`**, rangé en quatre dossiers ; à la racine il ne reste que le point d'entrée et les lanceurs.

| Élément | Rôle |
| --- | --- |
| `lancer_windows.bat`, `lancer_mac_linux.sh`, `scanatlas.py` | **lanceurs** (installent les dépendances au premier lancement) et point d'entrée |
| `atlas/application/` | `serveur.py` : serveur HTTP local (127.0.0.1, jeton, flux d'événements) · `document_carte.py` : la carte partagée (scans, filtres, import / export, recalage, assemblage, TP Jour 2) |
| `atlas/robot/` | `robot_wifi.py`, `robot_usb.py` : liaisons · `session_directe.py` : pilotage, reconnexion, démonstration · `journal_direct.py` : journaux · `exploration.py` : exploration autonome |
| `atlas/calcul/` | SLAM et TP : `cartographie_direct.py` + `suivi_lidar.py` (suivi en direct, carte incrémentale, replacement) · `cartographie.py` (grille, segments, carte vectorielle) · `localisation*.py`, `assemblage_global.py`, `recalage_capture.py` (ICP, recherche sur 360°, trois références) · `evaluer_tp_jour2.py` (les 42 essais) |
| `atlas/simulation/` | `simulation.py` : salles simulées · `simuler_robot_wifi.py` : robot simulé sur le PC (démonstration et tests) |
| `web/` | interface (HTML, CSS, JavaScript sans dépendance) ; `presentation.html` = onglet « Le projet » |
| `firmware/ScanAtlas_WiFi/` | firmware de l'ESP32 (Wi-Fi, lidar, moteurs) |
| `materiel/` | fichiers d'origine du châssis, test du lidar, support lidar (CAO) |
| `Cartes/` | relevés réels et sessions ([README](Cartes/README.md)) |
| `exemples/` | résultats des évaluations et scans simulés ([README](exemples/README.md)) |
| `outils/` | scripts d'évaluation reproductibles (`python outils/<nom>.py`) et rejeu de journaux du robot |
| `tests/` | tests automatiques (plus de 230) |
| `docs/` | documentation ([index](docs/README.md)) |
| `AGENTS.md` | consignes pour un assistant qui reprend le dépôt |


---

## 7. Le robot et son firmware

- Matériel : Keyestudio Mecanum Car V2 (ESP32), lidar LD06 (UART 230400 bauds, GPIO33), support lidar imprimé en 3D (`materiel/MecanumCarV2/CAD/`).
- Firmware : `firmware/ScanAtlas_WiFi/` (Arduino IDE, carte « ESP32 Dev Module », Arduino-ESP32 2.0.17, ouvrir le dossier du sketch). **Tous les réglages moteurs** (pilote PWM ou I2C, broches, sens, vitesse) sont dans `motor_config.h` : les robots du projet ne sont pas tous câblés pareil.
- Liaison : l'ESP32 crée le réseau Wi-Fi **ScanAtlas** (192.168.4.1) ; commandes en UDP 4210, scans en TCP 4211 ; ou câble USB.

---

## 8. Tests et documentation

```
python -m unittest discover -s tests        # ~2 min ; le test navigateur est ignoré sans Playwright
```

Documentation : [`docs/README.md`](docs/README.md) indique quel document lire (guide d'utilisation, reprise du projet, journal jour par jour, méthodes du TP, archives Tkinter). Pour reprendre le travail : [`docs/REPRISE_PROJET.md`](docs/REPRISE_PROJET.md), puis la fin de [`docs/JOURNAL_PROJET.md`](docs/JOURNAL_PROJET.md).
