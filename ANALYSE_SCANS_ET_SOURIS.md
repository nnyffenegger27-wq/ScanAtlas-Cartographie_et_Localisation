# Analyse des acquisitions et manipulation à la souris

2 novembre 2026 — session « Test plusieur scans pas la meme position.json ».
Les numéros ci-dessous suivent l'ordre de la session, à partir de 1.
L'analyse porte sur les mesures polaires originales, avant filtrage et pose.

## Résultats observés

| Scan | Points | Étendue déroulée | Écart angulaire maximal | Diagnostic indicatif |
|---|---:|---:|---:|---|
| 1 | 306 | 359.60° | 3.13° | Environ un tour (pertes non exclues) |
| 2 | 305 | 358.83° | 2.47° | Environ un tour (pertes non exclues) |
| 3 | 306 | 359.38° | 2.38° | Environ un tour (pertes non exclues) |
| 4 | 305 | 358.87° | 2.53° | Environ un tour (pertes non exclues) |
| 5 | 304 | 358.85° | 2.34° | Environ un tour (pertes non exclues) |
| 6 | 305 | 358.48° | 2.39° | Environ un tour (pertes non exclues) |
| 7 | 305 | 358.69° | 3.18° | Environ un tour (pertes non exclues) |
| 8 | 306 | 359.78° | 2.90° | Environ un tour (pertes non exclues) |
| 9 | 304 | 357.79° | 2.34° | Environ un tour (pertes non exclues) |
| 10 | 304 | 358.59° | 2.34° | Environ un tour (pertes non exclues) |
| 11 | 766 | 1079.54° | 176.99° | Plusieurs tours / bloc anormal |
| 12 | 305 | 358.37° | 2.38° | Environ un tour (pertes non exclues) |
| 13 | 545 | 643.04° | 2.46° | Plusieurs tours / bloc anormal |

Onze blocs couvrent environ un tour, avec 304 à 306 mesures. Le bloc 11
couvre près de trois tours (1079,54°) et le bloc 13 couvre 643,04°. Ils ne
sont pas des scans d'un seul tour. Les poses ne changent pas cette conclusion.
Les identifiants affichés « USB 1 » se répètent : ils ne sont pas uniques entre
captures. Se fier ici au numéro dans la liste pour identifier les acquisitions.

## Pourquoi 450 points attendus et seulement environ 305 reçus ?

Le raisonnement `points_par_tour = mesures_par_seconde / tours_par_seconde`
est correct : `4500 / 10 = 450`, sous réserve de la vitesse réelle et de la
conservation de toutes les mesures. La fiche fabricant indique 4500 mesures/s,
10 Hz typiques et une plage de rotation 5–13 Hz. La valeur typique ne mesure
pas la vitesse du montage. Le JSON ne conserve ni vitesse moteur ni horodatage
des paquets : impossible de trancher à partir de ce seul fichier.

En supposant zéro perte et 4500 mesures/s, 305 points impliqueraient 14,75 tours/s,
au-delà des 13 Hz indiqués dans cette fiche. Ce calcul est un indice, pas une
mesure de vitesse. Le pas moyen d'un tour reçu est environ 1,18° ; le pas médian
est voisin de 1,08° à cause des écarts périodiques entre paquets.

Un tour peut avoir peu de points et couvrir 360° tout en ayant perdu des mesures.
Le contrôle angulaire ne certifie donc pas la complétude de l'acquisition.

## Pistes identifiées dans le programme ESP32 fourni

Le ZIP ESP32 fourni antérieurement a été examiné en lecture seule ; on ne sait
pas si le programme actuellement téléversé est strictement identique.

1. `ld06.h`, `getAngleStep()` divise la différence début/fin par 12.
   `ld06.cpp` ajoute `(i + 0.5) * pas`. Le manuel LD06 décrit au contraire
   `pas = (fin - début)/(nombre_points - 1)` et `angle = début + i * pas` :
   pour 12 points, le diviseur est 11, sans décalage d'un demi-pas.
   Les écarts plus grands observés tous les 12 points sont compatibles avec
   cette interpolation. Cela déforme les angles ; cela ne prouve pas à lui seul
   pourquoi le nombre de mesures est inférieur à 450. Ne pas réécrire les anciens
   scans : les angles de début/fin des paquets ne sont plus disponibles.
