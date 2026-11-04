"""Trajectoire simulée déterministe, bruit 15 mm, 20 % de pertes, 5 % d’aberrants.
python outils/evaluer_lot.py
La vérité n'entre jamais dans le recalage ; seul le premier scan fixe le repère.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # modules de l'application à la racine
import csv
import numpy as np
from cartographie import Scan, intersection
from recalage_capture import recaler_lot
from localisation import erreur_pose


def generer():
    murs=[np.array(s,float) for s in [
        [[-3,-2],[3,-2]],[[3,-2],[3,2]],[[3,2],[-3,2]],[[-3,2],[-3,-2]],
        [[1,-.6],[1,.6]],[[1,.6],[1.5,.6]],[[1.5,.6],[1.5,-.6]],[[1.5,-.6],[1,-.6]]]]
    vraies=[[0,0,0],[.5,.1,20],[.8,.5,40],[.4,.9,55],[-.2,1,35],[-.7,.6,15],[-.8,.1,-5],[-.3,-.3,10]]
    rng=np.random.default_rng(20261103)
    scans=[]
    for i,pose in enumerate(vraies):
        mesures=[];origine=np.array(pose[:2])
        for angle in np.arange(359.,-1.,-1.):
            if rng.random()<.2: continue
            a=np.deg2rad(angle+pose[2]);rayon=np.array([origine,origine+20*np.array([np.cos(a),np.sin(a)])])
            impacts=[p for m in murs if (p:=intersection(rayon,m)) is not None]
            d=min(np.linalg.norm(p-origine) for p in impacts)+rng.normal(0,.015)
            if rng.random()<.05: d=rng.uniform(.1,8)
            mesures.append([angle,d,220])
        scans.append(Scan(f'Trajectoire {i+1}',np.array(mesures),[0.,0.,0.], 'SIMULATION',0.))
    return scans,vraies


def evaluer(sortie='exemples/robustesse_lot.csv'):
    scans,vraies=generer()
    lot=recaler_lot(scans)
    lignes=[]
    for i,(s,v) in enumerate(zip(lot,vraies)):
        ep,ea=erreur_pose(s.pose,v)
        lignes.append(dict(scan=i+1,x=s.pose[0],y=s.pose[1],theta=s.pose[2],erreur_position_m=ep,
            erreur_angle_deg=ea,accepte=s.suivi_recalage['valide'],
            succes=ep<=.1 and ea<=2,temps_s=s.suivi_recalage.get('duree',0),message=s.suivi_recalage['message']))
    with open(sortie,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    print(lignes)
    return lignes

if __name__=='__main__':evaluer()
