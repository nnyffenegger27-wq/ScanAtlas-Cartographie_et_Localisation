"""Banc MapTool reproductible : vérité utilisée uniquement pour les erreurs.

python outils/evaluer_robustesse.py chemin/ScanJules.zip
Trois perturbations identiques par scan, référence fixe = premier fichier ZIP.
Aucune remise en ordre chronologique supposée. Réussite <=10 cm ET <=2 degrés.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # modules de l'application à la racine
import csv
import sys
import numpy as np
from cartographie import lire_csv
from localisation import recherche_icp, icp_scan, erreur_pose


def evaluer(chemin, sortie='exemples/robustesse_maptool.csv'):
    scans = lire_csv(chemin)
    reference = scans[0]
    lignes = []
    for i, scan in enumerate(scans[1:], 2):
        if scan.pose_connue is None: raise ValueError('Pose connue nécessaire à l’évaluation.')
        vraie = list(scan.pose_connue)
        for delta in [[.5,.3,15.],[-.5,.4,-20.],[.8,-.6,25.]]:
            initiale = (np.asarray(vraie)+delta).tolist()
            for calcul in [icp_scan, recherche_icp]:
                r = calcul(scan, reference, pose_initiale=initiale)
                ep, ea = erreur_pose(r.pose, vraie)
                succes = ep <= .1 and ea <= 2.
                lignes.append(dict(scan=i,methode=r.methode,dx=delta[0],dy=delta[1],da=delta[2],
                    erreur_position_m=ep,erreur_angle_deg=ea,temps_s=r.duree,accepte=r.applicable,
                    succes=succes, faux_accepte=r.applicable and not succes, accord_fin=r.accord_fin,message=r.message))
    with open(sortie,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    for methode in sorted(set(l['methode'] for l in lignes)):
        g=[l for l in lignes if l['methode']==methode]
        print(methode, 'n=',len(g), 'corrects acceptés=',sum(l['accepte'] and l['succes'] for l in g),
              'faux acceptés=',sum(l['faux_accepte'] for l in g), 'refus=',sum(not l['accepte'] for l in g),
              'temps médian=',round(float(np.median([l['temps_s'] for l in g])),3),flush=True)
    return lignes

if __name__=='__main__': evaluer(sys.argv[1])
