# TP Jour 2 — trois localisations et évaluation chiffrée

## Ce qui est implémenté

Les trois références demandées sont maintenant disponibles dans l’onglet **Localisation**. Pour chacune, deux stratégies fonctionnent : affinement local robuste et recherche multi-résolution suivie du même affinement. Il ne s’agit pas de présenter trois fois un ICP contre les mêmes points.

| Référence | Données réellement utilisées | Distance minimisée |
| --- | --- | --- |
| Grille d’occupation | Cellules observées dont la probabilité d’occupation est au moins 0,60. | Champ de distances aux cellules occupées, interpolé dans la grille. Les espaces inconnus ne sont pas assimilés à des obstacles ou à une distance nulle. |
| Carte vectorielle | Extrémités et géométrie des segments finis construits dans Carte vectorielle. | Distance à la projection sur chaque segment, bornée à ses extrémités, puis choix du plus proche. La projection au-delà d’une extrémité ne reste pas sur une droite infinie. |
| Scan de référence | Points filtrés du scan fixe, dans sa pose. | Distance aux points les plus proches, trouvés par arbre cKDTree. |

La pose estimée comporte x, y et θ. Les points du mobile sont recalculés à partir de ses angles et distances locaux, puis transformés par la pose essayée. L’algorithme ne modifie pas les mesures brutes et n’utilise pas pose_connue pour se guider.

## Déroulement du calcul

1. Construire la référence à partir des seuls scans fixes. Le mobile doit en être exclu ; l’interface le vérifie pour les cartes construites par l’application.
2. Filtrer le mobile avec les filtres communs puis conserver au plus 600 points distincts pour borner le travail. Les scans à plusieurs tours ne sont pas refusés à cause de leur nombre de points.
3. Partir de sa pose actuelle. En mode local, lancer directement la minimisation. En mode multi-résolution, tester d’abord un voisinage de ±1 m et ±30° au pas de 0,50 m et 10°, puis affiner les candidats à 0,25 m / 5° et 0,125 m / 2,5°.
4. Affiner avec scipy.optimize.least_squares, méthode TRF, Jacobien numérique et perte soft_l1 de paramètre 0,05 m. Le résidu est issu de la référence choisie ; la perte robuste réduit le poids des points aberrants. Les résidus sont bornés pour limiter leur influence.
5. Vérifier la convergence, au moins douze points et 65 % d’accord à 12 cm, ainsi que le rang du problème. Pour la grille, plus de 8 % de contradictions avec les cases observées libres fait refuser la pose. La multi-résolution compare aussi les solutions éloignées de coûts voisins pour signaler les ambiguïtés.
6. Montrer l’aperçu et les métriques avant application. Appliquer ne change que la pose du mobile. Une référence, une pose ou des filtres modifiés pendant le calcul font écarter le résultat.

Ce mode TP suppose une pose approchée et permet d’évaluer la sensibilité à l’initialisation, comme demandé dans la consigne. Les fenêtres TP sont automatiques, sans réglage obligatoire à effectuer. Il ne remplace pas le mode de relocalisation globale 360°, qui reste dans Localisation pour les déplacements arbitraires. Un affinement local peut encore accepter une mauvaise convergence : les résultats ci-dessous le montrent explicitement.

## Utilisation étape par étape

Après mise à jour, relancer **installer_windows.bat** : SciPy est une nouvelle dépendance. Puis lancer l’application.

1. Importer les scans ou charger la démonstration.
2. Pour une carte de référence, cocher uniquement les scans fixes dans Carte, en excluant le futur mobile. Construire la grille dans Grille et la carte de segments dans Carte vectorielle.
3. Sélectionner le scan mobile à gauche puis ouvrir Localisation. Pour le mode Scan, choisir un autre scan comme référence fixe dans la liste dédiée.
4. Choisir le type et la stratégie, puis Localiser sur cette référence. Examiner la superposition, la concordance, le temps et le message. Appliquer seulement si le résultat convient.
5. Utiliser le bouton d’évaluation pour exporter les résultats détaillés et la synthèse sur les mêmes scans simulés. Cette évaluation ne change pas la session utilisateur.

On peut aussi relancer le banc sans interface :

`python evaluer_tp_jour2.py --sortie exemples/evaluation_tp_jour2.csv`

## Protocole reproductible

Le scan fixe de la démonstration construit les trois références. Le mobile, provenant de la même salle avec obstacle, a pour pose vraie (−0,8 m, +0,4 m, +15°). Cette pose n’est utilisée que pour définir les perturbations du banc et mesurer les erreurs. Elle n’est pas donnée au solveur comme une contrainte.

Pour chaque combinaison, le même mobile, les mêmes filtres 0,05–12 m / intensité 0 et les sept mêmes perturbations sont utilisés :

| Cas | Δx initial (m) | Δy initial (m) | Δθ initial (°) |
| --- | ---: | ---: | ---: |
| 1 | 0 | 0 | 0 |
| 2 | 0,10 | −0,10 | 2 |
| 3 | 0,30 | −0,20 | 6 |
| 4 | 0,50 | 0,30 | 15 |
| 5 | 0,80 | −0,60 | 20 |
| 6 | 1,00 | 0,50 | 25 |
| 7 | 3,00 | 3,00 | 70 |

