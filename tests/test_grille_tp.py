"""Vérification du parcours scan+pose -> grille -> mise à jour de cette grille."""
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import threading
import numpy as np
from atlas.calcul.cartographie import Scan, Grille


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


