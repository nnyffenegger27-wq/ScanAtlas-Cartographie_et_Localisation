# LD06 Atelier

Application Python locale pour le TP EIGSI Jour 1 de cartographie lidar.

- Acquisition USB et import CSV polaire.
- Nuages multiscans en couleurs et poses indépendantes.
- Grille d'occupation, segments et carte vectorielle.
- Mesures originales conservées et exports reproductibles.

## Démarrer

Python 3.10 ou plus récent. Sous Windows : `installer_windows.bat`, puis
`lancer_windows.bat`. Le guide complet est dans [LISEZ_MOI.md](LISEZ_MOI.md).

## Repère robot depuis v0.2.0

Pour les nouveaux imports/USB, **l'ancien 90° devient 0°** :
`angle_local = angle_mesure - 90°`. La pose du robot reste un réglage séparé.
Les sessions anciennes conservent leur convention tant qu'on ne la modifie pas.

## Suivi du projet

- [JOURNAL_PROJET.md](JOURNAL_PROJET.md) : contexte, décisions, observations et tâches.
- [GUIDE_GITHUB.md](GUIDE_GITHUB.md) : envoyer le dépôt et travailler avec GitHub.

## Tests

```bash
python -m unittest discover -s tests -v
```

Limite connue prioritaire : un bloc proche de 720° peut encore être accepté comme
un seul scan. La correction nécessite de vérifier les frontières de tours dans
les mesures réelles. Les captures d'écran ne suffisent pas à localiser sa cause.
