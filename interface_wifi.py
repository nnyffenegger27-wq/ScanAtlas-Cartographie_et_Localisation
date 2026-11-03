"""Onglet robot Wi-Fi : Tk au premier plan, transport et carte hors du thread UI."""
import csv
from copy import deepcopy
import queue
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
from cartographie_direct import CarteDirecte
from cartographie import mesures_valides
from apparence import curseur, FOND, SURFACE, ENCRE, SECONDAIRE, ACCENT

TOUCHES = {'Up':'FORWARD', 'Down':'BACK', 'Left':'LEFT', 'Right':'RIGHT',
           'a':'STRAFE_L', 'd':'STRAFE_R'}


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


class InterfaceWifi:
    def interface_wifi(self, cadre):
        self.wifi_cadre = cadre
        self.wifi_robot = None
        self.wifi_carte = None
        self.wifi_thread = None
        self.wifi_etat = None
        self.wifi_resultats = queue.Queue(maxsize=1)
        self.wifi_stop = threading.Event()
        self.wifi_reprise = threading.Event()
        self.wifi_clavier = ClavierRobot()
        self.wifi_relachements = {}
        self.wifi_actif = tk.BooleanVar(value=False)
        self.wifi_hote = tk.StringVar(value='192.168.4.1')
        self.wifi_pwm = tk.IntVar(value=65)
        self.wifi_info = tk.StringVar(value='Connecte le PC au Wi-Fi ScanAtlas, puis clique sur Connecter.')
        self.wifi_commande = tk.StringVar(value='STOP')
        self.wifi_dernier_resultat = 0.
        self.wifi_dernier_dessin = 0.
        self.wifi_artistes = None
        self.wifi_suivre = tk.BooleanVar(value=False)
        self.wifi_voir_points = tk.BooleanVar(value=True)
        self.wifi_voir_scan = tk.BooleanVar(value=True)
        self.wifi_voir_segments = tk.BooleanVar(value=True)
        self.wifi_metriques = {k:tk.StringVar(value='--') for k in ('pose','angle','concordance','calcul','carte')}
        ligne = ttk.Frame(cadre)
        ligne.pack(fill='x',pady=(2,10))
        ttk.Label(ligne, text='Robot Wi-Fi',style='Titre.TLabel').pack(side='left',padx=(0,18))
        ttk.Entry(ligne, textvariable=self.wifi_hote, width=16).pack(side='left', padx=5)
        ttk.Button(ligne, text='Connecter', command=self.wifi_connecter,style='Accent.TButton').pack(side='left')
        ttk.Button(ligne, text='Déconnecter', command=self.wifi_deconnecter).pack(side='left', padx=5)
        ttk.Button(ligne, text='ARRÊT · Espace', command=self.wifi_arreter,style='Danger.TButton').pack(side='right')
        metriques=ttk.Frame(cadre);metriques.pack(fill='x',pady=(0,10))
        for i,(cle,label) in enumerate([('pose','POSITION  x / y (m)'),('angle','ORIENTATION'),
                                       ('concordance','CONCORDANCE À 12 cm'),('calcul','CALCUL PAR TOUR'),('carte','CARTE VECTORIELLE')]):
            carte=ttk.Frame(metriques,style='Card.TFrame',padding=(12,9));carte.grid(row=0,column=i,sticky='nsew',padx=(0,5))
            metriques.columnconfigure(i,weight=1)
            ttk.Label(carte,text=label,style='Card.TLabel').pack(anchor='w')
            ttk.Label(carte,textvariable=self.wifi_metriques[cle],style='Metric.TLabel').pack(anchor='w',pady=(3,0))
        commandes = ttk.Frame(cadre)
        commandes.pack(fill='x', pady=(0,5))
        ttk.Checkbutton(commandes, text='Pilotage manuel au clavier', variable=self.wifi_actif,
                        command=self.wifi_activer).pack(side='left')
        ttk.Label(commandes, text='Puissance PWM').pack(side='left', padx=(16,5))
        vitesse=ttk.Frame(commandes,width=150);vitesse.pack(side='left',padx=4)
        self.wifi_curseur_pwm=curseur(vitesse,self.wifi_pwm,0,100)
        ttk.Label(commandes,textvariable=self.wifi_pwm,width=4).pack(side='left')
        ttk.Label(commandes,text='/ 255',style='SousTitre.TLabel').pack(side='left')
        ttk.Label(commandes, textvariable=self.wifi_commande,style='Status.TLabel').pack(side='right')
        self.wifi_zone = tk.Label(cadre, text='CLAVIER  |  Haut / Bas : avancer / reculer   ·   Gauche / Droite : tourner   ·   A / D : latéral', takefocus=True,
                                  background='#e0f0f2',foreground=ACCENT,padx=12,pady=10,font='TkDefaultFont')
        self.wifi_zone.pack(fill='x', pady=5)
        self.wifi_zone.bind('<Button-1>', lambda e:self.wifi_zone.focus_set())
        self.wifi_zone.bind('<KeyPress>', self.wifi_touche)
        self.wifi_zone.bind('<KeyRelease>', self.wifi_relacher)
        self.wifi_zone.bind('<FocusOut>', lambda e:self.wifi_arreter())
        self.bind('<KeyPress-space>', lambda e:self.wifi_arreter(), add='+')
        self.bind('<KeyPress-Escape>', lambda e:self.wifi_arreter(), add='+')
        self.onglets.bind('<<NotebookTabChanged>>', self.wifi_changer_onglet, add='+')
        affichage=ttk.Frame(cadre);affichage.pack(fill='x',pady=(0,4))
        for label,var in [('Points de carte',self.wifi_voir_points),('Scan courant',self.wifi_voir_scan),('Segments',self.wifi_voir_segments),('Suivre le robot',self.wifi_suivre)]:
            ttk.Checkbutton(affichage,text=label,variable=var,command=self.wifi_actualiser_vue).pack(side='left',padx=(0,8))
        ttk.Button(affichage,text='Centrer la carte',command=self.wifi_centrer).pack(side='right')
        self.wifi_badge=ttk.Label(cadre,text='HORS CONNEXION',style='Status.TLabel')
        self.wifi_badge.pack(anchor='w',pady=(2,3))
        ttk.Label(cadre, textvariable=self.wifi_info, wraplength=1000,style='SousTitre.TLabel').pack(fill='x', pady=(0,5))
        fig = Figure(figsize=(8,5), dpi=100,facecolor=SURFACE,constrained_layout=True)
        self.wifi_axes = fig.add_subplot(111)
        self.wifi_canvas = FigureCanvasTkAgg(fig, cadre)
        actions = ttk.Frame(cadre);actions.pack(side='bottom',fill='x',pady=(7,0))
        ttk.Button(actions, text='Reprendre le suivi', command=self.wifi_reprendre).pack(side='left')
        ttk.Button(actions, text='Nouvelle carte', command=self.wifi_nouvelle_carte).pack(side='left', padx=5)
        ttk.Button(actions, text='Vers la session', command=self.wifi_vers_session).pack(side='left')
        ttk.Button(actions, text='Exporter les segments...', command=self.wifi_exporter).pack(side='right')
        NavigationToolbar2Tk(self.wifi_canvas,cadre).pack(side='bottom',fill='x')
        self.wifi_canvas.get_tk_widget().pack(fill='both', expand=True)
        self.wifi_axes.set_aspect('equal',adjustable='box')
        self.wifi_axes.set_title('Carte vectorielle · premier scan à l’origine',color=ENCRE,fontsize=11)
        self.after(75, self.wifi_poll)

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
                raise ValueError('Adresse du robot manquante.')
        except ValueError as exc:
            messagebox.showerror('Robot Wi-Fi', str(exc))
            return
        self.wifi_arreter()
        self.wifi_stop = threading.Event()
        self.wifi_reprise = threading.Event()
        self.wifi_resultats = queue.Queue(maxsize=1)
        if self.wifi_carte is None:
            self.wifi_carte = CarteDirecte(filtres)
            self.wifi_etat = None
        else:
            self.wifi_carte.annuler.clear()
            self.wifi_reprise.set()
        robot = self.wifi_robot = RobotWifi(hote)
        self.wifi_info.set('Connexion… carte conservée si existante ; filtres figés jusqu’à Nouvelle carte.')
        robot.demarrer()
        # Captures locales : un ancien worker ne peut publier dans une nouvelle carte.
        stop, reprise, resultats, carte = self.wifi_stop, self.wifi_reprise, self.wifi_resultats, self.wifi_carte
        def calculer():
            while not stop.is_set() and not robot.arret.is_set():
                try:
                    trame = robot.scans.get(timeout=.1)
                except queue.Empty:
                    continue
                if reprise.is_set():
                    carte.reprendre()
                    reprise.clear()
                try:
                    etat = carte.traiter(trame)
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
        self.wifi_clavier.vider()
        self.wifi_commande.set('STOP')
        if self.wifi_robot is not None:
            self.wifi_robot.commander('STOP')

    def wifi_deconnecter(self):
        self.wifi_arreter()
        self.wifi_stop.set()
        if self.wifi_carte is not None:
            self.wifi_carte.annuler.set()
        if self.wifi_robot is not None:
            self.wifi_robot.fermer()
        self.wifi_robot = None
        self.wifi_badge.configure(text='HORS CONNEXION',foreground=SECONDAIRE)
        self.wifi_info.set('Déconnecté ; la dernière carte reste exportable.')

    def wifi_activer(self):
        self.wifi_clavier.vider()
        if self.wifi_actif.get():
            if (self.wifi_robot is None or not self.wifi_robot.connecte.is_set() or
                time.monotonic()-self.wifi_robot.dernier_scan > .6):
                self.wifi_arreter()
                self.wifi_info.set('Attendre la connexion et le flux lidar avant d’activer le clavier.')
            else:
                self.wifi_zone.focus_set()

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
                self.wifi_deconnecter()
                self.wifi_info.set(messages[-1] if messages else 'Connexion perdue ; moteurs arrêtés.')
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
                    self.wifi_dernier_resultat = time.monotonic()
                    self.wifi_info.set(f'{etat.message} {etat.cles} scans clés · {len(etat.segments)} segments · calcul {1000*etat.duree:.0f} ms · {robot.recus} tours reçus.')
                    pose=etat.trajectoire[-1] if len(etat.trajectoire) else np.zeros(3)
                    self.wifi_metriques['pose'].set(f'{pose[0]:.2f} / {pose[1]:.2f}')
                    self.wifi_metriques['angle'].set(f'{pose[2]:.1f}°')
                    self.wifi_metriques['concordance'].set(f'{etat.concordance:.0f} %' if np.isfinite(etat.concordance) else '--')
                    self.wifi_metriques['calcul'].set(f'{etat.duree*1000:.0f} ms')
                    self.wifi_metriques['carte'].set(f'{len(etat.segments)} segments')
                    self.wifi_badge.configure(text='SUIVI ACTIF' if etat.accepte else 'CARTE EN PAUSE · PILOTAGE MANUEL DISPONIBLE',foreground=ACCENT if etat.accepte else '#be3d4c')
                    if ((precedent is None or precedent.accepte != etat.accepte or (etat.accepte and time.monotonic()-self.wifi_dernier_dessin >= .25)) and
                        str(self.onglets.select())==str(self.wifi_cadre)):
                        self.wifi_dessiner(etat)
                        self.wifi_dernier_dessin = time.monotonic()
                actif = (self.wifi_actif.get() and self.focus_get() == self.wifi_zone and
                         str(self.onglets.select()) == str(self.wifi_cadre) and
                         robot.connecte.is_set() and time.monotonic()-robot.dernier_scan < .6)
                if self.wifi_actif.get() and not actif:
                    self.wifi_arreter()
                try:
                    pwm = int(self.wifi_pwm.get())
                    if not 0 <= pwm <= 100:
                        raise ValueError('PWM hors limite')
                    cmd = self.wifi_clavier.commande() if actif else 'STOP'
                    robot.commander(cmd, pwm)
                    diagnostic = robot.diagnostic_commande()
                    self.wifi_commande.set(f"PC : {diagnostic['envoyee']} | ESP32 : {diagnostic['effective']}")
                except (ValueError, tk.TclError):
                    self.wifi_arreter()
        self.after(75, self.wifi_poll)

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
        nuage.set_visible(self.wifi_voir_points.get())
        segments.set_segments(etat.segments);segments.set_visible(self.wifi_voir_segments.get())
        filtre=self.wifi_carte.filtres if self.wifi_carte is not None else {}
        pts=etat.scan.points()[mesures_valides(etat.scan,**filtre)] if etat.accepte else np.empty((0,2))
        courant.set_offsets(pts);courant.set_visible(self.wifi_voir_scan.get())
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
        ax.set_title('Carte vectorielle en direct' if etat.accepte else 'Suivi suspendu · carte conservée',fontsize=11,color=ENCRE)
        self.wifi_canvas.draw_idle()

    def wifi_centrer(self,dessiner=True):
        etat=self.wifi_etat
        if etat is None or not len(etat.points):return
        bas=etat.points.min(axis=0)-.5;haut=etat.points.max(axis=0)+.5
        self.wifi_axes.set_xlim(bas[0],haut[0]);self.wifi_axes.set_ylim(bas[1],haut[1])
        if dessiner:self.wifi_canvas.draw_idle()

    def wifi_actualiser_vue(self):
        if self.wifi_etat is not None:self.wifi_dessiner(self.wifi_etat)

