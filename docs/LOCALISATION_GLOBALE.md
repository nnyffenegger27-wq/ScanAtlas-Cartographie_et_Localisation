# Localisation globale et cartes cumulées

## Parcours dans l’application

Le mode par défaut est **Carte cumulée · recherche globale 360°**. Les anciens champs de fenêtre en mètres et en degrés sont cachés dans ce mode et ne participent pas au calcul. Une ancienne session en Recherche large est migrée vers le mode global. Les anciennes méthodes restent disponibles pour comparaison.

Pour les scans déjà chargés : ouvrir **Localisation**, puis **Assembler tous les scans — carte cumulée et groupes en attente**. Le premier scan de la liste fixe le repère. Tous les suivants sont traités, même décochés Carte ou masqués : ce bouton sert précisément à retrouver ceux qui sont en attente. La liste représente l’ordre de traitement, pas une obligation de proximité entre acquisitions.

En **Acquisition USB**, cocher la localisation automatique. Après réception et fermeture du port, le traitement global reprend la carte et les groupes de la session, puis traite les nouveaux scans. Un dernier scan en attente ne bloque plus les captures suivantes.

Les scans raccordés contribuent tous à la référence. Un scan non raccordé reste dans la liste, masqué et décoché Carte pour ne pas être dessiné dans un faux repère global. Sa sélection affiche le groupe, le pourcentage obtenu et le motif du refus. Les groupes se sauvegardent dans la session JSON. Un groupe secondaire possède son propre repère local ; le masquer ne supprime aucune mesure.

Les poses d’un lot sont appliquées à la fin. Le bouton d’annulation du dernier lot restaure les anciennes poses, les statuts, la visibilité et les cases Carte. Une annulation en cours écarte les poses calculées ; les mesures USB déjà reçues sont conservées. Un changement des données, des poses ou des filtres pendant le calcul fait aussi écarter le résultat devenu périmé.

## Recherche choisie

Implémentation NumPy, sans nouvelle dépendance : recherche corrélative hiérarchique, contrôle de cohérence avec les espaces libres puis ICP sur plusieurs départs.

1. La carte d’impacts cumule les observations raccordées dans des cellules de 5 cm, moyennées pour limiter le poids des points répétés. Dans le mode global, elle conserve toutes les cellules ; elle n’est plus limitée aux cinq derniers scans ou à 2400 points.
2. Les translations couvrent les bornes de la carte élargies de la portée maximale effectivement observée dans le scan mobile. Cela inclut les positions hors de la zone déjà cartographiée susceptibles de partager un impact. Aucun rayon de recherche autour du dernier scan n’est demandé.
3. Les orientations −180° à +180° sont explorées au pas de 4°, avec des translations au pas de 40 cm. Les calculs se font par blocs pour borner la mémoire. Le pas ne s’élargit pas quand la carte grandit.
4. Jusqu’à 48 candidats distincts sont conservés, puis affinés à 20, 10 et 5 cm et 2°, 1° et 0,5°. Jusqu’à 16 minima sont affinés avec ICP.
5. Le coût inclut les impacts non appariés et une pénalité pour les impacts projetés dans une zone déjà observée libre. Une marge de 18 cm autour des impacts connus évite de traiter l’incertitude d’un mur comme une contradiction.

Cette recherche couvre toute l’étendue et tout le tour, mais conserve un nombre fini de candidats pendant les affinements : ce n’est pas une preuve d’optimalité globale, ni une recherche exacte par branch-and-bound. Une petite zone de convergence peut encore être manquée. Les allocations de grilles gardent une protection mémoire ; une carte trop grande donne un message, sans couper silencieusement la recherche autour du dernier scan.

## Concordance et validation

La concordance affichée est la proportion des points filtrés du mobile à moins de **min(12 cm, demi-distance d’appariement ICP)** de la référence. Ce n’est pas une probabilité de pose correcte. Par défaut, un raccordement direct requiert au moins 65 % et douze points, une géométrie suffisamment contraignante et une convergence ICP.

Une grille interne de 7,5 cm est reconstruite à partir des rayons des scans de référence. Les cases libres ont été réellement traversées par un rayon ; les zones inconnues ne sont pas considérées libres. Au-delà de 8 % d’impacts mobiles en contradiction avec ces zones libres, la pose est refusée. Cette heuristique suppose une scène essentiellement statique ; des personnes ou du mobilier déplacé peuvent faire refuser un scan.