Le cas 7 est volontairement hors du voisinage TP annoncé. Les temps d’optimisation sont mesurés au chronomètre monotone ; le coût de préparation de la référence est enregistré séparément. Les timings dépendent du PC et de sa charge.

Erreur de position : norme euclidienne de l’écart en x et y. Erreur angulaire : plus petit écart modulo 360°. Réussite : position ≤0,10 m ET angle ≤2°. Le taux de réussite compte les poses dans ces seuils, même si le contrôle interne les refuse. Le nombre de poses correctes acceptées et le nombre de poses fausses acceptées sont donc donnés séparément. Un faible RMSE ou un pourcentage de concordance n’est pas une erreur vraie ni une probabilité de succès.

## Résultats obtenus

| Référence | Stratégie | Réussite vraie | Correctes acceptées | Fausses acceptées | Refus | Temps médian |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Grille | Locale | 5/7 (71,4 %) | 5 | 0 | 2 | 26,4 ms |
| Grille | Multi-résolution puis locale | 6/7 (85,7 %) | 6 | 0 | 1 | 260,1 ms |
| Vectorielle | Locale | 5/7 (71,4 %) | 5 | 1 | 1 | 21,4 ms |
| Vectorielle | Multi-résolution puis locale | 6/7 (85,7 %) | 6 | 0 | 1 | 217,0 ms |
| Scan | Locale | 5/7 (71,4 %) | 4 | 0 | 3 | 69,5 ms |
| Scan | Multi-résolution puis locale | 6/7 (85,7 %) | 6 | 0 | 1 | 418,7 ms |

La multi-résolution réussit ici les six départs dans son voisinage prévu. Le départ très éloigné est refusé pour les trois références. Le résultat local vectoriel du cas 6 est une fausse convergence acceptée : erreur 0,634 m et environ 90°, malgré 72,5 % de concordance. Ce défaut n’est pas supprimé des statistiques. L’affinement local convient au suivi avec une bonne prédiction ; il ne garantit pas la relocalisation après un grand saut.

Une pose de scan est correcte mais refusée en mode local, ce qui distingue qualité réelle et conservatisme du contrôle. La grille introduit une discrétisation à 5 cm ; son erreur ne doit pas être interprétée comme une mesure de l’incertitude du robot.

Fichiers de preuve :

- exemples/evaluation_tp_jour2.csv : 42 essais, erreurs, temps, concordances, décisions, seuils et départs.
- exemples/evaluation_tp_jour2_synthese.csv : six combinaisons, taux de réussite, faux acceptés et temps médian/P95.
- exemples/TP_JOUR2_ERREURS.png : sensibilité aux sept initialisations.
- exemples/TP_JOUR2_TROIS_REFERENCES.png : aperçus avant/après avec les trois vrais types de références.

Ce banc porte sur deux scans simulés d’une même géométrie, déjà utilisée pendant le développement. Il ne constitue ni une validation indépendante, ni une garantie de temps réel ou de robustesse sur le robot. Les CSV restent la source des chiffres ; les graphiques n’effacent pas les échecs.

## Références réelles et incertitudes

Aucune pose réelle mesurée au sol avec une incertitude documentée n’a été fournie pour cette comparaison. Les poses réglées manuellement sur des scans ne sont pas traitées comme une vérité exacte. L’erreur vraie sur le robot et le taux de réussite physique ne sont donc pas annoncés.

Pour compléter l’essai matériel, relever les poses par une méthode indépendante et renseigner le fichier references_robot_modele.csv : méthode, x, y, orientation et incertitudes associées. Indiquer la résolution de mesure et la répétabilité ; mesurer aussi le décalage du lidar sur le châssis. Comparer les méthodes sur les mêmes enregistrements et les mêmes départs. Si l’incertitude de référence est du même ordre que le seuil de réussite, préciser les cas dont la classification est indécidable plutôt que leur attribuer une réussite certaine.

## Sources et rôle des bibliothèques

- SciPy, least_squares : https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html — minimisation non linéaire robuste et Jacobien numérique. SciPy fournit le noyau numérique ; les modèles, les distances, les contrôles et le protocole sont implémentés dans ScanAtlas.
- SciPy, distance_transform_edt : https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html — distances euclidiennes sur la grille.
- SciPy, cKDTree : https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html — voisins des points du scan de référence.
- Cartographer, https://google-cartographer-ros.readthedocs.io/en/latest/algo_walkthrough.html — idée de recherche corrélative suivie d’une optimisation et distinction suivi local / corrections globales.
- CSM, https://github.com/AndreaCensi/csm — inspiration pour la distance point vers droite. Ici la distance porte sur des segments finis et le solveur est SciPy ; ce n’est pas une intégration du code CSM.

La recherche de projets existants et le projet Wi-Fi/moteurs restent détaillés dans ARCHITECTURE_TEMPS_REEL_WIFI.md. Le nouvel import GitHub f6fd482 contient maintenant MecanumCarV2/ESP32MecanumCar/ESP32MecanumCar.ino : six mouvements et arrêt via I2C SDA 19 / SCL 21. Ce code a été lu ; sa démonstration temporisée ne fournit pas encore de Wi-Fi. Son intégration réseau et matérielle reste une étape distincte de la localisation TP livrée ici.
