# Acquisition et dépannage du suivi

Mise à jour du 3 novembre 2026. Cette livraison concerne l'application PC ; le firmware reste inchangé.

## Capturer sans perdre les outils existants

L'onglet **Acquisition** propose USB ou Wi-Fi. Choisir 1 à 20 scans, puis Capturer. Sans la case de localisation automatique, les mesures brutes sont ajoutées à la session sans recalage. Les blocs de plusieurs tours restent conservés. Imports CSV/ZIP, sessions, filtres, poses, grille, segments et Localisation restent disponibles.

- **USB** : utiliser le programme ESP32 historique qui produit les six colonnes CSV, renseigner le port et le baud (habituellement 115200), fermer le moniteur série Arduino.
- **Wi-Fi** : utiliser `firmware/ScanAtlas_WiFi/ScanAtlas_WiFi.ino`, connecter le PC au hotspot et renseigner 192.168.4.1. La capture envoie seulement STOP et ne nécessite aucune carte préalable.

Le firmware Wi-Fi actuel ne produit pas le CSV USB historique : pour changer de transport, il faut encore charger le firmware correspondant. Une sortie USB à la demande dans le même firmware reste à intégrer et à tester. Le programme CSV historique n'est pas modifié.

Une capture déconnecte le pilotage actif, avec STOP, tout en conservant la carte directe et les scans de session. Reconnecter ensuite dans Robot Wi-Fi. « Vers la session » transfère les scans clés de la carte directe pour les enregistrer.

## Pilotage et suivi indépendants

Cocher **Pilotage manuel au clavier** place le focus dans la bande de pilotage. Les flèches commandent le robot si la connexion fonctionne et si les tours lidar arrivent depuis moins de 0,6 s. Une pose refusée suspend seulement l'ajout à la carte, sans désarmer le clavier.

La perte de focus, le changement d'onglet, le relâchement des touches, Espace et Échap conservent leurs arrêts. Une perte de connexion ou du flux lidar conserve aussi les protections existantes. Le pilotage est manuel ; il n'y a pas d'évitement automatique des obstacles.

L'affichage distingue **PC** (dernière commande envoyée) et **ESP32** (commande effective acquittée). EN ATTENTE indique l'absence d'acquittement récent. FORWARD côté ESP32 confirme le protocole, pas la rotation physique des roues.

## Reprise après refus

L'ancien code restait bloqué après le premier recalage refusé. Il réessaie maintenant au maximum deux fois par seconde près de la dernière pose acceptée. La reprise automatique est limitée à 25 cm et 8°. Le bouton Reprendre le suivi permet un essai explicite jusqu'à 1,2 m et 35°, sans contourner les contrôles de géométrie, de concordance et d'erreur. Ce n'est pas une relocalisation globale.

Les scans refusés n'entrent pas dans la carte. Une attente affiche « -- » plutôt qu'un faux 0 %. Le motif de refus reste visible. La prédiction est réinitialisée après récupération. La vue en pause n'est plus redessinée à chaque tour, ce qui évite une charge inutile sur Tk.

## Essais matériels restant à faire

L'utilisateur indique que l'exemple moteur ne fonctionne pas non plus sur le robot utilisé, parmi huit robots disponibles. Il prévoit d'en essayer un autre. Cela ne prouve ni la cause matérielle ni la correction du mouvement. La cause du premier refus de recalage à l'arrêt reste à mesurer ; le blocage permanent après ce refus, lui, a été identifié dans le code.

1. Robot immobile, vérifier plusieurs minutes de suivi, relever les messages de refus et les reprises.
2. Roues levées, vérifier PC et ESP32 pendant une touche puis à son relâchement. Contrôler le mouvement réel et l'arrêt.
3. Capturer en Wi-Fi, vérifier l'ajout dans la session ; vérifier séparément la capture USB avec le programme CSV historique.

Les tests automatisés utilisent un robot réseau simulé et des géométries connues. Ils ne valident pas les moteurs, la liaison radio réelle ni le comportement mécanique.