Si plusieurs poses éloignées de plus de 20 cm ou 5° ont des coûts voisins, le résultat est déclaré ambigu. Ce contrôle ne peut pas prouver que toutes les symétries ont été trouvées. Un taux élevé et un faible RMSE ne suffisent pas à garantir la bonne position.

## Groupes secondaires et fusion

Le premier scan ancre la carte principale. Un scan refusé essaie les groupes secondaires existants. S’il s’y raccorde, il les enrichit dans leur repère ; sinon, il devient l’ancre d’un nouveau groupe. Son score d’accord local ne signifie pas qu’il est localisé dans la salle.

Un nouveau scan pouvant être localisé dans les deux cartes sert de pont. Des recouvrements partiels sont autorisés pour ce pont seulement : chaque localisation doit satisfaire la géométrie, l’absence d’ambiguïté et les espaces libres, avec au moins 35 % de concordance par carte, et l’union des points concordants doit couvrir au moins 85 % du scan. Une faible concordance seule ne permet donc pas la fusion.

Les deux poses du même scan donnent une transformation rigide : R = R_globale × R_localeᵀ et t = position_globale − R × position_locale. La même transformation s’applique à toutes les poses du groupe. Les mesures restent inchangées. Une ancienne vue du groupe est également retentée sur la carte principale après extension et lors de la reprise d’une capture. Une modification de la pose de l’ancre invalide la reprise des anciennes poses et relance leur assemblage.

Cette gestion n’est pas une optimisation de graphe de poses. Elle ne corrige pas la dérive à l’intérieur d’un groupe et ne réalise pas une fermeture de boucle globale. Sans surfaces communes identifiables ou scan intermédiaire, le lidar seul ne donne pas la position relative de deux zones disjointes.

## Essais reproductibles

- `python -m unittest discover -s tests`
- `python outils/evaluer_global.py` : demi-tour et déplacement de 4,47 m avec demi-tour.
- `python outils/evaluer_global.py chemin/ScanJules.zip` : 14 scans MapTool contre une référence fixe.
- `python outils/evaluer_global.py --lot` : assemblage cumulé de huit scans bruités.

Les poses de départ du banc global sont volontairement fixées à des coordonnées erronées de plusieurs dizaines de mètres ; les poses connues servent uniquement aux erreurs finales. Réussite : position ≤ 10 cm et angle ≤ 2°.

| Essai | Erreur de position | Erreur angulaire | Concordance | Temps |
| --- | ---: | ---: | ---: | ---: |
| Demi-tour dans la démo | 0,00290 m | 0,0491° | 96,7 % | 4,64 s |
| Déplacement de 4,47 m et demi-tour dans une salle convexe asymétrique | 0,00083 m | 0,0298° | 100 % | 15,71 s |

Sur les 14 scans MapTool : cinq poses correctes acceptées, neuf refus, aucune pose fausse acceptée sur ce jeu ; temps médian 6,82 s. Ce jeu est déjà utilisé pour le développement : il ne constitue pas une validation indépendante. Certains scans ne partagent pas assez de points visibles avec la première référence et une pose correcte peut être refusée. Les détails sont dans exemples/localisation_globale_maptool.csv. Les temps dépendent du matériel et de la charge de calcul.

Les tests de groupes vérifient la transformation de toutes les poses, la non-fusion d’un pont insuffisant, les recouvrements partiels complémentaires, la reprise des groupes et la conservation des données. Les décisions de correspondance sont simulées dans ces tests de fusion afin d’isoler la logique des repères. Le parcours USB simulé utilise le véritable solveur global, le traitement des messages et l’application des poses. La fusion de groupes n’a pas encore été validée sur de nouveaux relevés physiques du robot. Les filtres et la référence angulaire lidar existants ne sont pas changés.

### Lot bruité sur la carte cumulée

Le banc de huit scans (graine 20261103, bruit de distance 15 mm, environ 20 % de pertes et 5 % d’aberrants) accepte correctement les sept scans après l’ancre. Erreurs maximales : 0.01239 m et 0.1982°, temps cumulé 93.74 s dans cet environnement chargé. Tous les scans raccordés participent à la référence. Détails : exemples/localisation_globale_lot.csv. Ce résultat en simulation ne remplace pas l’essai matériel.
