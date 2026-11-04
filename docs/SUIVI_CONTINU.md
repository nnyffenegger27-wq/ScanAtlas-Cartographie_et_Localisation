> **Note (interface web).** Les écrans, onglets et fichiers Tkinter cités ici (`app.py`, `interface_wifi.py`, `interface_tp.py`…) ont été remplacés par l'interface web : voir [GUIDE_WEB.md](GUIDE_WEB.md). Les principes, calculs et résultats décrits restent valables.

> **Version du 4 novembre 2026** — Interface en trois espaces, carte reprise, localisation seule, grille en direct, PWM et USB/Wi-Fi réunis. Consulter [le guide actuel](GUIDE_SCANATLAS_V3.md). Les descriptions antérieures ci-dessous peuvent correspondre à une version précédente.

# Suivi continu et interface simplifiée

L’application conserve **un seul onglet Localisation** pour le TP Jour 2 :
grille d’occupation, carte vectorielle et scan de référence. Le même mobile
sélectionné à gauche peut être testé avec les deux stratégies, et le banc
commun exporte erreurs, temps et taux de réussite. Les fonctions historiques
restent utilisables dans les scripts et l’acquisition USB ; leur second panneau
n’est plus affiché. Le suivi pendant la conduite appartient à **Robot Wi-Fi**.

## Ce qui change dans le suivi Wi-Fi

1. Les deux dernières poses **lidar acceptées** permettent une prédiction à
   vitesse corporelle constante dans SE(2), avec l’intervalle réel des tours.
   Le facteur d’extrapolation est borné à deux et la prédiction est désactivée
   après une interruption de plus de 0,6 s ou une reprise. Les commandes
   clavier et la puissance PWM ne sont jamais une mesure de mouvement.
2. La référence est construite à partir des **huit derniers scans clés validés**,
   voxelisés à 5 cm. La carte globale de points et de segments reste conservée.
3. L’arbre de voisins et les normales de cette référence sont **mis en cache**
   entre les scans clés. Chaque normale provient de la covariance de sept
   voisins ; les voisinages trop dispersés, les coins et les points isolés
   sont écartés de l’ajustement aux droites.
4. Le scan est ajusté par **ICP point-vers-droite**, avec correspondances
   réévaluées à chaque itération, poids de Cauchy de 4 cm, Jacobien analytique
   et résolution d’un système 3 × 3. La limite d’association se resserre de
   50 cm à 15 cm. Le calcul s’arrête à convergence ou après 30 itérations.
5. Si cette tentative échoue, la dernière pose valide est retestée puis le
   secours multi-résolution existant est utilisé. Son résultat repasse par le
   contrôle point-vers-droite : une recherche grossière ne doit pas faire
   accepter une géométrie indéterminée devant un mur unique.
6. La décision conserve les garde-fous de la version Wi-Fi : au moins 75 % des
   points distincts filtrés à moins de 12 cm des **impacts réels**, RMSE au plus
   de 10 cm sur les associations sous 50 cm, évolution de pose plausible et
   annulation respectée. L’accord avec la droite seule ne suffit pas.

Pour un point local p, une normale n et le centre de son voisinage µ, le résidu
est `r = nᵀ(R(θ)p + t - µ)`. Le Jacobien de ce résidu est calculé directement
par rapport à x, y et θ en radians. L’information normalisée doit contraindre
les trois composantes : un mur isolé ne permet pas de mesurer le déplacement
parallèle au mur. La concordance affichée reste un **pourcentage d’accord
géométrique**, jamais une probabilité de pose exacte.

Le premier scan reste à l’origine et n’est pas déplacé. Les mesures originales
ne sont pas modifiées. Une pose refusée suspend seulement l’insertion en carte.
Le pilotage manuel reste disponible si le flux lidar est récent ; le suivi réessaie automatiquement près de la dernière pose. Le suivi ne devient
pas une localisation globale après un déplacement arbitraire du robot.

## Interface

La palette, la typographie, les boutons, les onglets et la liste des scans sont
harmonisés. Les champs numériques de distance, intensité, résolution et
segmentation disposent de curseurs ; la saisie précise reste possible.
Le bouton **Appliquer les filtres** garde son rôle et les filtres de la carte
en direct restent figés jusqu’à **Nouvelle carte**.

