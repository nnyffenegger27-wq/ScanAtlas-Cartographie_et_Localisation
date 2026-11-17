"""Localisation 2D sur toute la carte, 360°, sans fenêtre autour du dernier scan.

Recherche corrélative vectorisée grossière/fine puis ICP multi-départ. Les
bornes sont déduites de la carte et de la portée des mesures, jamais de la pose
précédente. Pas de vérité terrain dans le solveur.
"""
from time import perf_counter
import numpy as np
from cartographie import Scan, Grille
from localisation import (ResultatICP, champ_distances, points_filtres, transformer,
                          rotation, icp_scan, score_pose, valider_solution, erreur_pose, plus_proches)

METHODE_GLOBALE = 'Carte cumulée · recherche globale 360°'


def localisation_globale(mobile, reference, pose_initiale=None, mini=.05, maxi=12., intensite=0,
                         distance_max=.5, iterations_max=80, annuler=None, progression=None, concordance_min=.65,
                         centre=None, rayon=None):
    """Recherche sur toute la carte ; `centre` et `rayon` (m) bornent les positions testées (recherche élargie)."""
    debut=perf_counter()
    valeurs=np.array([mini,maxi,intensite,distance_max,iterations_max],float)
    if (not np.isfinite(concordance_min) or not .3<=concordance_min<=.95 or mobile is reference or not np.isfinite(valeurs).all() or not 0<=mini<maxi or
        not 0<=intensite<=255 or distance_max<=0 or iterations_max!=int(iterations_max) or not 1<=iterations_max<=300):
        raise ValueError('Deux scans distincts, filtres valides, distance positive et 1 à 300 itérations requis.')
    initiale=np.array(mobile.pose if pose_initiale is None else pose_initiale,float)
    if initiale.shape!=(3,) or not np.isfinite(initiale).all(): raise ValueError('Pose initiale invalide.')
    filtres=dict(mini=mini,maxi=maxi,intensite=intensite)
    source=points_filtres(mobile,filtres,locaux=True)
    cible=points_filtres(reference,filtres)
    if min(len(source),len(cible))<12 or not np.isfinite(cible).all():
        raise ValueError('Au moins douze points distincts après filtrage sont nécessaires.')
    # Le centre du lidar peut être hors de la zone déjà mesurée. Une borne
    # déduite de la portée inclut toute pose ayant au moins un impact commun.
    rayon=float(np.linalg.norm(source,axis=1).max())
    bas=cible.min(axis=0)-rayon;haut=cible.max(axis=0)+rayon
    petits=source[np.linspace(0,len(source)-1,min(160,len(source)),dtype=int)]
    limite=max(.65,min(1.,distance_max*2))
    # Champ de distances et zones libres : calculés une fois par carte (la recherche est relancée
    # toutes les quelques secondes quand le robot est perdu), puis gardés sur l'objet de référence.
    cle_cache=(round(limite,4),mini,maxi,intensite,len(cible),round(float(cible.sum()),6))
    cache=None if isinstance(reference,Scan) else getattr(reference,'_cache_globale',None)
    if cache is not None and cache[0]==cle_cache:
        origine,resolution,champ,libre=cache[1:]
    else:
        origine,resolution,champ=champ_distances(cible,limite,resolution=.075)
        # Les impacts dans une zone déjà vue libre contredisent la carte.
        # Cela évite de ne noter que les murs superposables d'une salle symétrique.
        references=(reference,) if isinstance(reference,Scan) else getattr(reference,'sources',())
        libre=None
        if references:
            libre=Grille.creer(references,resolution=.075,**filtres)
            for scan in references:
                if annuler is not None and annuler.is_set(): break
                libre.mettre_a_jour(scan,**filtres)
        if not isinstance(reference,Scan) and (annuler is None or not annuler.is_set()):
            try:reference._cache_globale=(cle_cache,origine,resolution,champ,libre)
            except AttributeError:pass
    def conflits(x,y,distances_carrees):
        if libre is None: return np.zeros(np.shape(x),bool)
        ix=np.floor((x-libre.origine[0])/libre.resolution).astype(int)
        iy=np.floor((y-libre.origine[1])/libre.resolution).astype(int)
        ok=(ix>=0)&(ix<libre.log_odds.shape[1])&(iy>=0)&(iy<libre.log_odds.shape[0])
        masque=np.zeros(np.shape(x),bool)
        masque[ok]=libre.observe[iy[ok],ix[ok]]&(libre.log_odds[iy[ok],ix[ok]]<-.2)
        return masque&(distances_carrees>.18**2)
    total=0
    def verifier():
        if annuler is not None and annuler.is_set(): raise InterruptedError('Localisation globale annulée.')
    def cout(poses):
        nonlocal total
        verifier()
        poses=np.asarray(poses,float)
        a=np.deg2rad(poses[:,2]);c,s=np.cos(a),np.sin(a)
        x=petits[None,:,0]*c[:,None]-petits[None,:,1]*s[:,None]+poses[:,None,0]
        y=petits[None,:,0]*s[:,None]+petits[None,:,1]*c[:,None]+poses[:,None,1]
        ix=np.rint((x-origine[0])/resolution).astype(int);iy=np.rint((y-origine[1])/resolution).astype(int)
        ok=(ix>=0)&(ix<champ.shape[1])&(iy>=0)&(iy<champ.shape[0])
        d=np.full(x.shape,limite**2);d[ok]=champ[iy[ok],ix[ok]]
        total+=len(poses)
        return d.mean(axis=1)+1.5*conflits(x,y,d).mean(axis=1)
    def garder(scores,poses,nombre=48,distance=.4,angle=8.):
        retenus=[]
        for j in np.argsort(scores):
            p=poses[j]
            if all(np.linalg.norm(p[:2]-q[:2])>=distance or abs((p[2]-q[2]+180)%360-180)>=angle for _,q in retenus):
                retenus.append((float(scores[j]),p.copy()))
                if len(retenus)>=nombre: break
        return retenus
    def resultat_vide(message):
        return ResultatICP(initiale.tolist(),initiale.tolist(),float('inf'),float('inf'),0.,0,0,0.,False,False,message)
    try:
        # Tuiles mémoire bornées ; toute l'étendue et tous les angles sont
        # visités. Le pas ne s'élargit pas quand la carte grandit.
        xs=np.arange(bas[0],haut[0]+.4,.4);ys=np.arange(bas[1],haut[1]+.4,.4)
        xy=np.array(np.meshgrid(xs,ys,indexing='ij')).reshape(2,-1).T
        if centre is not None and rayon is not None:
            # Recherche élargie : seules les positions proches du dernier point connu (tous les angles).
            proche=np.linalg.norm(xy-np.asarray(centre,float),axis=1)<=float(rayon)+.3
            if proche.any():xy=xy[proche]
        graines=[]
        for k,angle in enumerate(np.arange(-180.,180.,4.)):
            verifier()
            if progression and k%6==0: progression(f'Recherche globale 360° : {k+1}/90 orientations, {total} poses…')
            poses=np.column_stack([xy,np.full(len(xy),angle)])
            scores=np.concatenate([cout(poses[j:j+1024]) for j in range(0,len(poses),1024)])
            meilleurs=np.argsort(scores)[:48]
            graines.extend((float(scores[j]),poses[j].copy()) for j in meilleurs)
        scores=np.array([s for s,_ in graines]);poses=np.array([p for _,p in graines])
        graines=garder(scores,poses)
        # Affinement spatial ET angulaire, y compris au raccord -180/+180.
        for etape,(dx,da) in enumerate([(.2,2.),(.1,1.),(.05,.5)]):
            verifier()
            if progression: progression(f'Recherche globale : affinement {etape+1}/3…')
            poses=np.array([p+[x,y,a] for _,p in graines for x in [-dx,0,dx] for y in [-dx,0,dx] for a in [-da,0,da]])
            poses[:,2]=(poses[:,2]+180)%360-180
            scores=np.concatenate([cout(poses[j:j+1024]) for j in range(0,len(poses),1024)])
            graines=garder(scores,poses,nombre=32,distance=max(.12,dx*2),angle=max(3.,da*2))
        # Plusieurs minima conservés pour rechercher les ambiguïtés.
        solutions=[]
        for i,(_,p) in enumerate(graines[:16]):
            verifier()
            if progression: progression(f'Validation globale ICP {i+1}/{min(16,len(graines))}…')
            r=icp_scan(mobile,reference,pose_initiale=p,**filtres,distance_max=distance_max,
                       iterations_max=iterations_max,annuler=annuler)
            if r.converge:
                valider_solution(r,source,cible,distance_max,concordance_min=concordance_min)
                points=transformer(source,r.pose)
                _,distances=plus_proches(points,cible)
                r.contradictions=float(conflits(points[:,0],points[:,1],distances**2).mean())
                if r.contradictions>.08:
                    r.applicable=False
                    r.message=f'Contradiction avec les zones libres connues : {r.contradictions:.1%} des impacts (maximum 8 %).'
                solutions.append((score_pose(source,cible,r.pose,min(distance_max,1.))+1.5*r.contradictions,r))
        solutions.sort(key=lambda v:v[0])
        acceptables=[v for v in solutions if v[1].applicable]
        if acceptables:
            meilleur,r=acceptables[0]
            r.message=f'Raccordement accepté : concordance {r.accord_fin:.1%}.'
            for score,autre in solutions:
                ep,ea=erreur_pose(autre.pose,r.pose)
                if (ep>.20 or ea>5.) and score<=meilleur+max(.0004,.08*meilleur):
                    r.marge_ambiguite=float(score-meilleur);r.applicable=False
                    r.message=f'Concordance {r.accord_fin:.1%}, mais plusieurs positions ou orientations se ressemblent : localisation ambiguë.'
                    break
        elif solutions:
            r=max((r for _,r in solutions),key=lambda r:r.accord_fin)
            r.message=f'Concordance {r.accord_fin:.1%} ; '+r.message
        else: r=resultat_vide('Aucun raccordement convergé sur la carte. Scan à mettre en attente.')
        verifier()
    except InterruptedError:
        r=resultat_vide('Localisation globale annulée ; pose inchangée.')
    _, distances=plus_proches(transformer(source,initiale),cible)
    bonnes=distances<=distance_max
    r.rmse_initiale=float(np.sqrt(np.mean(distances[bonnes]**2))) if bonnes.any() else float('inf')
    r.pose_initiale=initiale.tolist();r.duree=perf_counter()-debut;r.methode=METHODE_GLOBALE;r.candidats=total
    return r
