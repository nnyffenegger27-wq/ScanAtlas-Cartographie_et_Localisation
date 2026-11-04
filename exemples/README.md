# Exemples — résultats reproductibles

Sorties des scripts d'évaluation (`outils/`, `atlas/calcul/evaluer_tp_jour2.py`) et deux scans simulés pour essayer l'écran Carte.

| Fichier(s) | Produit par | Contenu |
| --- | --- | --- |
| `SIMULE_1.csv`, `SIMULE_2.csv`, `session_demo.json` | `cartographie.demonstration()` | Les deux scans simulés du TP |
| `evaluation_tp_jour2.csv`, `evaluation_tp_jour2_synthese.csv` | `python -m atlas.calcul.evaluer_tp_jour2` (ou le bouton *Évaluer les méthodes (TP)* de l'écran Carte) | TP Jour 2 : 42 essais (3 références × 2 stratégies × 7 départs) et leur synthèse |
| `TP_JOUR2_ERREURS.png`, `TP_JOUR2_TROIS_REFERENCES.png`, `APERCU_CARTES.png` | `python outils/produire_figures_tp.py` (matplotlib) | Figures du TP |
| `comparaison_*.csv`, `resultats_icp.csv`, `robustesse_*.csv`, `localisation_globale_*.csv`, `references_robot_modele.csv` | `outils/comparer_suivi.py`, `evaluer_localisation.py`, `evaluer_lot.py`, `evaluer_robustesse.py`, `evaluer_global.py` | Comparaisons de méthodes de recalage et de localisation |
| `evaluation_wifi_simulation.csv` | `python outils/evaluer_wifi.py` | Banc du suivi Wi-Fi en simulation |
