# Superposition automatique entre deux scans

Le mode par défaut est désormais **Recherche large + ICP**. Il teste des poses
autour du départ avant les ajustements locaux. **ICP local** reste sélectionnable
pour comparaison. Les filtres de la session ne sont pas modifiés.

## Utilisation

1. Lancer l'application et importer deux scans ou ouvrir une session existante.
2. Dans Nuages, approcher le mobile de sa pose supposée par la souris ou les
   coordonnées. Pour les coordonnées, cliquer sur Appliquer la pose.
3. Dans Localisation, choisir la référence fixe et le scan à déplacer. Les
   numéros distinguent les acquisitions de même nom. Les choix sont explicites :
   Visible et Carte ne les excluent pas du recalage.
4. Cliquer sur Voir avant, puis Localiser (ICP). Le départ est la pose actuelle
   du mobile, pas la pose du scan sélectionné dans la liste de gauche.
5. Vérifier les murs communs : gris = référence, orange = mobile avant,
   vert = résultat provisoire. Lire recouvrement, RMSE, temps et état.
6. Appliquer la pose trouvée change uniquement le mobile. Enregistrer la session.
   Les cartes concernées sont invalidées et doivent être recalculées.

Les filtres communs sont appliqués aux deux scans. Un filtrage 1,8–6 m et une
intensité 220 peuvent laisser peu de géométrie commune. Le calcul demande au
moins six points distincts par scan. Aucun bloc n'est exclu pour son nombre de
points ou sa couverture de plusieurs tours. Maximum 1200 points par nuage pour
le calcul, avec sous-échantillonnage déterministe ; les mesures originales restent intactes.

## Méthode

ICP point à point 2D, implémenté avec NumPy sans ajouter de dépendance.
Le mobile est reconstruit dans son repère local en respectant la référence lidar
fixe de 270° pour les acquisitions réelles. La référence est dans sa pose globale.
À chaque tour : plus proches voisins, rejet au-delà de la distance d'appariement,
conservation des 80 % meilleurs accords, ajustement rigide par SVD avec rotation
propre (sans réflexion), composition de la correction avec la pose courante.

Valeurs initiales : distance 0,5 m, maximum 80 itérations. Au moins 30 % des
points mobiles doivent avoir une correspondance sous la distance limite ;
une géométrie de correspondances colinéaire est refusée. Arrêt si la correction
de la position du lidar est <0,1 mm et celle de l'angle <0,001°. L'application est
refusée après annulation, manque de recouvrement, géométrie dégénérée ou limite
d'itérations. Les résultats devenus périmés (choix, données, poses, filtres) ne
peuvent pas être appliqués. Le calcul travaille sur des copies dans un thread ;
l'interface reste disponible et le bouton Annuler permet l'arrêt.

La pose retournée est ABSOLUE dans le même repère que la référence. Le recouvrement
est la fraction du mobile située à moins de la distance limite d'un point de la
référence. Le RMSE est calculé sur ces correspondances avant troncature. Ces
indicateurs ne sont pas des probabilités de justesse ; leur population peut
changer entre avant et après. Une convergence locale peut donner une mauvaise
position, notamment dans une pièce symétrique ou avec une pose initiale éloignée.

Référence de méthode : documentation officielle Open3D, ICP registration,
https://www.open3d.org/docs/release/tutorial/pipelines/icp_registration.html
(consultée le 3 novembre 2026). Notre calcul 2D utilise NumPy, pas Open3D.

## Vérification chiffrée

```bash
python -m unittest discover -s tests -v
python evaluer_localisation.py --sortie exemples/resultats_icp.csv
```

La démo génère deux acquisitions de la même salle avec des poses différentes
et des occultations. La référence reste au zéro et la vraie pose mobile est
(-0,8 m ; 0,4 m ; 15°). On perturbe seulement la pose initiale, jamais les mesures.
Les six essais utilisent les mêmes nuages et filtres, distance ICP 0,5 m, 80 tours.
Réussite : erreur de position ≤0,10 m ET erreur angulaire circulaire ≤2°.

