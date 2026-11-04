# ScanAtlas — Interface et robot en direct

Mise à jour du 4 novembre 2026. Cette version ajoute la nouvelle interface, les cartes reprises et le pilotage PWM direct. Les anciennes instructions de firmware à deux fils sont remplacées par ce guide.

## Les trois espaces

- **Cartographie** : imports CSV et ZIP, sessions, scans visibles et scans cochés Carte, poses manuelles et gestes souris, filtres, grille, extraction de segments et carte vectorielle. Le calcul vectoriel historique de cet espace est conservé. Acquisition USB et Wi-Fi se trouve dans les sous-onglets. La pose et les filtres sont repliables. « Annuler le dernier déplacement » restaure une pose précédente, jusqu'à 30 modifications.
- **Localisation** : choisir le mobile dans le panneau de droite, une référence Scan / Grille / Carte vectorielle et la méthode. Les deux méthodes du TP et l'évaluation chiffrée restent disponibles. La pose initiale est dans le panneau repliable. Une carte ne doit pas contenir le mobile à évaluer ; les contrôles existants sont conservés.
- **Robot en direct** : grande carte, panneau de pilotage redimensionnable et défilant, vues Points / Grille / Vectorielle. « Agrandir » masque le panneau ; le bouton rouge d'arrêt reste visible. La grille utilise le même modèle d'occupation que l'outil historique, avec cellules libres blanches, occupées sombres et inconnues bleu-gris. Les cellules non classées restent bleu-gris. Le zoom reste inchangé entre les tours.

Le logo est tracé dans l'en-tête sans dépendance graphique supplémentaire ; sa version SVG est dans `assets/logo.svg`. La palette claire bleu pétrole reprend la maquette validée. Le rendu exact des contrôles et de la police dépend du système.

## Une carte vide ou une carte existante

Pour commencer une carte : choisir **Nouvelle carte**, puis **Connecter**. Le premier tour valide fixe l'origine. Pour remplacer une carte directe déjà chargée, utiliser le bouton **Nouvelle carte** ; la confirmation rappelle de sauvegarder.

Pour reprendre une carte enregistrée :

1. Dans Cartographie, ouvrir la session JSON et vérifier les poses.
2. Cocher **Carte** pour les scans qui doivent servir de référence. Les scans masqués peuvent toujours être inclus si leur case Carte est cochée.
3. Dans Robot en direct, choisir **Scans cochés Carte** comme carte de départ. Cliquer sur Nouvelle carte si une carte directe précédente existe, puis connecter.
4. Rester immobile pendant la première recherche. La position n'a pas besoin d'être renseignée : recherche globale sur 360° et la carte, puis confirmation point-vers-droite. Une scène ambiguë ou insuffisante est refusée.

Les mesures, poses et éventuels segments construits sur exactement les scans cochés sont copiés. Les originaux de Cartographie restent indépendants. Une reconnexion reprend d'abord près de la dernière pose (le robot n'a en général pas bougé) ; si cela échoue, la récupération automatique ci-dessous prend le relais. **Position 360°** (ou **Me retrouver**, près de la carte) lance à la main une recherche sur toute la carte après un déplacement inconnu.

### Quand le robot se perd

Le suivi se perd quand un recalage est refusé (rotation rapide, mur unique ou couloir, obstacle mobile). Le bandeau indique alors `SUIVI PERDU · RECHERCHE EN COURS` ; la carte est conservée, le scan non accepté s'affiche en rouge à la dernière pose et le pilotage reste possible. La case **Me retrouver automatiquement si je suis perdu** (activée par défaut) enchaîne :

1. nouveaux essais près de la dernière pose, avec une fenêtre qui s'élargit avec le temps écoulé (le robot continue de rouler pendant la perte) ;
2. après 1 s, recherche élargie autour de la dernière pose, **tous angles**, rayon de 1,5 m grandissant jusqu'à 5 m ;
3. après 6 s, recherche sur **toute la carte**, relancée toutes les 3 s.

Chaque solution doit confirmer à 75 % à 12 cm sur la géométrie locale (RMSE ≤ 10 cm), sinon elle est refusée. Pour aider : ramener le robot face à une zone déjà cartographiée, avec des murs dans plusieurs directions. Dans un couloir ou devant un mur unique, la position est ambiguë et aucune recherche ne peut la trancher ; le message du refus le dit.

### Tourner vite

