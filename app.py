"""LD06 Atelier — interface pédagogique locale (Tkinter + Matplotlib).
Les calculs du TP sont dans cartographie.py ; l'USB dans acquisition.py.
"""
import csv
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
                         angle_segments, proches, fusionner, intersection, decouper, EPS)
from cartographie import ANGLE_REFERENCE_DEFAUT

AIDE = '''PARCOURS CONSEILLÉ
1. « Démonstration simulée » pour découvrir les vues sans matériel.
2. Importer un CSV réel ou capturer l'USB. Les scans importés sont ajoutés.
3. Sélectionner un scan, régler x, y et orientation, puis « Appliquer la pose ».
4. Cocher les scans à inclure, puis calculer une grille ou une carte vectorielle.
5. Exporter les scans réels et la session pour conserver le travail.

CONVENTIONS
Distances internes et poses en mètres ; angles en degrés antihoraires.
Pour les nouveaux imports/USB : angle utilisé = angle mesuré - 270°.
La référence 270° est fixe : seul le réglage de pose du robot est affiché.
Elle est aussi appliquée aux scans réels des anciennes sessions.
Le CSV ESP32 a 6 colonnes : indice, angle°, distance mm, intensité, x mm, y mm.
Nous recalculons x = r cos(angle), y = r sin(angle) : les colonnes x/y ESP32
ne sont pas utilisées. Ne pas inverser de nouveau les angles de la bibliothèque.
Un CSV à 3 colonnes est notre format angle_deg, distance_m, intensite.

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
Le laboratoire compare deux segments extraits du scan sélectionné.
Le découpage est explicite dans ce laboratoire ; il n'est pas automatiquement
appliqué aux murs d'une carte (ce qui pourrait retirer de vrais murs).

LIMITES
Lidar immobile pendant un scan ; environnement supposé fixe et plan.
Pas de SLAM ni de calcul automatique des poses. Vitres, mouvements et bruit
peuvent créer des erreurs. Des scans CSV fragmentaires peuvent être importés :
le nombre de points et l'étendue angulaire sont affichés pour contrôle.
Les retours nuls, trop faibles ou à portée maximale sont ignorés, sans libérer
les cellules du rayon. Les paramètres de segmentation demandent un réglage.
La carte vectorielle est une première méthode heuristique, pas une topologie parfaite.
Les deux documents de construction de cartes du cours n'ont pas été fournis :
ces méthodes doivent être comparées à ceux-ci.
La démo est SIMULÉE et ne remplace jamais les scans réels demandés au TP.
'''


