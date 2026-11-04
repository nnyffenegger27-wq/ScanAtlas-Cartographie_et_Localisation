# Guide de l'interface web

## Lancer

`python scanatlas.py` (ou `lancer_windows.bat`). Le navigateur s'ouvre sur `http://127.0.0.1:8765/`. Le terminal reste ouvert : c'est le serveur ; Ctrl+C ou la fermeture de la fenêtre quitte tout (moteurs arrêtés). Options : `--port N`, `--sans-navigateur`. Aucun accès Internet n'est nécessaire : polices et scripts sont locaux.

## Écran Direct

1. **Connexion** (en haut à droite) : Wi-Fi (adresse `192.168.4.1`, après avoir rejoint le réseau ScanAtlas du robot) ou USB (port COM ou `auto`). « Reconnecter automatiquement » rétablit la liaison après une coupure en conservant la carte. « Essayer avec un robot simulé » lance un robot virtuel sur le PC, dans la salle choisie dans la liste (appartement de 16 × 10 m avec couloir, cinq pièces, portes de 90 cm, une boucle et une vingtaine de meubles ; deux pièces reliées par une porte ; salle simple de 7 × 5 m). L'exploration complète de l'appartement dure quelques minutes ; se déconnecter en sort et rend la carte d'avant.
2. **Pilotage** : `Z` avance, `S` recule, `Q` / `D` translation latérale, `A` / `E` rotation, flèches équivalentes, `Espace` ou `Échap` = arrêt. Manette (Xbox) : stick gauche = translation, stick droit horizontal = rotation, `B` = arrêt tant qu'il est tenu, `RB` = change de mode. Puissance et Rotation max sont des plafonds (la rotation rapide déforme le tour du lidar et fait perdre la position). Une consigne n'est valable que 0,35 s : si la page se fige, le robot s'arrête.
3. **Couches** (en haut) : *Points* (mesures), *Occupation* (grille : libre / occupé / inconnu) et *Plan* (segments fusionnés), combinables, mises à jour pendant que le robot roule. La grille n'est demandée au serveur que si elle est affichée.
4. **Explorer seul** : le robot choisit lui-même où aller pour terminer la carte (voir ci-dessous). Toucher une commande (clavier, manette), `Espace`, `Arrêt` ou se déconnecter l'arrête aussitôt.
5. **Replacer** : quand le robot est perdu (le panneau le propose), ou n'importe quand : clique sur la carte à l'endroit où il se trouve et glisse pour indiquer vers où il regarde (un simple clic garde le cap affiché). La recherche se limite à 1 m autour du point et ±50° autour de la direction, puis la position est confirmée par la géométrie locale (mêmes seuils que partout ailleurs) : si elle ne l'est pas, un message le dit et la récupération automatique reprend. *Me retrouver* fait la même chose sans indice, sur toute la carte (plus lent, ambigu dans une pièce symétrique).
6. **Mode** : *Cartographier* ajoute des scans clés à la carte ; *Localiser* ne fait que suivre la position sur la carte existante. **Me retrouver** cherche la position sur toute la carte ; le menu ⋯ propose *Reprendre ici* (autour de la dernière position), *Nouvelle carte* et *Me retrouver automatiquement*.
7. **Vue** : molette = zoom, glisser = déplacer, deux doigts = pincer ; *Suivre* recentre sur le robot.

## Exploration autonome

Principe (frontières) : une *frontière* est une zone libre de la carte touchant une zone encore inconnue. Le robot va vers la plus proche frontière atteignable (chemin le plus court, qui préfère le milieu des passages), le lidar révèle la zone, la carte grandit, et on recommence. Quand plus aucune frontière n'est atteignable, l'exploration s'arrête : « Exploration terminée ». À l'écran : losanges orange = zones à voir, pointillés = chemin prévu, cercle = destination.

- Le robot se déplace **sans tourner** (mecanum) : pas de tour de lidar déformé, donc un suivi plus sûr. Le curseur *Puissance* est la vitesse maximale en ligne droite ; elle diminue près des obstacles et de la destination.
- Sécurités, indépendantes de la carte : le lidar est lu en continu ; un obstacle dans le couloir de 38 cm devant le robot réduit puis annule l'avance (arrêt à 20 cm), un obstacle proche sur le côté le repousse (il glisse le long des murs). Si la position n'est plus suivie, le robot s'arrête et cherche où il est ; au bout de 45 s, l'exploration s'arrête et demande de le replacer.
- Détections : si le robot ne bouge pas (obstacle, roues bloquées, puissance trop basse), il essaie une autre destination puis s'arrête après trois échecs ; s'il se déplace dans une autre direction que celle commandée (sens des moteurs ou orientation du lidar à vérifier), l'exploration s'arrête avec un message explicite. **Cette détection n'a été validée qu'en simulation.**
- Réglage matériel : `RAYON_ROBOT` (26 cm, distance de planification aux murs) et `DISTANCE_ARRET` dans `exploration.py` sont à ajuster au châssis réel.
- Prérequis : robot connecté, position suivie, mode *Cartographier*.

## Écran Carte

