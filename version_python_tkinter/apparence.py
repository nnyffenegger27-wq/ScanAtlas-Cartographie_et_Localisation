"""Palette et champs numériques communs, sans dépendance graphique ajoutée."""
import tkinter as tk
from tkinter import ttk, font

FOND = '#f4f5f7'
SURFACE = '#ffffff'
ENCRE = '#1b2430'
SECONDAIRE = '#667384'
ACCENT = '#1f5565'
ACCENT_FONCE = '#17424f'
BORDURE = '#dfe3e8'
DANGER = '#b0343d'
SUCCES = '#2f8f68'
SURVOL = '#eceff2'
BOUTON = '#e8ecf0'


def famille_police(root):
    familles = {f.casefold():f for f in font.families(root)}
    return next((familles[f.casefold()] for f in ('Segoe UI','Inter','DejaVu Sans','Nimbus Sans','Arial','Helvetica')
                 if f.casefold() in familles),'sans')


def style_matplotlib(famille='sans-serif'):
    """Réglages communs de tous les graphiques : fond blanc, cadre discret, grille légère."""
    import matplotlib as mpl
    mpl.rcParams.update({
        'font.family': 'sans-serif', 'font.sans-serif': [famille, 'Segoe UI', 'DejaVu Sans', 'Arial'],
        'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'axes.edgecolor': BORDURE, 'axes.linewidth': .8, 'axes.labelcolor': SECONDAIRE,
        'axes.titlesize': 11, 'axes.titleweight': 'bold', 'axes.titlecolor': ENCRE, 'axes.titlepad': 10,
        'axes.spines.top': False, 'axes.spines.right': False,
        'axes.grid': True, 'grid.color': '#eceff2', 'grid.linewidth': .8,
        'xtick.color': SECONDAIRE, 'ytick.color': SECONDAIRE, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
        'text.color': ENCRE, 'legend.frameon': True, 'legend.framealpha': .92, 'legend.edgecolor': BORDURE,
        'legend.fontsize': 9})


def habiller_barre(barre):
    """Barre d'outils Matplotlib aux couleurs de l'application (au mieux : l'API Tk varie)."""
    try:
        barre.configure(background=SURFACE)
        for enfant in barre.winfo_children():
            try:enfant.configure(background=SURFACE)
            except tk.TclError:pass
        barre._message_label.configure(foreground=SECONDAIRE,background=SURFACE)
    except (AttributeError,tk.TclError):pass
    return barre


def carte_ui(parent, titre=None, **pack):
    """Bloc blanc à bordure fine avec un titre ; renvoie le cadre intérieur où placer les widgets."""
    bord = tk.Frame(parent, background=BORDURE, padx=1, pady=1)
    interieur = ttk.Frame(bord, style='Card.TFrame', padding=(14, 12))
    interieur.pack(fill='both', expand=True)
    if titre:
        ttk.Label(interieur, text=titre, style='CardTitre.TLabel').pack(anchor='w', pady=(0, 8))
    if pack:bord.pack(**pack)
    return interieur