class Atelier(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LD06 Atelier · Acquisition et cartographie 2D')
        self.geometry('1320x850')
        self.minsize(1050, 720)
        self.scans, self.inclus = [], []
        self.grille, self.vecteurs = None, None
        self.segments = []
        self.messages, self.annuler = queue.Queue(), threading.Event()
        self.travail = False
        self.vars = {}
        self.statut = tk.StringVar(value='Commence par la démonstration ou importe un scan CSV réel.')
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TButton', padding=5)
        style.configure('Titre.TLabel', font=('Segoe UI', 17, 'bold'))
        entete = ttk.Frame(self, padding=(16, 10))
        entete.pack(fill='x')
        ttk.Label(entete, text='LD06 Atelier', style='Titre.TLabel').pack(side='left')
        ttk.Label(entete, text='   Mesurer → afficher → cartographier', foreground='#536276').pack(side='left')
        ttk.Button(entete, text='Comprendre l’application', command=self.aide).pack(side='right')
        corps = ttk.Panedwindow(self, orient='horizontal')
        corps.pack(fill='both', expand=True, padx=12)
        panneau = ttk.Frame(corps, width=360)
        defilement = tk.Canvas(panneau, width=345, highlightthickness=0)
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
        fichiers = ttk.LabelFrame(gauche, text='1 · Mes scans', padding=8)
        fichiers.pack(fill='x')
        self.bouton(fichiers, 'Importer un ou plusieurs CSV…', self.importer)
        self.bouton(fichiers, 'Démonstration simulée (2 scans)', self.demo)
        self.liste = ttk.Treeview(fichiers, columns=('inclure', 'points'), show='tree headings', height=7, selectmode='browse')
        self.liste.heading('#0', text='Scan')
        self.liste.column('#0', width=175)
        self.liste.heading('inclure', text='Carte')
        self.liste.column('inclure', width=45, anchor='center')
        self.liste.heading('points', text='Pts')
        self.liste.column('points', width=45, anchor='center')
        self.liste.pack(fill='x', pady=6)
        self.liste.bind('<<TreeviewSelect>>', self.selection)
        self.liste.bind('<ButtonRelease-1>', self.clic_liste)
        ttk.Label(fichiers, text='Clique dans « Carte » pour inclure/exclure.', font=('Segoe UI', 9)).pack(anchor='w')
        self.info = ttk.Label(fichiers, text='Aucun scan sélectionné', wraplength=300)
        self.info.pack(fill='x', pady=5)
        self.bouton(fichiers, 'Supprimer le scan sélectionné', self.supprimer)
        pose = ttk.LabelFrame(gauche, text='2 · Pose du scan sélectionné', padding=8)
        pose.pack(fill='x', pady=8)
        for cle, titre, valeur in [('x','Position x (m)',0), ('y','Position y (m)',0), ('orientation','Orientation (°)',0)]:
            self.champ(pose, cle, titre, valeur)
        self.bouton(pose, 'Appliquer la pose', self.appliquer_pose)
        filtres = ttk.LabelFrame(gauche, text='3 · Filtrage commun', padding=8)
        filtres.pack(fill='x')
        for cle, titre, valeur in [('mini','Distance min (m)',.05), ('maxi','Distance max exclue (m)',12), ('intensite','Intensité minimale',0)]:
            self.champ(filtres, cle, titre, valeur)
        self.bouton(filtres, 'Appliquer les filtres', self.filtrer)
        self.bouton(gauche, 'Enregistrer la session…', self.sauver_session)
        self.bouton(gauche, 'Ouvrir une session…', self.ouvrir_session)
        self.bouton(gauche, 'Exporter le scan sélectionné…', self.sauver_scan)
        self.onglets = ttk.Notebook(droite)
        self.onglets.pack(fill='both', expand=True)
        self.axes, self.canvas = {}, {}
        for titre in ['Nuages', 'Grille', 'Segments', 'Carte vectorielle', 'Acquisition USB']:
            cadre = ttk.Frame(self.onglets, padding=8)
            self.onglets.add(cadre, text=titre)
            if titre == 'Acquisition USB':
                self.interface_usb(cadre)
                continue
            barre = ttk.Frame(cadre)
            barre.pack(fill='x')
            if titre == 'Grille':
                self.champ(barre, 'resolution', 'Résolution (m/cellule)', .05)
                self.bouton(barre, 'Construire / actualiser avec les scans cochés', self.calculer_grille)
                self.bouton(barre, 'Exporter la grille (.npz)…', self.sauver_grille)
            elif titre == 'Segments':
                for cle, label, v in [('saut','Rupture entre points (m)',.20), ('erreur','Erreur de droite max (m)',.04)]:
                    self.champ(barre, cle, label, v)
                self.bouton(barre, 'Extraire les segments du scan sélectionné', self.calculer_segments)
                self.bouton(barre, 'Laboratoire : angle, fusion, intersection, découpage', self.laboratoire)
            elif titre == 'Carte vectorielle':
                for cle, label, v in [('angle_max','Écart angulaire max (°)',8), ('distance_max','Distance de fusion max (m)',.12)]:
                    self.champ(barre, cle, label, v)
                self.bouton(barre, 'Construire avec les scans cochés', self.calculer_vecteurs)
                self.bouton(barre, 'Exporter les segments (.csv)…', self.sauver_vecteurs)
            else:
                ttk.Label(barre, text='Une couleur par scan · repère global en mètres · flèches = poses').pack(anchor='w')
                ttk.Label(barre, text='Utilise la barre sous le graphique pour zoomer et déplacer la vue.').pack(anchor='w')
            fig = Figure(figsize=(7,5), dpi=100, constrained_layout=True)
            self.axes[titre] = fig.add_subplot(111)
            canvas = FigureCanvasTkAgg(fig, cadre)
            canvas.get_tk_widget().pack(fill='both', expand=True)
            NavigationToolbar2Tk(canvas, cadre).update()
            self.canvas[titre] = canvas
        ttk.Label(self, textvariable=self.statut, padding=(16, 8), wraplength=1250).pack(fill='x')
        self.protocol('WM_DELETE_WINDOW', self.fermer)
        self.actualiser()
        self.after(100, self.poll)

    def bouton(self, parent, texte, action):
        b = ttk.Button(parent, text=texte, command=lambda: self.proteger(action))
        b.pack(fill='x', pady=2)
        return b

    def champ(self, parent, cle, titre, valeur):
        ligne = ttk.Frame(parent)
        ligne.pack(fill='x', pady=2)
        ttk.Label(ligne, text=titre).pack(side='left')
        self.vars[cle] = tk.StringVar(value=str(valeur))
        ttk.Entry(ligne, textvariable=self.vars[cle], width=12).pack(side='right')

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
            self.liste.insert('', 'end', iid=str(i), text=s.nom, values=('✓' if self.inclus[i] else '—', len(s.mesures)))
        if self.scans:
            i = min(selection if selection is not None else int(ancien[0]) if ancien else 0, len(self.scans)-1)
            self.liste.selection_set(str(i))
            self.selection()
        else:
            self.info.configure(text='Aucun scan sélectionné')
        self.dessiner_nuages()

    def selection(self, event=None):
        if not self.liste.selection():
            return
        s = self.scans[self.indice()]
        for k, v in zip(['x','y','orientation'], s.pose):
            self.vars[k].set(str(round(v,5)))
        couverture = np.ptp(np.rad2deg(np.unwrap(np.deg2rad(s.mesures[:,0]))))
        self.info.configure(text=f'{s.source}\n{len(s.mesures)} points · étendue ≈ {couverture:.1f}°')
        self.segments = []
        self.effacer('Segments', 'Extraire les segments du scan sélectionné')

    def clic_liste(self, event):
        item = self.liste.identify_row(event.y)
        if item and self.liste.identify_column(event.x) == '#1':
            i = int(item)
            self.inclus[i] = not self.inclus[i]
            self.invalider()
            self.actualiser(i)

    def ajouter(self, scans):
        self.scans.extend(scans)
        self.inclus.extend([True]*len(scans))
        self.invalider()
        self.actualiser(len(self.scans)-len(scans))
        self.statut.set(f'{len(scans)} scan(s) ajouté(s). Vérifie la source, les points et l’étendue angulaire.')

    def importer(self):
        fichiers = filedialog.askopenfilenames(filetypes=[('Scans CSV','*.csv'), ('Tous','*.*')])
        nouveaux = []
        for f in fichiers:
            nouveaux.extend(lire_csv(f))
        if nouveaux:
            self.ajouter(nouveaux)

    def demo(self):
        self.ajouter(demonstration())
        self.statut.set('Deux scans SIMULÉS ajoutés. Ils ne remplacent pas tes propres acquisitions réelles.')

    def supprimer(self):
        i = self.indice()
        self.scans.pop(i)
        self.inclus.pop(i)
        self.invalider()
        self.actualiser()

    def appliquer_pose(self):
        s = self.scans[self.indice()]
        nouvelle_pose = [self.nombre(k) for k in ['x','y','orientation']]
        s.pose = nouvelle_pose
        self.invalider()
        self.dessiner_nuages()
        self.statut.set('Pose appliquée. Recalcule les cartes pour utiliser cette nouvelle pose.')

    def filtrer(self):
        self.filtres()
        self.invalider()
        self.dessiner_nuages()
        self.statut.set('Filtres appliqués à l’affichage ; les données originales sont conservées.')

    def invalider(self):
        self.grille, self.vecteurs, self.segments = None, None, []
        for t in ['Grille','Segments','Carte vectorielle']:
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

    def dessiner_nuages(self):
        ax = self.axes['Nuages']
        ax.clear()
        try:
            filtres = self.filtres()
        except ValueError:
            filtres = dict(mini=.05, maxi=12., intensite=0)
        from matplotlib import colormaps
        nombre = max(len(self.scans), 1)
        for i, s in enumerate(self.scans):
            if not self.inclus[i]:
                continue
            couleur = colormaps['hsv'](i/nombre*.85)
            pts = s.points()[mesures_valides(s, **filtres)]
            ax.scatter(pts[:,0], pts[:,1], s=5, color=couleur, label=s.nom)
            a = np.deg2rad(s.pose[2])
            ax.plot(*s.pose[:2], marker='x', color=couleur)
            ax.arrow(*s.pose[:2], .3*np.cos(a), .3*np.sin(a), width=.012, color=couleur)
        if any(self.inclus):
            ax.legend(fontsize=8, loc='upper right')
        ax.set_title('Scans cochés dans leur pose — coordonnées recalculées depuis angle et distance')
        self.fin_dessin('Nuages')

    def calculer_grille(self):
        scans, opts = self.choisis(), self.filtres()
        g = Grille.creer(scans, self.nombre('resolution'), **opts)
        for s in scans:
            g.mettre_a_jour(s, **opts)
        self.grille = g
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
        self.statut.set(f'Grille calculée depuis {len(scans)} scans ; résolution {g.resolution:g} m/cellule.')

    def tracer_segments(self, titre, segments, fond=None):
        ax = self.axes[titre]
        ax.clear()
        if fond is not None:
            ax.scatter(fond[:,0], fond[:,1], s=3, color='#bbc4cf')
        for i,s in enumerate(segments):
            ax.plot(s[:,0], s[:,1], linewidth=2)
            if titre == 'Segments':
                ax.text(*s.mean(axis=0), str(i), fontsize=9)
        ax.set_title(f'{len(segments)} segments · longueurs minimales 0,15 m · au moins 6 points/groupe')
        self.fin_dessin(titre)

    def calculer_segments(self):
        scan = self.scans[self.indice()]
        self.segments = extraire_segments(scan, **self.options_segments())
        self.tracer_segments('Segments', self.segments, scan.points()[mesures_valides(scan, **self.filtres())])
        self.statut.set('Les numéros identifient les segments utilisables dans le laboratoire.')

    def calculer_vecteurs(self):
        a, d = self.nombre('angle_max'), self.nombre('distance_max')
        if not 0 <= a <= 90 or d < 0:
            raise ValueError('Angle entre 0 et 90°, distance positive ou nulle.')
        self.vecteurs = carte_vectorielle(self.choisis(), a, d, **self.options_segments())
        self.tracer_segments('Carte vectorielle', self.vecteurs)
        self.statut.set('Carte vectorielle calculée : extraction puis fusion des segments proches.')

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
        p = filedialog.asksaveasfilename(defaultextension='.json',initialfile='session_ld06.json')
        if p:
            contenu = dict(version=2, parametres={k:v.get() for k,v in self.vars.items() if k not in ['x','y','orientation','reference']},
                           scans=[dict(nom=s.nom,mesures=s.mesures.tolist(),pose=s.pose,source=s.source,
                                       angle_reference=s.angle_reference,inclus=oui) for s,oui in zip(self.scans,self.inclus)])
            Path(p).write_text(json.dumps(contenu,ensure_ascii=False,indent=2),encoding='utf-8')
            self.statut.set('Session enregistrée : mesures originales, sources, poses et paramètres. Les cartes se recalculent.')

    def ouvrir_session(self):
        p = filedialog.askopenfilename(filetypes=[('Session','*.json')])
        if not p:
            return
        if self.scans and not messagebox.askyesno('Ouvrir une session', 'Remplacer la session affichée ? Enregistre-la avant si nécessaire.'):
            return
        data = json.loads(Path(p).read_text(encoding='utf-8'))
        if data.get('version') not in (1, 2):
            raise ValueError('Version de session inconnue.')
        scans, inclus = [], []
        for d in data['scans']:
            m,pose = np.asarray(d['mesures'],float),np.asarray(d['pose'],float)
            if m.ndim != 2 or m.shape[1] != 3 or len(m)==0 or pose.shape != (3,) or not np.isfinite(m).all() or not np.isfinite(pose).all():
                raise ValueError('Mesures ou pose invalides.')
            if (m[:,1] < 0).any() or ((m[:,2]<0)|(m[:,2]>255)).any():
                raise ValueError('Distance ou intensité invalide.')
            # Les scans réels utilisent toujours l'ancien 270° comme zéro.
            # Les exemples synthétiques sont construits dans un repère neutre.
            reference = 0. if 'SIMULATION' in str(d['source']) else ANGLE_REFERENCE_DEFAUT
            scans.append(Scan(str(d['nom']),m,pose.tolist(),str(d['source']),reference))
            inclus.append(bool(d['inclus']))
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
        self.scans,self.inclus=scans,inclus
        for k,v in nouveaux.items():
            self.vars[k].set(str(v))
        self.invalider()
        self.actualiser()
        self.statut.set('Session ouverte. Recalcule les cartes avec les boutons dédiés.')

    def interface_usb(self, cadre):
        ttk.Label(cadre,text='Capturer des scans réels depuis l’ESP32',style='Titre.TLabel').pack(anchor='w',pady=12)
        ttk.Label(cadre,text='Le programme ESP32 doit utiliser printScanCSV(Serial) uniquement.\nFerme le moniteur série Arduino et Teleplot avant de connecter le port.',wraplength=700).pack(anchor='w',pady=10)
        self.port = tk.StringVar()
        self.ports = ttk.Combobox(cadre,textvariable=self.port)
        self.ports.pack(fill='x')
        self.bouton(cadre,'Actualiser la liste des ports',self.actualiser_ports)
        self.champ(cadre,'baud','Baud ESP32 → PC (Serial.begin)',115200)
        self.champ(cadre,'quantite','Nombre de scans à capturer (1 à 20)',1)
        self.bouton(cadre,'Capturer',self.lancer_capture)
        self.bouton(cadre,'Annuler la capture',self.annuler.set)
        ttk.Label(cadre,text='Garde le lidar immobile. Les scans reçus sont ajoutés à la liste ; exporte-les ensuite.\nLe port se ferme automatiquement en fin de capture. Le délai maximal est de 40 s.\nLa capture attend le début d’un scan et rejette les blocs incomplets.\nUne étendue ≥340° ne permet pas de détecter toutes les pertes en amont de l’ESP32.',wraplength=740).pack(anchor='w',pady=15)

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

    def lancer_capture(self):
        if self.travail:
            raise ValueError('Une capture est déjà en cours.')
        port = self.port.get().strip()
        baud, quantite = self.nombre('baud'), self.nombre('quantite')
        if not port or baud != int(baud) or baud<=0 or quantite != int(quantite) or not 1<=quantite<=20:
            raise ValueError('Indique un port, un baud entier positif et 1 à 20 scans.')
        self.travail=True
        self.annuler.clear()
        self.statut.set('Capture en cours : attente d’un scan complet…')
        def travail():
            try:
                from acquisition import capturer
                scans=capturer(port,int(baud),int(quantite),self.annuler,lambda s:self.messages.put(('statut',s)))
                self.messages.put(('scans',scans))
            except Exception as exc:
                self.messages.put(('erreur',str(exc)))
            finally:
                self.messages.put(('fini',None))
        threading.Thread(target=travail,daemon=True).start()

    def poll(self):
        try:
            while True:
                type_,data=self.messages.get_nowait()
                if type_=='statut':
                    self.statut.set(data)
                elif type_=='scans':
                    if data:
                        self.ajouter(data)
                    else:
                        self.statut.set('Capture annulée.')
                elif type_=='erreur':
                    messagebox.showerror('Acquisition USB',data)
                    self.statut.set(data)
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
        if self.scans and not messagebox.askyesno('Fermer', 'Fermer l’application ? Pense à enregistrer ta session pour conserver les scans et leurs poses.'):
            return
        self.annuler.set()
        self.destroy()


if __name__ == '__main__':
    Atelier().mainloop()
