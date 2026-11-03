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
from robot_wifi import RobotWifi, dernier
from cartographie_direct import CarteDirecte

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
        ligne = ttk.Frame(cadre)
        ligne.pack(fill='x')
        ttk.Label(ligne, text='Robot').pack(side='left')
        ttk.Entry(ligne, textvariable=self.wifi_hote, width=16).pack(side='left', padx=5)
        ttk.Button(ligne, text='Connecter', command=self.wifi_connecter).pack(side='left')
        ttk.Button(ligne, text='Déconnecter', command=self.wifi_deconnecter).pack(side='left', padx=5)
        ttk.Button(ligne, text='ARRÊT · Espace', command=self.wifi_arreter).pack(side='right')
        commandes = ttk.Frame(cadre)
        commandes.pack(fill='x', pady=5)
        ttk.Checkbutton(commandes, text='Activer le clavier', variable=self.wifi_actif,
                        command=self.wifi_activer).pack(side='left')
        ttk.Label(commandes, text='Puissance PWM (0-100 / 255)').pack(side='left', padx=(16,3))
        ttk.Spinbox(commandes, from_=0, to=100, textvariable=self.wifi_pwm, width=5).pack(side='left')
        ttk.Label(commandes, textvariable=self.wifi_commande).pack(side='right')
        ttk.Label(cadre, text='Flèches haut/bas : avancer/reculer ; gauche/droite : tourner. A/D : déplacement latéral. Relâcher = arrêt.').pack(anchor='w')
        ttk.Label(cadre, text='Garder le focus dans la zone de pilotage. Espace / Échap, changement d’onglet ou perte de focus = arrêt.').pack(anchor='w')
        self.wifi_zone = tk.Label(cadre, text='Clique ici pour piloter avec les flèches', takefocus=True,
                                  background='#dfe9f0', padx=12, pady=8)
        self.wifi_zone.pack(fill='x', pady=5)
        self.wifi_zone.bind('<Button-1>', lambda e:self.wifi_zone.focus_set())
        self.wifi_zone.bind('<KeyPress>', self.wifi_touche)
        self.wifi_zone.bind('<KeyRelease>', self.wifi_relacher)
        self.wifi_zone.bind('<FocusOut>', lambda e:self.wifi_arreter())
        self.bind('<KeyPress-space>', lambda e:self.wifi_arreter(), add='+')
        self.bind('<KeyPress-Escape>', lambda e:self.wifi_arreter(), add='+')
        self.onglets.bind('<<NotebookTabChanged>>', self.wifi_changer_onglet, add='+')
        actions = ttk.Frame(cadre)
        actions.pack(fill='x')
        ttk.Button(actions, text='Reprendre ici après arrêt', command=self.wifi_reprendre).pack(side='left')
        ttk.Button(actions, text='Nouvelle carte', command=self.wifi_nouvelle_carte).pack(side='left', padx=5)
        ttk.Button(actions, text='Ajouter les scans clés à la session', command=self.wifi_vers_session).pack(side='left')
        ttk.Button(actions, text='Exporter les segments CSV...', command=self.wifi_exporter).pack(side='right')
        ttk.Label(cadre, textvariable=self.wifi_info, wraplength=1000).pack(fill='x', pady=5)
        fig = Figure(figsize=(8,5), dpi=100)
        self.wifi_axes = fig.add_subplot(111)
        self.wifi_canvas = FigureCanvasTkAgg(fig, cadre)
        self.wifi_canvas.get_tk_widget().pack(fill='both', expand=True)
        NavigationToolbar2Tk(self.wifi_canvas, cadre)
        self.wifi_axes.set_aspect('equal', adjustable='datalim')
        self.wifi_axes.set_title('Carte vectorielle en direct — premier scan à l’origine')
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
                etat = carte.traiter(trame)
                etat.scan.nom = f'Wi-Fi {robot.session[:8]} / {trame.sequence}'
                if not etat.accepte:
                    robot.commander('STOP')
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
        self.wifi_info.set('Déconnecté ; la dernière carte reste exportable.')

    def wifi_activer(self):
        self.wifi_clavier.vider()
        if self.wifi_actif.get():
            if (self.wifi_robot is None or not self.wifi_robot.connecte.is_set() or
                self.wifi_etat is None or not self.wifi_etat.accepte or
                time.monotonic()-self.wifi_dernier_resultat > .6):
                self.wifi_arreter()
                self.wifi_info.set('Attendre un scan localisé avant d’activer le clavier.')
            else:
                self.wifi_zone.focus_set()

    def wifi_changer_onglet(self, event=None):
        if str(self.onglets.select()) != str(self.wifi_cadre):
            self.wifi_arreter()

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
                    self.wifi_etat = etat
                    self.wifi_dernier_resultat = time.monotonic()
                    if not etat.accepte:
                        self.wifi_arreter()
                    self.wifi_info.set(f'{etat.message} {etat.cles} scans clés · {len(etat.segments)} segments · calcul {1000*etat.duree:.0f} ms · {robot.recus} tours reçus.')
                    if time.monotonic()-self.wifi_dernier_dessin >= .25 or not etat.accepte:
                        self.wifi_dessiner(etat)
                        self.wifi_dernier_dessin = time.monotonic()
                actif = (self.wifi_actif.get() and self.focus_get() == self.wifi_zone and
                         str(self.onglets.select()) == str(self.wifi_cadre) and
                         time.monotonic()-self.wifi_dernier_resultat < .6)
                if self.wifi_actif.get() and not actif:
                    self.wifi_arreter()
                try:
                    pwm = int(self.wifi_pwm.get())
                    if not 0 <= pwm <= 100:
                        raise ValueError('PWM hors limite')
                    cmd = self.wifi_clavier.commande() if actif else 'STOP'
                    robot.commander(cmd, pwm)
                    self.wifi_commande.set(cmd)
                except (ValueError, tk.TclError):
                    self.wifi_arreter()
        self.after(75, self.wifi_poll)

    def wifi_dessiner(self, etat):
        ax = self.wifi_axes
        ax.clear()
        points = etat.points
        if len(points):
            pas = max(1, len(points)//8000)
            ax.scatter(*points[::pas].T, s=2, c='#bdc8d0', label='Carte lidar validée')
        for s in etat.segments:
            ax.plot(*s.T, c='#237b56', linewidth=1.7)
        if len(etat.trajectoire):
            traj = etat.trajectoire
            ax.plot(traj[:,0], traj[:,1], c='#32659b', linewidth=1, label='Trajectoire lidar')
            x,y,a = traj[-1]
            ax.arrow(x,y,.35*np.cos(np.deg2rad(a)),.35*np.sin(np.deg2rad(a)),width=.025,color='#cb4525')
        ax.set_aspect('equal', adjustable='datalim')
        ax.set_xlabel('x (m)')
        ax.set_ylabel('y (m)')
        ax.set_title('Carte vectorielle en direct' if etat.accepte else 'Suivi suspendu — carte conservée')
        ax.grid(alpha=.15)
        self.wifi_canvas.draw_idle()
