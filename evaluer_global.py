"""Évaluation indépendante des poses d'entrée : première référence, recherche 360°.
python evaluer_global.py chemin/ScanJules.zip
Les en-têtes MapTool servent aux erreurs uniquement, jamais aux départs du calcul.
"""
import csv
import sys
import numpy as np
from cartographie import lire_csv
from localisation_globale import localisation_globale
from localisation import erreur_pose


def generer_convexe(pose,n=360):
    from cartographie import Scan,intersection
    sommets=np.array([[-6,-4],[6,-3],[7,3],[2,5],[-5,4]],float)
    murs=[np.array([sommets[i],sommets[(i+1)%len(sommets)]]) for i in range(len(sommets))]
    origine=np.asarray(pose[:2]);mesures=[]
    for angle in np.linspace(359,0,n):
        a=np.deg2rad(angle+pose[2])
        rayon=np.array([origine,origine+40*np.array([np.cos(a),np.sin(a)])])
        impacts=[p for mur in murs if (p:=intersection(rayon,mur)) is not None]
        mesures.append([angle,min(np.linalg.norm(p-origine) for p in impacts),220])
    return Scan('Salle convexe simulée',np.array(mesures),[0.,0.,0.],'SIMULATION',0.)


def evaluer(archive,sortie='exemples/localisation_globale_maptool.csv'):
    scans=lire_csv(archive);reference=scans[0];lignes=[]
    for i,scan in enumerate(scans[1:],2):
        vraie=list(scan.pose_connue)
        scan.pose=[20.,-20.,180.]
        r=localisation_globale(scan,reference)
        ep,ea=erreur_pose(r.pose,vraie)
        succes=ep<=.1 and ea<=2.
        lignes.append(dict(scan=i,erreur_position_m=ep,erreur_angle_deg=ea,temps_s=r.duree,
            accepte=r.applicable,succes=succes,faux_accepte=r.applicable and not succes,
            concordance=r.accord_fin,contradictions=r.contradictions,message=r.message))
        print(i, r.applicable,round(ep,3),round(ea,2),r.message,flush=True)
    with open(sortie,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    print('Corrects acceptés',sum(l['accepte'] and l['succes'] for l in lignes),
          'faux acceptés',sum(l['faux_accepte'] for l in lignes),'refus',sum(not l['accepte'] for l in lignes),
          'médiane',float(np.median([l['temps_s'] for l in lignes])),flush=True)
    return lignes


def evaluer_deplacements(sortie='exemples/localisation_globale_deplacements.csv'):
    from cartographie import demonstration
    r,m=demonstration();vraie=[m.pose[0],m.pose[1],180.]
    m.mesures[:,0]=(m.mesures[:,0]+m.pose[2]-180)%360
    cas=[('Demi-tour',r,m,vraie),
        ('Déplacement 4,47 m et demi-tour',generer_convexe([0,0,0],720),generer_convexe([4,2,180]),[4,2,180])]
    lignes=[]
    for nom,reference,mobile,vraie in cas:
        mobile.pose=[20.,-20.,47.]
        resultat=localisation_globale(mobile,reference)
        ep,ea=erreur_pose(resultat.pose,vraie)
        lignes.append(dict(cas=nom,erreur_position_m=ep,erreur_angle_deg=ea,temps_s=resultat.duree,
            accepte=resultat.applicable,concordance=resultat.accord_fin,contradictions=resultat.contradictions,
            succes=resultat.applicable and ep<=.1 and ea<=2))
        print(lignes[-1],flush=True)
    with open(sortie,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    return lignes


def evaluer_lot_global(sortie='exemples/localisation_globale_lot.csv'):
    from evaluer_lot import generer
    from assemblage_global import assembler_scans
    scans,vraies=generer()
    lot=assembler_scans(scans,progression=lambda t:None)
    lignes=[]
    for i,(s,v) in enumerate(zip(lot,vraies),1):
        ep,ea=erreur_pose(s.pose,v);info=s.suivi_recalage
        lignes.append(dict(scan=i,erreur_position_m=ep,erreur_angle_deg=ea,accepte=info['valide'],
            groupe=info['groupe'],concordance=info.get('accord_fin',0),temps_s=info.get('duree',0),
            succes=info['valide'] and ep<=.1 and ea<=2))
    with open(sortie,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    print(lignes,flush=True)
    return lignes

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--lot': evaluer_lot_global()
    elif len(sys.argv)>1: evaluer(sys.argv[1])
    else: evaluer_deplacements()