def appliquer_theme(root):
    famille = famille_police(root)
    style_matplotlib(famille)
    root.configure(background=FOND)
    font.nametofont('TkDefaultFont').configure(family=famille,size=10)
    font.nametofont('TkTextFont').configure(family=famille,size=10)
    style = ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=(famille,10),background=FOND,foreground=ENCRE,bordercolor=BORDURE,
                    focuscolor=FOND,troughcolor=BORDURE)
    style.configure('TFrame',background=FOND)
    style.configure('TLabel',background=FOND,foreground=ENCRE)
    style.configure('TButton',padding=(12,7),background=BOUTON,foreground=ENCRE,bordercolor='#cdd3da',
                    lightcolor=BOUTON,darkcolor=BOUTON,relief='flat',focuscolor=BOUTON)
    style.map('TButton',background=[('active','#dfe4ea'),('pressed','#d2d9e0'),('disabled',FOND)],
              foreground=[('disabled','#a3adb9')],bordercolor=[('focus',ACCENT),('active','#aab3bd')])
    for nom,couleur,survol in [('Accent',ACCENT,ACCENT_FONCE),('Danger',DANGER,'#8f2830')]:
        style.configure(nom+'.TButton',background=couleur,foreground='white',bordercolor=couleur,
                        lightcolor=couleur,darkcolor=couleur,font=(famille,10,'bold'))
        style.map(nom+'.TButton',background=[('active',survol),('pressed',survol),('disabled','#c8cfd6')],
                  foreground=[('disabled','#f4f5f7')],bordercolor=[('active',survol)])
    style.configure('Ghost.TButton',background=FOND,bordercolor=FOND,lightcolor=FOND,darkcolor=FOND,foreground=SECONDAIRE)
    style.map('Ghost.TButton',background=[('active',SURVOL)],foreground=[('active',ENCRE)],bordercolor=[('active',SURVOL)])
    style.configure('TLabelframe',background=FOND,bordercolor=BORDURE,relief='solid')
    style.configure('TLabelframe.Label',font=(famille,10,'bold'),background=FOND,foreground=SECONDAIRE)
    style.configure('TSeparator',background=BORDURE)
    style.configure('TNotebook',background=FOND,borderwidth=0,bordercolor=FOND,lightcolor=FOND,darkcolor=FOND,tabmargins=(0,0,0,0))
    normal=tk.PhotoImage(master=root,width=4,height=4);normal.put(FOND,to=(0,0,4,4))
    selection=tk.PhotoImage(master=root,width=4,height=4)
    selection.put(FOND,to=(0,0,4,4));selection.put(ACCENT,to=(0,2,4,4))
    root._images_onglets=(normal,selection)
    style.element_create('Flat.tab','image',normal,('selected',selection),border=(0,0,0,2),sticky='nsew')
    style.layout('TNotebook.Tab',[('Flat.tab',{'sticky':'nsew','children':[
        ('Notebook.padding',{'side':'top','sticky':'nsew','children':[
            ('Notebook.label',{'side':'top','sticky':''})]})]})])
    style.configure('TNotebook.Tab',padding=(16,10),background=FOND,foreground=SECONDAIRE,borderwidth=0,font=(famille,10))
    style.map('TNotebook.Tab',foreground=[('selected',ACCENT),('active',ENCRE)],font=[('selected',(famille,10,'bold'))])
    style.configure('TEntry',fieldbackground=SURFACE,bordercolor=BORDURE,lightcolor=SURFACE,darkcolor=SURFACE,padding=6)
    style.map('TEntry',bordercolor=[('focus',ACCENT)],lightcolor=[('focus',ACCENT)])
    style.configure('TCombobox',fieldbackground=SURFACE,background=SURFACE,bordercolor=BORDURE,arrowcolor=SECONDAIRE,
                    lightcolor=SURFACE,darkcolor=SURFACE,padding=6)
    style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],bordercolor=[('focus',ACCENT)],background=[('active',SURVOL)])
    root.option_add('*TCombobox*Listbox.background',SURFACE)
    root.option_add('*TCombobox*Listbox.foreground',ENCRE)
    root.option_add('*TCombobox*Listbox.selectBackground',ACCENT)
    root.option_add('*TCombobox*Listbox.font',(famille,10))
    for base,fond in (('',FOND),('Card.',SURFACE)):
        for widget in ('TCheckbutton','TRadiobutton'):
            style.configure(base+widget,background=fond,foreground=ENCRE,indicatorbackground=SURFACE,
                            indicatorcolor=SURFACE,focuscolor=fond,padding=(2,3),indicatorforeground=ACCENT)
            style.map(base+widget,background=[('active',fond)],indicatorcolor=[('selected',SURFACE)])
    style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=ENCRE,rowheight=28,bordercolor=BORDURE,
                    lightcolor=SURFACE,darkcolor=SURFACE)
    style.configure('Treeview.Heading',background=FOND,foreground=SECONDAIRE,padding=7,font=(famille,9,'bold'),
                    relief='flat',bordercolor=BORDURE)
    style.map('Treeview',background=[('selected',ACCENT)],foreground=[('selected','white')])
    style.map('Treeview.Heading',background=[('active',SURVOL)])
    style.configure('Titre.TLabel',font=(famille,17,'bold'),foreground=ENCRE)
    style.configure('Section.TLabel',font=(famille,10,'bold'),foreground=ENCRE)
    style.configure('SousTitre.TLabel',font=(famille,9),foreground=SECONDAIRE)
    style.configure('Card.TFrame',background=SURFACE)
    style.configure('Card.TLabel',background=SURFACE,foreground=SECONDAIRE,font=(famille,9))
    style.configure('CardTitre.TLabel',background=SURFACE,foreground=ENCRE,font=(famille,11,'bold'))
    style.configure('CardTexte.TLabel',background=SURFACE,foreground=ENCRE)
    style.configure('Metric.TLabel',background=SURFACE,foreground=ENCRE,font=(famille,14,'bold'))
    style.configure('MetricNom.TLabel',background=SURFACE,foreground=SECONDAIRE,font=(famille,8))
    style.configure('Status.TLabel',background=SURFACE,foreground=ACCENT,font=(famille,11,'bold'),padding=(12,8))
    style.configure('Badge.TLabel',background=SURFACE,foreground=SECONDAIRE,font=(famille,9,'bold'),padding=(12,6),
                    bordercolor=BORDURE,relief='solid',borderwidth=1)
    for nom,fond in (('Horizontal.TScale',FOND),('Card.Horizontal.TScale',SURFACE)):
        style.configure(nom,background=ACCENT,troughcolor=BORDURE,bordercolor=fond,lightcolor=ACCENT,darkcolor=ACCENT,
                        gripcount=0,sliderlength=18,sliderthickness=14,relief='flat')
        style.map(nom,background=[('active',ACCENT_FONCE)])
    style.configure('TScrollbar',background=BORDURE,troughcolor=FOND,bordercolor=FOND,arrowcolor=SECONDAIRE,
                    lightcolor=BORDURE,darkcolor=BORDURE,gripcount=0,relief='flat')
    style.map('TScrollbar',background=[('active','#c3c9d1')])
    style.configure('TPanedwindow',background=FOND)
    style.configure('Sash',sashthickness=8,background=FOND)
    return style


