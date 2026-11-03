"""Localisation TP sur grille, segments finis ou scan : références distinctes.

Moindres carrés robustes locaux, ou corrélation multi-résolution puis affinement.
SciPy fournit EDT, interpolation, arbre de voisins et solveur numérique ; les
résidus, modèles de référence, critères et tests sont propres à ScanAtlas.
"""
from time import perf_counter
import numpy as np
from scipy.ndimage import distance_transform_edt, map_coordinates
from scipy.spatial import cKDTree
from scipy.optimize import least_squares
from localisation import ResultatICP, points_filtres, transformer, erreur_pose

LOCALE='Affinement local robuste'
MULTI='Multi-résolution + affinement robuste'


class ReferenceGrille:
    type='Grille'
    def __init__(self,grille):
        self.origine=np.asarray(grille.origine,float).copy()
        self.resolution=float(grille.resolution)
        self.probabilites=np.asarray(grille.probabilites(),float).copy()
        self.observe=np.asarray(grille.observe,bool).copy()
        occupe=self.observe&(self.probabilites>=.6)
        if self.resolution<=0 or not np.isfinite(self.resolution) or occupe.sum()<3:
            raise ValueError('Grille : au moins trois cellules occupées observées sont nécessaires.')
        self.champ=distance_transform_edt(~occupe)*self.resolution
        yy,xx=np.nonzero(occupe)
        self.fond=self.origine+(np.column_stack([xx,yy])+.5)*self.resolution
    def distance(self,points):
        ij=(points-self.origine)/self.resolution-.5
        return map_coordinates(self.champ,ij[:,::-1].T,order=1,mode='constant',cval=1.,prefilter=False)
    def residus(self,points):return np.minimum(self.distance(points),.5)
    def contradictions(self,points):
        ij=np.floor((points-self.origine)/self.resolution).astype(int)
        ok=(ij[:,0]>=0)&(ij[:,1]>=0)&(ij[:,0]<self.observe.shape[1])&(ij[:,1]<self.observe.shape[0])
        conflit=np.zeros(len(points),bool)
        conflit[ok]=self.observe[ij[ok,1],ij[ok,0]]&(self.probabilites[ij[ok,1],ij[ok,0]]<.45)
        return float((conflit&(self.distance(points)>.18)).mean())


class ReferenceVectorielle:
    type='Carte vectorielle'
    def __init__(self,segments):
        self.segments=np.asarray(segments,float).copy()
        if (self.segments.ndim!=3 or self.segments.shape[1:]!=(2,2) or len(self.segments)==0 or
            not np.isfinite(self.segments).all()):raise ValueError('Carte vectorielle vide ou segments invalides.')
        self.a=self.segments[:,0];self.v=self.segments[:,1]-self.a
        self.longueurs2=np.sum(self.v*self.v,axis=1)
        if (self.longueurs2<1e-12).any():raise ValueError('Segment de longueur nulle.')
        self.normales=np.column_stack([-self.v[:,1],self.v[:,0]])/np.sqrt(self.longueurs2)[:,None]
        self.fond=self.segments.reshape(-1,2)
    def associations(self,points):
        projections=[];indices=[];distances=[];interieurs=[]
        for debut in range(0,len(points),512):
            p=points[debut:debut+512]
            relatif=p[:,None,:]-self.a[None,:,:]
            t=np.sum(relatif*self.v[None,:,:],axis=2)/self.longueurs2
            q=self.a[None,:,:]+np.clip(t,0,1)[:,:,None]*self.v[None,:,:]
            d2=np.sum((p[:,None,:]-q)**2,axis=2);idx=np.argmin(d2,axis=1);i=np.arange(len(p))
            projections.append(q[i,idx]);indices.append(idx);distances.append(np.sqrt(d2[i,idx]))
            interieurs.append((t[i,idx]>=0)&(t[i,idx]<=1))
        return np.concatenate(projections),np.concatenate(indices),np.concatenate(distances),np.concatenate(interieurs)
    def distance(self,points):return self.associations(points)[2]
    def residus(self,points):
        q,idx,d,interieur=self.associations(points)
        # Vecteur vers la projection sur le SEGMENT FINI : sa norme est
        # la distance orthogonale, ou la distance à une extrémité.
        delta=points-q
        return np.clip(delta,-.5,.5).ravel()
    def contradictions(self,points):return 0.


class ReferenceScan:
    type='Scan'
    def __init__(self,scan,filtres=None):
        self.fond=points_filtres(scan,filtres or dict(mini=.05,maxi=12,intensite=0)).copy()
        if len(self.fond)<12:raise ValueError('Scan de référence : au moins douze points distincts.')
        self.arbre=cKDTree(self.fond)
    def distance(self,points):return self.arbre.query(points)[0]
    def residus(self,points):
        _,idx=self.arbre.query(points)
        return np.clip(points-self.fond[idx],-.5,.5).ravel()
    def contradictions(self,points):return 0.


