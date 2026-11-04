# Cartes — relevés et sessions

Données utilisées pour développer et tester ScanAtlas. Elles s'ouvrent dans l'écran **Carte** (bouton *Importer*, ou glisser-déposer).

| Élément | Contenu |
| --- | --- |
| `scanenautonomie.json` | Session enregistrée pendant un scan **fait par le robot en autonomie** (version web, 4 novembre) |
| `session_ld06.json`, `scanmultiposition_ld06.json`, `Scansuperpose*.json`, `Localisation.json`, `testlocalisation*.json`, `Test plusieur scans pas la meme position.json` | Sessions enregistrées par l'application lors des TP Jour 1 et 2 : **acquisitions USB réelles** du LD06 (de 4 à 14 scans, à des positions différentes) |
| `MapToolNico1/` | Scans exportés avec MapTool (un CSV par position) |
| `ScanJules/`, `ScanJules 2/` (+ `.zip`) | Archives de scans MapTool fournies par le professeur ; le `.zip` est l'archive, le dossier son contenu extrait |

Un `.json` est une « session » (scans, poses, filtres) ; un `.csv` est un scan brut, à importer seul ou en `.zip`.
