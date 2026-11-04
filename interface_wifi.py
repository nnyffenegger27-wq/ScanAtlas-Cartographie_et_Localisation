"""Onglet robot Wi-Fi : Tk au premier plan, transport et carte hors du thread UI."""
import csv
from copy import deepcopy
import queue
from dataclasses import replace
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon
from robot_wifi import RobotWifi, dernier
from robot_usb import RobotUsb
from cartographie_direct import CarteDirecte
from cartographie import mesures_valides
from apparence import curseur, carte_ui, habiller_barre, FOND, SURFACE, ENCRE, SECONDAIRE, ACCENT, DANGER, SUCCES
from encart_commandes import EncartCommandes, pourcentages

# Clavier AZERTY : Z/S = surge, Q/D = sway, A/E = yaw. Les flèches restent un équivalent
# (haut/bas = surge, gauche/droite = yaw).
TOUCHES = {'z':'FORWARD', 's':'BACK', 'q':'STRAFE_L', 'd':'STRAFE_R', 'a':'LEFT', 'e':'RIGHT',
           'Up':'FORWARD', 'Down':'BACK', 'Left':'LEFT', 'Right':'RIGHT'}
# (axe, signe) : axe 0 = surge (avance +), 1 = sway (gauche +), 2 = yaw (rotation gauche +).
AXES_CLAVIER = {'z':(0, 1), 's':(0, -1), 'q':(1, 1), 'd':(1, -1), 'a':(2, 1), 'e':(2, -1),
                'Up':(0, 1), 'Down':(0, -1), 'Left':(2, 1), 'Right':(2, -1)}


class ClavierRobot:
    """Une touche à la fois ; les combinaisons contradictoires donnent STOP."""
    def __init__(self):
        self.touches = set()

    def presser(self, touche):
        if touche in TOUCHES:
            self.touches.add(touche)

    def relacher(self, touche):
        self.touches.discard(touche)

    def vider(self):
        self.touches.clear()

    def commande(self):
        return TOUCHES[next(iter(self.touches))] if len(self.touches) == 1 else 'STOP'

    def vecteur(self):
        """(surge, sway, yaw) en -1/0/1 : les touches se combinent, les opposées s'annulent."""
        v = [0, 0, 0]
        for touche in self.touches:
            axe, signe = AXES_CLAVIER[touche]
            v[axe] += signe
        return tuple(v)


