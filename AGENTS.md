# Consignes pour un assistant qui reprend ce dépôt

1. Lire `docs/REPRISE_PROJET.md` (état, architecture, décisions, suite) puis la fin de `docs/JOURNAL_PROJET.md`.
2. Répondre à l'utilisateur en français.
3. Lancer `python -m unittest discover -s tests` avant et après chaque lot ; tous les tests doivent passer. L'interface est web (`python scanatlas.py`, voir `docs/GUIDE_WEB.md`) : pas de Tk.
4. Les réglages du robot (broches, sens, vitesse) sont dans `firmware/ScanAtlas_WiFi/motor_config.h`.
5. Ne pas mentionner de projet extérieur comme source d'inspiration dans les fichiers.
6. Mettre à jour `docs/JOURNAL_PROJET.md` à chaque changement notable, difficultés comprises ; pas de rapport Word pour l'instant.