2. L'envoi CSV à 115200 bauds est bloquant et limité à environ 11520 octets/s
   en 8N1. À 4500 points/s, le flux binaire LD06 représente environ
   `(4500/12)*47 = 17625 octets/s`. Avec un tampon RX de 4096 octets,
   environ 0,23 s sans lecture suffit à le remplir. Un bloc de centaines
   de lignes peut prendre davantage de temps à imprimer : des pertes en amont
   sont plausibles, même si les indices CSV sont ensuite continus.
3. La logique de fin de tour et les permutations de tampons sont à vérifier
   en cas de pertes et de plusieurs tours reçus avant l'impression.
   Les blocs de 643° et 1080° montrent que le seul retour des indices à zéro
   ne suffit pas pour valider un tour.

La bibliothèque ESP32 n'a pas été modifiée dans cette livraison.

## Contrôle ajouté dans Python

`diagnostic_scan()` déroule les angles dans l'ordre reçu et mesure l'étendue
et le plus grand saut. Une capture est jugée plausible si elle couvre
340 à 380° et ne présente aucun saut supérieur à 10°. Ces seuils sont des
garde-fous pédagogiques, pas une preuve d'absence de pertes. Les prochains
blocs USB qui échouent sont refusés et un message indique pourquoi.
Les imports et sessions existants restent consultables, avec le diagnostic
affiché. Aucun découpage ou effacement automatique des anciens scans.

## Manipulation à la souris

1. Choisir un scan dans la liste et s'assurer qu'il est visible.
2. Désactiver les outils Pan/Zoom de la barre Matplotlib.
3. Dans Nuages, choisir **Déplacer le scan** ou **Tourner le scan**.
4. Maintenir le clic gauche dans le graphique et déplacer la souris.
   Le mode agit uniquement sur le scan sélectionné, même lorsque les nuages
   se chevauchent. La rotation se fait autour de sa position x/y.
5. Relâcher pour valider ; Échap pendant le geste restaure la pose initiale.
6. Recalculer les cartes et enregistrer la session.

Les champs x/y/orientation sont mis à jour pendant le geste et restent
utilisables. Les mesures, la référence fixe 270° et la visibilité restent
indépendantes de la pose. Le zoom est figé pendant le geste pour éviter
que le repère de déplacement change sous le curseur.

## Difficultés et solutions retenues

| Difficulté | Solution | Limite |
|---|---|---|
| Choisir un nuage parmi plusieurs superposés | Sélection explicite dans la liste | Pas de sélection automatique par proximité |
| Confondre déplacement de la vue et du scan | Modes séparés ; gestes bloqués si Pan/Zoom actif | Désactiver ces outils avant de manipuler |
| Rotation instable près de l'origine | Ignorer le geste à moins de 8 pixels du pivot | Commencer à distance de la flèche |
| Saut à ±180° | Accumuler les écarts signés courts | Orientation affichée dans [-180°,180°[ |
| Zoom qui bouge pendant le glissement | Conserver les limites des axes | Recentrage via la barre après le geste |
| Cartes devenues obsolètes | Invalider après validation d'une nouvelle pose | Recalcul manuel requis |
| Scan à plusieurs tours accepté | Contrôle de l'étendue et des lacunes | Cause ESP32 encore à mesurer |

## À mesurer ensuite

- Lire `ld06.getSpeed()/360` pour obtenir les tours/s réels et compter
  les erreurs CRC. Stocker ces métadonnées sans mélanger du texte de diagnostic
  avec les six colonnes CSV actuelles.
- Comparer nombre de points et erreurs avec/sans impression bloquante.
- Corriger et valider l'interpolation ESP32 sur les paquets bruts, puis refaire
  des acquisitions ; ne pas interpoler artificiellement jusqu'à 450 points.
- Tester les gestes sous Windows avec plusieurs nuages réels.
- Mettre à jour le rapport final avec les mesures de vitesse et les comparaisons,
  sans présenter ces hypothèses comme des résultats expérimentaux.

## Sources techniques

- [Fiche LDROBOT LD06, paramètres](https://www.debix.io/Uploads/Temp/file/20220921/LDrobot_LD06_Datasheet.pdf).
- [Manuel LDROBOT LD06, protocole et interpolation, §3.2](https://www.yahboom.net/xiazai/LiDar-LD06/LDROBOT_LD06_Development_manual.pdf).
- Programme ESP32 fourni : `ESP32_LD06_Test.zip`, examen en lecture seule.
- Résultats numériques : session JSON utilisateur, analyse locale, sans matériel.