Le lidar met 0,1 s à faire un tour : un robot qui tourne à 90°/s a tourné de 9° entre le début et la fin du même tour, ce qui déforme tous les murs lointains (environ 45 cm à 3 m) et fait refuser le recalage. Deux protections :

- **Redressement du tour** : dès que la vitesse estimée dépasse 6°/s ou 15 cm/s, chaque point du tour est ramené au repère de la fin du tour (rotation et translation selon l'instant de sa mesure), puis le recalage est refait une seconde fois avec la vitesse qu'il vient de mesurer. En simulation à 150°/s, l'erreur d'orientation passe de 21° à 1,5°. Le tour redressé est aussi celui qui est gardé dans la carte.
- **Rotation maximale** (curseur du bloc Pilotage, 60 % par défaut) : plafonne la rotation en pourcentage de la puissance. Monter cette valeur si le robot tourne trop mollement, la baisser s'il se perd encore en tournant.

Le redressement suppose que les points arrivent dans l'ordre de mesure (c'est le cas du firmware) et que le robot garde une vitesse à peu près constante pendant un tour ; la toute première image d'un démarrage brutal n'est pas redressée.

### Après une coupure (batteries, câble, Wi-Fi)

La case **Reconnecter automatiquement après une coupure** (activée par défaut) relance la connexion 3 s après une coupure subie, jusqu'à 8 essais, avec la même carte. En USB, le port met quelques secondes à revenir quand l'ESP32 redémarre (« Accès refusé ») : l'ouverture est réessayée pendant 8 s. Un clic sur **Déconnecter** annule la reconnexion automatique.

**Coupures brèves.** Le firmware ne ferme plus la session au premier trou : sans commande pendant 300 ms il coupe les **moteurs** (sécurité inchangée), mais garde la session et le flux de scans 6 s. Au retour des commandes, la première est appliquée comme un arrêt, la suivante agit normalement. Une session muette depuis plus d'une seconde est remplacée par une nouvelle demande (plus de « Robot déjà utilisé » après un plantage), y compris en USB où le PC essaie tour à tour 115200 et le débit rapide. Le PC attend jusqu'à 5 s une réponse et note chaque pause dans `evenements.log` (« Pause de 1.2 s sans scan… »). **Il faut téléverser le firmware `ScanAtlas_WiFi` mis à jour** pour en profiter.

**Vérification après une reprise.** Après une position retrouvée (récupération, « Position 360° », « Reprendre ici ») ou un trou de plus de 0,6 s entre deux tours, la carte n'est pas enrichie pendant 3 tours suivis normalement : une position douteuse ne dépose plus de scans clés. Le message indique « Carte non enrichie pendant la vérification de la position ». Après un saut sur la carte, le suivi se fait aussitôt sur le voisinage de la nouvelle position.

Une recherche globale est plus coûteuse qu'un suivi local. En cas d'échec, elle est retentée au plus toutes les cinq secondes. Ce n'est pas une garantie de retrouver n'importe quelle position : il faut du recouvrement et une géométrie suffisamment distinctive. Le suivi courant utilise l'ICP point-vers-droite et une référence mise en cache ; aucune odométrie n'est inventée depuis les touches.

## Cartographier ou seulement se localiser

| Mode | Pose estimée | Points, grille et segments |
| --- | --- | --- |
| Cartographier | Mise à jour à chaque recalage accepté | Enrichis aux scans clés validés |
| Localisation seule | Mise à jour à chaque recalage accepté | Figés |
| Déconnexion | Dernière pose conservée à l'écran | Figés |

Sans carte, le mode Localisation seule demande d'abord une référence. La cartographie ne reçoit jamais un scan refusé. La première ancre et les critères de concordance / géométrie restent protégés. La concordance indique l'accord des impacts à 12 cm, pas une probabilité d'exactitude de la pose. Un premier scan ancré affiche 100 % par convention.

La grille est mise à jour aux insertions de scans clés, pas à chaque tour. Son image est réutilisée tant que les cellules ne changent pas. Le fond de référence conserve la couverture de la carte importée. Les segments directs restent construits par ajustement des appuis et fusion prudente ; ce calcul est distinct de la commande qui reconstruit la carte vectorielle dans Cartographie.

## Sauvegarde et essais rejouables

**Enregistrer la session directe** produit un JSON version 2 compatible avec Ouvrir une session. Il conserve les scans clés, mesures, poses et filtres ; les cartes se reconstruisent depuis ces données. **Vers Cartographie** ajoute les scans clés à la session courante. Les noms déjà présents ne sont pas dupliqués.

