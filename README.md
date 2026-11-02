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

Pour les nouveaux imports/USB, **l'ancien 270° devient 0°** :
`angle_local = angle_mesure - 270°`. La pose du robot reste un réglage séparé.
Cette référence est fixe, sans champ supplémentaire dans l'interface. Elle
s'applique aussi aux scans réels des anciennes sessions ; les mesures restent
intactes et les cartes doivent être recalculées. Les simulations gardent leur
repère de démonstration.

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


## Masquer un scan

Dans « Mes scans », cliquer sur la case de la colonne **Visible** pour masquer
ou réafficher un scan dans l'onglet Nuages, avec ses points et sa flèche de pose.
La colonne **Carte** choisit indépendamment les scans utilisés pour les calculs
de cartographie. La visibilité est sauvegardée dans la session JSON.


## Déplacer et tourner un scan à la souris

Dans Nuages : sélectionner un scan visible dans la liste, désactiver Pan/Zoom,
puis choisir **Déplacer le scan** ou **Tourner le scan**. Maintenir le clic
gauche et glisser dans le graphique. La rotation pivote autour du lidar.
Les coordonnées sont actualisées ; Échap annule le geste avant validation.
Recalculer ensuite les cartes et enregistrer la session.

Le diagnostic du scan sélectionné signale les tours multiples et les grandes
lacunes. Les prochaines captures USB refusent ces blocs. Un scan de 305 points
couvrant 360° ne prouve pas que toutes les mesures ont été reçues.
Voir [l'analyse des acquisitions et des difficultés](ANALYSE_SCANS_ET_SOURIS.md).


## Rapport et supports du cours

Le premier rapport Word illustré reprend les cinq captures utilisateur.
Le suivi du rapport et la comparaison aux méthodes du cours sont consignés
dans [SUIVI_RAPPORT_ET_COURS.md](SUIVI_RAPPORT_ET_COURS.md).
La grid map est rapprochée de la méthode fournie ; la gestion des anciennes
formes traversées par les nouveaux rayons reste à intégrer à la carte vectorielle.
