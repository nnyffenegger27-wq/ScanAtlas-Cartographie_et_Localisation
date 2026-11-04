"""Comparaison TP : mêmes scans, références issues du seul scan fixe, mêmes départs.
python evaluer_tp_jour2.py --sortie exemples/evaluation_tp_jour2.csv
Erreurs vraies en simulation ; convergence et concordance ne valent pas vérité.
"""
import argparse
import csv
from pathlib import Path
from time import perf_counter
import numpy as np
from cartographie import demonstration,Grille,carte_vectorielle
from localisation import erreur_pose
from localisation_tp import ReferenceGrille,ReferenceVectorielle,ReferenceScan,localiser_sur_reference,LOCALE,MULTI

PERTURBATIONS=[(0,0,0),(.1,-.1,2),(.3,-.2,6),(.5,.3,15),(.8,-.6,20),(1.,.5,25),(3.,3.,70)]


def construire_references(scan):
    debut=perf_counter();grille=Grille.depuis_scan(scan,.05)
    rg=ReferenceGrille(grille);tg=perf_counter()-debut
    debut=perf_counter();segments=carte_vectorielle([scan],8,.12,mini=.05,maxi=12,intensite=0,saut=.25,erreur=.05)
    rv=ReferenceVectorielle(segments);tv=perf_counter()-debut
    debut=perf_counter();rs=ReferenceScan(scan);ts=perf_counter()-debut
    return [(rg,tg),(rv,tv),(rs,ts)],grille,segments


def calculer(annuler=None,progression=None):
    """Les 42 essais et la synthèse des six combinaisons ; ne touche à aucun fichier."""
    reference,mobile=demonstration();vraie=list(mobile.pose)
    modeles,_,_=construire_references(reference)
    lignes=[]
    for modele,temps_preparation in modeles:
        for methode in [LOCALE,MULTI]:
            for i,delta in enumerate(PERTURBATIONS):
                if annuler is not None and annuler.is_set():raise InterruptedError('Évaluation annulée ; export non remplacé.')
                if progression:progression(f'Évaluation {modele.type} · {methode} · départ {i+1}/{len(PERTURBATIONS)}…')
                initiale=(np.asarray(vraie)+delta).tolist()
                r=localiser_sur_reference(mobile,modele,methode,pose_initiale=initiale,annuler=annuler)
                ep,ea=erreur_pose(r.pose,vraie);correct=ep<=.1 and ea<=2
                lignes.append(dict(reference=modele.type,methode=methode,cas=i+1,dx_initial_m=delta[0],dy_initial_m=delta[1],
                    angle_initial_deg=delta[2],x_initial=initiale[0],y_initial=initiale[1],theta_initial=initiale[2],
                    erreur_position_m=ep,erreur_angle_deg=ea,temps_s=r.duree,preparation_reference_s=temps_preparation,
                    converge=r.converge,accepte=r.applicable,concordance=r.accord_fin,rmse_m=r.rmse,
                    reussite=correct,reussite_acceptee=correct and r.applicable,faux_accepte=r.applicable and not correct,
                    seuil_position_m=.1,seuil_angle_deg=2,message=r.message))
    if annuler is not None and annuler.is_set():raise InterruptedError('Évaluation annulée ; export non remplacé.')
    synthese=[]
    for modele,_ in modeles:
        for methode in [LOCALE,MULTI]:
            g=[l for l in lignes if l['reference']==modele.type and l['methode']==methode]
            synthese.append(dict(reference=modele.type,methode=methode,essais=len(g),
                reussites=sum(l['reussite'] for l in g),corrects_acceptes=sum(l['reussite_acceptee'] for l in g),
                faux_acceptes=sum(l['faux_accepte'] for l in g),refus=sum(not l['accepte'] for l in g),
                taux_reussite=sum(l['reussite'] for l in g)/len(g),
                mediane_s=float(np.median([l['temps_s'] for l in g])),p95_s=float(np.percentile([l['temps_s'] for l in g],95))))
    return lignes,synthese


def csv_texte(lignes):
    """Texte CSV (UTF-8) d'une liste de dictionnaires de mêmes clés."""
    import io
    tampon=io.StringIO(newline='');w=csv.DictWriter(tampon,fieldnames=list(lignes[0]),lineterminator='\r\n')
    w.writeheader();w.writerows(lignes);return tampon.getvalue()


def evaluer(sortie='exemples/evaluation_tp_jour2.csv',annuler=None,progression=None):
    lignes,synthese=calculer(annuler,progression)
    chemin=Path(sortie);chemin.parent.mkdir(parents=True,exist_ok=True)
    temporaire=chemin.with_suffix(chemin.suffix+'.tmp')
    with temporaire.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(lignes[0]));w.writeheader();w.writerows(lignes)
    temporaire.replace(chemin)
    synth=chemin.with_name(chemin.stem+'_synthese.csv')
    with synth.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(synthese[0]));w.writeheader();w.writerows(synthese)
    for l in synthese:print(l,flush=True)
    return lignes,synthese

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sortie',default='exemples/evaluation_tp_jour2.csv')
    args=p.parse_args();evaluer(args.sortie)