class InterfaceWifi:
    def interface_wifi(self, cadre):
        self.wifi_cadre=cadre
        self.wifi_robot=self.wifi_carte=self.wifi_thread=self.wifi_etat=None
        self.wifi_resultats=queue.Queue(maxsize=1)
        self.wifi_stop=threading.Event();self.wifi_reprise=threading.Event()
        self.wifi_global=threading.Event();self.wifi_cartographier=threading.Event();self.wifi_cartographier.set()
        self.wifi_clavier=ClavierRobot();self.wifi_relachements={}
        self.wifi_actif=tk.BooleanVar(value=False)
        self.wifi_manette_active=tk.BooleanVar(value=False)
        self.wifi_rb_precedent=False
        self.wifi_auto_recup=tk.BooleanVar(value=True)
        self.wifi_auto_connexion=tk.BooleanVar(value=True)
        self.wifi_tentatives=0;self.wifi_relance=None
        self.wifi_mode=tk.StringVar(value='Cartographier')
        self.wifi_reference=tk.StringVar(value='Nouvelle carte')
        self.wifi_vue=tk.StringVar(value='Vectorielle')
        self.wifi_liaison=tk.StringVar(value='Wi-Fi');self.wifi_hote=tk.StringVar(value='192.168.4.1');self.wifi_pwm=tk.IntVar(value=65)
        self.wifi_info=tk.StringVar(value='Connecte le PC au hotspot ScanAtlas ou démarre la démonstration.')
        self.wifi_commande=tk.StringVar(value='PC : STOP | ESP32 : EN ATTENTE')
        self.wifi_dernier_resultat=self.wifi_dernier_dessin=0.
        self.wifi_artistes=None;self.wifi_image_grille=None;self.wifi_grille_affichee=None
        self.wifi_suivre=tk.BooleanVar(value=False)
        self.wifi_voir_points=tk.BooleanVar(value=True);self.wifi_voir_scan=tk.BooleanVar(value=True)
        self.wifi_voir_segments=tk.BooleanVar(value=True)
        self.wifi_metriques={k:tk.StringVar(value='--') for k in ('pose','angle','concordance','calcul','carte')}
        from manette import ManetteXbox
        self.manette=ManetteXbox()
        self.wifi_demo_process=None
        self.wifi_journal=None
        entete=ttk.Frame(cadre);entete.pack(fill='x',pady=(2,10))
        ttk.Label(entete,text='Robot en direct',style='Titre.TLabel').pack(side='left')
        # Connexion dans l'en-tête : état et liaison toujours visibles, la colonne de droite reste pour le pilotage.
        liaison=ttk.Frame(entete);liaison.pack(side='left',padx=(28,0))
        liaisons=ttk.Combobox(liaison,textvariable=self.wifi_liaison,values=['Wi-Fi','USB filaire'],state='readonly',width=11)
        liaisons.pack(side='left');liaisons.bind('<<ComboboxSelected>>',lambda e:self.wifi_liaison_changer())
        ttk.Entry(liaison,textvariable=self.wifi_hote,width=16).pack(side='left',padx=6)
        ttk.Button(liaison,text='Connecter',command=self.wifi_connecter,style='Accent.TButton').pack(side='left')
        ttk.Button(liaison,text='Déconnecter',command=self.wifi_deconnecter,style='Ghost.TButton').pack(side='left',padx=(4,0))
        ttk.Button(entete,text='ARRÊT · ESPACE',command=self.wifi_arreter,style='Danger.TButton').pack(side='right')
        ttk.Button(entete,text='Démonstration',command=self.wifi_demo).pack(side='right',padx=8)
        self.wifi_badge=ttk.Label(entete,text='HORS CONNEXION',style='Badge.TLabel')
        self.wifi_badge.pack(side='right',padx=8)
        self.wifi_panes=ttk.Panedwindow(cadre,orient='horizontal')
        carte=ttk.Frame(self.wifi_panes)
        lateral=ttk.Frame(self.wifi_panes,width=330)
        fixe=ttk.Frame(lateral,padding=(14,0,8,0));fixe.pack(side='bottom',fill='x')  # Le pilotage reste toujours visible.
        defilement=tk.Canvas(lateral,width=325,background=FOND,highlightthickness=0)
        ascenseur=ttk.Scrollbar(lateral,orient='vertical',command=defilement.yview)
        defilement.configure(yscrollcommand=ascenseur.set)
        ascenseur.pack(side='right',fill='y');defilement.pack(fill='both',expand=True)
        panneau=ttk.Frame(defilement,padding=(14,0,8,0))
        fenetre=defilement.create_window((0,0),window=panneau,anchor='nw')
        panneau.bind('<Configure>',lambda e:defilement.configure(scrollregion=defilement.bbox('all')))
        defilement.bind('<Configure>',lambda e:defilement.itemconfigure(fenetre,width=e.width))
        self.wifi_panes.add(carte,weight=5);self.wifi_panes.add(lateral,weight=1)
        self.wifi_panneau=lateral
        # Bandeau d'instruments au-dessus de la carte : une seule ligne, lisible d'un coup d'œil.
        bandeau=carte_ui(carte,fill='x',pady=(0,8))
        rangee=ttk.Frame(bandeau,style='Card.TFrame');rangee.pack(fill='x')
        for i,(cle,texte) in enumerate([('pose','POSITION X / Y (M)'),('angle','ORIENTATION'),('concordance','CONCORDANCE À 12 CM'),
                                        ('calcul','CALCUL PAR TOUR'),('carte','CARTE VECTORIELLE')]):
            bloc=ttk.Frame(rangee,style='Card.TFrame');bloc.grid(row=0,column=i,sticky='w',padx=(0,28))
            ttk.Label(bloc,text=texte,style='MetricNom.TLabel').pack(anchor='w')
            ttk.Label(bloc,textvariable=self.wifi_metriques[cle],style='Metric.TLabel').pack(anchor='w')
        affichage=ttk.Frame(carte);affichage.pack(fill='x',pady=(0,4))
        for vue in ('Points','Grille','Vectorielle'):
            ttk.Radiobutton(affichage,text=vue,variable=self.wifi_vue,value=vue,command=self.wifi_actualiser_vue).pack(side='left',padx=(0,10))
        ttk.Separator(affichage,orient='vertical').pack(side='left',fill='y',padx=6,pady=3)
        for texte,var in [('Scan courant',self.wifi_voir_scan),('Segments',self.wifi_voir_segments),('Trajectoire centrée',self.wifi_suivre)]:
            ttk.Checkbutton(affichage,text=texte,variable=var,command=self.wifi_actualiser_vue).pack(side='left',padx=(0,10))
        ttk.Button(affichage,text='Vue complète',command=self.wifi_centrer).pack(side='right')
        ttk.Button(affichage,text='Me retrouver',command=self.wifi_relocaliser).pack(side='right',padx=(0,6))
        ttk.Button(affichage,text='Agrandir',command=self.wifi_agrandir).pack(side='right',padx=6)
        fig=Figure(figsize=(10,7),dpi=100,facecolor=SURFACE,constrained_layout=True)
        self.wifi_axes=fig.add_subplot(111)
        self.wifi_canvas=FigureCanvasTkAgg(fig,carte)
        habiller_barre(NavigationToolbar2Tk(self.wifi_canvas,carte)).pack(side='bottom',fill='x')
        self.wifi_canvas.get_tk_widget().pack(fill='both',expand=True)
        self.wifi_axes.set_aspect('equal',adjustable='box')
        # Colonne de droite : trois blocs, dans l'ordre d'utilisation (connecter, choisir, piloter).
        bloc=carte_ui(panneau,'Carte et mode',fill='x',pady=(0,10))
        ttk.Combobox(bloc,textvariable=self.wifi_reference,values=['Nouvelle carte','Scans cochés Carte'],state='readonly',width=26).pack(fill='x')
        modes=ttk.Combobox(bloc,textvariable=self.wifi_mode,values=['Cartographier','Localisation seule'],state='readonly')
        modes.pack(fill='x',pady=(8,6));modes.bind('<<ComboboxSelected>>',lambda e:self.wifi_mode_changer())
        ttk.Checkbutton(bloc,text='Me retrouver automatiquement si je suis perdu',variable=self.wifi_auto_recup,style='Card.TCheckbutton',
                        command=self.wifi_option_recup).pack(anchor='w')
        ttk.Checkbutton(bloc,text='Reconnecter automatiquement après une coupure',variable=self.wifi_auto_connexion,style='Card.TCheckbutton').pack(anchor='w',pady=(0,6))
        boutons=ttk.Frame(bloc,style='Card.TFrame');boutons.pack(fill='x')
        ttk.Button(boutons,text='Position 360°',command=self.wifi_relocaliser).pack(side='left',fill='x',expand=True,padx=(0,3))
        ttk.Button(boutons,text='Reprendre ici',command=self.wifi_reprendre).pack(side='left',fill='x',expand=True,padx=(3,0))
        bloc=carte_ui(fixe,'Pilotage',fill='x',pady=(0,6))
        choix=ttk.Frame(bloc,style='Card.TFrame');choix.pack(fill='x')
        ttk.Checkbutton(choix,text='Clavier actif',variable=self.wifi_actif,command=self.wifi_activer,style='Card.TCheckbutton').pack(side='left')
        ttk.Checkbutton(choix,text='Manette Xbox',variable=self.wifi_manette_active,command=self.wifi_activer_manette,style='Card.TCheckbutton').pack(side='left',padx=(14,0))
        ttk.Label(bloc,text='Manette : sticks · RB cartographie · B arrêt',
                  style='Card.TLabel',wraplength=262).pack(anchor='w',pady=(2,4))
        self.wifi_encart=EncartCommandes(bloc);self.wifi_encart.pack(fill='x',pady=(0,6))
        self.wifi_zone=tk.Label(bloc,text='Clique ici puis : Z S avancer / reculer · Q D gauche / droite · A E tourner',takefocus=True,
            background='#eef1f4',foreground=SECONDAIRE,pady=5,wraplength=262,highlightthickness=2,
            highlightbackground='#eef1f4',highlightcolor=ACCENT)
        self.wifi_zone.pack(fill='x')
        self.wifi_zone.bind('<Button-1>',lambda e:self.wifi_zone.focus_set())
        self.wifi_zone.bind('<KeyPress>',self.wifi_touche);self.wifi_zone.bind('<KeyRelease>',self.wifi_relacher)
        self.wifi_zone.bind('<FocusOut>',lambda e:self.wifi_arreter())
        self.bind('<KeyPress-space>',lambda e:self.wifi_arreter(),add='+')
        self.bind('<KeyPress-Escape>',lambda e:self.wifi_arreter(),add='+')
        self.onglets.bind('<<NotebookTabChanged>>',self.wifi_changer_onglet,add='+')
        titre=ttk.Frame(bloc,style='Card.TFrame');titre.pack(fill='x',pady=(6,0))
        ttk.Label(titre,text='Puissance maximale',style='CardTexte.TLabel').pack(side='left')
        ttk.Label(titre,text=' %',style='CardTexte.TLabel').pack(side='right')
        ttk.Label(titre,textvariable=self.wifi_pwm,style='CardTexte.TLabel').pack(side='right')
        self.wifi_curseur_pwm=curseur(bloc,self.wifi_pwm,0,100,style='Card.Horizontal.TScale')
        ttk.Button(bloc,text='ARRÊT · ESPACE',command=self.wifi_arreter,style='Danger.TButton').pack(fill='x',pady=(4,4))
        ttk.Label(bloc,textvariable=self.wifi_commande,wraplength=262,style='Card.TLabel').pack(fill='x')
        actions=ttk.Frame(cadre);actions.pack(side='bottom',fill='x',pady=(8,2))
        ttk.Button(actions,text='Nouvelle carte',command=self.wifi_nouvelle_carte).pack(side='left')
        ttk.Button(actions,text='Vers Cartographie',command=self.wifi_vers_session).pack(side='left',padx=6)
        ttk.Button(actions,text='Enregistrer la session directe…',command=self.wifi_sauver).pack(side='left')
        ttk.Button(actions,text='Dossier des essais',command=self.wifi_ouvrir_journal).pack(side='right',padx=3)
        ttk.Button(actions,text='Exporter les segments…',command=self.wifi_exporter).pack(side='right')
        ttk.Label(cadre,textvariable=self.wifi_info,wraplength=1200,style='SousTitre.TLabel').pack(side='bottom',fill='x',pady=(6,0))
        self.wifi_panes.pack(fill='both',expand=True)
        self.after(75,self.wifi_poll)

    def wifi_agrandir(self):
        self.wifi_arreter()
        if str(self.wifi_panneau) in self.wifi_panes.panes():
            self.wifi_panes.forget(self.wifi_panneau)
        else:self.wifi_panes.add(self.wifi_panneau,weight=1)

    def wifi_mode_changer(self):
        if self.wifi_mode.get()=='Cartographier':self.wifi_cartographier.set()
        else:self.wifi_cartographier.clear()

    def wifi_relocaliser(self):
        self.wifi_arreter();self.wifi_global.set()
        self.wifi_info.set('Recherche globale demandée ; la carte attend une pose validée.')

    def wifi_activer_manette(self):
        active=self.wifi_manette_active.get();self.wifi_arreter()
        self.wifi_manette_active.set(active)
        if active:
            self.wifi_zone.focus_set()
            if self.wifi_robot is None:
                self.wifi_info.set('Mode test : la manette s’affiche dans l’encart, rien n’est envoyé (robot non connecté).')

    def wifi_ouvrir_journal(self):
        self.wifi_arreter()
        if self.wifi_journal is None:return
        import os
        if hasattr(os,'startfile'):os.startfile(str(self.wifi_journal.dossier))
        else:messagebox.showinfo('Dossier des essais',str(self.wifi_journal.dossier))

    def wifi_sauver(self):
        self.wifi_arreter()
        if self.wifi_etat is None:return
        chemin=filedialog.asksaveasfilename(defaultextension='.json',initialfile='session_directe.json')
        if chemin:
            from journal_direct import sauver_carte
            sauver_carte(chemin,self.wifi_etat.scans_cles,self.wifi_carte.filtres)
            self.wifi_info.set('Session directe enregistrée ; ouvrir dans Cartographie pour la reprendre.')

    def wifi_demo(self):
        import subprocess,sys
        from pathlib import Path
        self.wifi_deconnecter()
        if self.wifi_demo_process is None or self.wifi_demo_process.poll() is not None:
            self.wifi_demo_process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('simuler_robot_wifi.py'))])
        self.wifi_liaison.set('Wi-Fi');self.wifi_hote.set('127.0.0.1')
        self.after(800,self.wifi_connecter)

    def wifi_liaison_changer(self):
        """Wi-Fi ↔ USB : propose la valeur usuelle du champ sans écraser une saisie personnalisée."""
        usb = self.wifi_liaison.get() == 'USB filaire'
        actuel = self.wifi_hote.get().strip()
        if usb and actuel in ('', '192.168.4.1', '127.0.0.1'):
            self.wifi_hote.set('auto')
        elif not usb and (actuel == '' or actuel.lower() == 'auto' or actuel.upper().startswith('COM')
                          or actuel.startswith('/dev/')):
            self.wifi_hote.set('192.168.4.1')
        if usb:
            self.wifi_info.set('USB filaire : brancher le robot en USB et fermer le moniteur série Arduino. '
                               'Le PC garde sa connexion internet.')

    def wifi_connecter(self):
        if self.wifi_robot is not None:
            self.wifi_info.set('Déconnecter avant une nouvelle connexion.')
            return
        if self.wifi_thread is not None and self.wifi_thread.is_alive():
            self.wifi_info.set('Arrêt du calcul précédent… réessaie dans un instant.')
            return
        if self.travail:
            self.wifi_info.set('Attendre la fin de l’acquisition ou du calcul en cours.')
            return
        try:
            filtres = self.filtres()
            hote = self.wifi_hote.get().strip()
            if not hote:
                raise ValueError('Adresse du robot (Wi-Fi) ou port (USB) manquant.')
        except ValueError as exc:
            messagebox.showerror('Robot Wi-Fi', str(exc))
            return
        self.wifi_arreter()
        self.wifi_stop = threading.Event()
        self.wifi_reprise = threading.Event()
        self.wifi_global.clear()
        self.wifi_resultats = queue.Queue(maxsize=1)
        sources = deepcopy([scan for scan,oui in zip(self.scans,self.inclus) if oui]) if self.wifi_reference.get()=='Scans cochés Carte' else []
        vecteurs = deepcopy(self.vecteurs) if sources and self.vecteurs is not None and self.scans_vecteurs=={id(scan) for scan,oui in zip(self.scans,self.inclus) if oui} else None
        if self.wifi_carte is None and self.wifi_reference.get()=='Scans cochés Carte' and not sources:
            self.wifi_info.set('Cocher au moins un scan Carte dans Cartographie.')
            return
        if self.wifi_carte is not None:
            self.wifi_carte.annuler.clear()
            self.wifi_carte.recup_auto=self.wifi_auto_recup.get()
            # Après une reconnexion le robot est en général au même endroit : reprise près de la dernière
            # pose ; si elle échoue, la récupération automatique élargit puis cherche sur toute la carte.
            self.wifi_reprise.set()
        from journal_direct import JournalDirect
        try:self.wifi_journal=JournalDirect()
        except OSError as exc:
            self.wifi_info.set('Impossible de créer le journal : '+str(exc));return
        usb = self.wifi_liaison.get() == 'USB filaire'
        robot = self.wifi_robot = RobotUsb(hote) if usb else RobotWifi(hote)
        self.wifi_info.set('Connexion… carte conservée si existante ; filtres figés jusqu’à Nouvelle carte.')
        robot.journal=self.wifi_journal
        robot.demarrer()
        # Captures locales : un ancien worker ne peut publier dans une nouvelle carte.
        stop, reprise, resultats, carte = self.wifi_stop, self.wifi_reprise, self.wifi_resultats, self.wifi_carte
        journal=self.wifi_journal
        recup=self.wifi_auto_recup.get()  # Lu ici : un thread de calcul ne doit pas toucher aux variables Tk.
        def calculer():
            nonlocal carte
            if carte is None:
                try:
                    if sources:robot._etat(f'Chargement de la carte de départ ({len(sources)} scans)… la position est cherchée ensuite sur toute la carte.')
                    carte=CarteDirecte(filtres,scans=sources,segments=vecteurs)
                    carte.recup_auto=recup
                    if stop.is_set() or robot.arret.is_set():return
                    self.wifi_carte=carte
                except Exception as exc:
                    robot._etat('Carte de départ refusée : '+str(exc));robot.fermer();return
            while not stop.is_set() and not robot.arret.is_set():
                try:
                    trame = robot.scans.get(timeout=.1)
                except queue.Empty:
                    continue
                if self.wifi_global.is_set():
                    carte.relocaliser();self.wifi_global.clear()
                if reprise.is_set():
                    carte.reprendre()
                    reprise.clear()
                try:
                    etat = carte.traiter(trame,enrichir=self.wifi_cartographier.is_set())
                    journal.resultat(trame,etat,carte.filtres)
                except Exception as exc:
                    robot.commander('STOP')
                    robot._etat('Suivi arrêté : '+str(exc))
                    robot.arret.set()
                    break
                etat.scan.nom = f'Wi-Fi {robot.session[:8]} / {trame.sequence}'
                dernier(resultats, etat)
        self.wifi_thread = threading.Thread(target=calculer, daemon=True)
        self.wifi_thread.start()

    def wifi_arreter(self):
        self.wifi_actif.set(False)
        self.wifi_manette_active.set(False)
        self.wifi_clavier.vider()
        self.wifi_commande.set('STOP')
        self.wifi_rb_precedent=False
        if self.wifi_robot is not None:
            self.wifi_robot.commander('STOP')

    def wifi_option_recup(self):
        if self.wifi_carte is not None:
            self.wifi_carte.recup_auto=self.wifi_auto_recup.get()

    def wifi_reconnecter(self):
        self.wifi_relance=None
        if self.wifi_robot is None and self.wifi_auto_connexion.get() and self.wifi_tentatives<=8:
            self.wifi_connecter()

    def wifi_deconnecter(self, automatique=False):
        if not automatique:
            self.wifi_tentatives=0
            if self.wifi_relance is not None:
                self.after_cancel(self.wifi_relance);self.wifi_relance=None
        self.wifi_arreter()
        self.wifi_stop.set()
        if self.wifi_carte is not None:
            self.wifi_carte.annuler.set()
        if self.wifi_robot is not None:
            self.wifi_robot.fermer()
        robot=self.wifi_robot
        if robot is not None and robot.journal is not None:
            journal=robot.journal;robot.journal=None
            threading.Thread(target=journal.fermer,daemon=True).start()
        self.wifi_robot = None
        self.wifi_badge.configure(text='HORS CONNEXION',foreground=SECONDAIRE)
        self.wifi_info.set('Déconnecté ; la dernière carte reste exportable.')

    def wifi_robot_pret(self):
        """Robot connecté avec un flux lidar récent : seul cas où une commande part."""
        robot=self.wifi_robot
        return (robot is not None and robot.connecte.is_set() and
                time.monotonic()-robot.dernier_scan <= .6)

    def wifi_activer(self):
        self.wifi_clavier.vider()
        if self.wifi_actif.get():
            self.wifi_manette_active.set(False)
            if self.wifi_robot is not None and not self.wifi_robot_pret():
                self.wifi_arreter()
                self.wifi_info.set('Attendre la connexion et le flux lidar avant d’activer le clavier.')
            else:
                self.wifi_zone.focus_set()
                if self.wifi_robot is None:
                    self.wifi_info.set('Mode test : les commandes s’affichent dans l’encart, rien n’est envoyé (robot non connecté).')

    def wifi_changer_onglet(self, event=None):
        if str(self.onglets.select()) != str(self.wifi_cadre):
            self.wifi_arreter()
        elif self.wifi_etat is not None:
            self.wifi_dessiner(self.wifi_etat)

    def wifi_touche(self, event):
        touche = event.keysym if event.keysym in TOUCHES else event.keysym.lower()
        if touche in ('space','Escape'):
            self.wifi_arreter()
            return 'break'
        if touche in TOUCHES:
            pending = self.wifi_relachements.pop(touche, None)
            if pending is not None:
                self.after_cancel(pending)  # Auto-répétition X11 : release/press successifs.
            if self.wifi_actif.get():
                self.wifi_clavier.presser(touche)
            return 'break'

    def wifi_relacher(self, event):
        touche = event.keysym if event.keysym in TOUCHES else event.keysym.lower()
        if touche in TOUCHES:
            def terminer():
                self.wifi_relachements.pop(touche, None)
                self.wifi_clavier.relacher(touche)
                if self.wifi_robot is not None:
                    # Réémet tout de suite ce qui reste pressé (STOP si plus rien).
                    try:
                        self.wifi_robot.conduire(*pourcentages(*self.wifi_clavier.vecteur(),self.wifi_pwm.get()))
                    except (ValueError, tk.TclError):
                        self.wifi_robot.commander('STOP')
            self.wifi_relachements[touche] = self.after_idle(terminer)
            return 'break'

    def wifi_reprendre(self):
        self.wifi_arreter()
        self.wifi_reprise.set()
        self.wifi_info.set('Reprise demandée près de la dernière pose validée. Réactiver le clavier après validation.')

    def wifi_nouvelle_carte(self):
        self.wifi_arreter()
        if self.wifi_etat is not None and not messagebox.askyesno('Nouvelle carte', 'Remplacer la carte en direct ? Exporter ou ajouter les scans clés à la session pour les conserver.'):
            return
        connecte = self.wifi_robot is not None
        self.wifi_deconnecter()
        self.wifi_carte = None
        self.wifi_etat = None
        self.wifi_axes.clear()
        self.wifi_artistes = None
        self.wifi_image_grille = None
        self.wifi_grille_affichee = None
        self.wifi_canvas.draw_idle()
        if connecte:
            # Le firmware libère son bail après 300 ms.
            self.after(650, self.wifi_connecter)

    def wifi_vers_session(self):
        self.wifi_arreter()
        if self.wifi_etat is not None:
            existants = {s.nom for s in self.scans}
            scans = [deepcopy(s) for s in self.wifi_etat.scans_cles if s.nom not in existants]
            self.ajouter(scans)
            self.wifi_info.set(f'{len(scans)} scans clés ajoutés ; enregistrer la session pour les conserver.')

    def wifi_exporter(self):
        self.wifi_arreter()
        if self.wifi_etat is None or not self.wifi_etat.segments:
            messagebox.showinfo('Carte Wi-Fi', 'Aucun segment à exporter.')
            return
        chemin = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('Segments CSV','*.csv')])
        if chemin:
            with open(chemin, 'w', newline='', encoding='utf-8') as fichier:
                w = csv.writer(fichier)
                w.writerow(['x1_m','y1_m','x2_m','y2_m'])
                for segment in self.wifi_etat.segments:
                    w.writerow(np.asarray(segment).ravel())

    def wifi_poll(self):
        robot = self.wifi_robot
        if robot is not None:
            if robot.arret.is_set():
                messages = []
                while not robot.etats.empty():
                    messages.append(robot.etats.get_nowait())
                self.wifi_deconnecter(automatique=True)
                perte=messages[-1] if messages else 'Connexion perdue ; moteurs arrêtés.'
                self.wifi_info.set(perte)
                if self.wifi_auto_connexion.get() and self.wifi_tentatives<8 and self.wifi_relance is None and not self.travail:
                    self.wifi_tentatives+=1
                    self.wifi_info.set(f'{perte} Reconnexion automatique dans 3 s (essai {self.wifi_tentatives}/8) ; la carte est conservée.')
                    self.wifi_relance=self.after(3000,self.wifi_reconnecter)
            else:
                while not robot.etats.empty():
                    self.wifi_info.set(robot.etats.get_nowait())
                try:
                    etat = self.wifi_resultats.get_nowait()
                except queue.Empty:
                    etat = None
                if etat is not None:
                    precedent = self.wifi_etat
                    self.wifi_etat = etat
                    if self.wifi_journal is not None and (precedent is None or precedent.accepte != etat.accepte):
                        self.wifi_journal.evenement('Suivi actif.' if etat.accepte else 'Suivi perdu : '+etat.message)
                    self.wifi_dernier_resultat = time.monotonic()
                    if etat.accepte:self.wifi_tentatives=0
                    self.wifi_info.set(f'{etat.message} {etat.cles} scans clés · {len(etat.segments)} segments · calcul {1000*etat.duree:.0f} ms · {robot.recus} tours reçus. {self.wifi_journal.erreur if self.wifi_journal else ""}')
                    pose=etat.trajectoire[-1] if len(etat.trajectoire) else np.zeros(3)
                    self.wifi_metriques['pose'].set(f'{pose[0]:.2f} / {pose[1]:.2f}')
                    self.wifi_metriques['angle'].set(f'{pose[2]:.1f}°')
                    self.wifi_metriques['concordance'].set(f'{etat.concordance:.0f} %' if np.isfinite(etat.concordance) else '--')
                    self.wifi_metriques['calcul'].set(f'{etat.duree*1000:.0f} ms')
                    self.wifi_metriques['carte'].set(f'{len(etat.segments)} segments')
                    self.wifi_badge.configure(text='SUIVI ACTIF' if etat.accepte else 'SUIVI PERDU · RECHERCHE EN COURS',foreground=SUCCES if etat.accepte else DANGER)
                    if ((precedent is None or precedent.accepte != etat.accepte or time.monotonic()-self.wifi_dernier_dessin >= .25) and
                        str(self.onglets.select())==str(self.wifi_cadre)):
                        self.wifi_dessiner(etat)
                        self.wifi_dernier_dessin = time.monotonic()
        try:
            self.wifi_pilotage()
        except (ValueError, KeyError, tk.TclError):
            self.wifi_arreter()
        self.after(75, self.wifi_poll)

    def wifi_basculer_cartographie(self):
        """RB : alterne cartographie active / localisation seule, sans toucher au mouvement."""
        cartographie=self.wifi_mode.get()!='Cartographier'
        self.wifi_mode.set('Cartographier' if cartographie else 'Localisation seule')
        self.wifi_mode_changer()
        self.wifi_info.set('Manette RB : cartographie activée.' if cartographie
                           else 'Manette RB : cartographie en pause, localisation seule.')

    def wifi_pilotage(self):
        """Entrées → encart → robot, à chaque cycle, avec ou sans robot connecté.

        Sans robot, l'encart montre exactement ce qui serait envoyé (mode test) mais
        aucun paquet ne part. Avec robot, le flux lidar doit être récent, comme avant.
        """
        robot=self.wifi_robot
        voulu=self.wifi_actif.get() or self.wifi_manette_active.get()
        try:
            focus=voulu and self.focus_get()==self.wifi_zone and str(self.onglets.select())==str(self.wifi_cadre)
        except KeyError:
            focus=False  # Tk signale ainsi le focus d'un menu déroulant : c'est une perte de focus.
        if voulu and (not focus or (robot is not None and not self.wifi_robot_pret())):
            self.wifi_arreter()  # Perte de focus, d'onglet ou de flux lidar : STOP et entrées désarmées.
        niveaux,note=(0,0,0),''
        if self.wifi_manette_active.get():
            etat=self.manette.lire_etat()
            if not etat.presente:
                self.wifi_arreter()
                self.wifi_info.set('Manette Xbox absente ; pilotage arrêté. Windows / XInput requis.')
            else:
                niveaux=(etat.surge,etat.sway,etat.yaw)
                if etat.stop:
                    self.wifi_arreter()  # B : arrêt immédiat, pilotage désactivé jusqu'à réactivation.
                    niveaux=(0,0,0)
                    self.wifi_info.set('Manette B : pilotage coupé. Recocher la manette ou le clavier pour reprendre ; lidar et localisation continuent.')
                elif etat.rb and not self.wifi_rb_precedent:self.wifi_basculer_cartographie()
                self.wifi_rb_precedent=etat.rb
        elif self.wifi_actif.get():
            niveaux=self.wifi_clavier.vecteur()
        pwm=int(self.wifi_pwm.get())
        if not 0<=pwm<=100:
            raise ValueError('PWM hors limite')
        surge,sway,yaw=pourcentages(*niveaux,pwm)
        pret=self.wifi_robot_pret()
        if robot is not None and pret:
            robot.conduire(surge,sway,yaw)
            diagnostic=robot.diagnostic_commande()
            self.wifi_commande.set(f"PC : {diagnostic['envoyee']} | ESP32 : {diagnostic['effective']}")
        elif robot is None:
            self.wifi_commande.set('Mode test : rien n’est envoyé (robot non connecté).' if (surge or sway or yaw) else 'STOP · robot non connecté')
        self.wifi_encart.afficher(surge,sway,yaw,pret,note)

    def wifi_dessiner(self, etat):
        ax = self.wifi_axes
        premiere=self.wifi_artistes is None
        if premiere:
            ax.set_facecolor('#fbfcfe')
            nuage=ax.scatter([],[],s=3,c='#b9c7d6',alpha=.65,label='Carte validée')
            courant=ax.scatter([],[],s=7,c='#e1a14a',alpha=.8,label='Scan courant')
            segments=LineCollection([],colors=ACCENT,linewidths=2.,label='Segments')
            ax.add_collection(segments)
            trajet,=ax.plot([],[],c='#5573bb',linewidth=1.2,label='Trajectoire')
            robot=Polygon(np.zeros((3,2)),closed=True,facecolor='#d64e5a',edgecolor='white',zorder=8)
            ax.add_patch(robot)
            self.wifi_artistes=nuage,courant,segments,trajet,robot
            ax.set_xlabel('x (m)',color=SECONDAIRE);ax.set_ylabel('y (m)',color=SECONDAIRE)
            ax.set_aspect('equal',adjustable='box');ax.grid(alpha=.13)
            for spine in ax.spines.values():spine.set_color('#dce5ef')
            ax.tick_params(colors=SECONDAIRE,labelsize=9)
            ax.legend(loc='upper right',fontsize=8,framealpha=.9)
        nuage,courant,segments,trajet,robot=self.wifi_artistes
        points=etat.points[::max(1,len(etat.points)//8000)]
        nuage.set_offsets(points if len(points) else np.empty((0,2)))
        vue=self.wifi_vue.get()
        limite_x,limite_y=ax.get_xlim(),ax.get_ylim()
        nuage.set_visible(self.wifi_vue.get()=='Points')
        segments.set_segments(etat.segments);segments.set_visible(self.wifi_voir_segments.get() and self.wifi_vue.get()!='Points')
        filtre=self.wifi_carte.filtres if self.wifi_carte is not None else {}
        if etat.accepte:
            pts=etat.scan.points()[mesures_valides(etat.scan,**filtre)]
            couleur='#e1a14a'
        else:
            # Suivi perdu ou pas de référence : le scan reste visible, posé à la dernière pose connue
            # (ou à l'origine), en rouge, pour voir que le lidar fonctionne et ce qu'il perçoit.
            pose=list(etat.trajectoire[-1]) if len(etat.trajectoire) else [0.,0.,0.]
            placé=replace(etat.scan,pose=pose)
            pts=placé.points()[mesures_valides(placé,**filtre)]
            couleur='#d64e5a'
        courant.set_color(couleur)
        courant.set_offsets(pts);courant.set_visible(self.wifi_voir_scan.get())
        grille=etat.grille
        if grille is not None and grille is not self.wifi_grille_affichee:
            self.wifi_grille_affichee=grille
            from matplotlib.colors import ListedColormap
            probabilites=grille.probabilites()
            valeurs=np.ones(grille.observe.shape,dtype=np.uint8)
            valeurs[grille.observe & (probabilites<.45)]=0
            valeurs[grille.observe & (probabilites>=.6)]=2
            ny,nx=valeurs.shape;o=grille.origine;r=grille.resolution
            extent=(o[0],o[0]+nx*r,o[1],o[1]+ny*r)
            if self.wifi_image_grille is None:
                self.wifi_image_grille=ax.imshow(valeurs,origin='lower',extent=extent,interpolation='nearest',
                    cmap=ListedColormap(['#ffffff','#a9b8c3','#26343d']),vmin=0,vmax=2,zorder=0)
            else:
                self.wifi_image_grille.set_data(valeurs);self.wifi_image_grille.set_extent(extent)
        if self.wifi_image_grille is not None:self.wifi_image_grille.set_visible(self.wifi_vue.get()=='Grille')
        if not premiere:
            ax.set_xlim(limite_x);ax.set_ylim(limite_y)
        if len(etat.trajectoire):
            traj = etat.trajectoire
            trajet.set_data(traj[:,0],traj[:,1])
            x,y,a = traj[-1]
            a=np.deg2rad(a);R=np.array([[np.cos(a),-np.sin(a)],[np.sin(a),np.cos(a)]])
            robot.set_xy(np.array([[.34,0],[-.16,.13],[-.16,-.13]])@R.T+[x,y])
            if self.wifi_suivre.get():
                dx=(ax.get_xlim()[1]-ax.get_xlim()[0])/2;dy=(ax.get_ylim()[1]-ax.get_ylim()[0])/2
                ax.set_xlim(x-dx,x+dx);ax.set_ylim(y-dy,y+dy)
        if premiere:self.wifi_centrer(dessiner=False)
        ax.set_title(self.wifi_vue.get()+' · '+('Cartographie active' if etat.enrichissement else 'Localisation seule') if etat.accepte else 'Position incertaine · carte conservée',fontsize=11,color=ENCRE)
        self.wifi_canvas.draw_idle()

    def wifi_centrer(self,dessiner=True):
        etat=self.wifi_etat
        if etat is None or not len(etat.points):return
        bas=etat.points.min(axis=0)-.5;haut=etat.points.max(axis=0)+.5
        self.wifi_axes.set_xlim(bas[0],haut[0]);self.wifi_axes.set_ylim(bas[1],haut[1])
        if dessiner:self.wifi_canvas.draw_idle()

    def wifi_actualiser_vue(self):
        if self.wifi_etat is not None:self.wifi_dessiner(self.wifi_etat)

