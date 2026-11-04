# Localisation sur plusieurs scans

## Utilisation

Dans Localisation, conserver **Recherche large + ICP**. Pour les scans déjà chargés : cocher les scans à recaler dans Carte, dans leur ordre d’acquisition, puis cliquer **Superposer le lot coché Carte**. Le premier scan conserve sa pose et définit le repère. Chaque suivant part de la dernière pose acceptée ; ses coordonnées initiales propres ne guident pas ce calcul de lot. La référence est une sous-carte des cinq derniers scans acceptés. Les mesures brutes ne changent pas.

Les poses acceptées sont appliquées à la fin du calcul. Les échecs conservent leurs poses d’entrée, sont signalés et décochés Carte pour éviter de fausser la cartographie. Le bouton d’annulation des poses du dernier lot restaure aussi leur état Carte. Une annulation pendant le calcul ou une modification des données fait écarter tout le résultat du lot. Enregistrer ensuite la session.

En Acquisition USB, la case automatique utilise désormais jusqu’à cinq références : le dernier scan chargé (ancre initiale si sa pose a été réglée manuellement) et jusqu’à quatre scans antérieurs validés automatiquement. Des scans importés sans statut ne sont pas tous supposés alignés. Un échec n’entre pas dans la sous-carte. Après un dernier scan refusé, corriger sa pose avant de reprendre. Le premier scan seul n’est pas localisé : il ancre le repère.

Les archives ZIP sont importées par nom de fichier : cet ordre peut différer de l’acquisition. Préparer la liste dans le bon ordre avant le recalage ; aucun ordre temporel n’est déduit des coordonnées connues de MapTool. Si besoin importer les CSV séparément dans l’ordre voulu.

## Recherche et décision

La recherche translation/rotation grossière puis fine conserve plusieurs départs, puis les affine par ICP tronqué. Les réglages existants restent ±1 m par axe et ±30° autour de la pose de départ, distance d’appariement 0,5 m, 80 itérations. Ces fenêtres doivent couvrir le mouvement réel. Les filtres existants ne changent pas.

La sous-carte moyenne les points par cellules de 5 cm et conserve au plus 2400 représentants. Répéter exactement un même scan ne lui donne donc pas un poids supplémentaire. Les blocs de plusieurs tours restent acceptés : le nombre de points n’est pas un motif de rejet.

Après convergence de la recherche large :

- au moins 65 % des points du mobile et au moins 12 impacts doivent se trouver à moins de min(12 cm, demi-distance d’appariement) de la référence ;
- les normales locales, estimées sur au plus sept voisins à moins de 35 cm, doivent contraindre les deux directions de translation ; des murs presque tous parallèles font refuser le glissement possible ;
- deux solutions séparées de plus de 20 cm ou 5°, dont les coûts bornés diffèrent de moins de max(0,0004 m², 8 % du meilleur coût), sont déclarées ambiguës.

Ces contrôles sont des heuristiques numériques, sans garantie absolue. Le seuil de 65 % a été ajusté sur les essais MapTool ci-dessous : ce jeu est un jeu de réglage, pas une validation indépendante. Un grand recouvrement apparent ne garantit pas une bonne pose dans une salle répétitive. ICP local reste disponible comme comparaison historique, sans ces contrôles complets dans la localisation manuelle ; le lot et l’acquisition contrôlent également son accord fin et sa géométrie, mais sans recherche de solutions concurrentes. Recherche large est le mode conseillé.

## Évaluation reproductible

`python -m unittest discover -s tests`

`python outils/evaluer_robustesse.py chemin/ScanJules.zip`

Le ZIP fourni contient 15 scans MapTool. Le premier fichier importé sert de référence fixe ; les 14 autres ont chacun trois erreurs initiales identiques pour les deux méthodes : (+0,50 m,+0,30 m,+15°), (−0,50 m,+0,40 m,−20°), (+0,80 m,−0,60 m,+25°). Les poses des en-têtes servent uniquement à fabriquer les erreurs initiales et mesurer les erreurs finales. Réussite : position ≤0,10 m ET angle ≤2°. Les scans ne voient pas tous les mêmes obstacles depuis la référence unique.

| Méthode | Essais | Poses correctes acceptées | Poses fausses acceptées | Refus | Temps médian |
| --- | ---: | ---: | ---: | ---: | ---: |
| ICP local historique | 42 | 5 | 26 | 11 | 0,195 s |
| Recherche large avec contrôles | 42 | 15 | 0 | 27 | 1,802 s |

Un refus peut concerner une pose juste : la priorité est de limiter la propagation d’erreurs. Le taux de poses correctes acceptées est 35,7 % sur ce jeu difficile à référence unique ; il ne faut pas le présenter comme une localisation universellement fiable. Zéro faux accepté sur ce jeu ne prédit pas zéro en conditions réelles. Les temps dépendent du PC.

`python outils/evaluer_lot.py`

Une trajectoire de huit scans est générée dans une salle avec un obstacle, graine aléatoire 20261103 : bruit de distance d’écart type 15 mm, environ 20 % de mesures supprimées et environ 5 % de distances aberrantes parmi les mesures restantes. Déplacements jusqu’à environ 0,64 m et rotations jusqu’à 20° entre poses. Toutes les poses d’entrée sont nulles ; les sept scans après l’ancre sont correctement acceptés. Erreurs maximales : 0,0118 m et 0,222°, temps total environ 12,7 s. Les poses vraies ne sont jamais données au recalage. Les résultats détaillés sont dans exemples/robustesse_lot.csv.

Tests supplémentaires : salle carrée aux orientations équivalentes refusée, murs parallèles refusés, mauvais accord fin refusé, référence d’un lot excluant un scan refusé, conservation des mesures, annulation et invalidation des résultats devenus périmés. Ce sont des essais logiciels sans nouveau test ESP32/LD06 sur Windows.

## Limites et suite

Une sous-carte locale évite d’accumuler tous les défauts d’une très grande carte, mais n’élimine pas la dérive. Ce n’est pas une optimisation globale des poses ni une fermeture de boucle. En présence de symétries ou de peu de recouvrement, ajouter une mesure d’odométrie, une orientation IMU ou une pose initiale plus proche reste utile. Ne pas forcer la superposition d’une vue qui ne couvre pas la même zone. Les localisations sur grille et sur segments demandées par le TP restent des travaux distincts.

## Évolution suivante

Ce document décrit la version à sous-carte de cinq scans. Le mode par défaut actuel, la recherche globale sur 360° et la gestion des groupes sont décrits dans [LOCALISATION_GLOBALE.md](LOCALISATION_GLOBALE.md). Les anciens modes restent disponibles pour comparaison.
