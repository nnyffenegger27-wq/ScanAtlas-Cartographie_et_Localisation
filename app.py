"""LD06 Atelier — interface pédagogique locale (Tkinter + Matplotlib).
Les calculs du TP sont dans cartographie.py ; l'USB dans acquisition.py.
"""
import csv
from copy import deepcopy
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from cartographie import (Scan, Grille, lire_csv, exporter_scan, demonstration,
                         mesures_valides, extraire_segments, carte_vectorielle,
                         angle_segments, proches, fusionner, intersection, decouper, EPS, extraire_multiscans)
from cartographie import ANGLE_REFERENCE_DEFAUT, diagnostic_scan
from manipulation import ManipulationScan
from localisation import icp_scan, recherche_icp, points_filtres, transformer
from recalage_capture import recaler_capture, recaler_lot
from localisation_globale import localisation_globale, METHODE_GLOBALE
from assemblage_global import assembler_scans
from interface_tp import InterfaceTP
from interface_wifi import InterfaceWifi
from apparence import appliquer_theme, curseur, PLAGES, cadre_defilant, habiller_barre, FOND
from localisation_tp import LOCALE as TP_LOCALE, MULTI as TP_MULTI

AIDE = '''PARCOURS CONSEILLÉ
1. « Démonstration simulée » pour découvrir les vues sans matériel.
2. Cartographie : importer un CSV/ZIP, ouvrir une session ou capturer par USB/Wi-Fi.
3. Sélectionner un scan ; régler sa pose par coordonnées ou modes souris Déplacer/Tourner.
4. Grille : créer depuis un scan, puis ajouter un autre ; ou reconstruire les scans cochés Carte.
5. Exporter les scans réels et la session pour conserver le travail.

CONVENTIONS
Distances internes et poses en mètres ; angles en degrés antihoraires.
Pour les imports/USB : référence lidar fixe à 0°, selon le réglage actuel du projet.
Seul le réglage de pose du robot est affiché.
Elle est aussi appliquée aux scans réels des anciennes sessions.
Le CSV ESP32 a 6 colonnes : indice, angle°, distance mm, intensité, x mm, y mm.
Nous recalculons x = r cos(angle), y = r sin(angle) : les colonnes x/y ESP32
ne sont pas utilisées. Ne pas inverser de nouveau les angles de la bibliothèque.
Un CSV à 3 colonnes est notre format angle_deg, distance_m, intensite.
MapTool : angle_deg,r_m,x_rel_m,y_rel_m ; distances en mètres, référence 0°.
La pose du commentaire Robot position est chargée et gardée comme référence.
Intensité absente dans MapTool : ce filtre est ignoré pour ces seuls scans.
Le bouton Importer accepte aussi les ZIP de CSV, sans extraction nécessaire.

GRILLE
Chaque rayon valide marque les cellules traversées libres et l'impact occupé.
Le gris désigne l'inconnu, le blanc le libre, le noir l'occupé.
Les log-odds s'accumulent (-0.4 libre, +0.85 occupé), bornées entre -4 et +4.
Une cellule reçoit au plus une mise à jour par scan ; un impact a priorité.
Le bouton recalcule depuis tous les scans cochés, pour éviter de compter deux fois
les mêmes relevés et pour tenir compte des changements de pose et de filtres.

SEGMENTS ET CARTE VECTORIELLE
Les discontinuités séparent les groupes de points. Un ajustement orthogonal
est découpé lorsque son erreur dépasse le seuil. Les groupes courts sont rejetés.
La carte accumule et fusionne les segments proches (angle ET distance).
Le laboratoire compare deux segments extraits. La carte raccourcit prudemment
les anciens segments contredits par au moins trois directions de rayons libres.

LOCALISATION
Un seul onglet Localisation réunit les trois références du TP : grille,
carte vectorielle et scan fixe. Choisir le mobile dans le panneau de droite.
Construire la grille ou la carte vectorielle sans y inclure ce mobile.
La pose actuelle sert de point de départ ; elle se règle dans Pose initiale.
La multi-résolution explore un voisinage de 1 m et 30° puis affine la pose.
L'affinement local robuste sert de deuxième méthode de comparaison.
Les filtres communs sont utilisés. Comparer l'aperçu avant/après puis Appliquer.
Une convergence locale n'est pas une garantie de position correcte.

ROBOT EN DIRECT
Connecter le PC au hotspot ScanAtlas, puis connecter l'application.
Nouvelle carte fixe l'origine au premier scan valide. Scans cochés Carte copie
une référence depuis Cartographie ; une recherche globale retrouve la pose.
Localisation seule poursuit le suivi sans enrichir les points, la grille ou les segments.
Points / Grille / Vectorielle sont trois affichages de la même carte.
Clavier AZERTY : Z S avancer / reculer, Q D gauche / droite, A E tourner (les flèches restent possibles).
Manette Xbox sous Windows : stick gauche et droit, B ou Espace pour arrêter.
Enregistrer la session directe conserve les scans clés ; Dossier des essais ouvre
le journal brut et la sauvegarde de secours. Démonstration utilise un robot simulé.

LIMITES
Environnement supposé fixe et plan. Les déplacements intra-tour ne sont pas
compensés : limiter la vitesse et vérifier l'alignement des murs.
Le firmware PWM demande un profil de câblage vérifié dans motor_config.h.
Les correspondances de roues restent à confirmer physiquement.
Pas encore de fermeture de boucle ni de navigation autonome. Vitres, mouvements et bruit
peuvent créer des erreurs. Des scans CSV fragmentaires peuvent être importés :
le nombre de points et l'étendue angulaire sont affichés pour contrôle.
Les retours nuls, trop faibles ou à portée maximale sont ignorés, sans libérer
les cellules du rayon. Les paramètres de segmentation demandent un réglage.
La carte vectorielle est une première méthode heuristique, pas une topologie parfaite.
L'onglet Localisation exporte les erreurs vraies sur les mêmes scans simulés.
La démo est SIMULÉE et ne remplace jamais les scans réels demandés au TP.
'''


AIDE = AIDE.replace('270°', f'{ANGLE_REFERENCE_DEFAUT:g}°')


SCANS_DETAIL = 25  # au-delà, le nuage est dessiné d'un seul bloc (voir dessiner_nuages)


