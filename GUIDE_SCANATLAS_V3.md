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

Les mesures, poses et éventuels segments construits sur exactement les scans cochés sont copiés. Les originaux de Cartographie restent indépendants. Une reconnexion demande aussi une localisation globale ; aucun déplacement nul n'est supposé entre deux connexions. **Rechercher ma position · 360°** permet de relancer cette recherche après un déplacement inconnu.

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

Cocher **Clavier actif** place le focus dans la bande de commandes : flèches haut/bas pour avancer/reculer, gauche/droite pour tourner, A/D pour le déplacement latéral. La localisation peut être en échec sans bloquer le pilotage manuel, tant que connexion et flux lidar sont récents.

Sous Windows, connecter une manette reconnue par XInput puis cocher **Manette Xbox**. Maintenir **LB** pour autoriser une commande. Stick gauche : translation avant/arrière ou latérale ; stick droit horizontal : rotation. L'axe dominant est utilisé ; les mouvements combinés ne sont pas implémentés dans le protocole actuel. La puissance est proportionnelle au stick, plafonnée par le curseur. Zone morte 22 %. B impose STOP, relâcher LB impose STOP. Il faut conserver le focus dans la bande de pilotage.

Espace, Échap, perte de focus, changement d'espace, disparition de la manette et perte du lidar ou de la connexion conservent les arrêts. Le plafond reste 100/255. Les lignes PC / ESP32 distinguent une commande émise et une commande effective acquittée ; elles ne mesurent pas la rotation des roues.

La démonstration lance le simulateur local sans matériel. Les touches y déplacent un robot virtuel. Elle permet de tester la carte et les contrôles, sans valider les moteurs ou la radio.

## Firmware PWM et câblage

Sketch : `firmware/ScanAtlas_WiFi/ScanAtlas_WiFi.ino`. Cible compilée : ESP32 classique, Arduino-ESP32 **2.0.17**. Le pilote prévoit aussi les appels LEDC 3.x, testés sur une API simulée ; une compilation réelle 3.x n'est pas revendiquée.

Le programme utilise maintenant huit sorties PWM directes. L'ancienne bibliothèque `MecanumCar_v2` et les exemples d'origine restent dans le dépôt pour référence, mais le sketch ScanAtlas ne les utilise plus.

| Entrée moteur | GPIO proposé |
| --- | ---: |
| M1A / M1B | 5 / 18 |
| M2A / M2B | 19 / 21 |
| M3A / M3B | 2 / 4 |
| M4A / M4B | 16 / 17 |

Ce relevé reste à confirmer sur chaque robot. Modifier **motor_config.h** : `MOTOR_PINS` fixe les GPIO de ces entrées ; `WHEEL_MOTOR` associe M1..M4 aux roues avant gauche, avant droite, arrière gauche et arrière droite ; `WHEEL_SIGN` inverse une polarité si nécessaire. L'affectation physique et les polarités sont provisoires. Les GPIO de la console et du lidar sont réservés ; une configuration incohérente refuse le démarrage moteur.

Pour vérifier une roue : passer `MOTOR_DIAGNOSTIC=true`, téléverser, ouvrir le moniteur série à 115200, roues levées. `1` à `4` donnent une impulsion dans un sens sur M1..M4 ; `a` à `d` dans l'autre sens. Impulsion de 250 ms à PWM 50 ; espace arrête. Ce mode ne démarre ni Wi-Fi ni lidar. Remettre la valeur à false et téléverser pour piloter normalement. Ces essais n'ont pas été réalisés physiquement ici.

## USB et Wi-Fi avec le même programme

Le nouveau firmware offre le hotspot ScanAtlas et la sortie USB à la demande. Pour utiliser l'USB avec ce programme, une mise à jour du sketch est nécessaire. Acquisition ouvre le port à 115200, attend le redémarrage éventuel, envoie `SCAN N`, reçoit le CSV historique à six colonnes puis envoie `SCAN 0`. Les tours sont complets ; la liaison USB peut être plus lente que la rotation lidar et ne transmet donc pas tous les tours physiques.

Un bail de pilotage Wi-Fi actif refuse une nouvelle capture USB. L'application déconnecte le pilotage avant de capturer. Le firmware continue de décoder le lidar pendant le transfert. L'ancien firmware qui émet du CSV en continu reste compatible avec l'acquisition PC ; le nouveau transport Wi-Fi garde le protocole SA1 / SA06.

## Validation et limites

Les vérifications couvrent le calcul historique, les trois références du TP, la conservation des sessions, la grille figée en localisation seule, une pose initiale inconnue à 145°, le journal, l'annulation de pose, les axes Xbox, le CSV USB et les appels PWM sur API simulée 2.x/3.x. Un test Tk sur écran virtuel contrôle les trois espaces, la grande carte, les vues, le clavier, la perte de suivi et sa récupération.

La compilation cible produit un binaire ESP32. Elle ne valide pas les branchements, l'emplacement des roues, les polarités, le seuil de démarrage des moteurs, la radio, le pilote Windows de la manette ou la déformation d'un scan pendant le mouvement. La fermeture de boucle et la navigation autonome restent à développer. Un environnement répétitif peut produire une ambiguïté ; aucune mesure réelle d'erreur absolue n'est déduite du score de concordance.

## Sources techniques publiques

- Espressif, migration LEDC 2.x vers 3.x : https://docs.espressif.com/projects/arduino-esp32/en/latest/migration_guides/2.x_to_3.0.html
- Microsoft, XInputGetState : https://learn.microsoft.com/en-us/windows/win32/api/xinput/nf-xinput-xinputgetstate
- Microsoft, XINPUT_GAMEPAD : https://learn.microsoft.com/en-us/windows/win32/api/xinput/ns-xinput-xinput_gamepad
- Les références antérieures sur le scan matching figurent dans SUIVI_CONTINU.md.
