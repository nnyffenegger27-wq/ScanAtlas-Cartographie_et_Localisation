# Cartes — quel fichier ouvrir ?

Les sessions s’ouvrent dans l’écran **Carte → Importer** de l’application. Les fichiers ont été rangés et renommés pour distinguer les résultats, les acquisitions et les essais. Leur contenu n’a pas été modifié.

## À ouvrir en premier

**[toutes_les_pieces_autonomie.json](01_resultats_slam/toutes_les_pieces_autonomie.json)** : le relevé réel de toutes les pièces, réalisé avec le robot en autonomie. Il contient **736 scans**. Passer entre les couches Points, Occupation et Plan pour voir les différentes représentations.

La [figure du compte rendu](../web/presentation-assets/carte-toutes-pieces.png) reprend les poses enregistrées, avec leurs défauts de raccordement. La ligne représente un parcours estimé, pas une mesure indépendante de la trajectoire. Je n’ai plus accès au robot pour mesurer sa précision absolue.

## Les dossiers

| Dossier | Usage |
| --- | --- |
| [01_resultats_slam/](01_resultats_slam/) | Relevé de toutes les pièces (736 scans) et autre parcours semi-autonome (578 scans). |
| [02_acquisitions_usb/](02_acquisitions_usb/) | Quatre scans à la même position et acquisition multiposition de 14 scans. |
| [03_essais_recalage/](03_essais_recalage/) | Essais de superposition, placement manuel et localisation. |
| [04_donnees_simulees/](04_donnees_simulees/) | Jeux MapTool de Nicolas et jeux fournis par le professeur ; ZIP d’origine dans `archives/`. |

## Retrouver un ancien nom

Les noms historiques restent dans le journal du projet et dans la version Tkinter archivée. Ce tableau donne leur emplacement dans la version finale. Une [copie CSV](correspondance_noms.csv) est également disponible.

| Ancien nom | Nouveau fichier ou dossier | Scans |
| --- | --- | ---: |
| `scanenautonomie.json` | [01_resultats_slam/toutes_les_pieces_autonomie.json](01_resultats_slam/toutes_les_pieces_autonomie.json) | 736 |
| `18-56-04-11-2026 cartographie semi autonome.json` | [01_resultats_slam/parcours_semi_autonome_2026-11-04.json](01_resultats_slam/parcours_semi_autonome_2026-11-04.json) | 578 |
| `session_ld06.json` | [02_acquisitions_usb/meme_position_4_scans.json](02_acquisitions_usb/meme_position_4_scans.json) | 4 |
| `scanmultiposition_ld06.json` | [02_acquisitions_usb/multi_positions_14_scans.json](02_acquisitions_usb/multi_positions_14_scans.json) | 14 |
| `Scansuperpose.json` | [03_essais_recalage/superposition_essai_01.json](03_essais_recalage/superposition_essai_01.json) | 13 |
| `Scansuperpose V2.json` | [03_essais_recalage/superposition_essai_02.json](03_essais_recalage/superposition_essai_02.json) | 13 |
| `Scansuperpose V3.json` | [03_essais_recalage/superposition_essai_03.json](03_essais_recalage/superposition_essai_03.json) | 13 |
| `Localisation.json` | [03_essais_recalage/localisation_session.json](03_essais_recalage/localisation_session.json) | 12 |
| `testlocalisation.json` | [03_essais_recalage/localisation_essai_01.json](03_essais_recalage/localisation_essai_01.json) | 7 |
| `testlocalisation V2.json` | [03_essais_recalage/localisation_essai_02.json](03_essais_recalage/localisation_essai_02.json) | 5 |
| `Test plusieur scans pas la meme position.json` | [03_essais_recalage/placement_manuel_multi_positions.json](03_essais_recalage/placement_manuel_multi_positions.json) | 13 |
| `MapToolNico1` | [04_donnees_simulees/maptool_nicolas](04_donnees_simulees/maptool_nicolas) |  |
| `ScanJules` | [04_donnees_simulees/maptool_jules_01](04_donnees_simulees/maptool_jules_01) |  |
| `ScanJules 2` | [04_donnees_simulees/maptool_jules_02](04_donnees_simulees/maptool_jules_02) |  |
| `ScanJules.zip` | [04_donnees_simulees/archives/maptool_jules_01.zip](04_donnees_simulees/archives/maptool_jules_01.zip) |  |
| `ScanJules 2.zip` | [04_donnees_simulees/archives/maptool_jules_02.zip](04_donnees_simulees/archives/maptool_jules_02.zip) |  |

Un `.json` contient une session (mesures, poses et filtres). Un `.csv` contient un scan brut ; un `.zip` regroupe plusieurs CSV. Les noms à l’intérieur des archives et les noms internes des scans sont conservés pour garder la trace des acquisitions.
