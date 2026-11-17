"""Cartes cumulées et groupes de scans en attente, indépendants de l'interface.

Le premier scan définit le repère global. Les groupes secondaires ont leur
propre repère et ne sont jamais intégrés à la carte principale avant un pont
validé. Les métadonnées sont persistées par les sessions existantes.
"""
from copy import deepcopy
import numpy as np
from localisation import sous_carte, rotation, points_filtres, transformer, plus_proches
from localisation_globale import localisation_globale, METHODE_GLOBALE


def assembler_scans(scans, reprendre=False, annuler=None, progression=None, **options):
    resultat=deepcopy(list(scans))
    if not resultat: return []
    options={k:v for k,v in options.items() if k not in ('fenetre_xy','fenetre_angle','methode','concordance_min')}
    filtres={k:options.get(k,v) for k,v in dict(mini=.05,maxi=12.,intensite=0).items()}
    if len(points_filtres(resultat[0],filtres,locaux=True))<12:
        raise ValueError('Premier scan insuffisant : au moins douze points après filtrage pour ancrer la carte.')
    ancien_ancrage=resultat[0].suivi_recalage or {}
    reprendre = reprendre and ancien_ancrage.get('methode') == METHODE_GLOBALE and ancien_ancrage.get('pose_ancre') == list(resultat[0].pose)
    groupes={0:[resultat[0]]}
    resultat[0].suivi_recalage=dict(valide=True,etat='ancrage',groupe=0,methode=METHODE_GLOBALE,
                                  pose_ancre=list(resultat[0].pose), message='Premier scan fixe : origine de la carte principale.')
    a_traiter=[]
    for scan in resultat[1:]:
        info=scan.suivi_recalage or {}
        if reprendre and 'groupe' in info:
            groupe=int(info['groupe'])
            # Un état périmé ou annulé ne devient pas une référence par reprise.
            if groupe==0 and info.get('valide'):
                groupes[0].append(scan)
            elif groupe>0 and info.get('etat') in ('groupe','attente'):
                groupes.setdefault(groupe,[]).append(scan)
            else:
                scan.suivi_recalage=None
                a_traiter.append(scan)
        else:
            scan.suivi_recalage=None
            a_traiter.append(scan)
    prochain=max(groupes)+1
    def interrompu(): return annuler is not None and annuler.is_set()
    def carte(g): return sous_carte(groupes[g],filtres,maximum=None)
    def chercher(scan,g,partiel=False):
        if interrompu(): raise InterruptedError('Assemblage annulé.')
        if progression: progression(f'{scan.nom} : recherche sur la carte {"principale" if g==0 else "secondaire "+str(g)}…')
        return localisation_globale(scan,carte(g),annuler=annuler,progression=progression,
            concordance_min=.35 if partiel else .65,**options)
    def info_resultat(r,g,valide,etat):
        return dict(valide=valide,etat=etat,groupe=g,methode=METHODE_GLOBALE,
                    accord_fin=float(r.accord_fin),recouvrement=float(r.recouvrement),
                    rmse=float(r.rmse) if np.isfinite(r.rmse) else None,duree=float(r.duree),
                    message=r.message)
    def fusionner(g,pose_locale,pose_globale,accord):
        angle=(pose_globale[2]-pose_locale[2]+180)%360-180
        rot=rotation(angle);translation=np.asarray(pose_globale[:2])-rot@np.asarray(pose_locale[:2])
        for membre in groupes.pop(g):
            xy=rot@np.asarray(membre.pose[:2])+translation
            membre.pose=[float(xy[0]),float(xy[1]),float((membre.pose[2]+angle+180)%360-180)]
            membre.suivi_recalage=dict(valide=True,etat='fusion',groupe=0,methode=METHODE_GLOBALE,
                accord_pont=float(accord),message=f'Groupe {g} raccordé à la carte principale par un scan commun (concordance du pont {accord:.1%}).')
            groupes[0].append(membre)
    def pont_couvre(scan,r_principal,r_secondaire,g):
        if not r_principal.applicable or not r_secondaire.applicable: return False,0.
        locaux=points_filtres(scan,filtres,locaux=True)
        seuil=min(.12,options.get('distance_max',.5)*.5)
        _,a=plus_proches(transformer(locaux,r_principal.pose),carte(0).points)
        _,b=plus_proches(transformer(locaux,r_secondaire.pose),carte(g).points)
        union=float(((a<=seuil)|(b<=seuil)).mean())
        return union>=.85,union
    def retenter_groupes(pont=None,solution_principale=None):
        for g in list(groupes):
            if g==0: continue
            if interrompu(): raise InterruptedError('Assemblage annulé.')
            # Un scan voyant les deux cartes donne deux poses du même lidar.
            # Leur transformation relative déplace rigidement tout le groupe.
            if pont is not None:
                try: r=chercher(pont,g,partiel=True)
                except ValueError: continue
                ok,union=pont_couvre(pont,solution_principale,r,g)
                if ok:
                    fusionner(g,r.pose,solution_principale.pose,min(r.accord_fin,solution_principale.accord_fin))
                    continue
            # Une ancienne vue peut devenir raccordable après extension.
            for membre in [groupes[g][-1]]:
                try: r=chercher(membre,0)
                except ValueError: continue
                if r.applicable:
                    fusionner(g,list(membre.pose),r.pose,r.accord_fin)
                    break
    try:
        # Permet de relancer les groupes sauvegardés même sans nouvelle capture.
        if reprendre and len(groupes)>1: retenter_groupes()
        for i,scan in enumerate(a_traiter):
            if interrompu(): raise InterruptedError('Assemblage annulé.')
            if progression: progression(f'Assemblage global : {i+1}/{len(a_traiter)} nouveaux scans…')
            try: r=chercher(scan,0)
            except ValueError as exc:
                scan.suivi_recalage=dict(valide=False,etat='insuffisant',groupe=-1,methode=METHODE_GLOBALE,
                    message='Scan conservé sans raccordement : '+str(exc))
                continue
            if r.applicable:
                scan.pose=list(r.pose);scan.suivi_recalage=info_resultat(r,0,True,'recalage')
                retenter_groupes(scan,r)
                groupes[0].append(scan)
                continue
            # Deux recouvrements partiels peuvent constituer un pont complet.
            # Un score faible seul ne suffit jamais à raccorder un groupe.
            if len(groupes)>1 and 'ambigu' not in r.message:
                partiel_principal=chercher(scan,0,partiel=True)
                if partiel_principal.applicable:
                    for g in list(groupes):
                        if g==0: continue
                        try: partiel_secondaire=chercher(scan,g,partiel=True)
                        except ValueError: continue
                        ok,union=pont_couvre(scan,partiel_principal,partiel_secondaire,g)
                        if ok:
                            fusionner(g,partiel_secondaire.pose,partiel_principal.pose,min(partiel_principal.accord_fin,partiel_secondaire.accord_fin))
                            scan.pose=list(partiel_principal.pose)
                            scan.suivi_recalage=info_resultat(partiel_principal,0,True,'pont')
                            scan.suivi_recalage['accord_fin']=union
                            scan.suivi_recalage['message']=f'Pont validé entre deux cartes : concordance cumulée {union:.1%} (85 % requis, au moins 35 % par carte).'
                            groupes[0].append(scan)
                            break
                    if scan.suivi_recalage and scan.suivi_recalage.get('etat')=='pont': continue
            rattache=False
            for g in list(groupes):
                if g==0: continue
                try: secondaire=chercher(scan,g)
                except ValueError: continue
                if secondaire.applicable:
                    scan.pose=list(secondaire.pose)
                    scan.suivi_recalage=info_resultat(secondaire,g,False,'groupe')
                    scan.suivi_recalage['message']=f'Groupe secondaire {g} : concordance locale {secondaire.accord_fin:.1%}. Raccordement principal en attente.'
                    groupes[g].append(scan);rattache=True;break
            if not rattache:
                g=prochain;prochain+=1
                scan.pose=[0.,0.,0.]
                scan.suivi_recalage=info_resultat(r,g,False,'attente')
                scan.suivi_recalage['message']=f'Groupe secondaire {g} créé ; '+r.message
                groupes[g]=[scan]
    except InterruptedError:
        # Le contrôleur écarte l'ensemble des résultats en cas d'annulation.
        for scan in resultat:
            if scan.suivi_recalage is None:
                scan.suivi_recalage=dict(valide=False,etat='annule',groupe=-1,message='Assemblage annulé.')
    return resultat
