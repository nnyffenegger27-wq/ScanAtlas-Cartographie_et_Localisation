# Outils de travail

L’application se lance depuis la racine avec `lancer_windows.bat` ou `python scanatlas.py`. Les fichiers de ce dossier servent aux évaluations et à la préparation des figures.

| Besoin | Commande depuis la racine |
| --- | --- |
| Refaire les 42 essais de localisation du TP | `python -m atlas.calcul.evaluer_tp_jour2` |
| Refaire les graphiques du TP | `python outils/produire_figures_tp.py` |
| Refaire la vue du relevé réel de toutes les pièces | `python outils/produire_carte_finale.py` |
| Rejouer un journal lidar enregistré | `python outils/rejouer_journal.py chemin/vers/tours.jsonl` |
| Autres bancs de développement | `evaluer_localisation.py`, `evaluer_global.py`, `evaluer_lot.py`, `evaluer_robustesse.py`, `evaluer_wifi.py`, `comparer_suivi.py` |

Les scripts de figures demandent Matplotlib (`pip install matplotlib`). Il n’est pas nécessaire pour utiliser l’application. Les résultats du TP sont dans `exemples/`, les illustrations du compte rendu dans `web/presentation-assets/`.

`captures_tk/` conserve localement les anciens scripts et prises d’écran de préparation du rapport. Ce dossier n’est pas nécessaire pour lancer ou évaluer la version finale.