| Décalage initial x y angle | Erreur de position | Erreur angulaire | Résultat |
| --- | --- | --- | --- |
| 0 m, 0 m, 0° | 0,00225 m | 0,0336° | Réussite |
| 0,1 m, -0,1 m, 2° | 0,00290 m | 0,0491° | Réussite |
| 0,3 m, -0,2 m, 6° | 0,00290 m | 0,0491° | Réussite |
| 0,5 m, 0,3 m, -10° | 0,00140 m | 0,0507° | Réussite |
| 1 m, 0,5 m, 15° | 1,0564 m | 0,2329° | Échec malgré convergence |
| 3 m, 3 m, 70° | 4,2426 m | 70° | Recouvrement insuffisant |

4/6 réussites (66,7 %) sur CE protocole, pas un taux général. Les temps mesurés
sur cet environnement sont environ 0,01–0,15 s, à remesurer sur le PC utilisateur.
Le CSV contient les valeurs non arrondies. La pose exacte initiale ne donne pas
nécessairement une erreur finale nulle : échantillonnage et visibilité diffèrent.

Les tests couvrent aussi référence à pose non nulle, passage ±180°, repère 270°,
non-mutation des entrées, points aberrants, filtres, doublons, annulation,
limite d'itérations, géométrie colinéaire et refus d'appliquer un résultat périmé.
L'interface est vérifiée par ses actions et tracés sans écran ; un essai visuel
sous Windows et une validation réelle avec poses mesurées restent nécessaires.

## Suite du TP

Cette livraison couvre le recalage scan contre scan. La localisation sur grille
et sur carte vectorielle reste à réaliser ; le jour 2 n'est donc pas terminé.
Pour les cartes, exclure le scan évalué de leur construction. Sur les données
réelles, le placement manuel constitue seulement une référence approximative.
Le jour 3 devra combiner estimation de pose et intégration cartographique.


## Correction après les essais réels du jour 2

L’utilisateur observe un fonctionnement correct pour de petites corrections
(20–30 cm) et des rotations seules, mais des difficultés vers 50 cm et pour
rotation + translation. Sa capture confirme les filtres **0,05–12 m, intensité 0**.
L’hypothèse précédente de filtres 1,8–6 m / 220 ne s’appliquait pas à ces essais.
Les déplacements rapportés sont approximatifs, sans pose mesurée de référence.

Recherche large par défaut : fenêtre carrée ±1 m en x ET y et ±30° autour
de la pose actuelle du mobile. Réglages jusqu’à ±3 m et ±90°. Ces fenêtres sont
des limites de recherche, pas une précision garantie ; l’ICP affiné sortant
de ces limites est refusé. Le coût inclut les points non appariés avec une
pénalité bornée, au lieu de choisir un minuscule sous-ensemble très bien aligné.

Un champ de distances bornées aux impacts à 5 cm accélère la recherche NumPy,
sans nouvelle dépendance. La recherche utilise jusqu’à 300 points mobiles,
une grille de poses à environ 25 cm / 5° puis deux affinements locaux par deux.
Sur les grandes fenêtres, le pas de translation augmente pour limiter à 6000
poses la grille initiale. On conserve huit candidats spatialement distincts,
puis affine chacun par ICP sur jusqu’à 1200 points, avec le départ original
en candidat supplémentaire. Le score final utilise les distances exactes
sur tous les points échantillonnés, avec pénalité pour les points non appariés.
L’annulation est vérifiée pendant la recherche et entre les raffinements.

Pour reproduire la comparaison :

```bash
python evaluer_localisation.py --comparer --sortie exemples/comparaison_localisation.csv
```

Même référence, mobile, filtres, neuf poses initiales et critères (0,10 m / 2°)
pour les deux méthodes : **ICP local 7/9, recherche large + ICP 8/9**. Temps
médians de cet essai : environ 0,154 s et 0,892 s. Le cas à +1 m, +0,5 m, +15°
est corrigé par la recherche large ; l’ICP seul aboutit à 1,056 m d’erreur.
Le départ +3 m, +3 m, +70° reste hors de la fenêtre par défaut et échoue.
Cela ne constitue pas un taux général de réussite ni une validation sur le robot.
75 tests passent, dont translation/rotation combinées, limites, annulation et
prise en compte des points non appariés. Essai Windows et nouvelle session
réelle nécessaires ; symétries et objets mobiles peuvent toujours piéger le calcul.
