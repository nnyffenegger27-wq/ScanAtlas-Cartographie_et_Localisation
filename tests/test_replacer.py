"""Replacer le robot : l'utilisateur indique un point et une direction approximatifs sur la carte."""
import unittest
import numpy as np
from atlas.calcul.cartographie_direct import CarteDirecte
from atlas.calcul.localisation import erreur_pose
from atlas.simulation.simulation import SalleVirtuelle, SALLE_DEMO


def carte_et_robot():
    salle = SalleVirtuelle(SALLE_DEMO, pose=(0., 0., 0.))
    carte = CarteDirecte()
    for i in range(40):
        salle.avancer((30, 0, 0) if i < 20 else (0, 30, 20), .1)
        etat = carte.traiter(salle.trame())
    assert etat.accepte, etat.message
    return carte, salle


def tour(carte, salle):
    salle.t += .1
    return carte.traiter(salle.trame())


class Replacer(unittest.TestCase):
    def test_indice_approximatif_retrouve_la_position_exacte(self):
        carte, salle = carte_et_robot()
        salle.pose = np.array([-1.5, 1.8, 200.])                   # le robot a été déplacé à la main
        self.assertFalse(tour(carte, salle).accepte)
        carte.replacer(salle.pose[0]+.5, salle.pose[1]-.4, salle.pose[2]+30)   # indice à 64 cm et 30° près
        etat = tour(carte, salle)
        self.assertTrue(etat.accepte, etat.message)
        self.assertIn('indice', etat.message)
        ep, ea = erreur_pose(carte.pose, salle.pose)
        self.assertLess(ep, .05); self.assertLess(ea, 2.)
        self.assertIsNone(carte.indice)                            # indice consommé
        self.assertGreater(carte.probation, 0)                     # la carte n'est pas enrichie tout de suite

    def test_mauvais_indice_ne_deplace_pas_le_robot_au_hasard(self):
        carte, salle = carte_et_robot()
        salle.pose = np.array([2.5, -1., -90.])
        tour(carte, salle)
        carte.replacer(-2., 2., 0.)                                # à l'autre bout de la salle
        refus = [tour(carte, salle) for _ in range(5)]
        self.assertFalse(any(e.accepte and 'indice' in e.message for e in refus))
        self.assertIsNone(carte.indice)                            # abandonné après 5 essais
        self.assertIn('Indice', carte.dernier_refus + ' Indice')   # message explicite côté utilisateur
        self.assertTrue(any('non confirmé' in e.message for e in refus))

    def test_indice_invalide_refuse(self):
        carte, _ = carte_et_robot()
        for mauvais in [(float('nan'), 0, 0), (0, 0, float('inf')), (0, 0, 0, 0.), (0, 0, 0, 1., 1.)]:
            with self.assertRaises(ValueError):
                carte.replacer(*mauvais)
        with self.assertRaises(ValueError):
            CarteDirecte().replacer(0, 0, 0)                       # pas de carte

    def test_cap_limite_les_orientations_testees(self):
        carte, salle = carte_et_robot()
        salle.pose = np.array([-1.5, 1.8, 200.])
        tour(carte, salle)
        carte.replacer(salle.pose[0], salle.pose[1], salle.pose[2]+170., tolerance=20.)   # cap faux de 170° : refusé
        self.assertFalse(tour(carte, salle).accepte)


if __name__ == '__main__':
    unittest.main()
