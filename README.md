# ScanAtlas

Cartographie et localisation en direct avec un robot Keyestudio Mecanum Car V2 (ESP32) équipé d'un lidar LD06 : le robot roule, la carte se dessine, le robot s'y retrouve. L'application tourne sur le PC dans le navigateur ; le calcul reste en Python.

## Démarrer

```
pip install -r requirements.txt
python scanatlas.py
```

Sous Windows : `installer_windows.bat` puis `lancer_windows.bat` (détails dans `DEMARRER.txt`). Sans robot, « Essayer avec un robot simulé » dans le menu de connexion.

## Deux écrans

- **Direct** : connexion (Wi-Fi ou USB), pilotage (clavier, manette, pavé à l'écran), carte et position en temps réel. Modes *Cartographier* (ajoute des scans) et *Localiser* (se positionne sans modifier la carte), *Me retrouver* (recherche sur toute la carte), *Reprendre ici*, *Nouvelle carte*.
- **Carte** : la même carte, hors connexion. Importer des CSV / ZIP / sessions, afficher ou exclure des scans, les déplacer ou les tourner, les recaler automatiquement, assembler tous les scans inclus, voir en points, en grille d'occupation ou en plan vectoriel, exporter.

Une seule carte alimente les deux écrans ; elle n'est modifiable que robot déconnecté.

## Organisation

| Élément | Rôle |
| --- | --- |
| `scanatlas.py`, `serveur.py` | point d'entrée ; serveur HTTP local (127.0.0.1, jeton, flux d'événements SSE) |
| `web/` | interface (HTML, CSS, JavaScript sans dépendance, fonctionne hors ligne) |
| `session_directe.py` | connexion au robot, pilotage, reconnexion, démonstration, suivi en direct |
| `document_carte.py` | le document de carte partagé (scans, filtres, import/export, recalage, assemblage) |
| `robot_wifi.py`, `robot_usb.py` | transports (UDP/TCP Wi-Fi, USB-série), bail de commande |
| `cartographie_direct.py`, `suivi_lidar.py`, `localisation*.py`, `assemblage_global.py`, `cartographie.py` | calcul : suivi ICP, localisation globale, grille, segments |
| `firmware/ScanAtlas_WiFi/` | firmware ESP32 |
| `docs/` | guide, reprise de projet, journal |
| `tests/` | `python -m unittest discover -s tests` |

Pour reprendre le travail : `docs/REPRISE_PROJET.md`, puis la fin de `docs/JOURNAL_PROJET.md`. L'ancienne interface Tkinter est conservée dans l'historique git (branche `claude/commandes-combinees`) ; sa documentation est dans `docs/ANCIEN_README_TK.md`.