def localiser_sur_reference(mobile,reference,methode=MULTI,pose_initiale=None,
                           mini=.05,maxi=12.,intensite=0,iterations_max=80,
                           annuler=None,progression=None):
    """Pose approchée, coordonnées en mètres et degrés ; entrées inchangées.

    Multi-résolution : ±1 m et ±30° autour du départ pour le protocole TP.
    Le solveur local n'est pas une relocalisation globale. La recherche 360°
    historique reste séparée et disponible pour les grandes discontinuités.
    """
    debut=perf_counter()
    if methode not in (LOCALE,MULTI):raise ValueError('Méthode TP inconnue.')
    initiale=np.asarray(mobile.pose if pose_initiale is None else pose_initiale,float)
    if initiale.shape!=(3,) or not np.isfinite(initiale).all():raise ValueError('Pose initiale invalide.')
    if (not np.isfinite([mini,maxi,intensite,iterations_max]).all() or not 0<=mini<maxi or not 0<=intensite<=255 or
        iterations_max!=int(iterations_max) or not 1<=iterations_max<=300):raise ValueError('Filtres ou limite d’itérations invalides.')
    source=points_filtres(mobile,dict(mini=mini,maxi=maxi,intensite=intensite),locaux=True,maximum=600)
    if len(source)<12:raise ValueError('Scan mobile : au moins douze points distincts après filtrage.')
    def verifier():
        if annuler is not None and annuler.is_set():raise InterruptedError('Localisation TP annulée.')
    def cout(pose,points=source):
        p=transformer(points,pose);d=reference.distance(p)
        return float(np.mean(np.minimum(d,.5)**2)+.5*reference.contradictions(p))
    def optimiser(pose):
        def fonction(x):
            verifier()
            return reference.residus(transformer(source,[x[0],x[1],np.rad2deg(x[2])]))
        x0=np.array([pose[0],pose[1],np.deg2rad(pose[2])])
        calcul=least_squares(fonction,x0,method='trf',jac='2-point',loss='soft_l1',f_scale=.05,x_scale=[1.,1.,.3],
                            max_nfev=int(iterations_max),ftol=1e-7,xtol=1e-7,gtol=1e-7)
        p=[float(calcul.x[0]),float(calcul.x[1]),float((np.rad2deg(calcul.x[2])+180)%360-180)]
        d=reference.distance(transformer(source,p));bons=d<=.5
        rmse=float(np.sqrt(np.mean(d[bons]**2))) if bons.any() else float('inf')
        info=np.linalg.eigvalsh(calcul.jac.T@calcul.jac)
        geometrie=info[-1]>1e-12 and info[0]>1e-7*info[-1]
        accord=float((d<=.12).mean());contrad=reference.contradictions(transformer(source,p))
        applicable=bool(calcul.success and accord>=.65 and (d<=.12).sum()>=12 and geometrie and contrad<=.08)
        message=(f'Concordance {accord:.1%} ; affinement convergé.' if applicable else
            f'Pose refusée : concordance {accord:.1%}, géométrie {"contrainte" if geometrie else "ambiguë"}, contradictions {contrad:.1%}.')
        r=ResultatICP(p,initiale.tolist(),0.,rmse,float(bons.mean()),int(bons.sum()),int(calcul.nfev),0.,
                      bool(calcul.success),applicable,message)
        r.accord_fin=accord;r.contradictions=contrad
        return r
    total=0;graines=[initiale.copy()]
    try:
        verifier()
        if methode==MULTI:
            petits=source[np.linspace(0,len(source)-1,min(160,len(source)),dtype=int)]
            candidats=[]
            for da in np.arange(-30.,30.1,10.):
                for dx in np.arange(-1.,1.01,.5):
                    for dy in np.arange(-1.,1.01,.5):
                        verifier();p=initiale+[dx,dy,da];candidats.append((cout(p,petits),p));total+=1
            def retenir(liste,ecart,angle):
                resultat=[]
                for score,p in sorted(liste,key=lambda v:v[0]):
                    if all(np.linalg.norm(p[:2]-q[:2])>=ecart or abs((p[2]-q[2]+180)%360-180)>=angle for _,q in resultat):
                        resultat.append((score,p))
                        if len(resultat)==6:break
                return resultat
            meilleurs=retenir(candidats,.4,8.)
            for etape,(dx,da) in enumerate([(.25,5.),(.125,2.5)]):
                if progression:progression(f'{reference.type} : multi-résolution {etape+1}/2…')
                candidats=list(meilleurs)
                for _,p in meilleurs:
                    for x in [-dx,0,dx]:
                        for y in [-dx,0,dx]:
                            for a in [-da,0,da]:
                                verifier();q=p+[x,y,a]
                                if np.any(abs(q[:2]-initiale[:2])>1+1e-8) or abs(q[2]-initiale[2])>30+1e-8:continue
                                candidats.append((cout(q,petits),q));total+=1
                meilleurs=retenir(candidats,dx,max(3.,da))
            graines=[p for _,p in meilleurs]+[initiale.copy()]
        solutions=[]
        for i,p in enumerate(graines):
            verifier()
            if progression:progression(f'{reference.type} : affinement {i+1}/{len(graines)}…')
            r=optimiser(p);solutions.append((cout(r.pose),r))
        solutions.sort(key=lambda x:x[0]);valide=[x for x in solutions if x[1].applicable]
        score,r=valide[0] if valide else solutions[0]
        if valide and methode==MULTI:
            for autre_score,autre in solutions:
                ep,ea=erreur_pose(autre.pose,r.pose)
                if (ep>.2 or ea>5) and autre_score<=score+max(.0004,.08*score):
                    r.applicable=False;r.message='Pose ambiguë : plusieurs solutions de coûts voisins.';break
        verifier()
    except InterruptedError:
        r=ResultatICP(initiale.tolist(),initiale.tolist(),float('inf'),float('inf'),0,0,0,0,False,False,'Localisation TP annulée.')
    d=reference.distance(transformer(source,initiale));bons=d<=.5
    r.rmse_initiale=float(np.sqrt(np.mean(d[bons]**2))) if bons.any() else float('inf')
    r.duree=perf_counter()-debut;r.methode=reference.type+' · '+methode;r.candidats=total+len(graines)
    return r
