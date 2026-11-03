"""Figures à partir du CSV mesuré ; aperçu calculé sur les trois références."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from cartographie import demonstration
from evaluer_tp_jour2 import construire_references
from localisation_tp import localiser_sur_reference,MULTI
from localisation import points_filtres,transformer


def produire():
    base=Path(__file__).parent/'exemples';ls=list(csv.DictReader((base/'evaluation_tp_jour2.csv').open()))
    couleurs={'Grille':'#3366aa','Carte vectorielle':'#d07a23','Scan':'#25845b'}
    fig,axes=plt.subplots(2,1,figsize=(7,5.7),sharex=True,constrained_layout=True)
    for ref,c in couleurs.items():
        for multi in [False,True]:
            g=[l for l in ls if l['reference']==ref and ('Multi' in l['methode'])==multi]
            for ax,cle,seuil in [(axes[0],'erreur_position_m',.1),(axes[1],'erreur_angle_deg',2)]:
                ax.plot([int(l['cas']) for l in g],[max(float(l[cle]),1e-5) for l in g],
                    color=c,linestyle='-' if multi else '--',marker='o',markersize=3,
                    label=ref+(' multi-résolution' if multi else ' locale'))
    for ax,seuil in zip(axes,[.1,2]):
        ax.axhline(seuil,color='black',linestyle=':',label='Seuil TP');ax.set_yscale('log');ax.grid(alpha=.2)
        ax.axvspan(6.6,7.4,color='#e2d1d1',alpha=.4)
    axes[0].set_ylabel('Erreur position (m)');axes[1].set_ylabel('Erreur angle (°)');axes[1].set_xlabel('Cas initial — 7 hors du voisinage TP')
    axes[1].set_xticks(range(1,8));axes[0].legend(fontsize=7,ncol=2,loc='upper left')
    fig.savefig(base/'TP_JOUR2_ERREURS.png',dpi=180);plt.close(fig)
    reference,mobile=demonstration();modeles,_,_=construire_references(reference)
    avant=(np.array(mobile.pose)+[.5,.3,15]).tolist();source=points_filtres(mobile,dict(mini=.05,maxi=12,intensite=0),locaux=True)
    fig,axes=plt.subplots(3,1,figsize=(7,8.3),constrained_layout=True)
    for ax,(modele,_) in zip(axes,modeles):
        r=localiser_sur_reference(mobile,modele,MULTI,pose_initiale=avant)
        if modele.type=='Grille':
            p=modele.probabilites;im=np.repeat((1-p)[...,None],3,axis=2);im[~modele.observe]=[.7,.77,.8]
            ny,nx=p.shape;x,y=modele.origine
            ax.imshow(im,origin='lower',extent=[x,x+nx*modele.resolution,y,y+ny*modele.resolution],interpolation='nearest')
        elif modele.type=='Carte vectorielle':
            for s in modele.segments:ax.plot(s[:,0],s[:,1],color='#333333',lw=1.5)
        else:ax.scatter(modele.fond[:,0],modele.fond[:,1],s=3,c='#737f89')
        for pose,col,nom in [(avant,'#dc8e36','Avant'),(r.pose,'#188659','Après')]:
            p=transformer(source,pose);ax.scatter(p[:,0],p[:,1],s=3,c=col,label=nom)
        ax.set_title(f'{modele.type} — concordance {r.accord_fin:.1%}',fontsize=10)
        tout=np.vstack([transformer(source,avant),transformer(source,r.pose),modele.fond])
        ax.set_aspect('equal');ax.set_xlim(tout[:,0].min()-.3,tout[:,0].max()+.3);ax.set_ylim(tout[:,1].min()-.3,tout[:,1].max()+.3);ax.grid(alpha=.15)
        ax.set_xlabel('x (m)',fontsize=8);ax.set_ylabel('y (m)',fontsize=8);ax.tick_params(labelsize=8);ax.legend(fontsize=8,loc='upper right')
    fig.savefig(base/'TP_JOUR2_TROIS_REFERENCES.png',dpi=180);plt.close(fig)
    return str(base)

if __name__=='__main__':print(produire())
