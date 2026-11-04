"""Compare la même trajectoire avec une ancienne version de cartographie_direct.py.

python outils/comparer_suivi.py --ancienne /chemin/cartographie_direct.py
L'ancien module doit provenir du dépôt ScanAtlas (par exemple commit b28f7c9).
Les deux moteurs reçoivent les mêmes mesures synthétiques et horodatages.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # modules de l'application à la racine
import argparse
import csv
import importlib.util
from pathlib import Path
import sys
import numpy as np
from cartographie_direct import CarteDirecte
from simuler_robot_wifi import mesures_simulees
from robot_wifi import TrameScan
from localisation import erreur_pose


def comparer(ancienne,sortie='exemples/comparaison_suivi_continu.csv'):
    spec=importlib.util.spec_from_file_location('scanatlas_reference_comparaison',ancienne)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    rng=np.random.default_rng(2026)
    trames=[(np.array([.012*i,.004*i,.6*i]),TrameScan(i+1,1000000+i*100000,100000,
            mesures_simulees([.012*i,.004*i,.6*i],rng))) for i in range(60)]
    rows=[]
    for version,classe in [('Suivi initial',module.CarteDirecte),('Suivi point-vers-droite',CarteDirecte)]:
        carte=classe()
        for vraie,trame in trames:
            etat=carte.traiter(trame);ep,ea=erreur_pose(etat.scan.pose,vraie)
            rows.append(dict(version=version,scan=trame.sequence,accepte=etat.accepte,
                erreur_position_m=ep,erreur_angle_deg=ea,calcul_ms=etat.duree*1000,
                concordance_pct=etat.concordance,scans_cles=etat.cles,segments=len(etat.segments)))
        groupe=[r for r in rows if r['version']==version]
        print(version,dict(acceptes=sum(r['accepte'] for r in groupe),
            mediane_ms=float(np.median([r['calcul_ms'] for r in groupe])),
            p95_ms=float(np.percentile([r['calcul_ms'] for r in groupe],95)),
            erreur_max_m=max(r['erreur_position_m'] for r in groupe),
            erreur_max_deg=max(r['erreur_angle_deg'] for r in groupe)),flush=True)
    path=Path(sortie);path.parent.mkdir(exist_ok=True,parents=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    return rows


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ancienne',required=True,type=Path)
    parser.add_argument('--sortie',default='exemples/comparaison_suivi_continu.csv')
    args=parser.parse_args();comparer(args.ancienne,args.sortie)
