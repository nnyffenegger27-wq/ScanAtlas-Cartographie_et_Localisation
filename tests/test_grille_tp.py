"""Vérification du parcours scan+pose -> grille -> mise à jour de cette grille."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import threading
import numpy as np
from cartographie import Scan, Grille
from acquisition import capturer
from test_interface_sans_ecran import interface_factice


def cellule(grille, point):
    x, y = np.floor((np.asarray(point)-grille.origine)/grille.resolution).astype(int)
    return y, x


class GrilleTP(unittest.TestCase):
    def test_creation_scan_pose_et_indices_negatifs(self):
        scan = Scan('pose', np.array([[0., 1., 200.]]), [-2., -3., 90.])
        grille = Grille.depuis_scan(scan, .1)
        self.assertLess(grille.probabilites()[cellule(grille, [-2, -3])], .5)
        self.assertGreater(grille.probabilites()[cellule(grille, [-2, -2])], .5)
        self.assertFalse(grille.observe[0, 0])
        self.assertEqual(grille.probabilites()[0, 0], .5)

    def test_extension_conserve_cellules_et_repere_monde(self):
        initial = Scan('initial', np.array([[0, 1, 200.]]))
        grille = Grille.depuis_scan(initial, .1)
        ancien = grille.log_odds.copy()
        observe = grille.observe.copy()
        origine = grille.origine.copy()
        lointain = Scan('loin', np.array([[0, 1, 200.]]), [-4., 3., 0.])
        grille.mettre_a_jour(lointain)
        debut = np.rint((origine-grille.origine)/.1).astype(int)
        x, y = debut
        h, w = ancien.shape
        np.testing.assert_array_equal(grille.log_odds[y:y+h, x:x+w], ancien)
        np.testing.assert_array_equal(grille.observe[y:y+h, x:x+w], observe)
        self.assertGreater(grille.probabilites()[cellule(grille, [-3, 3])], .5)
        self.assertLess(grille.probabilites()[cellule(grille, [-4, 3])], .5)
        self.assertFalse(grille.observe[0, 0])

    def test_nouveau_rayon_peut_contredire_ancien_obstacle(self):
        mur = Scan('mur', np.array([[0, 1, 200.]]))
        libre = Scan('plus loin', np.array([[0, 2, 200.]]))
        grille = Grille.depuis_scan(mur, .1)
        for _ in range(3):
            grille.mettre_a_jour(libre)
        self.assertLess(grille.probabilites()[cellule(grille, [1, 0])], .5)
        self.assertGreater(grille.probabilites()[cellule(grille, [2, 0])], .5)

    def test_impact_prioritaire_sur_passage_meme_scan(self):
        scan = Scan('deux rayons', np.array([[0, 1, 200.], [0, 2, 200.]]))
        grille = Grille.depuis_scan(scan, .1)
        self.assertAlmostEqual(grille.log_odds[cellule(grille, [1, 0])], .85)

    def test_hors_portee_qualite_faible_et_distance_nulle_ignores(self):
        grille = Grille.creer([Scan('vide', np.array([[0, 1, 200.]]))], .1)
        scan = Scan('invalides', np.array([[0, 0, 200.], [30, 12, 200.], [60, 1, 2.]]))
        origine, shape = grille.origine.copy(), grille.log_odds.shape
        grille.mettre_a_jour(scan, intensite=20)
        self.assertFalse(grille.observe.any())
        np.testing.assert_array_equal(grille.origine, origine)
        self.assertEqual(grille.log_odds.shape, shape)

    def test_extension_trop_grande_ne_corrompt_pas_carte(self):
        scan = Scan('initial', np.array([[0, 1, 200.]]))
        grille = Grille.depuis_scan(scan, .1)
        origine, valeurs = grille.origine.copy(), grille.log_odds.copy()
        with self.assertRaises(ValueError):
            grille.mettre_a_jour(Scan('loin', scan.mesures, [10000, 10000, 0]))
        np.testing.assert_array_equal(grille.origine, origine)
        np.testing.assert_array_equal(grille.log_odds, valeurs)


class ParcoursInterface(unittest.TestCase):
    def test_capture_conserve_bloc_deux_tours(self):
        angles = np.linspace(359, -360, 600) % 360
        flux = ''.join(f'{i},{a},1000,200,0,0\n' for i,a in enumerate(angles)) + '\n'
        class Liaison:
            def __init__(self, *args, **kwargs): self.flux = flux.encode('ascii')
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def reset_input_buffer(self): pass
            @property
            def in_waiting(self): return len(self.flux)
            def read(self, n):
                data,self.flux = self.flux[:n],self.flux[n:]
                return data
        messages = []
        with patch.dict('sys.modules', {'serial':SimpleNamespace(Serial=Liaison)}):
            scans = capturer('FAUX',115200,1,threading.Event(),messages.append)
        self.assertEqual(len(scans),1)
        self.assertEqual(len(scans[0].mesures),600)
        self.assertIn('plusieurs tours',messages[-1])

    def test_creation_puis_ajout_et_pas_de_double_compte(self):
        a = interface_factice()
        a.creer_grille_selection()
        grille = a.grille
        a.indice = lambda: 1
        a.ajouter_grille_selection()
        self.assertIs(a.grille, grille)
        self.assertEqual(len(a.scans_grille), 2)
        valeurs = grille.log_odds.copy()
        a.ajouter_grille_selection()
        np.testing.assert_array_equal(grille.log_odds, valeurs)
        a.vars['resolution'].set('.2')
        with self.assertRaisesRegex(ValueError, 'reconstruis'):
            a.ajouter_grille_selection()

    def test_bloc_multiple_integre_sans_rejet(self):
        a = interface_factice()
        a.creer_grille_selection()
        grille = a.grille
        angles = np.linspace(359, -360, 600) % 360
        a.scans.append(Scan('deux tours', np.column_stack([angles, np.ones(600), np.full(600, 200)])))
        a.indice = lambda: 2
        a.ajouter_grille_selection()
        self.assertIn('plusieurs tours', a.statut.get())
        self.assertIn('conservé', a.statut.get())
        self.assertIs(a.grille, grille)
        self.assertEqual(len(a.scans_grille), 2)

    def test_creation_et_reconstruction_bloc_multiple(self):
        a=interface_factice()
        a.scans[0].mesures=np.tile(a.scans[0].mesures,(2,1))
        a.creer_grille_selection()
        self.assertIn('conservé',a.statut.get())
        a.calculer_grille()
        self.assertEqual(len(a.scans_grille),2)
        self.assertIn('conservé',a.statut.get())

    def test_deux_tours_ne_doublent_pas_preuves_cellules(self):
        a=interface_factice()
        scan=a.scans[0]
        simple=Grille.depuis_scan(scan)
        multiple=Grille.depuis_scan(Scan('deux tours',np.tile(scan.mesures,(2,1)),scan.pose))
        np.testing.assert_array_equal(simple.log_odds,multiple.log_odds)
        np.testing.assert_array_equal(simple.observe,multiple.observe)
