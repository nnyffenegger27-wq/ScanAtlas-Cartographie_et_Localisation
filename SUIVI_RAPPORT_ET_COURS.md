# Suivi du rapport et confrontation au cours

## État du 2 novembre 2026

Un premier rapport Word illustré de cinq pages a été commencé avec cinq captures utilisateur.

[Ouvrir le rapport Word](https://chatgpt.com/library?file_id=libfile_b6ee79fe47e0819184a36ce1160611f1&account_id=personal)

Ce lien nécessite le compte ChatGPT propriétaire du document.
Il décrit les résultats observés et les difficultés sans inventer de précision
mesurée. Le rapport final reste à compléter après validation des acquisitions.

## Comparaison avec les supports reçus

| Étape du cours | Application actuelle | Suite nécessaire |
|---|---|---|
| Pose 2D et transformation locale vers globale | x, y, orientation ; référence lidar fixe 270° | Vérifier les axes physiquement |
| Grille inconnue, libre et occupée | État observé séparé et log-odds | Comparer sur des scans validés |
| Cellules traversées et impact | Bresenham, preuves libres/occupées | Mesurer l'effet de la résolution |
| Segmentation et ajustement | Ruptures, division et ajustement orthogonal | Réduire la fragmentation sans sur-fusion |
| Ajout et fusion des formes | Accumulation et fusion par seuils | Mesurer la stabilité de la carte |
| Anciennes formes traversées par les nouveaux rayons | Découpage disponible au laboratoire seulement | Intégrer la gestion des absences dans la carte |
| Scan matching | Recalage manuel par champs ou souris | Étudier ensuite une aide automatique, non encore implémentée |
| Nettoyage et vieillissement | Non implémentés | À envisager après acquisition fiable |

## Captures du rapport

1. image(20261102-145344).png : quatre acquisitions à position fixe,
   présence d'un bloc de 719,4°.
2. image(20261102-145354).png : grid map à 0,05 m, 289 × 260 cellules.
3. image(20261102-145402).png : 52 segments extraits d'un scan.
4. image(20261102-145422).png : carte fusionnée affichant 43 segments.
5. image(20261102-164837).png : superposition manuelle mult positions,
   bloc 766 encore inclus dans Carte et bloc 545 exclu.

Les nombres 52 et 43 portent sur des opérations différentes et ne donnent pas
un taux de réussite. Les captures anciennes ne correspondent pas à la même
session ou convention de repère que la dernière.

## Mesures à ajouter au rapport

Vitesse réelle, nombre de points par tour, erreurs de réception, influence
de l'impression CSV, recalage sur une référence mesurée, comparaison des cartes
après exclusion des blocs multiples et sensibilité aux seuils. Les hypothèses
actuelles sur les pertes et l'interpolation ESP32 ne sont pas des causes prouvées.

Sources : supports EIGSI de Jonathan Quillès, 2026, contenus dans les archives
Cartographie-20261102.zip et Localisation-20261102.zip.


## Mise à jour de la grille après lecture du cours

Création depuis un scan sélectionné et ajout explicite d'un nouveau scan à
la carte existante désormais disponibles dans l'interface. Les bornes peuvent
s'agrandir sans perdre les observations déjà intégrées. Le comportement antérieur
ignorait un rayon hors grille dans le noyau ; ce cas est désormais traité
par l'agrandissement. Un double ajout manuel du même scan est empêché.

Les étapes de base du TP sont donc utilisables séparément. Le recalage demeure
manuel et les extensions de vieillissement/nettoyage temporel ne sont pas
implémentées. Le rapport Word illustré reste un état antérieur : son prochain
complément pourra présenter ce parcours incrémental et une nouvelle capture.
