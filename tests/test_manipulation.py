"""Vrais événements Matplotlib, sans fenêtre Windows ni matériel."""
import unittest
from types import SimpleNamespace
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backend_bases import MouseEvent, KeyEvent
from cartographie import Scan, diagnostic_scan
from manipulation import ManipulationScan


class Gestes(unittest.TestCase):
    def setUp(self):
        self.fig = Figure(figsize=(6, 6))
        self.canvas = FigureCanvasAgg(self.fig)
        self.ax = self.fig.add_subplot(111)
        self.ax.set(xlim=(-5, 5), ylim=(-5, 5))
        self.canvas.draw()
        self.scan = Scan('mobile', np.array([[270, 2, 200.]]), [1., 1., 0.], angle_reference=270.)
        self.brut = self.scan.mesures.copy()
        self.mode = 'deplacer'
        self.fins, self.apercus = 0, []
        self.controle = ManipulationScan(self.canvas, self.ax, lambda: self.mode,
            lambda: self.scan, self.apercu, self.fin)

    def apercu(self, scan, limites):
        self.apercus.append(list(scan.pose))
        self.assertEqual(limites, ((-5., 5.), (-5., 5.)))

    def fin(self):
        self.fins += 1

    def event(self, nom, x, y, bouton=1):
        px, py = self.ax.transData.transform([x, y])
        self.canvas.callbacks.process(nom, MouseEvent(nom, self.canvas, px, py, button=bouton))

    def test_translation_et_validation(self):
        self.event('button_press_event', 0, 0)
        self.event('motion_notify_event', 2, -1)
        self.event('button_release_event', 2, -1)
        np.testing.assert_allclose(self.scan.pose, [3, 0, 0], atol=1e-12)
        np.testing.assert_array_equal(self.scan.mesures, self.brut)
        self.assertEqual(self.fins, 1)

    def test_rotation_autour_origine(self):
        self.mode = 'tourner'
        self.event('button_press_event', 3, 1)
        self.event('motion_notify_event', 1, 3)
        self.event('button_release_event', 1, 3)
        np.testing.assert_allclose(self.scan.pose, [1, 1, 90], atol=1e-10)
        np.testing.assert_allclose(self.scan.points(), [[1, 3]], atol=1e-10)
        np.testing.assert_array_equal(self.scan.mesures, self.brut)

    def test_rotation_passage_moins_plus_180(self):
        self.mode = 'tourner'
        for nom, angle in [('button_press_event', 179), ('motion_notify_event', -179),
                           ('button_release_event', -179)]:
            a = np.deg2rad(angle)
            self.event(nom, 1+2*np.cos(a), 1+2*np.sin(a))
        self.assertAlmostEqual(self.scan.pose[2], 2.)

    def test_echap_restaure_pose(self):
        self.event('button_press_event', 0, 0)
        self.event('motion_notify_event', 2, -1)
        self.canvas.callbacks.process('key_press_event', KeyEvent('key_press_event', self.canvas, key='escape'))
        np.testing.assert_allclose(self.scan.pose, [1, 1, 0])
        self.assertEqual(self.fins, 0)

    def test_navigation_et_pan_ne_deplacent_pas(self):
        for mode, barre in [('naviguer', ''), ('deplacer', 'pan/zoom')]:
            self.mode = mode
            self.canvas.toolbar = SimpleNamespace(mode=barre)
            self.event('button_press_event', 0, 0)
            self.event('motion_notify_event', 2, -1)
            self.event('button_release_event', 2, -1)
            np.testing.assert_allclose(self.scan.pose, [1, 1, 0])

    def test_pivot_et_scan_absent(self):
        self.mode = 'tourner'
        self.event('button_press_event', 1, 1)
        self.event('motion_notify_event', 2, 2)
        self.assertIsNone(self.controle.geste)
        self.mode = 'deplacer'
        self.controle.selection = lambda: None
        self.event('button_press_event', 0, 0)
        self.assertIsNone(self.controle.geste)

    def test_relachement_hors_axes_termine(self):
        self.event('button_press_event', 0, 0)
        self.event('motion_notify_event', 1, 0)
        self.event('button_release_event', 20, 20)
        np.testing.assert_allclose(self.scan.pose, [2, 1, 0])
        self.assertIsNone(self.controle.geste)
        self.assertEqual(self.fins, 1)


class Diagnostic(unittest.TestCase):
    def mesures(self, angles):
        a = np.asarray(angles) % 360.
        return np.column_stack([a, np.ones(len(a)), np.full(len(a), 200.)])

    def test_305_points_peuvent_couvrir_un_tour(self):
        d = diagnostic_scan(self.mesures(np.linspace(359.5, .5, 305)))
        self.assertTrue(d['tour_plausible'])
        self.assertAlmostEqual(d['etendue'], 359.)

    def test_tours_multiples_et_fragment_refuses(self):
        for angles in [np.linspace(359, -720, 766), np.linspace(283, -360, 545),
                       np.linspace(280, 1, 230)]:
            self.assertFalse(diagnostic_scan(self.mesures(angles))['tour_plausible'])

    def test_lacune_et_passage_zero(self):
        self.assertFalse(diagnostic_scan(self.mesures([359, 300, 200, 100, 0]))['tour_plausible'])
        self.assertTrue(diagnostic_scan(self.mesures(np.linspace(80, -279, 305)))['tour_plausible'])
