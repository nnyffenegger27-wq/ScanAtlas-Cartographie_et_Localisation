"""Vérifie les actions et les tracés sans créer de fenêtre Tk.
Ce test ne remplace pas une vérification visuelle sous Windows.
"""
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from app import Atelier
from cartographie import demonstration, lire_csv


class Variable:
    def __init__(self,v=''):
        self.v=str(v)
    def get(self):
        return self.v
    def set(self,v):
        self.v=str(v)


def interface_factice():
    # Réutilisation des vraies actions ; seul le système de fenêtres est remplacé.
    a=types.SimpleNamespace()
    for nom in ['nombre','filtres','options_segments','choisis','dessiner_nuages',
                'fin_dessin','calculer_grille','calculer_segments','tracer_segments',
                'calculer_vecteurs','sauver_grille','sauver_scan','sauver_vecteurs',
                'sauver_session','ouvrir_session']:
        setattr(a,nom,types.MethodType(getattr(Atelier,nom),a))
    a.scans=demonstration()
    a.inclus=[True,True]
    a.vars={k:Variable(v) for k,v in dict(mini=.05,maxi=12,intensite=0,resolution=.05,saut=.2,erreur=.04,angle_max=8,distance_max=.12).items()}
    a.statut=Variable()
    a.axes={}
    a.canvas={}
    for nom in ['Nuages','Grille','Segments','Carte vectorielle']:
        fig=Figure(figsize=(6,4),constrained_layout=True)
        a.axes[nom]=fig.add_subplot(111)
        a.canvas[nom]=FigureCanvasAgg(fig)
    a.indice=lambda:0
    a.invalider=lambda:None
    a.actualiser=lambda:None
    return a


class Actions(unittest.TestCase):
    def test_traces_et_exports_et_session(self):
        a=interface_factice()
        a.dessiner_nuages()
        a.calculer_grille()
        a.calculer_segments()
        a.calculer_vecteurs()
        self.assertGreater(len(a.segments),3)
        with tempfile.TemporaryDirectory() as d:
            for action,nom in [(a.sauver_scan,'scan.csv'),(a.sauver_grille,'grille.npz'),
                               (a.sauver_vecteurs,'vecteurs.csv'),(a.sauver_session,'session.json')]:
                p=Path(d)/nom
                with patch('app.filedialog.asksaveasfilename',return_value=str(p)):
                    action()
                self.assertTrue(p.stat().st_size>0)
            self.assertEqual(len(lire_csv(Path(d)/'scan.csv')),1)
            a.scans=[]
            with patch('app.filedialog.askopenfilename',return_value=str(Path(d)/'session.json')):
                a.ouvrir_session()
            self.assertEqual(len(a.scans),2)
            self.assertEqual(a.scans[1].pose,[-.8,.4,15.])
            self.assertIn('SIMULATION',a.scans[0].source)
            self.assertTrue(a.inclus[0])