Importer (CSV, ZIP de CSV, session JSON ; glisser-déposer possible), enregistrer la session, exporter un scan en CSV. Colonnes de la liste : œil = affiché, coche = inclus dans les calculs et dans la carte de départ du direct. Couches : Points, Occupation (grille de probabilité), Plan (segments fusionnés). Outils : Vue, Déplacer (glisse le scan sélectionné), Tourner. Le menu **Recalage sur…** de l'inspecteur calcule la pose du scan sélectionné et propose un aperçu orange à *Appliquer* ou *Ignorer* (rien n'est modifié avant) : soit sur toute la carte sans indice (recherche 360°), soit, comme dans le TP Jour 2, depuis la pose actuelle (±1 m, ±30°) sur l'une des trois références construites **sans** ce scan — grille d'occupation, carte vectorielle, ou un autre scan au choix — avec la stratégie *affinement local* ou *multi-résolution*. Le résultat affiche pose, concordance, RMSE, durée et nombre de candidats. **Assembler les scans inclus** replace tous les scans dans un même repère (annulable). Les filtres (distances, intensité, taille de cellule) valent pour l'affichage et les calculs. Pendant une connexion, la carte se met à jour en direct et seule la visibilité reste modifiable.

**Une seule carte.** Tant que la carte vient du direct et n'a pas été modifiée, l'écran Carte affiche exactement la carte fusionnée de l'écran Direct (nuage dédoublonné, segments fusionnés, grille d'occupation) au lieu de la recalculer depuis chaque scan clé ; elle reste affichée après la déconnexion. Dès qu'on modifie un scan (masquer, exclure, déplacer, recaler, assembler), l'écran revient à l'affichage scan par scan. Dans la carte du direct, les points qu'un scan plus récent a vus traverser (objet déplacé, porte refermée, personne passée) sont retirés, ainsi que les segments dont la majorité des mesures est périmée.

## Ce qui a été fusionné par rapport à l'ancienne interface

Un seul réglage de connexion, un seul arrêt, un seul « Me retrouver », une seule carte. Les onglets Acquisition et Capture directe sont le direct ; Nuages, Grille, Segments et Carte vectorielle sont les couches de l'écran Carte ; l'onglet Localisation est le recalage de l'inspecteur et l'assemblage. Les TP précédents sont dans la version web : le Jour 1 (nuages, grille d'occupation, segments, carte vectorielle) = les couches de l'écran Carte ; le Jour 2 (localisation sur grille / plan / scan, locale ou multi-résolution) = le menu *Recalage sur…* et le bouton **Évaluer les méthodes (TP)**, qui lance le banc 3 références × 2 stratégies × 7 départs (42 essais) sur les deux scans simulés du TP, affiche la synthèse (réussite vraie à 10 cm / 2°, acceptations correctes et fausses, refus, temps médian) et propose deux exports CSV (synthèse, 42 essais). Les scripts restent utilisables : `python outils/produire_figures_tp.py`, `python evaluer_tp_jour2.py`.

## Architecture

```
navigateur (web/)  ⇄  serveur.py (HTTP 127.0.0.1)  ⇄  SessionDirecte  ⇄  robot (UDP/TCP ou USB-série)
   canvas 2D            REST/JSON + flux SSE            DocumentCarte
```

- Le serveur écoute uniquement `127.0.0.1`, vérifie l'en-tête `Host` (anti « DNS rebinding ») et exige un jeton aléatoire (`X-Jeton`, injecté dans la page) pour toute requête `/api/`. Une autre page web ouverte dans le même navigateur ne peut donc pas piloter le robot.
- `GET /api/flux` (Server-Sent Events) diffuse : `etat` (connexion, suivi, réglages), `scan` (points en mm entiers + pose, le navigateur les transforme), `carte` (points de la carte et grille, limités en fréquence), `document` (version de la carte), `message`, `tache` (progression d'un recalage ou d'un assemblage). Un client lent perd les événements intermédiaires au lieu de ralentir le robot.
- Ordres : `POST /api/connexion|deconnexion|demo (`{actif, salle}`)|pilote|arret|reglages|retrouver|replacer|reprendre|nouvelle_carte|auto` (`replacer` : `{x, y, cap}` en mètres et degrés dans le repère de la carte ; `auto` : `{actif}`), `GET /api/direct/grille` (grille de la carte en cours, compressée) ; carte : `GET /api/carte[/nuage|grille|plan|session|scan/<i>.csv]`, `POST /api/carte/scan|supprimer|tous|filtres|demo|vider|recaler|assembler|annuler|importer?nom=`. Un seul calcul long à la fois. `409` si on modifie la carte pendant la connexion.
- `exploration.py` ne contient aucun fil ni horloge : `planifier` (frontières, chemin, ~10 ms) tourne à 1 Hz dans un fil de `SessionDirecte`, `commande` (évitement, vitesse) à 20 Hz dans la boucle de sécurité. Les deux se testent en temps simulé (`simulation.py`).
- La boucle de sécurité (50 ms) tourne côté serveur : elle envoie le pilotage au robot, coupe les moteurs si la consigne est périmée, reconnecte après une coupure.

## Tests

`python -m unittest discover -s tests`. `tests/test_serveur.py` (API et sécurité), `tests/test_session_directe.py` (reconnexion, démo, pilotage), `tests/test_replacer.py` (position indiquée), `tests/test_exploration.py` (exploration en boucle fermée, évitement, détection d'axes inversés ou de blocage), `tests/test_navigateur.py` (vrai navigateur ; ignoré si Playwright n'est pas installé : `pip install playwright && playwright install chromium`).
