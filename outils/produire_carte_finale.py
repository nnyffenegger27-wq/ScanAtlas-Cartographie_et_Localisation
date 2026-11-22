"""Vue du relevé réel, sans recalage supplémentaire ni modification des mesures.

Depuis la racine : python outils/produire_carte_finale.py
Matplotlib est nécessaire uniquement pour produire cette figure.
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def produire(racine, sortie):
    sys.path.insert(0, str(racine))
    from atlas.calcul.cartographie import Scan, mesures_valides
    chemin = racine / 'Cartes/01_resultats_slam/toutes_les_pieces_autonomie.json'
    session = json.loads(chemin.read_text(encoding='utf-8-sig'))
    filtres = {k: float(session['parametres'][k]) for k in ('mini', 'maxi', 'intensite')}
    nuages, poses = [], []
    for donnees in session['scans']:
        if not donnees.get('inclus', True):
            continue
        scan = Scan(donnees['nom'], np.asarray(donnees['mesures'], float),
                    donnees['pose'], angle_reference=donnees.get('angle_reference', 0.),
                    intensite_disponible=donnees.get('intensite_disponible', True))
        nuages.append(scan.points()[mesures_valides(scan, **filtres)])
        poses.append(scan.pose[:2])
    points, trajet = np.vstack(nuages), np.asarray(poses)
    # Alléger seulement le dessin : un point par carré de 3 cm.
    _, indices = np.unique(np.floor(points/.03).astype(np.int64), axis=0, return_index=True)
    dessin = points[np.sort(indices)]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10})
    fig, ax = plt.subplots(figsize=(11, 8), layout='constrained')
    ax.scatter(*dessin.T, s=.65, color='#34494c', alpha=.65, linewidths=0, rasterized=True,
               label='Impacts lidar (affichage allégé à 3 cm)')
    ax.plot(*trajet.T, lw=1.1, color='#c57128', alpha=.85, label='Parcours estimé enregistré')
    ax.scatter(*trajet[0], s=65, color='#147a66', marker='o', edgecolors='white', label='Départ', zorder=4)
    ax.scatter(*trajet[-1], s=75, color='#c57128', marker='X', edgecolors='white', label='Fin', zorder=4)
    ax.set(aspect='equal', xlabel='x (m)', ylabel='y (m)',
           title=f'Relevé de toutes les pièces - {len(poses)} scans réels enregistrés')
    ax.grid(alpha=.16)
    ax.spines[['top', 'right']].set_visible(False)
    ax.legend(loc='best', fontsize=8, framealpha=.95)
    fig.supxlabel('Source : toutes_les_pieces_autonomie.json\nPoses conservées telles quelles ; précision absolue non mesurée.',
                  fontsize=9, color='#526365')
    sortie.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(sortie, dpi=180, facecolor='white')
    plt.close(fig)
    print(f'{len(poses)} scans inclus ; {len(points)} mesures filtrées ; {len(dessin)} points dessinés.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--racine', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--sortie', type=Path)
    args = p.parse_args()
    produire(args.racine, args.sortie or args.racine/'web/presentation-assets/carte-toutes-pieces.png')
