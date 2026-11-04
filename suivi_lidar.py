"""Suivi 2D : prédiction SE(2) et ICP robuste point-vers-droite indexé.

Implémentation NumPy/SciPy indépendante. Normales par covariance locale ;
Jacobien analytique et système 3x3, sans dérivation numérique du voisinage.
Les commandes moteur ne participent jamais à la prédiction.
"""
from time import perf_counter
import numpy as np
from scipy.spatial import cKDTree
from localisation import ResultatICP, transformer


def composer(a, b):
    angle = np.deg2rad(a[2]);c,s = np.cos(angle),np.sin(angle)
    return np.array([a[0]+c*b[0]-s*b[1],a[1]+s*b[0]+c*b[1],(a[2]+b[2]+180)%360-180])


def inverse(p):
    a = np.deg2rad(p[2]);c,s = np.cos(a),np.sin(a)
    return np.array([-c*p[0]-s*p[1],s*p[0]-c*p[1],-p[2]])


def predire(precedente, actuelle, ratio):
    """Extrapole une vitesse corporelle constante, avec petit horizon borné."""
    delta = composer(inverse(precedente),actuelle)
    angle = np.deg2rad(delta[2]);ratio = float(np.clip(ratio,0,2))
    def V(a):
        if abs(a)<1e-8:return np.eye(2)
        return np.array([[np.sin(a),-(1-np.cos(a))],[1-np.cos(a),np.sin(a)]])/a
    vitesse = np.linalg.solve(V(angle),delta[:2])
    mouvement = np.r_[V(angle*ratio)@(vitesse*ratio),delta[2]*ratio]
    return composer(actuelle,mouvement)


class ReferenceSuivi:
    def __init__(self, points):
        self.fond = np.asarray(points,float).copy()
        if self.fond.ndim!=2 or self.fond.shape[1]!=2 or len(self.fond)<12 or not np.isfinite(self.fond).all():
            raise ValueError('Référence locale insuffisante.')
        self.arbre = cKDTree(self.fond)
        distances,idx = self.arbre.query(self.fond,k=7)
        voisins = self.fond[idx];centres = voisins.mean(axis=1)
        ecarts = voisins-centres[:,None,:]
        covariance = np.einsum('nki,nkj->nij',ecarts,ecarts)/7
        valeurs,axes = np.linalg.eigh(covariance)
        self.normales = axes[:,:,0]
        self.centres = centres
        self.valides = ((valeurs[:,1]>.0001)&(valeurs[:,0]<.08*valeurs[:,1])&
                        (distances[:,-1]<.6))

    def distance(self, points):return self.arbre.query(points)[0]


def icp_droites(source, reference, initiale, annuler=None, iterations=30):
    debut = perf_counter();pose = np.asarray(initiale,float).copy()
    source = np.asarray(source,float)
    if len(source)>600:source=source[np.linspace(0,len(source)-1,600).astype(int)]
    init = pose.copy();converge=False;geometrie=False;nombre=0;dernier_pas=(np.inf,np.inf)
    for k in range(iterations):
        if annuler is not None and annuler.is_set():break
        monde = transformer(source,pose)
        d,idx = reference.arbre.query(monde)
        limite = max(.15,.5*.82**k)
        ok = (d<limite)&reference.valides[idx]
        nombre = int(ok.sum())
        if nombre<20:break
        normales = reference.normales[idx[ok]]
        residus = np.sum((monde[ok]-reference.centres[idx[ok]])*normales,axis=1)
        # Cauchy : les points éloignés de leur support pèsent progressivement moins.
        poids = 1/(1+(residus/.04)**2)
        relatif = monde[ok]-pose[:2]
        J = np.column_stack([normales,-normales[:,0]*relatif[:,1]+normales[:,1]*relatif[:,0]])
        H = J.T@(poids[:,None]*J)
        normalisation = np.maximum(np.sqrt(np.diag(H)),1e-9)
        information = H/normalisation[:,None]/normalisation[None,:]
        valeurs = np.linalg.eigvalsh(information)
        geometrie = bool(valeurs[0]>1e-4 and np.isfinite(valeurs).all())
        if not geometrie:break
        pas = np.linalg.solve(H+np.eye(3)*1e-8,-J.T@(poids*residus))
        facteur = min(1.,.25/max(np.linalg.norm(pas[:2]),1e-9),np.deg2rad(12)/max(abs(pas[2]),1e-9))
        pas *= facteur
        dernier_pas=(float(np.linalg.norm(pas[:2])),abs(float(np.rad2deg(pas[2]))))
        pose[:2] += pas[:2];pose[2] = (pose[2]+np.rad2deg(pas[2])+180)%360-180
        if np.linalg.norm(pas[:2])<.0002 and abs(pas[2])<.0001 and k>=4:
            converge=True;break
    # Validation exacte point-à-point : ne pas compter un prolongement de droite comme un impact.
    d = reference.distance(transformer(source,pose));bons = d<.5
    accord = float(np.mean(d<=.12))
    rmse = float(np.sqrt(np.mean(d[bons]**2))) if bons.any() else float('inf')
    # Un suivi dont le dernier pas est déjà de moins de 3 mm et 0,05° est stable même si le seuil
    # strict n'est pas atteint en 30 itérations (robot en mouvement, bruit du lidar) : l'ancien critère
    # refusait des recalages à 99 % de concordance.
    stable = converge or (dernier_pas[0]<.003 and dernier_pas[1]<.05)
    applicable = bool(stable and geometrie and accord>=.65 and nombre>=20 and
                      not (annuler is not None and annuler.is_set()))
    if applicable:raison='Suivi point-vers-droite validé.'
    elif nombre<20:raison='Trop peu de points communs avec la carte.'
    elif not geometrie:raison='Géométrie insuffisante (mur unique ou couloir : une direction non contrainte).'
    elif not stable:raison='Recalage non stabilisé.'
    else:raison='Concordance insuffisante.'
    initial = reference.distance(transformer(source,init));b = initial<.5
    erreur_init = float(np.sqrt(np.mean(initial[b]**2))) if b.any() else float('inf')
    return ResultatICP(pose.tolist(),init.tolist(),erreur_init,rmse,float(bons.mean()),
        int(bons.sum()),k+1,perf_counter()-debut,converge,applicable,
        raison,
        methode='ICP point-vers-droite robuste',accord_fin=accord)
