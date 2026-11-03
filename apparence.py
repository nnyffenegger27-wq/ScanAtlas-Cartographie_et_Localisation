"""Palette et champs numériques communs, sans dépendance graphique ajoutée."""
import tkinter as tk
from tkinter import ttk, font

FOND = '#f2f5fa'
SURFACE = '#ffffff'
ENCRE = '#22334b'
SECONDAIRE = '#667990'
ACCENT = '#147d87'
BORDURE = '#dce5ef'


def appliquer_theme(root):
    familles = set(font.families(root))
    famille = next((f for f in ('Segoe UI','DejaVu Sans','Helvetica') if f in familles),'sans')
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
    style.configure('TLabelframe',background=FOND,bordercolor=BORDURE,relief='solid')
    style.configure('TLabelframe.Label',font=(famille,10,'bold'),background=FOND,foreground=SECONDAIRE)
    style.configure('TNotebook',background=FOND,borderwidth=0)
    style.configure('TNotebook.Tab',padding=(12,9),background='#e5ebf3',foreground=SECONDAIRE,borderwidth=0)
    style.map('TNotebook.Tab',background=[('selected',SURFACE),('active','#dce8f1')],foreground=[('selected',ACCENT)])
    style.configure('TEntry',fieldbackground=SURFACE,bordercolor=BORDURE,padding=5)
    style.configure('TCombobox',fieldbackground=SURFACE,background=SURFACE,padding=4)
    style.configure('TCheckbutton',background=FOND,foreground=ENCRE)
    style.configure('TRadiobutton',background=FOND,foreground=ENCRE)
    style.configure('Treeview',background=SURFACE,fieldbackground=SURFACE,foreground=ENCRE,rowheight=28,bordercolor=BORDURE)
    style.configure('Treeview.Heading',background='#e7edf5',foreground=ENCRE,padding=7,font=(famille,9,'bold'))
    style.map('Treeview',background=[('selected','#176d7b')],foreground=[('selected','white')])
    style.configure('Titre.TLabel',font=(famille,20,'bold'),foreground=ENCRE)
    style.configure('SousTitre.TLabel',font=(famille,10),foreground=SECONDAIRE)
    style.configure('Card.TFrame',background=SURFACE)
    style.configure('Card.TLabel',background=SURFACE,foreground=SECONDAIRE,font=(famille,9))
    style.configure('Metric.TLabel',background=SURFACE,foreground=ENCRE,font=(famille,16,'bold'))
    style.configure('Status.TLabel',background=SURFACE,foreground=ACCENT,font=(famille,11,'bold'),padding=(12,8))
    style.configure('Horizontal.TScale',background=FOND,troughcolor='#d6e4ec',bordercolor=FOND)
    return style


PLAGES = {'mini':(0,4,.05),'maxi':(1,20,.1),'intensite':(0,255,1),
          'resolution':(.01,.3,.01),'saut':(.05,1,.01),'erreur':(.01,.3,.01),
          'angle_max':(1,15,1),'distance_max':(.02,3,.01)}


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