class Atelier(InterfaceWifi, InterfaceTP, tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ScanAtlas · Cartographie et localisation')
        self.geometry('1440x940')
        self.minsize(1050, 720)
        self.scans, self.inclus, self.visibles = [], [], []
        self.grille, self.vecteurs = None, None
        self.scans_grille, self.parametres_grille = set(), None
        self.scans_vecteurs=set()
        self.segments = []
        self.manipulation = None
        self.annulations_pose = []
        self.resultat_localisation = None
        self.scans_localisation = []
        self.messages, self.annuler = queue.Queue(), threading.Event()
        self.travail = False
        self.vars = {}
        self.statut = tk.StringVar(value='Commence par la démonstration ou importe un scan CSV réel.')
        appliquer_theme(self)
        entete = ttk.Frame(self, padding=(16, 10))
        entete.pack(fill='x')
        from apparence import dessiner_logo
        dessiner_logo(entete).pack(side='left',padx=(0,10))
        ttk.Label(entete, text='ScanAtlas', style='Titre.TLabel').pack(side='left')
        ttk.Label(entete, text='   LD06 · Cartographie et localisation', style='SousTitre.TLabel').pack(side='left')
        ttk.Button(entete, text='Comprendre l’application', command=self.aide).pack(side='right')
        corps = self.corps = ttk.Panedwindow(self, orient='horizontal')
        corps.pack(fill='both', expand=True, padx=12)
        panneau = self.panneau_scans = ttk.Frame(corps, width=325)
        defilement = tk.Canvas(panneau, width=310, highlightthickness=0,background=FOND)
        ascenseur = ttk.Scrollbar(panneau, orient='vertical', command=defilement.yview)
        defilement.configure(yscrollcommand=ascenseur.set)
        ascenseur.pack(side='right', fill='y')
        defilement.pack(side='left', fill='both', expand=True)
        gauche = ttk.Frame(defilement, padding=8)
        fenetre = defilement.create_window((0,0), window=gauche, anchor='nw')
        gauche.bind('<Configure>', lambda e: defilement.configure(scrollregion=defilement.bbox('all')))
        defilement.bind('<Configure>', lambda e: defilement.itemconfigure(fenetre, width=e.width))
        droite = ttk.Frame(corps)
        corps.add(panneau, weight=0)
        corps.add(droite, weight=1)
        fichiers = ttk.LabelFrame(gauche, text='Scans', padding=8)
        fichiers.pack(fill='x')
        self.bouton(fichiers, 'Importer des CSV ou un ZIP…', self.importer)
        self.bouton(fichiers, 'Démonstration simulée (2 scans)', self.demo)
        self.liste = ttk.Treeview(fichiers, columns=('visible', 'inclure', 'points'), show='tree headings', height=7, selectmode='browse')
        self.liste.heading('#0', text='Scan')
        self.liste.column('#0', width=140)
        self.liste.heading('visible', text='Visible')
        self.liste.column('visible', width=50, anchor='center')
        self.liste.heading('inclure', text='Carte')
        self.liste.column('inclure', width=45, anchor='center')
        self.liste.heading('points', text='Pts')
        self.liste.column('points', width=45, anchor='center')
        self.liste.pack(fill='x', pady=6)
        self.liste.bind('<<TreeviewSelect>>', self.selection)
        self.liste.bind('<ButtonRelease-1>', self.clic_liste)
        ttk.Label(fichiers, text='Visible : afficher/masquer · Carte : inclure/exclure.',wraplength=285).pack(anchor='w')
        self.info = ttk.Label(fichiers, text='Aucun scan sélectionné', wraplength=285)
        self.info.pack(fill='x', pady=5)
        self.bouton(fichiers, 'Supprimer le scan sélectionné', self.supprimer)
        from apparence import Repliable
        section_pose=Repliable(gauche,'Pose du scan sélectionné',ouvert=False)
        section_pose.pack(fill='x',pady=8)
        pose=section_pose.contenu
        for cle, titre, valeur in [('x','Position x (m)',0), ('y','Position y (m)',0), ('orientation','Orientation (°)',0)]:
            self.champ(pose, cle, titre, valeur)
        self.bouton(pose, 'Appliquer la pose', self.appliquer_pose)
        self.bouton(pose, 'Annuler le dernier déplacement', self.annuler_pose)
        section_filtres=Repliable(gauche,'Filtres');section_filtres.pack(fill='x')
        filtres=section_filtres.contenu
        for cle, titre, valeur in [('mini','Distance min (m)',.05), ('maxi','Distance max exclue (m)',12), ('intensite','Intensité minimale',0)]:
            self.champ(filtres, cle, titre, valeur)
        self.bouton(filtres, 'Appliquer les filtres', self.filtrer)
        self.bouton(gauche, 'Enregistrer la session…', self.sauver_session)
        self.bouton(gauche, 'Ouvrir une session…', self.ouvrir_session)
        self.bouton(gauche, 'Exporter le scan sélectionné…', self.sauver_scan)
        self.onglets = ttk.Notebook(droite)
        self.onglets.pack(fill='both', expand=True)
        self.cadre_carto=ttk.Frame(self.onglets)
        self.onglets.add(self.cadre_carto,text='Cartographie')
        self.sous_onglets=ttk.Notebook(self.cadre_carto)
        self.sous_onglets.pack(fill='both',expand=True)
        self.onglets.bind('<<NotebookTabChanged>>',self.adapter_espace,add='+')
        self.axes, self.canvas = {}, {}
        self.preparer_variables_capture()
        for titre in ['Nuages', 'Grille', 'Segments', 'Carte vectorielle', 'TP Localisation', 'Acquisition USB', 'Robot Wi-Fi']:
            parent=self.onglets if titre in ('TP Localisation','Robot Wi-Fi') else self.sous_onglets
            cadre = ttk.Frame(parent, padding=8)
            parent.add(cadre, text={'TP Localisation':'Localisation','Acquisition USB':'Acquisition','Robot Wi-Fi':'Robot en direct'}.get(titre,titre))
            if titre == 'Robot Wi-Fi':
                self.interface_wifi(cadre)
                continue
            if titre == 'Acquisition USB':
                self.interface_usb(cadre)
                continue
            if titre == 'TP Localisation':
                colonne = ttk.Frame(cadre)
                colonne.pack(side='right', fill='y', padx=(12,0))
                barre = cadre_defilant(colonne)  # Capture + réglages ICP + comparaison : la colonne défile.
            else:
                barre = ttk.Frame(cadre)
                barre.pack(fill='x')
            if titre == 'TP Localisation':
                self.interface_tp(barre)
            elif titre == 'Grille':
                self.champ(barre, 'resolution', 'Résolution (m/cellule)', .05)
                self.bouton(barre, 'Créer depuis le scan sélectionné', self.creer_grille_selection)
                self.bouton(barre, 'Ajouter le scan sélectionné à la grille', self.ajouter_grille_selection)
                self.bouton(barre, 'Reconstruire depuis les scans cochés Carte', self.calculer_grille)
                self.bouton(barre, 'Exporter la grille (.npz)…', self.sauver_grille)
                ttk.Label(barre, text='Créer remplace la grille. Ajouter conserve les observations et étend les bornes.').pack(anchor='w')
            elif titre == 'Segments':
                for cle, label, v in [('saut','Rupture entre points (m)',.20), ('erreur','Erreur de droite max (m)',.04)]:
                    self.champ(barre, cle, label, v)
                self.bouton(barre, 'Extraire les segments des scans cochés Carte', self.calculer_segments)
                self.bouton(barre, 'Rétablir des seuils prudents', self.seuils_prudents)
                self.bouton(barre, 'Laboratoire : angle, fusion, intersection, découpage', self.laboratoire)
            elif titre == 'Carte vectorielle':
                for cle, label, v in [('angle_max','Écart angulaire max (°)',8), ('distance_max','Distance de fusion max (m)',.12)]:
                    self.champ(barre, cle, label, v)
                self.bouton(barre, 'Construire avec les scans cochés', self.calculer_vecteurs)
                self.bouton(barre, 'Exporter les segments (.csv)…', self.sauver_vecteurs)
            else:
                ttk.Label(barre, text='Une couleur par scan · repère global en mètres · flèches = poses').pack(anchor='w')
                self.mode_souris = tk.StringVar(value='naviguer')
                modes = ttk.Frame(barre)
                modes.pack(fill='x')
                for valeur, texte in [('naviguer','Naviguer'), ('deplacer','Déplacer le scan'), ('tourner','Tourner le scan')]:
                    ttk.Radiobutton(modes, text=texte, variable=self.mode_souris,
                                    value=valeur, command=self.annuler_geste).pack(side='left', padx=4)
                ttk.Label(barre, text='Sélectionne un scan dans la liste, puis glisse avec le clic gauche. Échap annule.\nRotation autour de sa flèche. Désactive Pan/Zoom pour modifier le scan.').pack(anchor='w')
            fig = Figure(figsize=(7,5), dpi=100, constrained_layout=True)
            self.axes[titre] = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, cadre)
            barre_navigation=habiller_barre(NavigationToolbar2Tk(canvas,cadre,pack_toolbar=False))
            barre_navigation.pack(side='bottom',fill='x')
            canvas.get_tk_widget().pack(fill='both',expand=True)
            barre_navigation.update()
            self.canvas[titre] = canvas
            if titre == 'Nuages':
                self.manipulation = ManipulationScan(canvas, self.axes[titre], self.mode_souris.get,
                    self.scan_manipulable, self.apercu_pose, self.fin_geste)
                canvas.get_tk_widget().bind('<Button-1>', lambda e: e.widget.focus_set(), add='+')
        ttk.Label(self, textvariable=self.statut, padding=(16, 8), wraplength=1250).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW', self.fermer)
        self.actualiser()
        self.after(100, self.poll)

    def adapter_espace(self,event=None):
        if not hasattr(self,'wifi_cadre'):return
        robot=str(self.onglets.select())!=str(self.cadre_carto)
        present=str(self.panneau_scans) in self.corps.panes()
        if robot and present:self.corps.forget(self.panneau_scans)
        elif not robot and not present:self.corps.insert(0,self.panneau_scans,weight=0)

    def bouton(self, parent, texte, action):
        b = ttk.Button(parent, text=texte, command=lambda: self.proteger(action))
        b.pack(fill='x', pady=2)
        return b

    def champ(self, parent, cle, titre, valeur):
        ensemble=ttk.Frame(parent)
        ensemble.pack(fill='x',pady=2)
        ligne = ttk.Frame(ensemble)
        ligne.pack(fill='x', pady=2)
        ttk.Label(ligne,text=titre,wraplength=185).pack(side='left')
        if cle not in self.vars:  # Une variable déjà créée est partagée avec les autres onglets.
            self.vars[cle] = tk.StringVar(value=str(valeur))
        ttk.Entry(ligne, textvariable=self.vars[cle], width=8).pack(side='right')
        if cle in PLAGES:
            curseur(ensemble,self.vars[cle],*PLAGES[cle])

    def preparer_variables_capture(self):
        """Variables de capture et d'ICP créées une fois, partagées par Acquisition et Localisation."""
        defauts = dict(baud=115200, quantite=1, auto_icp='0', icp_methode=METHODE_GLOBALE, icp_distance=.5,
                       icp_iterations=80, icp_fenetre_xy=1., icp_fenetre_angle=30.,
                       loc_methode='Recherche large + ICP')
        for cle, valeur in defauts.items():
            self.vars.setdefault(cle, tk.StringVar(value=str(valeur)))
        self.capture_source = tk.StringVar(value='USB')
        self.capture_hote = tk.StringVar(value='192.168.4.1')
        self.port = tk.StringVar()
        self.capture_depuis_localisation = False

    def informer_capture(self, texte):
        """Message de capture visible dans Acquisition et dans Localisation."""
        for nom in ('info_capture', 'info_tp'):
            cible = getattr(self, nom, None)
            if cible is not None:
                cible.configure(text=texte)

    def nombre(self, cle):
        try:
            v = float(self.vars[cle].get().replace(',', '.'))
            if not np.isfinite(v):
                raise ValueError()
            return v
        except ValueError:
            raise ValueError(f'Valeur numérique invalide : {cle}')

    def proteger(self, action):
        try:
            action()
        except Exception as exc:
            messagebox.showerror('À vérifier', str(exc), parent=self)
            self.statut.set(str(exc))

    def filtres(self):
        d = {k:self.nombre(k) for k in ['mini','maxi','intensite']}
        if not 0 <= d['mini'] < d['maxi'] or not 0 <= d['intensite'] <= 255:
            raise ValueError('Il faut 0 ≤ min < max et une intensité entre 0 et 255.')
        return d

    def options_segments(self):
        d = dict(self.filtres(), saut=self.nombre('saut'), erreur=self.nombre('erreur'))
        if d['saut'] <= 0 or d['erreur'] <= 0:
            raise ValueError('Les seuils de segmentation doivent être positifs.')
        return d

    def choisis(self):
        scans = [s for s, oui in zip(self.scans, self.inclus) if oui]
        if not scans:
            raise ValueError('Inclure au moins un scan dans la colonne Carte.')
        return scans

    def indice(self):
        choix = self.liste.selection()
        if not choix:
            raise ValueError('Sélectionne un scan dans la liste.')
        return int(choix[0])

    def actualiser(self, selection=None):
        ancien = self.liste.selection()
        self.liste.delete(*self.liste.get_children())
        for i,s in enumerate(self.scans):
            self.liste.insert('', 'end', iid=str(i), text=s.nom, values=('✓' if self.visibles[i] else '—', '✓' if self.inclus[i] else '—', len(s.mesures)))
        if self.scans:
            i = min(selection if selection is not None else int(ancien[0]) if ancien else 0, len(self.scans)-1)
            self.liste.selection_set(str(i))
            self.selection()
        else:
            self.info.configure(text='Aucun scan sélectionné')
        self.dessiner_nuages()
        self.actualiser_choix_localisation()
        if hasattr(self,'choix_reference_tp'): self.actualiser_choix_tp()

    def selection(self, event=None):
        self.annuler_geste()
        if not self.liste.selection():
            return
        s = self.scans[self.indice()]
        for k, v in zip(['x','y','orientation'], s.pose):
            self.vars[k].set(str(round(v,5)))
        d = diagnostic_scan(s.mesures)
        precision = '\nIntensité absente : ce filtre est ignoré.' if not s.intensite_disponible else ''
        if s.suivi_recalage:
            precision += '\nAuto : '+str(s.suivi_recalage.get('message', ''))
        self.info.configure(text=f"{s.source}\n{d['points']} points · étendue ≈ {d['etendue']:.1f}°\n{d['etat']} · écart max {d['pas_max']:.1f}°{precision}")

    def clic_liste(self, event):
        self.annuler_geste()
        item = self.liste.identify_row(event.y)
        colonne = self.liste.identify_column(event.x)
        if item and colonne in ('#1', '#2'):
            i = int(item)
            if colonne == '#1':
                self.visibles[i] = not self.visibles[i]
                self.liste.set(item, 'visible', '✓' if self.visibles[i] else '—')
                self.dessiner_nuages()
                self.statut.set('Visibilité modifiée. La participation aux cartes reste inchangée.')
            else:
                self.inclus[i] = not self.inclus[i]
                self.invalider()
                self.actualiser(i)

    def ajouter(self, scans):
        self.annuler_geste()
        self.scans.extend(scans)
        self.inclus.extend([True]*len(scans))
        self.visibles.extend([True]*len(scans))
        self.invalider(conserver_grille=True)
        self.actualiser(len(self.scans)-len(scans))
        self.statut.set(f'{len(scans)} scan(s) ajouté(s). Vérifie la source, les points et l’étendue angulaire.')

    def importer(self):
        fichiers = filedialog.askopenfilenames(filetypes=[('Scans CSV ou ZIP','*.csv *.zip'), ('Scans CSV','*.csv'), ('Archives ZIP','*.zip'), ('Tous','*.*')])
        nouveaux = []
        for f in fichiers:
            nouveaux.extend(lire_csv(f))
        if nouveaux:
            self.ajouter(nouveaux)
            n = sum('MapTool' in s.source for s in nouveaux)
            if n:
                self.statut.set(f'{n} scan(s) MapTool SIMULÉS importés. Poses du fichier chargées si présentes ; intensité non fournie, filtre ignoré pour ces scans.')

    def demo(self):
        self.ajouter(demonstration())
        self.statut.set('Deux scans SIMULÉS ajoutés. Ils ne remplacent pas tes propres acquisitions réelles.')

    def supprimer(self):
        self.annuler_geste()
        i = self.indice()
        self.scans.pop(i)
        self.inclus.pop(i)
        self.visibles.pop(i)
        self.invalider()
        self.actualiser()

    def annuler_geste(self):
        if self.manipulation is not None:
            self.manipulation.annuler()

    def scan_manipulable(self):
        if not self.liste.selection():
            self.statut.set('Sélectionne un scan dans la liste avant de le déplacer.')
            return None
        i = self.indice()
        if not self.visibles[i]:
            self.statut.set('Réaffiche ce scan dans Visible avant de le déplacer.')
            return None
        return self.scans[i]

    def apercu_pose(self, scan, limites):
        for cle, valeur in zip(['x','y','orientation'], scan.pose):
            self.vars[cle].set(f'{valeur:.5f}')
        self.dessiner_nuages(limites)

    def fin_geste(self):
        scan = self.scans[self.indice()]
        ancienne=getattr(self.manipulation,'derniere_pose_avant',None)
        if ancienne is not None:Atelier.memoriser_pose(self,scan,ancienne)
        scan.suivi_recalage = None
        self.invalider(conserver_grille=id(scan) not in self.scans_grille)
        self.statut.set('Pose modifiée à la souris. Recalcule les cartes, puis enregistre la session.')

    def memoriser_pose(self,scan,pose=None):
        historique=getattr(self,'annulations_pose',[])
        historique.append((scan,list(scan.pose if pose is None else pose),deepcopy(scan.suivi_recalage)))
        self.annulations_pose=historique[-30:]

    def annuler_pose(self):
        self.annuler_geste()
        historique=getattr(self,'annulations_pose',[])
        while historique:
            scan,pose,suivi=historique.pop()
            if any(scan is s for s in self.scans):
                scan.pose=pose;scan.suivi_recalage=suivi
                self.invalider(conserver_grille=id(scan) not in self.scans_grille)
                self.actualiser(next(i for i,s in enumerate(self.scans) if s is scan))
                self.statut.set('Dernière modification de pose annulée ; recalculer les cartes concernées.')
                return
        self.statut.set('Aucune modification de pose à annuler.')

    def appliquer_pose(self):
        self.annuler_geste()
        s = self.scans[self.indice()]
        nouvelle_pose = [self.nombre(k) for k in ['x','y','orientation']]
        Atelier.memoriser_pose(self,s)
        s.pose = nouvelle_pose
        s.suivi_recalage = None
        self.invalider(conserver_grille=id(s) not in self.scans_grille)
        self.dessiner_nuages()
        self.statut.set('Pose appliquée. Recalcule les cartes pour utiliser cette nouvelle pose.')

    def filtrer(self):
        self.filtres()
        self.invalider()
        self.dessiner_nuages()
        self.statut.set('Filtres appliqués à l’affichage ; les données originales sont conservées.')

    def invalider(self, conserver_grille=False):
        self.resultat_localisation = None
        self.resultat_tp=None
        self.scans_vecteurs=set()
        if 'TP Localisation' in self.axes: self.effacer('TP Localisation','Choisir une référence et localiser le scan mobile')
        if 'Localisation' in self.axes:
            self.effacer('Localisation', 'Choisir deux scans et lancer le recalage ICP')
        self.vecteurs, self.segments = None, []
        if not conserver_grille:
            self.grille = None
            self.scans_grille, self.parametres_grille = set(), None
            self.effacer('Grille', 'À calculer avec les paramètres actuels')
        for t in ['Segments','Carte vectorielle']:
            self.effacer(t, 'À calculer avec les paramètres actuels')

    def effacer(self, titre, message):
        ax = self.axes[titre]
        ax.clear()
        ax.set_title(message)
        self.fin_dessin(titre)

    def fin_dessin(self, titre):
        ax = self.axes[titre]
        ax.set_aspect('equal', adjustable='box')
        ax.set_xlabel('x (m)')
        ax.set_ylabel('y (m)')
        ax.grid(True, alpha=.15)
        self.canvas[titre].draw_idle()

    def dessiner_nuages(self, limites=None):
        ax = self.axes['Nuages']
        ax.clear()
        try:
            filtres = self.filtres()
        except ValueError:
            filtres = dict(mini=.05, maxi=12., intensite=0)
        from matplotlib import colormaps
        nombre = max(len(self.scans), 1)
        visibles = [i for i in range(len(self.scans)) if self.visibles[i]]
        if len(visibles) <= SCANS_DETAIL:
            for i in visibles:
                s = self.scans[i]
                couleur = colormaps['hsv'](i/nombre*.85)
                pts = s.points()[mesures_valides(s, **filtres)]
                ax.scatter(pts[:,0], pts[:,1], s=5, color=couleur, label=s.nom)
                a = np.deg2rad(s.pose[2])
                ax.plot(*s.pose[:2], marker='x', color=couleur)
                ax.arrow(*s.pose[:2], .3*np.cos(a), .3*np.sin(a), width=.012, color=couleur)
            if visibles:
                ax.legend(fontsize=8, loc='upper right')
            ax.set_title('Scans visibles dans leur pose — coordonnées recalculées depuis angle et distance')
        else:
            # Beaucoup de scans (cartographie en direct, import d'une session) : un seul nuage, une seule
            # flèche par scan et pas de légende. Un artiste par scan + une légende de 150 lignes coûtaient
            # plus d'une seconde à chaque affichage de l'onglet.
            blocs, couleurs, poses = [], [], []
            for i in visibles:
                s = self.scans[i]
                pts = s.points()[mesures_valides(s, **filtres)]
                blocs.append(pts)
                couleurs.append(np.repeat([colormaps['hsv'](i/nombre*.85)], len(pts), axis=0))
                poses.append((s.pose, colormaps['hsv'](i/nombre*.85)))
            tous = np.vstack(blocs) if blocs else np.empty((0, 2))
            if len(tous):
                # Un point par case de 3 cm (le plus récent l'emporte) : l'écran ne montre pas davantage et
                # Matplotlib dessine chaque point séparément (67 000 points ≈ 1 s).
                couleurs = np.vstack(couleurs)[::-1]; tous = tous[::-1]
                cases = np.floor(tous/0.03).astype(np.int64)
                _, garde = np.unique(cases[:,0]*1_000_003+cases[:,1], return_index=True)
                tous, couleurs = tous[garde], couleurs[garde]
                ax.scatter(tous[:,0], tous[:,1], s=3, c=couleurs, rasterized=True)
            xy = np.array([p[0][:2] for p in poses]); a = np.deg2rad([p[0][2] for p in poses])
            ax.quiver(xy[:,0], xy[:,1], .3*np.cos(a), .3*np.sin(a), color=[p[1] for p in poses], angles='xy',
                      scale_units='xy', scale=1, width=.003, headwidth=3)
            ax.set_title(f'{len(visibles)} scans visibles dans leur pose (légende masquée au-delà de {SCANS_DETAIL})')
        if limites is not None:
            ax.set_xlim(limites[0])
            ax.set_ylim(limites[1])
        self.fin_dessin('Nuages')

    def verifier_scans_grille(self, scans):
        remarques = []
        for scan in scans:
            d = diagnostic_scan(scan.mesures)
            if not mesures_valides(scan, **self.filtres()).any():
                raise ValueError(f'{scan.nom} : aucune mesure utilisable après filtrage.')
            if not d['tour_plausible']:
                remarques.append(f"{d['etat']} ({d['etendue']:.1f}°), conservé")
        if remarques:
            return 'Information : ' + ' ; '.join(remarques) + '. Une pose unique est appliquée à chaque bloc.'
        return ''

    def creer_grille_selection(self):
        self.annuler_geste()
        scan = self.scans[self.indice()]
        remarque = self.verifier_scans_grille([scan])
        opts, resolution = self.filtres(), self.nombre('resolution')
        grille = Grille.depuis_scan(scan, resolution, **opts)
        self.grille = grille
        self.scans_grille = {id(scan)}
        self.parametres_grille = (resolution, opts)
        self.dessiner_grille()
        self.statut.set('Grille créée depuis le scan sélectionné et sa pose. ' + remarque)

    def ajouter_grille_selection(self):
        self.annuler_geste()
        if self.grille is None:
            raise ValueError('Crée d’abord une grille depuis un scan ou reconstruis les scans cochés.')
        opts, resolution = self.filtres(), self.nombre('resolution')
        if self.parametres_grille != (resolution, opts):
            raise ValueError('Résolution ou filtres modifiés : reconstruis la grille avant de continuer.')
        scan = self.scans[self.indice()]
        if id(scan) in self.scans_grille:
            self.statut.set('Ce scan est déjà intégré : aucune observation comptée deux fois.')
            return
        remarque = self.verifier_scans_grille([scan])
        self.grille.mettre_a_jour(scan, **opts)
        self.scans_grille.add(id(scan))
        self.dessiner_grille()
        self.statut.set(f'Grille mise à jour : {len(self.scans_grille)} scans intégrés, anciennes observations conservées. ' + remarque)

    def calculer_grille(self):
        self.annuler_geste()
        scans, opts = self.choisis(), self.filtres()
        remarque = self.verifier_scans_grille(scans)
        resolution = self.nombre('resolution')
        g = Grille.creer(scans, resolution, **opts)
        for s in scans:
            g.mettre_a_jour(s, **opts)
        self.grille = g
        self.scans_grille = {id(s) for s in scans}
        self.parametres_grille = (resolution, opts)
        self.dessiner_grille()
        self.statut.set(f'Grille reconstruite depuis {len(scans)} scans ; résolution {g.resolution:g} m/cellule. ' + remarque)

    def dessiner_grille(self):
        g = self.grille
        ax = self.axes['Grille']
        ax.clear()
        p = g.probabilites()
        image = np.repeat((1-p)[...,None], 3, axis=2)
        image[~g.observe] = [.55,.63,.70]
        ny,nx = p.shape
        x,y = g.origine
        ax.imshow(image, origin='lower', extent=[x,x+nx*g.resolution,y,y+ny*g.resolution], interpolation='nearest')
        ax.set_title(f'Inconnu : bleu-gris · libre : blanc · occupé : noir | {nx} × {ny} cellules')
        self.fin_dessin('Grille')


    def tracer_segments(self, titre, segments, fond=None, couleurs=None):
        ax = self.axes[titre]
        ax.clear()
        if fond is not None:
            ax.scatter(fond[:,0], fond[:,1], s=3, color='#bbc4cf')
        for i,s in enumerate(segments):
            ax.plot(s[:,0], s[:,1], linewidth=2, **({'color':couleurs[i]} if couleurs is not None else {}))
            if titre == 'Segments':
                ax.text(*s.mean(axis=0), str(i), fontsize=9)
        ax.set_title(f'{len(segments)} segments · longueurs minimales 0,15 m · au moins 6 points/groupe')
        self.fin_dessin(titre)

    def seuils_prudents(self):
        for cle, valeur in [('saut',.25),('erreur',.05),('angle_max',8),('distance_max',.12)]:
            self.vars[cle].set(str(valeur))
        self.segments, self.vecteurs = [], None
        self.effacer('Segments', 'Recalculer les segments avec les nouveaux seuils')
        self.effacer('Carte vectorielle', 'Reconstruire avec les nouveaux seuils')
        self.statut.set('Seuils rétablis : rupture 0,25 m ; erreur 0,05 m ; fusion 8° et 0,12 m.')

    def calculer_segments(self):
        scans = self.choisis()
        self.segments, self.origines_segments = extraire_multiscans(scans, **self.options_segments())
        fonds = [s.points()[mesures_valides(s, **self.filtres())] for s in scans]
        fond = np.vstack(fonds)
        from matplotlib import colormaps
        palette = {id(s): colormaps['hsv'](i/max(len(self.scans),1)*.85) for i,s in enumerate(self.scans)}
        couleurs = [palette[id(scans[i])] for i in self.origines_segments]
        self.tracer_segments('Segments', self.segments, fond, couleurs)
        self.axes['Segments'].set_title(f'{len(self.segments)} segments extraits de {len(scans)} scans cochés Carte · avant fusion')
        self.canvas['Segments'].draw_idle()
        self.statut.set(f'Segments de {len(scans)} scans, chacun dans sa pose ; aucun lien entre deux scans. Numéros utilisables au laboratoire.')

    def calculer_vecteurs(self):
        a, d = self.nombre('angle_max'), self.nombre('distance_max')
        if not 0 <= a <= 90 or d < 0:
            raise ValueError('Angle entre 0 et 90°, distance positive ou nulle.')
        scans = self.choisis()
        self.vecteurs, bilan = carte_vectorielle(scans, a, d, retour_details=True, **self.options_segments())
        self.scans_vecteurs={id(s) for s in scans}
        fonds = [s.points()[mesures_valides(s, **self.filtres())] for s in scans]
        self.tracer_segments('Carte vectorielle', self.vecteurs, np.vstack(fonds))
        self.axes['Carte vectorielle'].set_title(f"{len(self.vecteurs)} segments de carte · {len(scans)} scans · {bilan['fusions']} fusions · {bilan['coupes']} coupes")
        self.canvas['Carte vectorielle'].draw_idle()
        self.statut.set('Carte : extraction par scan, fusion contrôlée sur les points sources et raccourcissement après au moins trois rayons libres distincts.')

    def laboratoire(self):
        if len(self.segments) < 2:
            raise ValueError('Extrais au moins deux segments auparavant.')
        win = tk.Toplevel(self)
        win.title('Laboratoire de deux segments')
        win.geometry('650x390')
        ttk.Label(win, text='Choisis les numéros visibles sur le graphique. A est le segment à couper.', wraplength=610).pack(pady=10)
        av,bv = tk.StringVar(value='0'),tk.StringVar(value='1')
        for label,v in [('Segment A',av), ('Segment B',bv)]:
            ttk.Label(win,text=label).pack()
            ttk.Combobox(win,textvariable=v,values=list(range(len(self.segments))),state='readonly').pack()
        texte = tk.Text(win,height=11,wrap='word')
        texte.pack(fill='both',expand=True,padx=10,pady=8)
        def analyser():
            a,b = self.segments[int(av.get())], self.segments[int(bv.get())]
            am,dm = self.nombre('angle_max'),self.nombre('distance_max')
            p = intersection(a,b)
            coupe = decouper(a,b)
            res = f'Tolérance numérique : {EPS:g} m\nAngle non orienté : {angle_segments(a,b):.3f}°\n'
            res += f'Proches (≤{am:g}°, ≤{dm:g} m) : {proches(a,b,am,dm)}\n'
            res += f'Intersection unique sur les deux : {p if p is not None else "aucune (ou colinéaires)"}\n'
            res += f'A après découpage :\n{np.round(coupe,5)}\n'
            if proches(a,b,am,dm):
                res += f'Fusion proposée :\n{np.round(fusionner(a,b,am,dm),5)}\n'
            res += 'Égalité des côtés : conservation du côté contenant A[0].\nCette analyse ne modifie pas la carte.'
            texte.delete('1.0','end')
            texte.insert('1.0',res)
        ttk.Button(win,text='Comparer / calculer',command=lambda:self.proteger(analyser)).pack(pady=5)
        analyser()

    def sauver_scan(self):
        s = self.scans[self.indice()]
        p = filedialog.asksaveasfilename(defaultextension='.csv', initialfile='scan_polaire.csv')
        if p:
            exporter_scan(s,p)
            self.statut.set('Scan polaire exporté : angle_deg, distance_m, intensite. Pose conservée dans la session JSON.')

    def sauver_grille(self):
        if self.grille is None:
            raise ValueError('Calcule d’abord la grille.')
        p = filedialog.asksaveasfilename(defaultextension='.npz')
        if p:
            g = self.grille
            np.savez_compressed(p, origine=g.origine, resolution=g.resolution, log_odds=g.log_odds, observe=g.observe, probabilite=g.probabilites())
            self.statut.set('Grille exportée avec son origine, sa résolution et son masque de cellules observées.')

    def sauver_vecteurs(self):
        if self.vecteurs is None:
            raise ValueError('Calcule d’abord la carte vectorielle.')
        p = filedialog.asksaveasfilename(defaultextension='.csv')
        if p:
            with open(p,'w',newline='',encoding='utf-8') as f:
                w=csv.writer(f)
                w.writerow(['x1_m','y1_m','x2_m','y2_m'])
                w.writerows(s.ravel() for s in self.vecteurs)
            self.statut.set('Segments de la carte exportés en mètres.')

    def sauver_session(self):
        self.annuler_geste()
        p = filedialog.asksaveasfilename(defaultextension='.json',initialfile='session_ld06.json')
        if p:
            contenu = dict(version=2, parametres={k:v.get() for k,v in self.vars.items() if k not in ['x','y','orientation','reference']},
                           scans=[dict(nom=s.nom,mesures=s.mesures.tolist(),pose=s.pose,source=s.source,
                                       angle_reference=s.angle_reference,inclus=oui,visible=visible,
                                       intensite_disponible=s.intensite_disponible,pose_connue=s.pose_connue,
                                       suivi_recalage=s.suivi_recalage)
                                  for s,oui,visible in zip(self.scans,self.inclus,self.visibles)])
            Path(p).write_text(json.dumps(contenu,ensure_ascii=False,indent=2),encoding='utf-8')
            self.statut.set('Session enregistrée : mesures originales, sources, poses et paramètres. Les cartes se recalculent.')

    def ouvrir_session(self):
        self.annuler_geste()
        p = filedialog.askopenfilename(filetypes=[('Session','*.json')])
        if not p:
            return
        if self.scans and not messagebox.askyesno('Ouvrir une session', 'Remplacer la session affichée ? Enregistre-la avant si nécessaire.'):
            return
        data = json.loads(Path(p).read_text(encoding='utf-8'))
        if data.get('version') not in (1, 2):
            raise ValueError('Version de session inconnue.')
        scans, inclus, visibles = [], [], []
        for d in data['scans']:
            m,pose = np.asarray(d['mesures'],float),np.asarray(d['pose'],float)
            if m.ndim != 2 or m.shape[1] != 3 or len(m)==0 or pose.shape != (3,) or not np.isfinite(m).all() or not np.isfinite(pose).all():
                raise ValueError('Mesures ou pose invalides.')
            if (m[:,1] < 0).any() or ((m[:,2]<0)|(m[:,2]>255)).any():
                raise ValueError('Distance ou intensité invalide.')
            # Les scans réels utilisent toujours l'ancien 270° comme zéro.
            # Les exemples synthétiques sont construits dans un repère neutre.
            reference = 0. if 'SIMULATION' in str(d['source']) else ANGLE_REFERENCE_DEFAUT
            connue = d.get('pose_connue')
            if connue is not None:
                connue = np.asarray(connue, float)
                if connue.shape != (3,) or not np.isfinite(connue).all():
                    raise ValueError('Pose connue invalide dans la session.')
                connue = connue.tolist()
            scans.append(Scan(str(d['nom']),m,pose.tolist(),str(d['source']),reference,
                              bool(d.get('intensite_disponible', 'MapTool' not in str(d['source']))), connue))
            suivi = d.get('suivi_recalage')
            if suivi is not None and (not isinstance(suivi, dict) or not isinstance(suivi.get('valide'), bool)):
                raise ValueError('Suivi de recalage automatique invalide.')
            if suivi is not None and 'groupe' in suivi and (isinstance(suivi['groupe'],bool) or not isinstance(suivi['groupe'],int) or suivi['groupe'] < -1):
                raise ValueError('Identifiant de groupe invalide dans la session.')
            scans[-1].suivi_recalage = suivi
            inclus.append(bool(d['inclus']))
            visibles.append(bool(d.get('visible', d['inclus'])))
        parametres = data.get('parametres',{})
        nouveaux = {}
        for k in ['mini','maxi','intensite','resolution','saut','erreur','angle_max','distance_max']:
            v = float(str(parametres.get(k,self.vars[k].get())).replace(',','.'))
            if not np.isfinite(v):
                raise ValueError('Paramètres non finis.')
            nouveaux[k]=v
        if not (0 <= nouveaux['mini'] < nouveaux['maxi'] and 0 <= nouveaux['intensite'] <= 255 and
                all(nouveaux[k]>0 for k in ['resolution','saut','erreur']) and 0<=nouveaux['angle_max']<=90 and nouveaux['distance_max']>=0):
            raise ValueError('Paramètres de session hors limites.')
        for k, defaut in [('icp_distance', .5), ('icp_iterations', 80), ('icp_fenetre_xy', 1.), ('icp_fenetre_angle', 30.)]:
            if k in self.vars:
                v = float(str(parametres.get(k, defaut)).replace(',', '.'))
                if not np.isfinite(v) or v <= 0 or (k == 'icp_iterations' and (v != int(v) or v > 300)):
                    raise ValueError('Paramètres ICP de session invalides.')
                if (k == 'icp_fenetre_xy' and v > 3) or (k == 'icp_fenetre_angle' and v > 90):
                    raise ValueError('Fenêtre de recherche limitée à 3 m et 90°.')
                nouveaux[k] = v
        methode = parametres.get('icp_methode', METHODE_GLOBALE)
        if methode == 'Recherche large + ICP': methode = METHODE_GLOBALE
        if methode not in ('ICP local', 'Recherche large + ICP', METHODE_GLOBALE):
            raise ValueError('Méthode de localisation inconnue dans la session.')
        tp_type=parametres.get('tp_reference','Grille');tp_methode=parametres.get('tp_methode',TP_MULTI)
        if tp_type not in ('Grille','Carte vectorielle','Scan') or tp_methode not in (TP_LOCALE,TP_MULTI):
            raise ValueError('Paramètres de localisation TP invalides.')
        auto = str(parametres.get('auto_icp', '0'))
        if auto not in ('0', '1'):
            raise ValueError('Option de recalage automatique invalide.')
        self.scans,self.inclus,self.visibles=scans,inclus,visibles
        for k,v in nouveaux.items():
            self.vars[k].set(str(v))
        if 'icp_methode' in self.vars:
            self.vars['icp_methode'].set(methode)
            if hasattr(self,'reglages_fenetres'):
                if methode == 'Recherche large + ICP': self.reglages_fenetres.pack(before=self.reglages_precision,fill='x')
                else: self.reglages_fenetres.pack_forget()
        if 'auto_icp' in self.vars:
            self.vars['auto_icp'].set(auto)
        if 'tp_reference' in self.vars: self.vars['tp_reference'].set(tp_type)
        if 'tp_methode' in self.vars: self.vars['tp_methode'].set(tp_methode)
        self.invalider()
        self.actualiser()
        self.statut.set('Session ouverte. Recalcule les cartes avec les boutons dédiés.')

    def interface_localisation(self, cadre):
        ttk.Label(cadre, text='Superposition automatique entre scans').pack(anchor='w')
        ligne = ttk.Frame(cadre)
        ligne.pack(fill='x', pady=3)
        self.choix_reference = ttk.Combobox(ligne, state='readonly', width=30)
        self.choix_mobile = ttk.Combobox(ligne, state='readonly', width=30)
        for label, choix in [('Référence fixe', self.choix_reference), ('Scan à déplacer', self.choix_mobile)]:
            ttk.Label(ligne, text=label).pack(side='left', padx=3)
            choix.pack(side='left', fill='x', expand=True)
            choix.bind('<<ComboboxSelected>>', lambda e: self.proteger(self.apercu_localisation))
        methodes = ttk.Frame(cadre)
        methodes.pack(fill='x', pady=3)
        ttk.Label(methodes, text='Méthode').pack(side='left')
        self.vars['icp_methode'] = tk.StringVar(value=METHODE_GLOBALE)
        choix_methode = ttk.Combobox(methodes, textvariable=self.vars['icp_methode'], state='readonly',
                     values=[METHODE_GLOBALE, 'Recherche large + ICP', 'ICP local'], width=42)
        choix_methode.pack(side='right')
        self.reglages_fenetres = ttk.Frame(cadre)
        choix_methode.bind('<<ComboboxSelected>>', lambda e: self.reglages_fenetres.pack(before=self.reglages_precision, fill='x')
            if self.vars['icp_methode'].get() == 'Recherche large + ICP' else self.reglages_fenetres.pack_forget())
        self.champ(self.reglages_fenetres, 'icp_fenetre_xy', 'Recherche large : ± déplacement en x et y (m)', 1.)
        self.champ(self.reglages_fenetres, 'icp_fenetre_angle', 'Recherche large : ± orientation (°)', 30.)
        self.reglages_precision = ttk.Frame(cadre)
        self.reglages_precision.pack(fill='x')
        self.champ(self.reglages_precision, 'icp_distance', 'Distance maximale d’appariement ICP (m)', .5)
        self.champ(self.reglages_precision, 'icp_iterations', 'Nombre maximal d’itérations', 80)
        ttk.Label(cadre, text='Mode global : toute la carte et 360°, sans fenêtre autour de la pose initiale.\nConcordance = points à moins de 12 cm (ou demi-distance ICP si plus petite), seuil 65 %.\nUne concordance élevée peut rester ambiguë. Les scans sans raccordement forment des groupes séparés.').pack(anchor='w')
        actions = ttk.Frame(cadre)
        actions.pack(fill='x')
        for texte, action in [('Voir avant', self.apercu_localisation), ('Localiser', self.lancer_localisation),
                              ('Appliquer la pose trouvée', self.appliquer_localisation), ('Annuler le calcul', self.annuler_calcul)]:
            ttk.Button(actions, text=texte, command=lambda a=action: self.proteger(a)).pack(side='left', padx=2, pady=4)
        ttk.Button(cadre, text='Assembler tous les scans — carte cumulée et groupes en attente',
                   command=lambda: self.proteger(self.lancer_lot)).pack(fill='x', pady=4)
        ttk.Button(cadre, text='Annuler les poses du dernier lot appliqué',
                   command=lambda: self.proteger(self.annuler_lot)).pack(fill='x')
        ttk.Label(cadre, text='Global : premier scan fixe, tous les scans raccordés enrichissent la carte. '
            'Groupes en attente conservés et masqués jusqu’au raccordement.').pack(anchor='w')
        self.info_localisation = ttk.Label(cadre, text='La référence reste fixe. Les scans doivent voir une zone commune.', wraplength=850)
        self.info_localisation.pack(anchor='w')

    def annuler_calcul(self):
        self.annuler.set()

    def actualiser_choix_localisation(self):
        if not hasattr(self, 'choix_reference'):
            return
        anciens = getattr(self, 'scans_localisation', [])
        choix = [self.choix_reference, self.choix_mobile]
        selections = [anciens[c.current()] if 0 <= c.current() < len(anciens) else None for c in choix]
        self.scans_localisation = list(self.scans)
        labels = [f'{i+1} · {s.nom}' for i, s in enumerate(self.scans)]
        for n, (c, selection) in enumerate(zip(choix, selections)):
            c['values'] = labels
            if labels:
                indice = next((i for i, s in enumerate(self.scans) if s is selection), min(n, len(labels)-1))
                c.current(indice)
            else:
                c.set('')

    def paire_localisation(self):
        indices = [self.choix_reference.current(), self.choix_mobile.current()]
        if any(i < 0 or i >= len(self.scans_localisation) for i in indices):
            raise ValueError('Importer au moins deux scans, puis choisir référence et mobile.')
        reference, mobile = [self.scans_localisation[i] for i in indices]
        if reference is mobile:
            raise ValueError('La référence et le mobile doivent être deux scans différents.')
        return reference, mobile

    def apercu_localisation(self):
        reference, mobile = self.paire_localisation()
        filtres = self.filtres()
        self.resultat_localisation = None
        self.dessiner_localisation(points_filtres(reference, filtres),
            points_filtres(mobile, filtres, locaux=True), mobile.pose)
        self.info_localisation.configure(text='Avant recalage. Le mobile utilise sa pose actuelle ; aucune mesure n’est modifiée.')

    def dessiner_localisation(self, reference, locaux, avant, apres=None):
        ax = self.axes['Localisation']
        ax.clear()
        ax.scatter(reference[:, 0], reference[:, 1], s=7, c='#465b70', label='Référence fixe')
        points = transformer(locaux, avant)
        ax.scatter(points[:, 0], points[:, 1], s=8, c='#d88422', alpha=.5, label='Mobile avant')
        if apres is not None:
            points = transformer(locaux, apres)
            ax.scatter(points[:, 0], points[:, 1], s=8, c='#138961', label='Mobile après (aperçu)')
            ax.plot(*apres[:2], marker='x', color='#138961')
        ax.set_title('ICP entre scans — aperçu avant application')
        ax.legend(fontsize=8)
        self.fin_dessin('Localisation')

    def contexte_localisation_valide(self, contexte):
        reference, mobile, pose_r, pose_m, mesures_r, mesures_m, filtres = contexte
        try:
            paire = self.paire_localisation()
            return (paire[0] is reference and paire[1] is mobile and
                    any(s is reference for s in self.scans) and any(s is mobile for s in self.scans) and
                    np.array_equal(reference.pose, pose_r) and np.array_equal(mobile.pose, pose_m) and
                    np.array_equal(reference.mesures, mesures_r) and np.array_equal(mobile.mesures, mesures_m) and
                    self.filtres() == filtres)
        except ValueError:
            return False

    def parametres_recalage(self, methode=None):
        distance, iterations = self.nombre('icp_distance'), self.nombre('icp_iterations')
        if distance <= 0 or iterations != int(iterations) or not 1 <= iterations <= 300:
            raise ValueError('Distance positive et nombre entier d’itérations entre 1 et 300 requis.')
        if methode is None:
            methode = self.vars['icp_methode'].get()
        options = {}
        if methode == 'Recherche large + ICP':
            xy, angle = self.nombre('icp_fenetre_xy'), self.nombre('icp_fenetre_angle')
            if not 0 < xy <= 3 or not 0 < angle <= 90:
                raise ValueError('Les fenêtres doivent être positives, jusqu’à 3 m et 90°.')
            options = dict(fenetre_xy=xy, fenetre_angle=angle)
        elif methode not in ('ICP local', METHODE_GLOBALE):
            raise ValueError('Méthode de localisation inconnue.')
        options.update(distance_max=distance, iterations_max=int(iterations))
        return methode, options

    def lancer_lot(self):
        if self.travail: raise ValueError('Un calcul ou une capture est déjà en cours.')
        self.annuler_geste()
        methode, options = self.parametres_recalage()
        globale = methode == METHODE_GLOBALE
        scans = list(self.scans) if globale else self.choisis()
        if len(scans) < 2: raise ValueError('Charge au moins deux scans (ou coche-les dans Carte pour les anciens modes).')
        filtres = self.filtres()
        copies = deepcopy(scans)
        contexte = (scans, copies, filtres, globale)
        self.travail = True
        self.annuler.clear()
        self.info_localisation.configure(text='Recalage du lot en cours ; poses inchangées pendant le calcul…')
        def travail():
            try:
                if globale:
                    lot = assembler_scans(copies, annuler=self.annuler,
                        progression=lambda texte: self.messages.put(('statut', texte)), **filtres, **options)
                else:
                    lot = recaler_lot(copies, methode=methode, annuler=self.annuler,
                        progression=lambda texte: self.messages.put(('statut', texte)), **filtres, **options)
                self.messages.put(('lot', (contexte, lot)))
            except Exception as exc:
                self.messages.put(('erreur', str(exc)))
            finally: self.messages.put(('fini', None))
        threading.Thread(target=travail, daemon=True).start()

    def recevoir_lot(self, data):
        contexte, lot = data
        scans, copies, filtres = contexte[:3]
        globale = len(contexte) > 3 and contexte[3]
        try:
            valide = not self.annuler.is_set() and self.filtres() == filtres
        except ValueError:
            valide = False
        actuels = list(self.scans) if globale else [s for s, oui in zip(self.scans, self.inclus) if oui]
        valide = valide and len(actuels) == len(scans) and all(a is b for a, b in zip(actuels, scans))
        for s, c in zip(scans, copies):
            valide = valide and np.array_equal(s.pose, c.pose) and np.array_equal(s.mesures, c.mesures) and (
                s.angle_reference == c.angle_reference and s.intensite_disponible == c.intensite_disponible)
        if not valide:
            self.info_localisation.configure(text='Lot annulé ou contexte modifié : aucune pose appliquée.')
            return
        self.sauvegarde_lot = [(s, deepcopy(s.pose), deepcopy(s.suivi_recalage), self.inclus[next(i for i, x in enumerate(self.scans) if x is s)],
            self.visibles[next(i for i, x in enumerate(self.scans) if x is s)] if hasattr(self,'visibles') else True) for s in scans]
        for original, nouveau in zip(scans, lot):
            original.pose = list(nouveau.pose)
            original.suivi_recalage = deepcopy(nouveau.suivi_recalage)
            index = next(i for i, x in enumerate(self.scans) if x is original)
            if not nouveau.suivi_recalage['valide']:
                self.inclus[index] = False
                if globale and hasattr(self,'visibles'): self.visibles[index] = False
            elif globale:
                self.inclus[index] = True
                if hasattr(self,'visibles'): self.visibles[index] = True
        self.invalider()
        self.actualiser()
        echecs = [(i+1, s.suivi_recalage['message']) for i, s in enumerate(lot) if not s.suivi_recalage['valide']]
        texte = f'Lot : {len(lot)-1-len(echecs)} scans recalés, {len(echecs)} échecs, première pose fixe. Vérifie les murs puis enregistre la session.'
        if globale:
            groupes = {s.suivi_recalage.get('groupe') for s in lot if s.suivi_recalage.get('groupe',0)>0}
            texte = f'Carte principale : {len(lot)-len(echecs)} scans ; {len(echecs)} en attente dans {len(groupes)} groupe(s). Premier scan fixe. Concordances dans les détails des scans.'
        self.info_localisation.configure(text=texte)
        self.statut.set(texte)
        if echecs:
            messagebox.showwarning('Lot : localisations non appliquées', '\n'.join(f'Scan {i} : {m}' for i, m in echecs), parent=self)

    def annuler_lot(self):
        if self.travail: raise ValueError('Attends la fin du calcul.')
        sauvegarde = getattr(self, 'sauvegarde_lot', None)
        if not sauvegarde: raise ValueError('Aucun lot appliqué à annuler.')
        for scan, pose, suivi, inclus, visible in sauvegarde:
            if any(s is scan for s in self.scans):
                scan.pose = list(pose)
                scan.suivi_recalage = deepcopy(suivi)
                index = next(i for i, x in enumerate(self.scans) if x is scan)
                self.inclus[index] = inclus
                if hasattr(self,'visibles'): self.visibles[index] = visible
        self.sauvegarde_lot = None
        self.invalider()
        self.actualiser()
        self.info_localisation.configure(text='Poses antérieures au dernier lot restaurées.')

    def lancer_localisation(self):
        if self.travail:
            raise ValueError('Un calcul ou une capture est déjà en cours.')
        self.annuler_geste()
        reference, mobile = self.paire_localisation()
        filtres = self.filtres()
        methode, options = self.parametres_recalage()
        ref = Scan(reference.nom, reference.mesures.copy(), list(reference.pose), reference.source, reference.angle_reference, reference.intensite_disponible)
        mob = Scan(mobile.nom, mobile.mesures.copy(), list(mobile.pose), mobile.source, mobile.angle_reference, mobile.intensite_disponible)
        contexte = (reference, mobile, ref.pose, mob.pose, ref.mesures, mob.mesures, filtres)
        self.resultat_localisation = None
        self.travail = True
        self.annuler.clear()
        self.info_localisation.configure(text=f'{methode} en cours…')
        self.statut.set('Recalage en cours ; la référence et le mobile restent inchangés.')
        def travail():
            try:
                calcul = localisation_globale if methode == METHODE_GLOBALE else recherche_icp if methode == 'Recherche large + ICP' else icp_scan
                resultat = calcul(mob, ref, **filtres, annuler=self.annuler, **options)
                self.messages.put(('localisation', (contexte, resultat, ref, mob)))
            except Exception as exc:
                self.messages.put(('erreur', str(exc)))
            finally:
                self.messages.put(('fini', None))
        threading.Thread(target=travail, daemon=True).start()

    def recevoir_localisation(self, data):
        contexte, resultat, reference, mobile = data
        if not self.contexte_localisation_valide(contexte):
            self.info_localisation.configure(text='Résultat écarté : scans, choix, poses ou filtres modifiés pendant le calcul. Relance ICP.')
            return
        self.resultat_localisation = (contexte, resultat)
        self.dessiner_localisation(points_filtres(reference, contexte[-1]),
            points_filtres(mobile, contexte[-1], locaux=True), resultat.pose_initiale, resultat.pose)
        texte = (f'{resultat.methode} · {resultat.candidats} poses testées · '
                 f'x = {resultat.pose[0]:.4f} m · y = {resultat.pose[1]:.4f} m · θ = {resultat.pose[2]:.3f}°\n'
                 f'Concordance fine : {resultat.accord_fin:.1%} · RMSE des correspondances : {resultat.rmse_initiale:.4f} → {resultat.rmse:.4f} m · '
                 f'recouvrement : {resultat.recouvrement:.0%} · {resultat.iterations} itérations · {resultat.duree:.3f} s\n'
                 f'{resultat.message} Le RMSE n’est pas l’erreur de pose réelle.')
        self.info_localisation.configure(text=texte)
        self.statut.set('Aperçu prêt. Vérifie la superposition avant d’appliquer la pose.' if resultat.applicable else resultat.message)

    def appliquer_localisation(self):
        if self.resultat_localisation is None:
            raise ValueError('Lance d’abord un recalage ICP.')
        contexte, resultat = self.resultat_localisation
        if not self.contexte_localisation_valide(contexte):
            self.resultat_localisation = None
            raise ValueError('Scans, poses ou filtres modifiés : relance le recalage.')
        if not resultat.applicable:
            raise ValueError('Ce recalage n’est pas applicable. '+resultat.message)
        mobile = contexte[1]
        Atelier.memoriser_pose(self,mobile)
        mobile.pose = list(resultat.pose)
        mobile.suivi_recalage = None
        self.invalider(conserver_grille=id(mobile) not in self.scans_grille)
        self.actualiser(next(i for i, s in enumerate(self.scans) if s is mobile))
        self.info_localisation.configure(text='Pose appliquée au mobile. Référence inchangée. Enregistre la session ; recalcule les cartes concernées.')
        self.dessiner_localisation(points_filtres(contexte[0], contexte[-1]),
            points_filtres(mobile, contexte[-1], locaux=True), resultat.pose_initiale, resultat.pose)
        self.statut.set('Pose ICP appliquée. Les mesures brutes sont conservées.')

    def interface_usb(self, cadre):
        # Les réglages ICP et de capture sont créés dans preparer_variables_capture et
        # partagés avec l'onglet Localisation.
        ttk.Label(cadre,text='Capturer des scans réels depuis l’ESP32',style='Titre.TLabel').pack(anchor='w',pady=12)
        ttk.Label(cadre,text='USB : firmware ScanAtlas_WiFi avec commande SCAN, ou ancien firmware CSV.\nFerme le moniteur série Arduino et Teleplot avant de connecter le port.',wraplength=700).pack(anchor='w',pady=10)
        ttk.Label(cadre,text='Source : USB (firmware CSV historique) ou Wi-Fi (firmware ScanAtlas_WiFi)').pack(anchor='w')
        ttk.Combobox(cadre,textvariable=self.capture_source,values=['USB','Wi-Fi'],state='readonly').pack(fill='x')
        ttk.Label(cadre,text='Adresse Wi-Fi (ignorée en USB)').pack(anchor='w')
        ttk.Entry(cadre,textvariable=self.capture_hote).pack(fill='x')
        self.ports = ttk.Combobox(cadre,textvariable=self.port)
        self.ports.pack(fill='x')
        self.bouton(cadre,'Actualiser la liste des ports',self.actualiser_ports)
        self.champ(cadre,'baud','Baud ESP32 → PC (Serial.begin)',115200)
        self.champ(cadre,'quantite','Nombre de scans à capturer (1 à 20)',1)
        ttk.Checkbutton(cadre, text='Localiser automatiquement sur la carte cumulée (360°)',
                        variable=self.vars['auto_icp'], onvalue='1', offvalue='0',
                        command=lambda: self.info_capture.configure(text='Recalage automatique activé : les poses acceptées seront appliquées.'
                            if self.vars['auto_icp'].get() == '1' else 'Recalage automatique désactivé.')).pack(anchor='w', pady=6)
        ttk.Label(cadre, text='Mode global conseillé : premier scan fixe, carte cumulée de tous les scans raccordés.\nRecherche sur 360° et toute la carte, sans limite liée au dernier scan.\nSans concordance suffisante : groupe secondaire masqué, conservé puis retenté.\nLes groupes rejoignent la carte lorsqu’un raccordement est validé.', wraplength=740).pack(anchor='w')
        self.info_capture = ttk.Label(cadre, text='Recalage automatique désactivé par défaut.', wraplength=740)
        self.info_capture.pack(anchor='w', pady=4)
        self.bouton(cadre,'Capturer',self.lancer_capture)
        self.bouton(cadre,'Annuler la capture',self.annuler.set)
        ttk.Label(cadre,text='Garde le lidar immobile. Les scans reçus sont ajoutés à la liste ; exporte-les ensuite.\nLe port se ferme automatiquement en fin de capture. Le délai maximal est adapté au nombre de scans demandé.\nLa capture attend le début d’un scan et rejette les blocs incomplets.\nCapture : étendue ≥340°. Les blocs de plusieurs tours sont conservés avec une information.',wraplength=740).pack(anchor='w',pady=15)

    def actualiser_ports(self):
        try:
            from serial.tools import list_ports
        except ImportError:
            raise ValueError('PySerial manquant. Relance installer_windows.bat ou installe requirements.txt.')
        ports = [p.device for p in list_ports.comports()]
        self.ports['values']=ports
        if ports and self.port.get() not in ports:
            self.port.set(ports[0])
        self.statut.set(f'{len(ports)} port(s) détecté(s). Tu peux aussi saisir COM3, COM4… manuellement.')

    def lancer_capture(self, depuis_localisation=False):
        """Capture USB/Wi-Fi. Depuis Localisation : toujours localisée, sur le dernier scan de la liste."""
        if self.travail:
            raise ValueError('Un calcul ou une capture est déjà en cours.')
        source = self.capture_source.get() if hasattr(self,'capture_source') else 'USB'
        hote = self.capture_hote.get().strip() if source == 'Wi-Fi' else ''
        port = self.port.get().strip()
        baud = self.nombre('baud') if source == 'USB' else 115200
        quantite = self.nombre('quantite')
        if quantite != int(quantite) or not 1<=quantite<=20:
            raise ValueError('Indique 1 à 20 scans.')
        if source == 'USB' and (not port or baud != int(baud) or baud<=0):
            raise ValueError('Indique un port et un baud entier positif.')
        if source == 'Wi-Fi' and not hote:
            raise ValueError('Indique une adresse Wi-Fi.')
        if getattr(self, 'wifi_robot', None) is not None:
            self.wifi_deconnecter()  # Conserve la carte et les scans de session.

        self.annuler_geste()
        automatique = depuis_localisation or self.vars['auto_icp'].get() == '1'
        reference = self.scans[-1] if self.scans else None
        copie = deepcopy(reference)
        originaux_globaux = list(self.scans)
        copies_globales = deepcopy(self.scans)
        historique = deepcopy([s for s in self.scans[:-1] if s.suivi_recalage and s.suivi_recalage.get("valide")][-4:])
        if copie is not None: historique.append(copie)
        self.contexte_capture_historique = [(s, deepcopy(s)) for s in self.scans]
        methode, options, filtres = None, {}, {}
        if automatique:
            methode, options = (self.parametres_recalage(self.vars['loc_methode'].get())
                                if depuis_localisation else self.parametres_recalage())
            if methode != METHODE_GLOBALE and reference is not None and reference.suivi_recalage and not reference.suivi_recalage['valide']:
                raise ValueError('Le dernier scan n’est pas recalé. Corrige sa pose manuellement ou dans Localisation avant de reprendre le recalage automatique.')
            filtres = self.filtres()
        self.capture_depuis_localisation = bool(depuis_localisation)
        self.travail=True
        self.annuler.clear()
        self.statut.set('Capture en cours : attente d’un scan complet…')
        self.informer_capture(('Auto global activé · premier scan fixe et carte cumulée. Réception en cours…'
            if automatique and methode == METHODE_GLOBALE else f'Auto activé · référence : scan {len(self.scans)} — {reference.nom}. Réception en cours…'
            if automatique and reference is not None else 'Auto activé · premier scan : création de la référence.'
            if automatique else 'Auto désactivé · capture sans localisation.'))
        def travail():
            try:
                from acquisition import capturer, capturer_wifi
                progression = lambda s:self.messages.put(('capture_statut',s))
                if source == 'Wi-Fi':
                    scans=capturer_wifi(hote,int(quantite),self.annuler,progression)
                else:
                    scans=capturer(port,int(baud),int(quantite),self.annuler,progression,demander_scan=True,delai=max(40,int(quantite)*4+5)) if hasattr(self,'capture_source') else capturer(port,int(baud),int(quantite),self.annuler,progression)
                if automatique and scans:
                    self.messages.put(('capture_statut', f'Capture terminée : {len(scans)} scan(s) reçus. Localisation automatique en cours…'))
                    try:
                        if methode == METHODE_GLOBALE:
                            lot = assembler_scans(copies_globales+scans, reprendre=True, annuler=self.annuler,
                                progression=lambda s:self.messages.put(('capture_statut',s)), **filtres, **options)
                            self.messages.put(('capture_globale', (originaux_globaux,copies_globales,filtres,lot,scans)))
                            return
                        scans = recaler_capture(scans, copie, methode=methode, annuler=self.annuler,
                            progression=lambda s:self.messages.put(('capture_statut',s)), historique=historique, **filtres, **options)
                    except Exception as exc:
                        for s in scans:
                            s.suivi_recalage = dict(valide=False, etat='erreur', message='Échec de localisation automatique : '+str(exc))
                    self.messages.put(('capture_recalee', (scans, reference, copie, filtres)))
                else:
                    self.messages.put(('scans',scans))
            except Exception as exc:
                self.messages.put(('erreur',str(exc)))
            finally:
                self.messages.put(('fini',None))
        threading.Thread(target=travail,daemon=True).start()

    def recevoir_capture_globale(self, data):
        originaux, copies, filtres, lot, bruts = data
        try:
            valide = (not self.annuler.is_set() and self.filtres() == filtres and
                len(self.scans) == len(originaux) and all(a is b for a,b in zip(self.scans,originaux)))
            for s,c in zip(originaux,copies):
                valide = valide and np.array_equal(s.pose,c.pose) and np.array_equal(s.mesures,c.mesures) and (
                    s.angle_reference == c.angle_reference and s.intensite_disponible == c.intensite_disponible and s.suivi_recalage == c.suivi_recalage)
        except ValueError: valide=False
        if not valide:
            nouveaux=deepcopy(bruts)
            for s in nouveaux:
                s.suivi_recalage=dict(valide=False,etat='perime',message='Calcul annulé ou contexte modifié ; capture conservée sans pose appliquée.')
        else:
            for i,(s,nouveau) in enumerate(zip(originaux,lot)):
                etait_attente = s.suivi_recalage and not s.suivi_recalage.get('valide')
                s.pose=list(nouveau.pose);s.suivi_recalage=deepcopy(nouveau.suivi_recalage)
                if not s.suivi_recalage['valide']:
                    self.inclus[i]=False;self.visibles[i]=False
                elif etait_attente:
                    self.inclus[i]=True;self.visibles[i]=True
            nouveaux=lot[len(originaux):]
        debut=len(self.scans)
        self.ajouter(nouveaux)
        for i,s in enumerate(nouveaux,debut):
            if not s.suivi_recalage['valide']:
                self.inclus[i]=False;self.visibles[i]=False
        self.actualiser(len(self.scans)-1)
        attentes=[s for s in nouveaux if not s.suivi_recalage['valide']]
        texte='\n'.join(s.nom+' : '+s.suivi_recalage['message'] for s in nouveaux)
        self.informer_capture(texte)
        self.statut.set(f'Capture globale : {len(nouveaux)-len(attentes)} raccordé(s), {len(attentes)} en attente.')
        if self.capture_depuis_localisation:
            self.dessiner_capture_localisation(originaux[-1] if originaux else None, nouveaux)
        if attentes: messagebox.showwarning('Scans en attente de raccordement',texte,parent=self)
        if self.capture_depuis_localisation:
            return
        onglets=getattr(self,'sous_onglets',getattr(self,'onglets',None))
        if onglets is not None:
            for tab in onglets.tabs():
                if onglets.tab(tab,'text')=='Nuages': onglets.select(tab);break

    def recevoir_capture_recalee(self, data):
        scans, reference, copie, filtres = data
        try:
            actuel = self.scans[-1] if self.scans else None
            contexte_valide = (actuel is reference and self.filtres() == filtres and
                (reference is None or (np.array_equal(reference.pose, copie.pose) and
                 np.array_equal(reference.mesures, copie.mesures) and
                 reference.angle_reference == copie.angle_reference)))
            for original, ancien in getattr(self, 'contexte_capture_historique', []):
                contexte_valide = contexte_valide and any(s is original for s in self.scans) and (
                    np.array_equal(original.pose, ancien.pose) and
                    np.array_equal(original.mesures, ancien.mesures) and
                    original.angle_reference == ancien.angle_reference and
                    original.intensite_disponible == ancien.intensite_disponible and
                    original.suivi_recalage == ancien.suivi_recalage)
        except ValueError:
            contexte_valide = False
        if not contexte_valide:
            for s in scans:
                s.pose = [0., 0., 0.]
                s.suivi_recalage = dict(valide=False, etat='perime', message='Référence ou filtres modifiés pendant la capture ; recalage écarté, mesures conservées.')
        debut = len(self.scans)
        self.ajouter(scans)
        refus = 0
        for i, s in enumerate(scans, debut):
            if not s.suivi_recalage['valide']:
                self.inclus[i] = False
                refus += 1
        self.actualiser(len(self.scans)-1)
        reussis = [s for s in scans if s.suivi_recalage.get('etat') == 'recalage' and s.suivi_recalage['valide']]
        if refus:
            motifs = [f'{i+1}. {s.nom} : {s.suivi_recalage.get("message", "Échec sans détail")}'
                      for i,s in enumerate(scans) if not s.suivi_recalage['valide']]
            texte = (f'Échec de localisation automatique pour {refus} scan(s). '
                     'Mesures conservées, scans non recalés décochés Carte.\n'+'\n'.join(motifs[:3]))
        elif reussis:
            dernier = reussis[-1]
            p = dernier.pose
            texte = (f'Localisation automatique réussie : {len(reussis)} scan(s) déplacé(s). '
                     f'Dernière pose : x={p[0]:.3f} m, y={p[1]:.3f} m, θ={p[2]:.2f}°. '
                     'Vérifie la superposition et enregistre la session.')
        else:
            texte = 'Premier scan enregistré comme référence. Aucun scan précédent : aucune localisation à effectuer.'
        self.informer_capture(texte)
        self.statut.set(texte)
        if self.capture_depuis_localisation:
            # Rester dans Localisation et tracer la superposition avant toute fenêtre d'alerte.
            self.dessiner_capture_localisation(reference, scans)
        if refus:
            messagebox.showwarning('Échec de localisation automatique', texte, parent=self)
        elif reussis and not self.capture_depuis_localisation:
            # Montrer la superposition réellement appliquée, pas seulement un compteur.
            onglets = getattr(self, 'sous_onglets', getattr(self,'onglets',None))
            if onglets is not None:
                for tab in onglets.tabs():
                    if onglets.tab(tab, 'text') == 'Nuages':
                        onglets.select(tab)
                        break

    def poll(self):
        try:
            while True:
                type_,data=self.messages.get_nowait()
                if type_=='statut':
                    self.statut.set(data)
                elif type_=='capture_statut':
                    self.statut.set(data)
                    self.informer_capture(data)
                elif type_=='scans':
                    if data:
                        self.ajouter(data)
                    else:
                        self.statut.set('Capture annulée.')
                elif type_=='erreur':
                    messagebox.showerror('Calcul ou acquisition',data)
                    self.statut.set(data)
                    if hasattr(self, 'info_localisation'):
                        self.info_localisation.configure(text=data)
                elif type_=='tp_statut':
                    self.info_tp.configure(text=data)
                    self.statut.set(data)
                elif type_=='tp_resultat':
                    self.recevoir_localisation_tp(data)
                elif type_=='tp_evaluation':
                    self.recevoir_evaluation_tp(data)
                elif type_=='lot':
                    self.recevoir_lot(data)
                elif type_=='localisation':
                    self.recevoir_localisation(data)
                elif type_=='capture_globale':
                    self.recevoir_capture_globale(data)
                elif type_=='capture_recalee':
                    self.recevoir_capture_recalee(data)
                elif type_=='fini':
                    self.travail=False
        except queue.Empty:
            pass
        self.after(100,self.poll)

    def aide(self):
        fen=tk.Toplevel(self)
        fen.title('Comprendre LD06 Atelier')
        fen.geometry('850x680')
        t=tk.Text(fen,wrap='word',padx=20,pady=15,font=('Segoe UI',11))
        t.pack(fill='both',expand=True)
        t.insert('1.0',AIDE)
        t.configure(state='disabled')
        scroll=ttk.Scrollbar(t,command=t.yview)
        scroll.pack(side='right',fill='y')
        t.configure(yscrollcommand=scroll.set)

    def fermer(self):
        self.wifi_arreter()
        if self.scans and not messagebox.askyesno('Fermer', 'Fermer l’application ? Pense à enregistrer ta session pour conserver les scans et leurs poses.'):
            return
        self.annuler.set()
        self.wifi_deconnecter()
        if self.wifi_demo_process is not None and self.wifi_demo_process.poll() is None:
            self.wifi_demo_process.terminate()
        self.destroy()


if __name__ == '__main__':
    Atelier().mainloop()

