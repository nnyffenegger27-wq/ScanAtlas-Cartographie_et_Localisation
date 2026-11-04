"""Salles simulées : géométrie des plans et robot simulé (sans réseau)."""
import unittest
from collections import deque
import numpy as np
from atlas.simulation.simulation import (SALLES, SALLE_PAR_DEFAUT, SALLE_APPARTEMENT, RAYON_ROBOT, cloison, rectangle, polygone,
                        distance_aux_murs, deplacer, mesures_simulees)

MARGE = .26      # distance aux murs que garde l'exploration (voir atlas/robot/exploration.py)


def composante(murs, depart, pas=.05, marge=MARGE):
    """Cellules de 5 cm atteignables depuis `depart` en restant à `marge` des murs."""
    x0, y0 = murs.reshape(-1, 2).min(axis=0)
    x1, y1 = murs.reshape(-1, 2).max(axis=0)
    w, h = int((x1-x0)/pas)+1, int((y1-y0)/pas)+1
    libre = np.zeros((h, w), bool)
    xs, ys = x0+pas*np.arange(w), y0+pas*np.arange(h)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            libre[j, i] = distance_aux_murs((x, y), murs) >= marge
    d = (int((depart[1]-y0)/pas), int((depart[0]-x0)/pas))
    vu = np.zeros_like(libre)
    vu[d] = True
    file = deque([d])
    while file:
        j, i = file.popleft()
        for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            b, a = j+dj, i+di
            if 0 <= b < h and 0 <= a < w and libre[b, a] and not vu[b, a]:
                vu[b, a] = True
                file.append((b, a))
    return vu, (x0, y0, pas)


class Constructeurs(unittest.TestCase):
    def test_cloison_avec_portes(self):
        segments = np.array(cloison((0, 0), (10, 0), portes=[(2, 3), (6, 7)]))
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[:, :, 0].tolist(), [[0, 2], [3, 6], [7, 10]])

    def test_cloison_porte_au_bord(self):
        segments = np.array(cloison((0, 0), (0, 4), portes=[(0, 1)]))
        self.assertEqual(segments.tolist(), [[[0, 1], [0, 4]]])

    def test_rectangle_et_polygone_sont_fermes(self):
        for cotes in (rectangle(0, 0, 1, 2), polygone(0, 0, .5, 8)):
            c = np.array(cotes)
            self.assertTrue(np.allclose(c[:-1, 1], c[1:, 0]))           # chaque côté part où le précédent finit
            self.assertTrue(np.allclose(c[-1, 1], c[0, 0]))


class Salles(unittest.TestCase):
    def test_registre(self):
        self.assertIn(SALLE_PAR_DEFAUT, SALLES)
        for nom, salle in SALLES.items():
            self.assertEqual(salle['murs'].shape[1:], (2, 2), nom)
            self.assertTrue(salle['titre'], nom)
            self.assertGreater(distance_aux_murs(salle['depart'][:2], salle['murs']), .3, nom)   # départ dégagé

    def test_appartement_est_grand_et_meuble(self):
        m = SALLE_APPARTEMENT.reshape(-1, 2)
        self.assertGreaterEqual(m[:, 0].max()-m[:, 0].min(), 15.9)
        self.assertGreaterEqual(m[:, 1].max()-m[:, 1].min(), 9.9)
        self.assertGreater(len(SALLE_APPARTEMENT), 100)

    def test_toutes_les_pieces_sont_accessibles_depuis_le_depart(self):
        murs, depart = SALLES['appartement']['murs'], SALLES['appartement']['depart']
        vu, (x0, y0, pas) = composante(murs, depart)
        pieces = dict(salon=(2, 4.6), couloir_ouest=(.8, 6.6), couloir_est=(15.2, 6.6), bureau=(2.5, 8.2), chambre=(8.8, 8.5),
                      reunion=(11, 8.7), cuisine_ouest=(8.2, 3), cuisine_est=(14.8, 2.5), derriere_table_ronde=(15, 5.2))
        for nom, (x, y) in pieces.items():
            self.assertTrue(vu[int((y-y0)/pas), int((x-x0)/pas)], nom)

    def test_le_robot_ne_traverse_pas_les_meubles(self):
        murs = SALLES['appartement']['murs']
        pose = np.array(SALLES['appartement']['depart'], float)
        for _ in range(2000):                                           # pousse tout droit vers la table à manger
            pose = deplacer(pose, 0, -100, 0, .1, murs)                 # vers la droite du robot, soit vers le bas
        self.assertGreaterEqual(distance_aux_murs(pose[:2], murs), RAYON_ROBOT-1e-6)

    def test_le_lidar_voit_les_murs_a_la_bonne_distance(self):
        murs = SALLES['appartement']['murs']
        mesures = mesures_simulees((2., 5., 0.), np.random.default_rng(0), murs, bruit=0.)
        self.assertAlmostEqual(mesures[0, 1], 5.0, delta=.02)                   # 0° : cloison salon/cuisine à x = 7
        self.assertAlmostEqual(mesures[len(mesures)//4, 1], 1.0, delta=.02)     # 90° : mur du couloir à y = 6 (la porte est en x 2,8–3,7)
        self.assertAlmostEqual(mesures[len(mesures)//2, 1], 2.0, delta=.02)     # 180° : mur ouest à x = 0
        self.assertAlmostEqual(mesures[3*len(mesures)//4, 1], 2.3, delta=.02)   # 270° : la table basse (haut à y = 2,7)


if __name__ == '__main__':
    unittest.main()
