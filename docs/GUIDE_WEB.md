# Guide de l'interface web

## Lancer

`python scanatlas.py` (ou `lancer_windows.bat`). Le navigateur s'ouvre sur `http://127.0.0.1:8765/`. Le terminal reste ouvert : c'est le serveur ; Ctrl+C ou la fermeture de la fenêtre quitte tout (moteurs arrêtés). Options : `--port N`, `--sans-navigateur`. Aucun accès Internet n'est nécessaire : polices et scripts sont locaux.

## Écran Direct

1. **Connexion** (en haut à droite) : Wi-Fi (adresse `192.168.4.1`, après avoir rejoint le réseau ScanAtlas du robot) ou USB (port COM ou `auto`). « Reconnecter automatiquement » rétablit la liaison après une coupure en conservant la carte. « Essayer avec un robot simulé » lance un robot virtuel sur le PC ; se déconnecter en sort et rend la carte d'avant.
2. **Pilotage** : `Z` avance, `S` recule, `Q` / `D` translation latérale, `A` / `E` rotation, flèches équivalentes, `Espace` ou `Échap` = arrêt. Manette (Xbox) : stick gauche = translation, stick droit horizontal = rotation, `B` = arrêt tant qu'il est tenu, `RB` = change de mode. Puissance et Rotation max sont des plafonds (la rotation rapide déforme le tour du lidar et fait perdre la position). Une consigne n'est valable que 0,35 s : si la page se fige, le robot s'arrête.
3. **Mode** : *Cartographier* ajoute des scans clés à la carte ; *Localiser* ne fait que suivre la position sur la carte existante. **Me retrouver** cherche la position sur toute la carte ; le menu ⋯ propose *Reprendre ici* (autour de la dernière position), *Nouvelle carte* et *Me retrouver automatiquement*.
4. **Vue** : molette = zoom, glisser = déplacer, deux doigts = pincer ; *Suivre* recentre sur le robot.

## Écran Carte

Importer (CSV, ZIP de CSV, session JSON ; glisser-déposer possible), enregistrer la session, exporter un scan en CSV. Colonnes de la liste : œil = affiché, coche = inclus dans les calculs et dans la carte de départ du direct. Couches : Points, Occupation (grille de probabilité), Plan (segments fusionnés). Outils : Vue, Déplacer (glisse le scan sélectionné), Tourner. **Recaler automatiquement** calcule la pose du scan sélectionné sur les autres et propose un aperçu orange à *Appliquer* ou *Ignorer*. **Assembler les scans inclus** replace tous les scans dans un même repère (annulable). Les filtres (distances, intensité, taille de cellule) valent pour l'affichage et les calculs. Pendant une connexion, la carte se met à jour en direct et seule la visibilité reste modifiable.

## Ce qui a été fusionné par rapport à l'ancienne interface

Un seul réglage de connexion, un seul arrêt, un seul « Me retrouver », une seule carte. Les onglets Acquisition et Capture directe sont le direct ; Nuages, Grille, Segments et Carte vectorielle sont les couches de l'écran Carte ; l'onglet Localisation est le recalage de l'inspecteur et l'assemblage. Les comparaisons du TP (trois types de référence) restent disponibles comme scripts : `python outils/produire_figures_tp.py`.

## Architecture

```
navigateur (web/)  ⇄  serveur.py (HTTP 127.0.0.1)  ⇄  SessionDirecte  ⇄  robot (UDP/TCP ou USB-série)
   canvas 2D            REST/JSON + flux SSE            DocumentCarte
```

- Le serveur écoute uniquement `127.0.0.1`, vérifie l'en-tête `Host` (anti « DNS rebinding ») et exige un jeton aléatoire (`X-Jeton`, injecté dans la page) pour toute requête `/api/`. Une autre page web ouverte dans le même navigateur ne peut donc pas piloter le robot.
- `GET /api/flux` (Server-Sent Events) diffuse : `etat` (connexion, suivi, réglages), `scan` (points en mm entiers + pose, le navigateur les transforme), `carte` (points de la carte et grille, limités en fréquence), `document` (version de la carte), `message`, `tache` (progression d'un recalage ou d'un assemblage). Un client lent perd les événements intermédiaires au lieu de ralentir le robot.
- Ordres : `POST /api/connexion|deconnexion|demo|pilote|arret|reglages|retrouver|reprendre|nouvelle_carte` ; carte : `GET /api/carte[/nuage|grille|plan|session|scan/<i>.csv]`, `POST /api/carte/scan|supprimer|tous|filtres|demo|vider|recaler|assembler|annuler|importer?nom=`. Un seul calcul long à la fois. `409` si on modifie la carte pendant la connexion.
- La boucle de sécurité (50 ms) tourne côté serveur : elle envoie le pilotage au robot, coupe les moteurs si la consigne est périmée, reconnecte après une coupure.

## Tests

`python -m unittest discover -s tests`. `tests/test_serveur.py` (API et sécurité), `tests/test_session_directe.py` (reconnexion, démo, pilotage), `tests/test_navigateur.py` (vrai navigateur ; ignoré si Playwright n'est pas installé : `pip install playwright && playwright install chromium`).
