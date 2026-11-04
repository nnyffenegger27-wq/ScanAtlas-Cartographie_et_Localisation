"""Palette et champs numériques communs, sans dépendance graphique ajoutée."""
import tkinter as tk
from tkinter import ttk, font

FOND = '#f7f8fa'
SURFACE = '#ffffff'
ENCRE = '#20262d'
SECONDAIRE = '#667990'
ACCENT = '#276575'
BORDURE = '#dce5ef'


def appliquer_theme(root):
    familles = {f.casefold():f for f in font.families(root)}
    famille = next((familles[f.casefold()] for f in ('Segoe UI','Inter','DejaVu Sans','Nimbus Sans','Arial','Helvetica') if f.casefold() in familles),'sans')
    root.configure(background=FOND)
    font.nametofont('TkDefaultFont').configure(family=famille,size=10)
    style = ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=(famille,10),background=FOND,foreground=ENCRE)
    style.configure('TFrame',background=FOND)
    style.configure('TLabel',background=FOND,foreground=ENCRE)
    style.configure('TButton',padding=(11,7),background=SURFACE,foreground=ENCRE,bordercolor=BORDURE,
                    lightcolor=SURFACE,darkcolor=SURFACE,relief='flat')
    style.map('TButton',background=[('active','#e6f0f4'),('pressed','#d5e9ed')])
    for nom,couleur in [('Accent',ACCENT),('Danger','#be3d4c')]:
        style.configure(nom+'.TButton',background=couleur,foreground='white',bordercolor=couleur,
                        lightcolor=couleur,darkcolor=couleur,font=(famille,10,'bold'))
        style.map(nom+'.TButton',background=[('active','#244d64'),('pressed','#153348')],foreground=[('disabled','#bdc9d5')])
    style.configure('TLabelframe',background=FOND,bordercolor=FOND,relief='flat')
    style.configure('TLabelframe.Label',font=(famille,10,'bold'),background=FOND,foreground=SECONDAIRE)
    style.configure('TNotebook',background=FOND,borderwidth=0)
    normal=tk.PhotoImage(master=root,width=4,height=4);normal.put(FOND,to=(0,0,4,4))
    selection=tk.PhotoImage(master=root,width=4,height=4)
    selection.put(SURFACE,to=(0,0,4,4));selection.put(ACCENT,to=(0,2,4,4))
    root._images_onglets=(normal,selection)
    style.element_create('Flat.tab','image',normal,('selected',selection),border=(0,0,0,2),sticky='nsew')
    style.layout('TNotebook.Tab',[('Flat.tab',{'sticky':'nsew','children':[
        ('Notebook.padding',{'side':'top','sticky':'nsew','children':[
            ('Notebook.label',{'side':'top','sticky':''})]})]})])
    style.configure('TNotebook.Tab',padding=(14,9),background=FOND,foreground=SECONDAIRE,borderwidth=0)
    style.map('TNotebook.Tab',foreground=[('selected',ACCENT)])
    style.configure('TEntry',fieldbackground=SURFACE,bordercolor=BORDURE,padding=5)
    style.configure('TCombobox',fieldbackground=SURFACE,background=SURFACE,padding=4)
    style.configure('TCheckbutton',background=FOND,foreground=ENCRE)
    style.configure('TRadiobutton',background=FOND,foreground=ENCRE)
    style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=ENCRE,rowheight=28,bordercolor=BORDURE)
    style.configure('Treeview.Heading',background='#e7edf5',foreground=ENCRE,padding=7,font=(famille,9,'bold'))
    style.map('Treeview',background=[('selected','#176d7b')],foreground=[('selected','white')])
    style.configure('Titre.TLabel',font=(famille,17,'bold'),foreground=ENCRE)
    style.configure('Section.TLabel',font=(famille,11,'bold'),foreground=ENCRE)
    style.configure('SousTitre.TLabel',font=(famille,10),foreground=SECONDAIRE)
    style.configure('Card.TFrame',background=SURFACE)
    style.configure('Card.TLabel',background=SURFACE,foreground=SECONDAIRE,font=(famille,9))
    style.configure('Metric.TLabel',background=SURFACE,foreground=ENCRE,font=(famille,16,'bold'))
    style.configure('Status.TLabel',background=SURFACE,foreground=ACCENT,font=(famille,11,'bold'),padding=(12,8))
    style.configure('Horizontal.TScale',background=FOND,troughcolor='#d6e4ec',bordercolor=FOND)
    return style


PLAGES = {'mini':(0,4,.05),'maxi':(1,20,.1),'intensite':(0,255,1),
          'resolution':(.01,.3,.01),'saut':(.05,1,.01),'erreur':(.01,.3,.01),
          'angle_max':(1,15,1),'distance_max':(.02,3,.01),
          'icp_distance':(.05,1.5,.01),'icp_iterations':(10,300,1),
          'icp_fenetre_xy':(.1,3,.1),'icp_fenetre_angle':(5,90,1)}


def curseur(parent, variable, minimum, maximum, pas=1, command=None):
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
    scale=ttk.Scale(parent,from_=minimum,to=maximum,variable=valeur,command=glisser)
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
        self.bouton=ttk.Button(self,command=self.basculer)
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
