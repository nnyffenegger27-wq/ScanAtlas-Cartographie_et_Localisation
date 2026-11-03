"""Évaluation reproductible du recalage entre les deux scans simulés de la démo.

python evaluer_localisation.py --sortie resultats_icp.csv
Les critères de réussite utilisent la pose vraie, pas la convergence du solveur.
"""
import argparse
import csv
import numpy as np
from cartographie import demonstration
from localisation import icp_scan, erreur_pose


def evaluer(sortie):
    reference, mobile = demonstration()
    vraie = list(mobile.pose)
    lignes = []
    for dx, dy, da in [(0, 0, 0), (.1, -.1, 2), (.3, -.2, 6), (.5, .3, -10),
                       (1, .5, 15), (3, 3, 70)]:
        initiale = (np.asarray(vraie)+[dx, dy, da]).tolist()
        r = icp_scan(mobile, reference, pose_initiale=initiale)
        ep, ea = erreur_pose(r.pose, vraie)
        lignes.append(dict(dx_initial_m=dx, dy_initial_m=dy, angle_initial_deg=da,
            erreur_position_m=ep, erreur_angle_deg=ea, duree_s=r.duree,
            iterations=r.iterations, converge=r.converge, applicable=r.applicable,
            rmse_m=r.rmse, recouvrement=r.recouvrement, reussite=ep <= .1 and ea <= 2))
    with open(sortie, 'w', newline='', encoding='utf-8') as fichier:
        w = csv.DictWriter(fichier, fieldnames=list(lignes[0]))
        w.writeheader(); w.writerows(lignes)
    print(f"{sum(l['reussite'] for l in lignes)}/{len(lignes)} réussites (position ≤0,10 m ET angle ≤2°).")
    print('Simulation : mêmes deux scans, mêmes filtres (0,05–12 m ; intensité 0), distance ICP 0,5 m, 80 itérations maximum.')
    print('Un solveur peut converger vers une mauvaise pose ; consulter les erreurs vraies dans le CSV.')
    return lignes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sortie', default='resultats_icp.csv')
    evaluer(parser.parse_args().sortie)
