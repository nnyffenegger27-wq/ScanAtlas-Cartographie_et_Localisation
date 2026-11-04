> **Note (interface web).** Les écrans, onglets et fichiers Tkinter cités ici (`app.py`, `interface_wifi.py`, `interface_tp.py`…) ont été remplacés par l'interface web : voir [GUIDE_WEB.md](../GUIDE_WEB.md). Les principes, calculs et résultats décrits restent valables.

# Segments multiscans et carte vectorielle

## Changements du 2 novembre 2026

L'onglet Segments utilise tous les scans cochés **Carte**, indépendamment de
la sélection et de la colonne Visible. Les mesures restent séparées par scan
et par retour de tour : aucun segment ne relie artificiellement deux acquisitions.
Chaque scan est transformé avec sa propre pose. Les segments extraits portent
la couleur de leur scan et conservent un numéro pour le laboratoire. Sélectionner
un autre scan ne supprime plus ce résultat global.

La carte vectorielle utilisait déjà tous les scans cochés. Le défaut principal
était la fusion trop permissive : proximité de deux extrémités ou intersection
pouvait suffire, puis les fusions successives réajustaient seulement des
extrémités déjà moyennées. Le résultat pouvait dériver.

## Fusion corrigée

Angle, distance entre segments et compatibilité de leurs droites sont vérifiés.
La fusion est ensuite ajustée sur tous les points sources des segments concernés.
Elle n'est acceptée que si l'erreur orthogonale maximale reste sous le seuil
Erreur de droite. Les mêmes points sources sont conservés pour les fusions
suivantes, ce qui évite de perdre leur contrainte lors de fusions en chaîne.
Une grande distance de fusion ne suffit donc plus à réunir deux murs distincts.

Le bouton **Rétablir des seuils prudents** règle explicitement rupture 0,25 m,
erreur 0,05 m, angle 8° et distance de fusion 0,12 m. Les paramètres de session
existants ne sont pas modifiés automatiquement. Des seuils à 1 m et 0,5 m
restent possibles mais peuvent autoriser des approximations importantes.

## Anciennes formes traversées par un nouveau scan

À la question posée, l'utilisateur a choisi de raccourcir prudemment les segments.
Avant d'intégrer un nouveau scan, la carte teste les anciens segments contre
les nouveaux rayons valides. La coupe exige au moins trois directions distinctes
(groupées par pas angulaire de 0,5°). Un rayon répété dans plusieurs tours ne
suffit donc pas à déclencher une coupe. Les intersections proches de l'impact
ou du capteur et les contacts aux extrémités ne sont pas utilisés.

La marge vaut au moins 5 cm et deux fois l'erreur de droite. Après trois rayons
concordants, une coupe médiane est appliquée, en conservant le côté le plus long
(et le premier point en cas d'égalité), conformément à la règle du TP. Les
segments devenus plus courts que la longueur minimale sont retirés. Les
points sources de la partie coupée ne participent plus aux fusions suivantes.

Les rayons sont traités par tableaux NumPy pour limiter le coût du nettoyage.
L'ordre des scans correspond à l'ordre de la liste ; il influence le nettoyage.
Il n'y a pas de vieillissement temporel, de vote sur plusieurs dates ni de
scan matching automatique. Un mauvais recalage peut encore provoquer des
coupes erronées : ce mécanisme ne remplace pas une pose correcte.

## Trois réglages comparés

Calcul sur les 13 blocs du JSON précédemment envoyé, avec tous les blocs conservés
et **les poses anciennes enregistrées dans ce fichier**. Les poses ajustées
à la souris des dernières captures ne sont pas disponibles dans ce JSON.
Ces résultats vérifient le comportement du calcul, sans mesurer sa précision
sur le recalage actuel.

| Essai | Rupture | Erreur | Angle | Fusion | Segments extraits | Segments finaux | Fusions | Coupes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Prudent | 0.2 m | 0.04 m | 8° | 0.12 m | 138 | 63 | 46 | 99 |
| Intermediaire | 0.35 m | 0.06 m | 8° | 0.18 m | 160 | 65 | 65 | 102 |
| Captures | 1.0 m | 0.5 m | 10° | 1.0 m | 222 | 88 | 133 | 119 |

Le nombre final de segments n'est pas un score de qualité. Un nombre plus faible
peut provenir d'une meilleure fusion ou d'une suppression excessive. Le nombre
élevé de coupes sur ces poses anciennes impose une vérification sur la session
recalée actuelle avant de conclure sur l'environnement réel.

## Validation ciblée

60 tests logiciels passent. Cas ajoutés : prise en compte des scans cochés même
masqués ; absence de pont entre scans et tours ; persistance du résultat lors
d'un changement de sélection ; fusion d'un même mur ; séparation de murs
parallèles ; non-dérive des fusions successives ; coupe après trois rayons ;
absence de coupe après un seul rayon répété, un impact proche ou un obstacle
situé avant le segment. Sur la salle simulée à poses connues : 12 segments
extraits, 7 fusions et aucune coupe, pour 2 scans.

La fenêtre Windows et les dernières poses réelles restent à vérifier. Les
captures utilisateur illustrent le résultat avant correction et ne servent
pas de preuve de qualité de la nouvelle carte. Le rapport Word est complété
avec les deux captures et les trois essais.
