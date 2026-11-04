"""Pose vraie connue, géométrie 2D, filtres et actions d'application ICP."""
import copy
import threading
import types
import unittest
import numpy as np
from cartographie import Scan, demonstration
from localisation import icp_scan, recherche_icp, erreur_pose, transformer, points_filtres
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg


def scan_points(points, pose, nom='scan', reference=0):
    locaux = (points-np.asarray(pose[:2])) @ __import__('localisation').rotation(pose[2])
    angles = (np.rad2deg(np.arctan2(locaux[:, 1], locaux[:, 0]))+reference) % 360
    return Scan(nom, np.column_stack((angles, np.linalg.norm(locaux, axis=1), np.full(len(points), 230))), list(pose), angle_reference=reference)


class ICP(unittest.TestCase):
    def test_pose_globale_et_reference_270_sans_mutation(self):
        rng = np.random.default_rng(24)
        monde = rng.uniform([-2, -1], [3, 2], (200, 2))
        vraie = [1.2, -.4, 178.]
        reference = scan_points(monde, [-1., 2., -30.], reference=270)
        mobile = scan_points(monde, vraie, reference=270)
        mobile.pose = [1.26, -.47, -179.]
        avant = copy.deepcopy((mobile, reference))
        resultat = icp_scan(mobile, reference, iterations_max=150)
        self.assertTrue(resultat.applicable)
        self.assertLess(erreur_pose(resultat.pose, vraie)[0], 1e-6)
        self.assertLess(erreur_pose(resultat.pose, vraie)[1], 1e-6)
        for s, origine in zip((mobile, reference), avant):
            np.testing.assert_array_equal(s.mesures, origine.mesures)
            self.assertEqual(s.pose, origine.pose)

    def test_deux_positions_simulees_occlusions(self):
        ref, mob = demonstration()
        resultat = icp_scan(mob, ref, pose_initiale=[-.5, .2, 21.])
        self.assertTrue(resultat.applicable)
        position, angle = erreur_pose(resultat.pose, mob.pose)
        self.assertLess(position, .01)
        self.assertLess(angle, .1)

    def test_points_aberrants_lointains(self):
        rng = np.random.default_rng(9)
        points = rng.normal(size=(180, 2))
        vraie = [.4, .3, -12.]
        ref = scan_points(points, [0, 0, 0])
        mob = scan_points(np.vstack([points, rng.uniform(7, 8, (20, 2))]), vraie)
        v = icp_scan(mob, ref, pose_initiale=[.45, .25, -10.])
        self.assertTrue(v.applicable)
        self.assertLess(erreur_pose(v.pose, vraie)[0], .01)
        self.assertLess(v.recouvrement, 1.)

    def test_aucun_recouvrement(self):
        ref, mob = demonstration()
        v = icp_scan(mob, ref, pose_initiale=[100, 100, 0])
        self.assertFalse(v.applicable)
        self.assertEqual(v.recouvrement, 0.)

    def test_annulation_et_limite(self):
        ref, mob = demonstration()
        evt = threading.Event(); evt.set()
        self.assertFalse(icp_scan(mob, ref, annuler=evt).applicable)
        v = icp_scan(mob, ref, pose_initiale=[-.5, .2, 21.], iterations_max=1)
        self.assertFalse(v.applicable)
        self.assertFalse(v.converge)

    def test_geometrie_colineaire(self):
        points = np.column_stack((np.linspace(1, 4, 100), np.ones(100)))
        ref = scan_points(points, [0, 0, 0])
        mob = scan_points(points, [.2, 0, 0])
        self.assertFalse(icp_scan(mob, ref).applicable)

    def test_filtres_et_doublons(self):
        ref, mob = demonstration()
        with self.assertRaisesRegex(ValueError, 'six points'):
            icp_scan(mob, ref, intensite=221)
        points = points_filtres(mob, dict(mini=.05, maxi=12, intensite=220))
        mob.mesures = np.vstack((mob.mesures, mob.mesures))
        self.assertEqual(len(points), len(points_filtres(mob, dict(mini=.05, maxi=12, intensite=220))))

    def test_entrees_invalides(self):
        ref, mob = demonstration()
        for options in [dict(distance_max=0), dict(distance_max=float('nan')),
                        dict(iterations_max=1.5), dict(pose_initiale=[0, 0, float('nan')])]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                icp_scan(mob, ref, **options)
        with self.assertRaises(ValueError):
            icp_scan(ref, ref)


class RechercheLarge(unittest.TestCase):
    def test_rotation_et_translation_combinees(self):
        ref, mob = demonstration()
        for dx, dy, da in [(.5, .3, 15), (-.5, .5, -25), (1., .5, 15)]:
            initiale = np.asarray(mob.pose)+[dx, dy, da]
            avant = list(mob.pose)
            v = recherche_icp(mob, ref, pose_initiale=initiale)
            with self.subTest(decalage=(dx, dy, da)):
                self.assertTrue(v.applicable, v.message)
                ep, ea = erreur_pose(v.pose, mob.pose)
                self.assertLess(ep, .01)
                self.assertLess(ea, .1)
                np.testing.assert_array_equal(v.pose_initiale, initiale)
                self.assertGreater(v.candidats, 100)
                self.assertEqual(mob.pose, avant)

    def test_annulation_avant_et_pendant_recherche(self):
        ref, mob = demonstration()
        event = threading.Event(); event.set()
        self.assertFalse(recherche_icp(mob, ref, annuler=event).applicable)
        event.clear()
        def progres(message): event.set()
        v = recherche_icp(mob, ref, annuler=event, progression=progres)
        self.assertFalse(v.applicable)
        self.assertIn('annulée', v.message)

    def test_fenetres_filtres_et_pas_de_recouvrement(self):
        ref, mob = demonstration()
        for opts in [dict(fenetre_xy=0), dict(fenetre_angle=100), dict(fenetre_xy=float('nan')),
                     dict(iterations_max=2.5), dict(intensite=221)]:
            with self.subTest(opts=opts), self.assertRaises(ValueError):
                recherche_icp(mob, ref, **opts)
        v = recherche_icp(mob, ref, pose_initiale=[100, 100, 0], fenetre_xy=.2, fenetre_angle=5)
        self.assertFalse(v.applicable)

    def test_score_penalise_faible_recouvrement(self):
        from localisation import score_pose
        ref, mob = demonstration()
        source = points_filtres(mob, dict(mini=.05, maxi=12, intensite=0), locaux=True)
        cible = points_filtres(ref, dict(mini=.05, maxi=12, intensite=0))
        self.assertLess(score_pose(source, cible, mob.pose, .5),
                        score_pose(source, cible, [100, 100, 0], .5))




if __name__ == '__main__':
    unittest.main()