Robot Wi-Fi présente la position x/y, l’orientation, la concordance, le temps
de calcul et le nombre de segments. Le curseur de puissance garde la plage
0–100 / 255. Les couches de points, scan courant et segments s’affichent
séparément. Le zoom est conservé, **Centrer la carte** donne la vue d’ensemble
et **Suivre le robot** déplace la caméra. Ces réglages visuels ne déplacent pas
les scans et ne changent pas la carte calculée.

Les artistes Matplotlib sont réutilisés : une collection de segments et des
nuages mis à jour remplacent l’effacement de l’axe à chaque tour. La vue n’est
pas redessinée quand l’onglet Wi-Fi est masqué. Les contrôles d’arrêt au
relâchement, à la perte de focus et au changement d’onglet sont conservés.

## Comparaison sur les mêmes mesures

Les deux versions reçoivent les mêmes 60 tours : 450 points, bruit gaussien
σ = 3 mm, graine 2026, occultations de murs et obstacle, intervalle 100 ms,
translation et rotation simultanées. La version initiale est celle du commit
`b28f7c9`. Les poses vraies servent seulement à mesurer les erreurs.

| Mesure | Suivi initial | Point-vers-droite avec prédiction |
| --- | ---: | ---: |
| Tours acceptés | 60 / 60 | 60 / 60 |
| Calcul médian | 33,33 ms | 3,73 ms |
| Calcul au percentile 95 | 58,46 ms | 13,63 ms |
| Erreur de position maximale | 5,03 mm | 0,64 mm |
| Erreur angulaire maximale | 0,400° | 0,0144° |

Sur **cette exécution**, le calcul médian est environ neuf fois plus rapide.
Ce résultat mesure le moteur de suivi, hors interface et hors réseau radio.
Il ne prouve pas la précision réelle du LD06, ni la fréquence atteignable sur
un autre PC. Le fichier `exemples/comparaison_suivi_continu.csv` contient les
120 lignes détaillées. `outils/comparer_suivi.py --ancienne CHEMIN` permet de répéter
le banc avec une copie du module de la version initiale. `outils/evaluer_wifi.py`
évalue séparément la version actuelle.

## Vérifications

La suite compte 144 tests : **143 réussissent sans écran**, le test Tk étant
exécuté séparément sur un écran virtuel. Le test d’interface vérifie le seul
onglet Localisation, le curseur PWM, les indicateurs, la conservation du zoom,
les touches, le relâchement, le focus et la déconnexion. Les nouveaux tests
numériques couvrent aussi la composition SE(2), le passage de 180°, le cache,
les normales de points isolés et la géométrie d’un mur unique.

Un test de **105 tours** avec translation et rotation progressives dépasse le
demi-tour, avec tous les recalages acceptés et des erreurs sous les seuils de
test de 6 cm / 1°. Il s’agit encore de scans synthétiques et non d’une rotation
mesurée sur le robot physique.

## Compatibilité et limites

Cette mise à jour concerne le **PC**. Le firmware, le hotspot et le protocole
UDP/TCP sont inchangés : aucun nouveau téléversement n’est nécessaire. Garder
le firmware ScanAtlas_WiFi déjà fourni et redémarrer l’application après mise
à jour du code Python, à la fin des essais de conduite en cours.

La dérive, les scènes répétitives, les objets mobiles et le mouvement pendant
un tour restent des limites. Il n’y a toujours ni compensation intra-tour par
odométrie/IMU, ni fermeture de boucle, ni évitement d’obstacles ou navigation
autonome. Les essais réels du Wi-Fi et des moteurs restent séparés de ce banc.

## Références méthodologiques

- [CSM](https://github.com/AndreaCensi/csm) : principe du scan matching 2D point-vers-droite. L’implémentation est propre à ScanAtlas ; la bibliothèque CSM n’est pas embarquée.
- [PCL et estimation des normales](https://pointclouds.org/documentation/tutorials/normal_estimation.html) : normales par covariance et valeurs propres ; application ici à des voisinages 2D avec NumPy.
- [Cartographer](https://google-cartographer-ros.readthedocs.io/en/latest/algo_walkthrough.html) : séparation du suivi local, des scans clés et de la carte.
- [SciPy cKDTree](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.html) : index des voisins ; NumPy assure les calculs de covariance et les systèmes linéaires.

