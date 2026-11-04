"""Banc reproductible du suivi continu, salle synthétique avec occultations.

python outils/evaluer_wifi.py
60 tours espacés de 100 ms, translation et rotation simultanées, bruit 3 mm.
Ce banc ne mesure ni le réseau radio, ni les moteurs, ni le rolling scan.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # le paquet atlas est à la racine du dépôt
import csv
from pathlib import Path
import numpy as np
from atlas.simulation.simuler_robot_wifi import mesures_simulees
from atlas.calcul.cartographie_direct import CarteDirecte
from atlas.robot.robot_wifi import TrameScan
from atlas.calcul.localisation import erreur_pose


def evaluer(sortie='exemples/evaluation_wifi_simulation.csv'):
    rng=np.random.default_rng(2026);carte=CarteDirecte();rows=[]
    for i in range(60):
        pose=[.012*i,.004*i,.6*i]
        e=carte.traiter(TrameScan(i+1,1000000+i*100000,100000,mesures_simulees(pose,rng)))
        ep,ea=erreur_pose(e.scan.pose,pose)
        rows.append(dict(scan=i+1,x_vrai=pose[0],y_vrai=pose[1],angle_vrai_deg=pose[2],
            x_estime=e.scan.pose[0],y_estime=e.scan.pose[1],angle_estime_deg=e.scan.pose[2],
            erreur_position_m=ep,erreur_angle_deg=ea,accepte=e.accepte,
            concordance_pct=e.concordance,calcul_ms=e.duree*1000,cles=e.cles,segments=len(e.segments)))
    path=Path(sortie);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    print(f'{sum(r["accepte"] for r in rows)}/60 acceptés ; médiane / P95 calcul (ms) :',
          np.percentile([r['calcul_ms'] for r in rows],[50,95]))
    return rows


if __name__=='__main__':evaluer()
