"""Évaluation reproductible du recalage entre les deux scans simulés de la démo.

python evaluer_localisation.py --sortie resultats_icp.csv
Les critères de réussite utilisent la pose vraie, pas la convergence du solveur.
"""
import argparse
import csv
import numpy as np
from cartographie import demonstration
from localisation import icp_scan, recherche_icp, erreur_pose


def evaluer(sortie, comparer=False):
    reference, mobile = demonstration()
    vraie = list(mobile.pose)
    lignes = []
    cas = [(0, 0, 0), (.1, -.1, 2), (.3, -.2, 6), (.5, .3, -10),
           (1, .5, 15), (3, 3, 70)]
    if comparer: cas += [(.5, .3, 15), (-.5, .5, -25), (.8, -.6, 20)]
    methodes = [icp_scan, recherche_icp] if comparer else [icp_scan]
    for methode in methodes:
      for dx, dy, da in cas:
        initiale = (np.asarray(vraie)+[dx, dy, da]).tolist()
        r = methode(mobile, reference, pose_initiale=initiale)
        ep, ea = erreur_pose(r.pose, vraie)
        lignes.append(dict(methode=r.methode, dx_initial_m=dx, dy_initial_m=dy, angle_initial_deg=da,
            erreur_position_m=ep, erreur_angle_deg=ea, duree_s=r.duree,
            iterations=r.iterations, converge=r.converge, applicable=r.applicable,
            rmse_m=r.rmse, recouvrement=r.recouvrement, reussite=ep <= .1 and ea <= 2))
    with open(sortie, 'w', newline='', encoding='utf-8') as fichier:
        w = csv.DictWriter(fichier, fieldnames=list(lignes[0]))
        w.writeheader(); w.writerows(lignes)
    print(f"{sum(l['reussite'] for l in lignes)}/{len(lignes)} réussites (position ≤0,10 m ET angle ≤2°).")
    print('Simulation : mêmes deux scans, mêmes filtres (0,05–12 m ; intensité 0), distance ICP 0,5 m, 80 itérations maximum.')
    print('Un solveur peut converger vers une mauvaise pose ; consulter les erreurs vraies dans le CSV.')
    for nom in sorted({l['methode'] for l in lignes}):
        groupe = [l for l in lignes if l['methode'] == nom]
        print(f"{nom} : {sum(l['reussite'] for l in groupe)}/{len(groupe)} réussites ; temps médian {np.median([l['duree_s'] for l in groupe]):.3f} s.")
    return lignes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sortie', default='resultats_icp.csv')
    parser.add_argument('--comparer', action='store_true', help='Comparer ICP local et recherche ±1 m / ±30° sur neuf initialisations identiques.')
    args = parser.parse_args()
    evaluer(args.sortie, args.comparer)