PLAGES = {'mini':(0,4,.05),'maxi':(1,20,.1),'intensite':(0,255,1),
          'resolution':(.01,.3,.01),'saut':(.05,1,.01),'erreur':(.01,.3,.01),
          'angle_max':(1,15,1),'distance_max':(.02,3,.01),
          'icp_distance':(.05,1.5,.01),'icp_iterations':(10,300,1),
          'icp_fenetre_xy':(.1,3,.1),'icp_fenetre_angle':(5,90,1)}


def curseur(parent, variable, minimum, maximum, pas=1, command=None, style=None):
    valeur = tk.DoubleVar(value=minimum)
    def synchroniser(*_):
        try:
            v=float(variable.get().replace(',','.')) if isinstance(variable.get(),str) else float(variable.get())
            if minimum<=v<=maximum:valeur.set(v)
        except (ValueError,tk.TclError):pass  # Saisie en cours ; le champ conserve la validation habituelle.
    def glisser(v):
        arrondi=round(round((float(v)-minimum)/pas)*pas+minimum,5)
        variable.set(str(int(arrondi)) if pas>=1 else f'{arrondi:g}')
        if command:command()
    scale=ttk.Scale(parent,from_=minimum,to=maximum,variable=valeur,command=glisser,**({'style':style} if style else {}))
    variable.trace_add('write',synchroniser);synchroniser()
    scale.pack(fill='x',pady=(2,5))
    return scale



def cadre_defilant(parent, largeur=335):
    """Colonne verticale avec ascenseur ; renvoie le cadre intérieur où placer les widgets."""
    zone = tk.Canvas(parent, width=largeur, background=FOND, highlightthickness=0)
    ascenseur = ttk.Scrollbar(parent, orient='vertical', command=zone.yview)
    zone.configure(yscrollcommand=ascenseur.set)
    ascenseur.pack(side='right', fill='y')
    zone.pack(side='left', fill='both', expand=True)
    interieur = ttk.Frame(zone, padding=(0, 0, 6, 0))
    fenetre = zone.create_window((0, 0), window=interieur, anchor='nw')
    interieur.bind('<Configure>', lambda e: zone.configure(scrollregion=zone.bbox('all')))
    zone.bind('<Configure>', lambda e: zone.itemconfigure(fenetre, width=e.width))
    return interieur


class Repliable(ttk.Frame):
    def __init__(self,parent,titre,ouvert=True):
        super().__init__(parent)
        self.ouvert=ouvert;self.titre=titre
        self.bouton=ttk.Button(self,command=self.basculer,style='Ghost.TButton')
        self.bouton.pack(fill='x')
        self.contenu=ttk.Frame(self,padding=(6,4))
        self.actualiser()
    def basculer(self):
        self.ouvert=not self.ouvert;self.actualiser()
    def actualiser(self):
        self.bouton.configure(text=('▾ ' if self.ouvert else '▸ ')+self.titre)
        if self.ouvert:self.contenu.pack(fill='x')
        else:self.contenu.pack_forget()


def dessiner_logo(parent):
    c=tk.Canvas(parent,width=35,height=35,background=FOND,highlightthickness=0)
    c.create_line(29,12,29,4,4,4,4,31,15,31,fill=ACCENT,width=3,capstyle='round',joinstyle='round')
    c.create_oval(18,27,22,31,fill=ACCENT,outline=ACCENT)
    c.create_arc(10,19,30,39,start=0,extent=90,style='arc',outline=ACCENT,width=3)
    c.create_arc(4,13,36,45,start=0,extent=90,style='arc',outline=ACCENT,width=3)
    return c
