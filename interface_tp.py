"""Onglet de comparaison TP : aucune commande du robot ni accès réseau."""
from copy import deepcopy
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
import numpy as np
from cartographie import Scan
from localisation import points_filtres,transformer
from localisation_tp import (ReferenceGrille,ReferenceVectorielle,ReferenceScan,
                             localiser_sur_reference,LOCALE,MULTI)


class InterfaceTP:
    def interface_tp(self,cadre):
        ttk.Label(cadre,text='Localisation sur les trois références du TP',style='SousTitre.TLabel').pack(anchor='w',pady=(2,8))
        self.vars['tp_reference']=tk.StringVar(value='Grille')
        self.vars['tp_methode']=tk.StringVar(value=MULTI)
        for label,cle,choix in [('Type de référence','tp_reference',['Grille','Carte vectorielle','Scan']),
                                ('Méthode','tp_methode',[MULTI,LOCALE])]:
            ligne=ttk.Frame(cadre);ligne.pack(fill='x',pady=2)
            ttk.Label(ligne,text=label).pack(side='left')
            ttk.Combobox(ligne,textvariable=self.vars[cle],values=choix,state='readonly',width=44).pack(side='right')
        ligne=ttk.Frame(cadre);ligne.pack(fill='x')
        ttk.Label(ligne,text='Référence pour le mode Scan').pack(side='left')
        self.choix_reference_tp=ttk.Combobox(ligne,state='readonly',width=44)
        self.choix_reference_tp.pack(side='right')
        ttk.Label(cadre,text='Mobile = scan sélectionné à gauche. Construis la grille ou la carte vectorielle sans ce mobile.\n'
            'Ces méthodes partent de sa pose actuelle. Multi-résolution : voisinage ±1 m / ±30°, puis affinement.').pack(anchor='w')
        actions=ttk.Frame(cadre);actions.pack(fill='x')
        for texte,action in [('Localiser sur cette référence',self.lancer_localisation_tp),
                             ('Appliquer la pose',self.appliquer_localisation_tp),('Annuler',self.annuler_calcul)]:
            ttk.Button(actions,text=texte,command=lambda a=action:self.proteger(a)).pack(side='left',padx=2,pady=4)
        ttk.Button(cadre,text='Évaluer les 6 combinaisons sur les mêmes scans simulés et exporter les CSV',
                   command=lambda:self.proteger(self.lancer_evaluation_tp)).pack(fill='x')
        self.info_tp=ttk.Label(cadre,text='Résultats de pose à vérifier ; concordance et RMSE ne sont pas des erreurs vraies.',wraplength=900)
        self.info_tp.pack(anchor='w')
        self.resultat_tp=None
        self.actualiser_choix_tp()

    def actualiser_choix_tp(self):
        ancien=getattr(self,'references_tp',[])
        index=self.choix_reference_tp.current()
        objet=ancien[index] if 0<=index<len(ancien) else None
        self.references_tp=list(self.scans)
        self.choix_reference_tp['values']=[f'{i+1} · {s.nom}' for i,s in enumerate(self.scans)]
        if self.scans:self.choix_reference_tp.current(next((i for i,s in enumerate(self.scans) if s is objet),0))
        else:self.choix_reference_tp.set('')

    def preparer_reference_tp(self):
        if not self.scans:raise ValueError('Charge les scans et sélectionne le mobile à gauche.')
        mobile=self.scans[self.indice()];type_ref=self.vars['tp_reference'].get();filtres=self.filtres()
        c=dict(mobile=mobile,pose=list(mobile.pose),mesures=mobile.mesures.copy(),angle=mobile.angle_reference,
               intensite_disponible=mobile.intensite_disponible,type=type_ref,filtres=filtres)
        if type_ref=='Grille':
            g=self.grille
            if g is None:raise ValueError('Construis la grille de référence dans Grille, sans inclure le mobile.')
            if id(mobile) in self.scans_grille:raise ValueError('Le mobile est dans la grille : décoche-le Carte et reconstruis la référence pour éviter une comparaison à lui-même.')
            modele=ReferenceGrille(g)
            c.update(objet=g,geometrie=(g.origine.copy(),g.resolution,g.log_odds.copy(),g.observe.copy()))
        elif type_ref=='Carte vectorielle':
            if self.vecteurs is None or not getattr(self,'scans_vecteurs',None):raise ValueError('Construis la carte vectorielle de référence, sans le mobile.')
            if id(mobile) in self.scans_vecteurs:raise ValueError('Le mobile est dans la carte vectorielle : décoche-le Carte et reconstruis la référence.')
            modele=ReferenceVectorielle(self.vecteurs);c.update(objet=self.vecteurs,geometrie=np.asarray(self.vecteurs).copy())
        elif type_ref=='Scan':
            i=self.choix_reference_tp.current()
            if not 0<=i<len(self.references_tp):raise ValueError('Choisis le scan de référence fixe.')
            ref=self.references_tp[i]
            if ref is mobile:raise ValueError('Choisis un autre scan comme référence fixe.')
            modele=ReferenceScan(ref,filtres)
            c.update(objet=ref,geometrie=(list(ref.pose),ref.mesures.copy(),ref.angle_reference,ref.intensite_disponible))
        else:raise ValueError('Type de référence TP inconnu.')
        c['modele']=modele
        return c

    def contexte_tp_valide(self,c):
        try:
            m=c['mobile']
            if (self.vars['tp_reference'].get()!=c['type'] or self.filtres()!=c['filtres'] or
                not any(s is m for s in self.scans) or self.scans[self.indice()] is not m or
                not np.array_equal(m.pose,c['pose']) or not np.array_equal(m.mesures,c['mesures']) or
                m.angle_reference!=c['angle'] or m.intensite_disponible!=c['intensite_disponible']):return False
            if c['type']=='Grille':
                g=self.grille;o,r,l,v=c['geometrie']
                return g is c['objet'] and np.array_equal(g.origine,o) and g.resolution==r and np.array_equal(g.log_odds,l) and np.array_equal(g.observe,v)
            if c['type']=='Carte vectorielle':return self.vecteurs is c['objet'] and np.array_equal(self.vecteurs,c['geometrie'])
            ref=c['objet'];p,mes,a,inte=c['geometrie'];i=self.choix_reference_tp.current()
            return (0<=i<len(self.references_tp) and self.references_tp[i] is ref and any(s is ref for s in self.scans) and
                np.array_equal(ref.pose,p) and np.array_equal(ref.mesures,mes) and ref.angle_reference==a and ref.intensite_disponible==inte)
        except (ValueError,IndexError):return False

    def lancer_localisation_tp(self):
        if self.travail:raise ValueError('Un calcul ou une capture est déjà en cours.')
        self.annuler_geste();c=self.preparer_reference_tp()
        mobile=deepcopy(c['mobile']);methode=self.vars['tp_methode'].get()
        self.resultat_tp=None;self.travail=True;self.annuler.clear()
        self.info_tp.configure(text=f"Calcul TP sur {c['type']}…")
        def travail():
            try:
                r=localiser_sur_reference(mobile,c['modele'],methode,**c['filtres'],annuler=self.annuler,
                    progression=lambda t:self.messages.put(('tp_statut',t)))
                self.messages.put(('tp_resultat',(c,r)))
            except Exception as exc:self.messages.put(('erreur',str(exc)))
            finally:self.messages.put(('fini',None))
        threading.Thread(target=travail,daemon=True).start()

    def dessiner_tp(self,c,r):
        ax=self.axes['TP Localisation'];ax.clear();modele=c['modele']
        if c['type']=='Grille':
            p=modele.probabilites;image=np.repeat((1-p)[...,None],3,axis=2);image[~modele.observe]=[.65,.73,.78]
            ny,nx=p.shape;x,y=modele.origine
            ax.imshow(image,origin='lower',extent=[x,x+nx*modele.resolution,y,y+ny*modele.resolution],interpolation='nearest')
        elif c['type']=='Carte vectorielle':
            for s in modele.segments:ax.plot(s[:,0],s[:,1],c='#333333',linewidth=2)
        else:ax.scatter(modele.fond[:,0],modele.fond[:,1],s=4,c='#7d8991',label='Référence fixe')
        locaux=points_filtres(c['mobile'],c['filtres'],locaux=True)
        for pose,couleur,texte in [(r.pose_initiale,'#dd8c32','Avant'),(r.pose,'#138961','Pose trouvée')]:
            points=transformer(locaux,pose);ax.scatter(points[:,0],points[:,1],s=4,c=couleur,label=texte)
            ax.plot(*pose[:2],marker='x',c=couleur)
        ax.set_title(r.methode);ax.legend(fontsize=8);self.fin_dessin('TP Localisation')

    def recevoir_localisation_tp(self,data):
        c,r=data
        if not self.contexte_tp_valide(c):
            self.info_tp.configure(text='Résultat TP écarté : données, référence, choix ou filtres modifiés.');return
        self.resultat_tp=(c,r);self.dessiner_tp(c,r)
        self.info_tp.configure(text=f'{r.methode}\nx={r.pose[0]:.4f} m ; y={r.pose[1]:.4f} m ; θ={r.pose[2]:.3f}° ; '
            f'concordance={r.accord_fin:.1%} ; RMSE référence={r.rmse:.4f} m ; temps={r.duree:.3f} s.\n{r.message} '
            'L’erreur vraie est calculée seulement dans l’évaluation avec pose connue.')

    def appliquer_localisation_tp(self):
        if getattr(self,'resultat_tp',None) is None:raise ValueError('Lance d’abord une localisation TP.')
        c,r=self.resultat_tp
        if not self.contexte_tp_valide(c):raise ValueError('Résultat TP périmé : relance le calcul.')
        if not r.applicable:raise ValueError('Pose TP refusée : '+r.message)
        c['mobile'].pose=list(r.pose);c['mobile'].suivi_recalage=None
        self.invalider(conserver_grille=id(c['mobile']) not in self.scans_grille)
        self.actualiser(next(i for i,s in enumerate(self.scans) if s is c['mobile']))
        self.dessiner_tp(c,r)
        self.info_tp.configure(text='Pose appliquée au mobile ; mesures et référence de calcul conservées. Recalcule les cartes affectées si nécessaire.')

    def lancer_evaluation_tp(self):
        if self.travail:raise ValueError('Un calcul ou une capture est déjà en cours.')
        chemin=filedialog.asksaveasfilename(defaultextension='.csv',initialfile='evaluation_tp_jour2.csv',filetypes=[('CSV','*.csv')])
        if not chemin:return
        self.travail=True;self.annuler.clear()
        def travail():
            try:
                from evaluer_tp_jour2 import evaluer
                _,synthese=evaluer(chemin,annuler=self.annuler,progression=lambda t:self.messages.put(('tp_statut',t)))
                self.messages.put(('tp_evaluation',(chemin,synthese)))
            except Exception as exc:self.messages.put(('erreur',str(exc)))
            finally:self.messages.put(('fini',None))
        threading.Thread(target=travail,daemon=True).start()

    def recevoir_evaluation_tp(self,data):
        chemin,synthese=data
        texte='\n'.join(f"{r['reference']} · {r['methode']} : {r['reussites']}/{r['essais']} poses dans 10 cm et 2° ; "
            f"{r['corrects_acceptes']} correctes acceptées, {r['faux_acceptes']} fausses acceptées ; médiane {r['mediane_s']:.3f} s." for r in synthese)
        self.info_tp.configure(text=texte+'\nCSV détaillé et synthèse enregistrés : '+chemin)
        self.statut.set('Évaluation TP terminée ; simulation connue, pas une mesure sur le robot.')
