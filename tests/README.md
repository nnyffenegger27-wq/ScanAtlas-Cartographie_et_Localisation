# Vérifier le projet

Depuis la racine, dans l’environnement Python du projet :

```
python -m unittest discover -s tests
```

Les tests couvrent les calculs, les imports, le suivi, la simulation, les connexions et le firmware. Ils n’ont pas tous les mêmes prérequis :

- NumPy, SciPy et pyserial : dépendances de `requirements.txt`.
- `g++` accessible dans le PATH : tests C++ du protocole et des pilotes moteurs, même pour une exécution depuis Windows. Arduino IDE seul ne rend pas nécessairement cette commande accessible.
- Connexions TCP/UDP locales autorisées : tests du serveur et du robot simulé. Un refus réseau Windows (`WinError 10013`) ou une connexion qui expire empêche leur validation.
- Playwright et Chromium : tests navigateur, ignorés si ces outils sont absents.
- `SCANATLAS_LENT=1` : active aussi l’essai long d’exploration complète de l’appartement simulé.

La durée dépend du PC et des délais de connexion ; elle peut dépasser les deux minutes indiquées dans d’anciennes notes.

Pour vérifier séparément le cœur du TP :

```
python -m unittest discover -s tests -p test_calculs.py
python -m unittest discover -s tests -p test_grille_tp.py
python -m unittest discover -s tests -p test_segments_multiscans.py
python -m unittest discover -s tests -p test_localisation_tp.py
```

Lors de la relecture du 22 novembre, ces quatre groupes (45 tests) passent. Le banc des 42 essais retrouve les nombres de réussites, refus et faux positifs publiés. La suite complète n’a pas pu être validée dans l’environnement de relecture : compilateur absent et restrictions réseau. Les essais sur le robot physique ne peuvent plus être refaits, le matériel n’étant plus disponible.