Chaque connexion crée un dossier dans `%LOCALAPPDATA%\ScanAtlas\journaux` sous Windows, ou `~/.local/share/ScanAtlas/journaux` ailleurs. **Dossier des essais** permet de le retrouver.

- `tours.jsonl` conserve tous les tours complets reçus, avant la file qui ne garde que le dernier scan pour le calcul, ainsi que les décisions de localisation des tours effectivement traités. Une absence de décision correspond notamment à un tour non traité.
- `session_secours.json` est remplacé atomiquement quand le nombre de scans clés change. Les mesures refusées restent dans le journal brut, sans entrer dans cette session.

Le journal ne contient pas le jeton d'authentification réseau. Un problème d'écriture est signalé dans l'interface. L'espace disque nécessaire augmente avec la durée des essais ; les journaux ne sont pas supprimés automatiquement. Les fichiers sont utilisables pour une analyse ou un rejeu programmatique ; un lecteur graphique de journal n'est pas inclus.

## Clavier et manette Xbox

L'encart **Commandes** du panneau Pilotage est un **pavé 3 × 3** : rotation gauche, avance, rotation droite ; gauche, croix, droite ; recul. Derrière chaque flèche, un **carré vert se remplit** proportionnellement à la puissance demandée, du côté d'où part le mouvement (l'avance monte depuis le bas de la case, le recul descend depuis le haut, etc.), avec le pourcentage écrit dans la case. Au clavier le remplissage est fixe (tout ou rien, égal au réglage PWM) ; à la manette il suit l'inclinaison du stick. **La croix centrale est pleine quand le robot est à l'arrêt.** Le fond de l'encart est beige tant que le robot n'est pas connecté et vert pâle une fois connecté et le flux lidar reçu.

**Clavier et manette sont actifs d'emblée** et restent cochés : un arrêt (Espace, B, bouton ARRÊT, perte de focus, déconnexion, « Position 360° », « Reprendre ici ») arrête les moteurs mais ne décoche rien. On ne décoche une case que par un clic. Les deux entrées coexistent ; si la manette est inclinée, elle prime sur le clavier. Sans manette branchée, le clavier fonctionne normalement.

**Le pilotage se teste sans robot** : sans être connecté affiche l'encart exactement comme avec un robot, mais **aucune commande n'est envoyée**. Avec un robot connecté, les commandes ne partent que si le flux lidar est récent (comme avant).

Clavier AZERTY : la zone de commandes prend le focus quand on ouvre l'onglet Robot (sinon cliquer dedans), puis :

| Mouvement | Touches |
|---|---|
| Surge : avancer / reculer | **Z** / **S** |
| Sway : gauche / droite | **Q** / **D** |
| Yaw : tourner à gauche / à droite | **A** / **E** |

Les flèches haut/bas (surge) et gauche/droite (yaw) restent acceptées comme équivalents. **Les touches se combinent** (Z + D + E : avancer en diagonale à droite en tournant à droite) ; deux touches opposées d'un même axe s'annulent. La localisation peut être en échec sans bloquer le pilotage manuel, tant que connexion et flux lidar sont récents.

Sous Windows, il suffit de brancher une manette reconnue par XInput (la case **Manette Xbox** est cochée d'office) :

| Entrée | Action |
|---|---|
| Stick gauche | Surge (haut / bas) et sway (gauche / droite) en même temps, proportionnels |
| Stick droit, axe horizontal | Yaw (rotation) |
| **RB** (un appui) | Bascule la cartographie : activée ↔ en pause (localisation seule). Le mouvement n'est pas touché |
| **B** (maintenu) ou **Espace** | STOP immédiat, sans rien décocher ; le pilotage reprend dès que B est relâché. Le lidar et la localisation continuent |

Recentrer les sticks ou relâcher les touches arrête déjà le mouvement. Zone morte 22 % (radiale sur le stick gauche), puissance proportionnelle plafonnée par le curseur PWM. Le clavier n'agit que si la zone de commandes a le focus et la manette que si l'onglet Robot est affiché : **sinon les moteurs s'arrêtent** (évite qu'une commande reste active pendant qu'on écrit ailleurs), et le pilotage reprend tout seul au retour. En revanche, une **localisation perdue ne bloque pas le pilotage** : seul l'ajout de points à la carte est suspendu.

**Protocole.** Un mouvement sur un seul axe part toujours en `SA1` (identique à avant, compatible avec l'ancien firmware). Un mouvement combiné part en `SA2 jeton séquence vx vy w` avec trois pourcentages signés (-100 à 100 ; positifs = avance, gauche, rotation à gauche). Le firmware mélange les quatre roues mécanum et, si une roue dépasserait 100, réduit toutes les roues ensemble : la direction est conservée, seule la vitesse baisse. Le firmware annonce `READY jeton SA2` ; **il faut le reflasher pour les mouvements combinés**. Avec l'ancien firmware, l'application garde l'axe dominant et affiche « Reflasher ScanAtlas_WiFi » plutôt que de perdre la liaison.

Espace, Échap, perte de focus, changement d'espace, disparition de la manette et perte du lidar ou de la connexion conservent les arrêts. Le plafond reste 100/255. Les lignes PC / ESP32 distinguent une commande émise et une commande effective acquittée ; elles ne mesurent pas la rotation des roues.

La démonstration lance le simulateur local sans matériel. Les touches y déplacent un robot virtuel. Elle permet de tester la carte et les contrôles, sans valider les moteurs ou la radio.

## Firmware moteurs : choix PWM ou I2C

Sketch : `firmware/ScanAtlas_WiFi/ScanAtlas_WiFi.ino`. Cible compilée : ESP32 classique, Arduino-ESP32 **2.0.17**. Le pilote PWM prévoit aussi les appels LEDC 3.x, testés sur une API simulée ; une compilation réelle 3.x n'est pas revendiquée.

**Tous les réglages moteurs sont dans un seul fichier : `firmware/ScanAtlas_WiFi/motor_config.h`.** Les robots n'étant pas tous câblés pareil, le firmware sait piloter la carte moteur de deux manières ; on choisit à la compilation (puis on téléverse) :

```cpp
#define MOTOR_DRIVER MOTOR_DRIVER_PWM   // ou MOTOR_DRIVER_I2C
```

Le protocole Wi-Fi (SA1 / SA2), l'interface, le mélange mecanum et le mode diagnostic sont identiques avec les deux pilotes ; seule la façon d'écrire sur la carte moteur change. Au démarrage, le moniteur série à 115200 affiche `Pilote moteur : PWM` ou `Pilote moteur : I2C`. Une configuration incohérente (broche inutilisable, doublon, roue affectée deux fois) affiche `Profil moteur invalide (pilote ...)` et bloque le démarrage moteur.

### Pilote PWM (`MOTOR_DRIVER_PWM`)

Huit sorties PWM directes (LEDC, 20 kHz) vers les entrées de la carte moteur.

| Entrée moteur | GPIO proposé |
| --- | ---: |
| M1A / M1B | 5 / 18 |
| M2A / M2B | 19 / 21 |
| M3A / M3B | 2 / 4 |
| M4A / M4B | 16 / 17 |

Ce relevé reste à confirmer sur chaque robot. Réglages dans `motor_config.h` : **`PIN_M1A` … `PIN_M4B`** (un nom par entrée de la carte moteur) fixent les GPIO, il suffit d'écrire le bon numéro ; les GPIO acceptés et interdits sont listés dans le fichier ; `WHEEL_MOTOR` associe M1..M4 aux roues avant gauche, avant droite, arrière gauche et arrière droite ; `WHEEL_SIGN` inverse une polarité si nécessaire ; `MOTOR_PWM_HZ` règle la fréquence.

### Pilote I2C (`MOTOR_DRIVER_I2C`)

La carte moteur est pilotée par un bus I2C logiciel (bibliothèque `MecanumCar_v2` fournie dans le dossier du sketch, adresse 0x30 fixée dans `MecanumCar_v2.cpp`). Réglages : `I2C_SDA_PIN` / `I2C_SCL_PIN` (19 / 21 par défaut, comme le firmware de démonstration d'origine) ; `I2C_WHEEL_MOTOR` associe les roues aux moteurs I2C ; `I2C_WHEEL_SIGN` inverse une polarité.

| Moteur I2C | Canaux | Roue par défaut |
| --- | --- | --- |
| Upper_R | 1 / 2 | avant droite |
| Upper_L | 3 / 4 | avant gauche |
| Lower_R | 5 / 6 | arrière droite |
| Lower_L | 7 / 8 | arrière gauche |

Une puissance positive agit sur le canal pair (2, 4, 6, 8), comme « avancer » dans la bibliothèque d'origine. Le sens d'avance de chaque roue reste à vérifier sur chaque robot.

### Sens des axes et vitesse (les deux pilotes)

Dans `motor_config.h` :

- **`AXIS_SURGE_SIGN`, `AXIS_SWAY_SIGN`, `AXIS_YAW_SIGN`** (1 ou -1) inversent un mouvement entier (avancer, déplacement latéral, rotation) sans toucher au câblage. Le sway est à **-1** par défaut : sur le robot essayé, Q (gauche) partait à droite. Si le vôtre est correct dans l'autre sens, mettre 1.
- **`MOTOR_DUTY_MIN` / `MOTOR_DUTY_MAX`** (sur 0..255) : le pourcentage de l'application (0..100) est converti en PWM dans cet intervalle ; 100 % = `MOTOR_DUTY_MAX` (255 par défaut). Avant ce réglage, le pourcentage était envoyé tel quel comme PWM sur 255, donc 100 % ne donnait que 39 % de puissance : c'est la cause de la lenteur observée. Si les roues ne tournent pas aux petites valeurs, mettre par exemple `MOTOR_DUTY_MIN` à 50.
- Alimentation : les moteurs doivent être alimentés par les piles 18650 (interrupteur de la carte sur ON). Sur le seul USB, la tension chute dès que les moteurs démarrent : lenteur, puis redémarrage de l'ESP32 (« suspendu »). Le moniteur série à 115200 affiche la cause du dernier démarrage, `BROWNOUT` en cas de chute de tension.

### Vérifier les roues (les deux pilotes)

Passer `MOTOR_DIAGNOSTIC=true`, téléverser, ouvrir le moniteur série à 115200, roues levées. `1` à `4` donnent une impulsion dans un sens sur le moteur 1..4 (M1..M4 en PWM ; Upper_R, Upper_L, Lower_R, Lower_L en I2C) ; `a` à `d` dans l'autre sens. Impulsion de 250 ms à puissance 50 ; espace arrête. Ce mode ne démarre ni Wi-Fi ni lidar. Remettre la valeur à false et téléverser pour piloter normalement. Les GPIO de la console et du lidar sont réservés. Ces essais n'ont pas été réalisés physiquement ici.

## Direct filaire (USB)

La barre de connexion, en haut de l'espace **Robot en direct**, propose **Wi-Fi** ou **USB filaire** (adresse du robot, ou port : `auto` ou `COM8`). En USB, le PC garde sa connexion internet (le hotspot du robot la coupe) et le Wi-Fi est hors de cause : c'est le moyen le plus simple de savoir si une perte de scans vient du Wi-Fi.

1. Téléverser le firmware `ScanAtlas_WiFi` à jour (la liaison filaire en fait partie).
2. Brancher le robot en USB avec un câble de données, **fermer le moniteur série d'Arduino** (il occuperait le port).
3. Choisir **USB filaire**. Le champ vaut `auto` : le port est trouvé tout seul s'il n'y en a qu'un plausible ; sinon écrire le port (par exemple `COM8`).
4. Connecter. Cartographie, localisation, clavier, manette et encart fonctionnent comme en Wi-Fi.

Principe : le PC ouvre le port à 115200, envoie `LIVE jeton débit`, le robot répond `READY` puis les deux côtés passent à **921 600 bauds** (115200 ne suffit pas pour environ dix tours lidar par seconde). Les tours lidar (mêmes trames SA06 avec CRC) et les commandes SA1 / SA2 circulent ensuite sur le même câble. Le bail de 300 ms est identique : sans commande, les moteurs s'arrêtent et le robot revient à 115200, ce qui laisse l'acquisition USB historique utilisable. Les trames abîmées sont ignorées (jamais insérées en carte). Un robot déjà piloté en Wi-Fi répond « déjà utilisé » ; un robot qui ne répond pas dans les 6 secondes donne un message demandant de vérifier le firmware et le moniteur série.

Limites : non essayé avec un vrai câble ni un vrai robot ici ; le débit 921 600 dépend de la puce USB de la carte (CP210x et CH340 le gèrent) ; si le port est mauvais ou occupé, le message de l'application le dit.

## Diagnostiquer une coupure : le journal série du robot

Le firmware écrit sur la console série (115200, moniteur série d'Arduino) des événements horodatés en millisecondes, **hors liaison filaire** et hors capture CSV :

- au démarrage, **la cause du dernier redémarrage** (mise sous tension, plantage, watchdog, **BROWNOUT** = tension trop basse, donc alimentation ou batterie) ;
- appareils Wi-Fi associés ou déconnectés ;
- session Wi-Fi ouverte, bail expiré (plus de commande pendant 300 ms), flux de scans ouvert ou fermé ;
- lidar muet : aucun octet reçu (alimentation, câble ou broche 33) ou plus de tour complet depuis 1,5 s.

Pour une coupure, laisser le moniteur série ouvert pendant l'essai et noter les dernières lignes avant l'arrêt des scans. Le réglage `LOG_LIAISON` du sketch désactive ces messages.

## USB et Wi-Fi avec le même programme

Le nouveau firmware offre le hotspot ScanAtlas et la sortie USB à la demande. Pour utiliser l'USB avec ce programme, une mise à jour du sketch est nécessaire. Acquisition ouvre le port à 115200, attend le redémarrage éventuel, envoie `SCAN N`, reçoit le CSV historique à six colonnes puis envoie `SCAN 0`. Les tours sont complets ; la liaison USB peut être plus lente que la rotation lidar et ne transmet donc pas tous les tours physiques.

Un bail de pilotage Wi-Fi actif refuse une nouvelle capture USB. L'application déconnecte le pilotage avant de capturer. Le firmware continue de décoder le lidar pendant le transfert. L'ancien firmware qui émet du CSV en continu reste compatible avec l'acquisition PC ; le nouveau transport Wi-Fi garde le protocole SA1 / SA06.

## Validation et limites

Les vérifications couvrent le calcul historique, le mixage mécanum et l'analyse `SA2` du firmware compilés côté hôte, la négociation avec un ancien firmware, la conversion manette, l'encart des commandes, les trois références du TP, la conservation des sessions, la grille figée en localisation seule, une pose initiale inconnue à 145°, le journal, l'annulation de pose, les axes Xbox, le CSV USB et les appels PWM sur API simulée 2.x/3.x. Un test Tk sur écran virtuel contrôle les trois espaces, la grande carte, les vues, le clavier, la perte de suivi et sa récupération.

La compilation cible produit un binaire ESP32. Elle ne valide pas les branchements, l'emplacement des roues, les polarités, le seuil de démarrage des moteurs, la radio, le pilote Windows de la manette ou la déformation d'un scan pendant le mouvement. La fermeture de boucle et la navigation autonome restent à développer. Un environnement répétitif peut produire une ambiguïté ; aucune mesure réelle d'erreur absolue n'est déduite du score de concordance.

## Sources techniques publiques

- Espressif, migration LEDC 2.x vers 3.x : https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html
- Microsoft, XInputGetState : https://learn.microsoft.com/en-us/windows/win32/api/xinput/nf-xinput-xinputgetstate
- Microsoft, XINPUT_GAMEPAD : https://learn.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_gamepad
- Les références antérieures sur le scan matching figurent dans SUIVI_CONTINU.md.

## Capture directe dans Localisation

Le panneau de droite de l'onglet **Localisation** commence par **Capture directe**. **Capturer et localiser** reçoit un ou plusieurs scans (USB ou Wi-Fi, source choisie dans ce panneau ; port USB, baud et adresse Wi-Fi restent dans Acquisition) et les superpose automatiquement **au dernier scan de la liste**, qui sert de référence et de pose de départ. La localisation est toujours active ici, quelle que soit la case de l'onglet Acquisition.

Méthodes : **Recherche large + ICP** (par défaut : fenêtre de ± x, y et ± orientation autour de la pose du dernier scan), **ICP local** (rapide, pour de petits déplacements) ou **recherche sur la carte cumulée 360°** (toute la carte, sans fenêtre ; les scans non raccordés forment des groupes en attente). Le résultat reste dans Localisation : référence en gris, nouveau scan à sa pose en vert (orange si non localisé), avec le motif de l'échec le cas échéant. Une mesure n'est jamais perdue : un scan non localisé est conservé, décoché Carte.

Le panneau repliable **Réglages ICP** donne les curseurs et champs de distance d'appariement, d'itérations et de fenêtre de recherche. Ce sont les **mêmes réglages** que pour l'acquisition automatique et l'assemblage : un seul jeu pour toute l'application. Les fenêtres ne servent qu'à « Recherche large + ICP ».
