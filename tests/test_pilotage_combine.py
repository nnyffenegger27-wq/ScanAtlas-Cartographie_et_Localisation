"""Pilotage combiné : manette, encart des commandes, mode test sans robot, capture depuis Localisation."""
import copy
import os
import queue
import threading
import time
import unittest
from types import MethodType, SimpleNamespace
from unittest.mock import MagicMock, patch
import numpy as np
from cartographie import demonstration
from manette import (vecteur_manette, EtatManette, BOUTON_LB, BOUTON_RB, BOUTON_B)
from encart_commandes import pourcentages, remplissages
from test_interface_sans_ecran import Variable

LB, RB, B = BOUTON_LB, BOUTON_RB, BOUTON_B


class ManetteCombinee(unittest.TestCase):
    def test_lb_obligatoire_et_b_arrete_tout(self):
        self.assertEqual(vecteur_manette(0, 1, 1, 0), (0, 0, 0))
        self.assertEqual(vecteur_manette(.8, .8, .8, LB | B), (0, 0, 0))
        self.assertEqual(vecteur_manette(0, 1, 0, RB), (0, 0, 0))  # RB seul n'autorise pas le mouvement.

    def test_axes_et_signes(self):
        self.assertEqual(vecteur_manette(0, 1, 0, LB), (1, 0, 0))     # stick gauche en haut : avance
        self.assertEqual(vecteur_manette(0, -1, 0, LB), (-1, 0, 0))   # en bas : recule
        self.assertEqual(vecteur_manette(-1, 0, 0, LB), (0, 1, 0))    # à gauche : sway gauche (+)
        self.assertEqual(vecteur_manette(1, 0, 0, LB), (0, -1, 0))    # à droite : sway droite (-)
        self.assertEqual(vecteur_manette(0, 0, -1, LB), (0, 0, 1))    # stick droit à gauche : yaw gauche (+)
        self.assertEqual(vecteur_manette(0, 0, 1, LB), (0, 0, -1))    # à droite : yaw droite (-)

    def test_combinaison_surge_sway_yaw(self):
        surge, sway, yaw = vecteur_manette(-.6, .6, -.7, LB)
        self.assertGreater(surge, 0); self.assertGreater(sway, 0); self.assertGreater(yaw, 0)
        self.assertAlmostEqual(surge, sway)

    def test_zone_morte_et_proportionnalite(self):
        self.assertEqual(vecteur_manette(.15, .15, .2, LB), (0, 0, 0))
        self.assertAlmostEqual(vecteur_manette(0, .61, 0, LB)[0], .5, places=2)
        self.assertAlmostEqual(vecteur_manette(0, 0, -.61, LB)[2], .5, places=2)

    def test_sorties_toujours_bornees_et_sans_zero_negatif(self):
        rng = np.random.default_rng(3)
        for lx, ly, rx in rng.uniform(-1.2, 1.2, (500, 3)):
            v = vecteur_manette(lx, ly, rx, LB)
            self.assertTrue(all(-1 <= x <= 1 for x in v), v)
        self.assertEqual([str(x) for x in vecteur_manette(0, 0, 0, LB)], ['0.0', '0.0', '0.0'])


class EncartCalculs(unittest.TestCase):
    def test_pourcentages(self):
        self.assertEqual(pourcentages(1, .4, -.2, 50), (50, 20, -10))
        self.assertEqual(pourcentages(0, 0, 0, 65), (0, 0, 0))
        self.assertEqual(pourcentages(5, -5, 0, 80), (80, -80, 0))   # niveaux bornés à ±1
        self.assertEqual(pourcentages(1, 1, 1, 250), (100, 100, 100))  # PWM borné à 100

    def test_remplissages_par_case(self):
        self.assertEqual(remplissages(40, True), (.4, 0.))
        self.assertEqual(remplissages(40, False), (0., .4))
        self.assertEqual(remplissages(-100, True), (0., 1.))
        self.assertEqual(remplissages(150, False), (0., 1.))
        self.assertEqual(remplissages(0, True), (0., 0.))


class FausseManette:
    def __init__(self, etats):
        self.etats = list(etats)
        self.dernier = EtatManette()

    def lire_etat(self):
        if self.etats:
            self.dernier = self.etats.pop(0)
        return self.dernier


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Écran Tk requis')
class InterfacePilotageReelle(unittest.TestCase):
    def test_dessin_de_l_encart(self):
        import tkinter as tk
        from encart_commandes import EncartCommandes, VERT, FOND_CONNECTE, FOND_HORS_LIGNE
        racine = tk.Tk(); racine.geometry('420x300')
        try:
            e = EncartCommandes(racine); e.pack(fill='x'); racine.update()
            def vertes():
                return [e.coords(i) for i in e.find_all() if e.type(i) == 'rectangle' and e.itemcget(i, 'fill') == VERT]
            e.afficher(0, 0, 0, False); racine.update_idletasks()
            self.assertEqual(vertes(), [])
            self.assertEqual(e.cget('background'), FOND_HORS_LIGNE)
            e.afficher(100, 0, 0, True); racine.update_idletasks()
            self.assertEqual(e.cget('background'), FOND_CONNECTE)
            plein = vertes(); self.assertEqual(len(plein), 1)
            largeur_case = plein[0][2]-plein[0][0]
            self.assertGreater(largeur_case, 100)
            e.afficher(-50, 0, 0, True); racine.update_idletasks()
            demi = vertes(); self.assertEqual(len(demi), 1)       # recul : case de gauche, remplie depuis le centre
            self.assertAlmostEqual(demi[0][2]-demi[0][0], largeur_case/2, delta=1)
            self.assertLess(demi[0][0], plein[0][0])
            e.afficher(30, -30, 30, True, 'note'); racine.update_idletasks()
            self.assertEqual(len(vertes()), 3)
            textes = [e.itemcget(i, 'text') for i in e.find_all() if e.type(i) == 'text']
            self.assertIn('30 %', textes); self.assertIn('note', textes)
        finally:
            racine.destroy()

    def test_mode_test_sans_robot_clavier_manette_et_rb(self):
        from app import Atelier
        from encart_commandes import FOND_CONNECTE, FOND_HORS_LIGNE
        app = Atelier(); app.geometry('1500x950')
        try:
            app.onglets.select(app.wifi_cadre); app.update()
            self.assertIsNone(app.wifi_robot)
            app.wifi_pwm.set(60)
            app.wifi_actif.set(True); app.wifi_activer(); app.wifi_zone.focus_force(); app.update()
            self.assertTrue(app.wifi_actif.get())          # Activable sans robot.
            for touche in ('Up', 'a', 'Left'):
                app.wifi_zone.event_generate(f'<KeyPress-{touche}>')
            app.update(); app.wifi_pilotage()
            self.assertEqual(app.wifi_encart._valeurs, (60, 60, 60))
            self.assertFalse(app.wifi_encart._connecte)
            self.assertEqual(app.wifi_encart.cget('background'), FOND_HORS_LIGNE)
            self.assertIn('rien n’est envoyé', app.wifi_commande.get())
            app.wifi_zone.event_generate('<KeyRelease-Up>'); app.update(); app.wifi_pilotage()
            self.assertEqual(app.wifi_encart._valeurs, (0, 60, 60))
            app.wifi_zone.event_generate('<FocusOut>'); app.update()
            self.assertFalse(app.wifi_actif.get())          # Perte de focus : entrées désarmées.
            app.wifi_pilotage()
            self.assertEqual(app.wifi_encart._valeurs, (0, 0, 0))

            # Manette : stick gauche + stick droit proportionnels, RB bascule la cartographie.
            app.manette = FausseManette([
                EtatManette(True, .5, .0, -1., True, False, False),
                EtatManette(True, 0., 0., 0., True, True, False),      # RB pressé : pause
                EtatManette(True, 0., 0., 0., True, True, False),      # RB maintenu : rien de plus
                EtatManette(True, 0., 0., 0., True, False, False),     # relâché
                EtatManette(True, 0., 0., 0., True, True, False),      # RB pressé : reprise
                EtatManette(True, 0., 0., 0., False, False, False),    # sans LB
                EtatManette(False)])                                   # manette débranchée
            app.wifi_manette_active.set(True); app.wifi_activer_manette(); app.wifi_zone.focus_force(); app.update()
            self.assertTrue(app.wifi_manette_active.get())
            self.assertEqual(app.wifi_mode.get(), 'Cartographier')
            app.wifi_pilotage()
            self.assertEqual(app.wifi_encart._valeurs, (30, 0, -60))
            app.wifi_pilotage(); self.assertEqual(app.wifi_mode.get(), 'Localisation seule')
            self.assertFalse(app.wifi_cartographier.is_set())
            app.wifi_pilotage(); self.assertEqual(app.wifi_mode.get(), 'Localisation seule')
            app.wifi_pilotage(); app.wifi_pilotage()
            self.assertEqual(app.wifi_mode.get(), 'Cartographier'); self.assertTrue(app.wifi_cartographier.is_set())
            app.wifi_pilotage()
            self.assertIn('LB', app.wifi_encart._note)
            app.wifi_pilotage()
            self.assertFalse(app.wifi_manette_active.get())  # Manette absente : désarmée.
            self.assertEqual(app.wifi_encart._valeurs, (0, 0, 0))
        finally:
            app.destroy()

    def test_robot_connecte_commande_combinee_et_fond(self):
        from app import Atelier
        from robot_wifi import RobotWifi
        from test_wifi import FauxRobot
        from encart_commandes import FOND_CONNECTE
        fake = FauxRobot(); app = Atelier(); app.geometry('1500x950')
        def creer(hote):
            return RobotWifi('127.0.0.1', fake.udp.getsockname()[1], fake.tcp.getsockname()[1])
        def attendre(predicat, timeout=5.):
            fin = time.monotonic()+timeout
            while time.monotonic() < fin:
                app.update()
                if predicat():
                    return
                time.sleep(.01)
            self.fail('Événement UI absent : '+app.wifi_info.get())
        try:
            with patch('interface_wifi.RobotWifi', side_effect=creer):
                app.onglets.select(app.wifi_cadre); app.update(); app.wifi_connecter()
                attendre(lambda: app.wifi_etat is not None and app.wifi_etat.accepte)
                app.wifi_pwm.set(70)
                app.wifi_actif.set(True); app.wifi_activer(); app.wifi_zone.focus_force(); app.update()
                app.wifi_zone.event_generate('<KeyPress-Up>'); app.wifi_zone.event_generate('<KeyPress-Right>')
                attendre(lambda: (70, 0, -70) in fake.vecteurs)
                self.assertTrue(app.wifi_encart._connecte)
                self.assertEqual(app.wifi_encart.cget('background'), FOND_CONNECTE)
                self.assertEqual(app.wifi_encart._valeurs, (70, 0, -70))
                app.wifi_zone.event_generate('<KeyRelease-Right>')
                attendre(lambda: any(c == 'FORWARD' for _, c in fake.commandes[-3:]))   # Reste un seul axe : SA1 compatible.
                app.wifi_zone.event_generate('<KeyRelease-Up>')
                attendre(lambda: fake.commandes[-1][1] == 'STOP')
        finally:
            app.wifi_deconnecter(); app.destroy(); fake.fermer()

    def test_onglet_localisation_capture_et_reglages_icp_partages(self):
        from app import Atelier
        import tkinter as tk
        app = Atelier(); app.geometry('1500x950')
        try:
            def widgets(w):
                yield w
                for enfant in w.winfo_children():
                    yield from widgets(enfant)
            textes = [w.cget('text') for w in widgets(app) if isinstance(w, tk.Widget) and 'text' in w.keys()]
            self.assertIn('Capturer et localiser', textes)
            self.assertIn('▸ Réglages ICP', textes)
            for cle, defaut in [('icp_distance', .5), ('icp_iterations', 80), ('icp_fenetre_xy', 1.), ('icp_fenetre_angle', 30.)]:
                self.assertEqual(app.nombre(cle), defaut)
            methode, options = app.parametres_recalage('Recherche large + ICP')
            self.assertEqual((methode, options['fenetre_xy'], options['fenetre_angle'], options['iterations_max']),
                             ('Recherche large + ICP', 1., 30., 80))
            app.vars['icp_distance'].set('0.35')            # Un seul jeu de réglages pour toute l'application.
            self.assertEqual(app.parametres_recalage('ICP local')[1]['distance_max'], .35)
            self.assertEqual(app.vars['loc_methode'].get(), 'Recherche large + ICP')
            reference, nouveau = demonstration()
            nouveau.suivi_recalage = dict(valide=True)
            app.dessiner_capture_localisation(reference, [nouveau])
            ax = app.axes['TP Localisation']
            self.assertEqual(len(ax.collections), 2)
            self.assertEqual(ax.get_title(), 'Capture localisée sur le dernier scan')
            app.dessiner_capture_localisation(None, [nouveau])
            self.assertEqual(len(app.axes['TP Localisation'].collections), 1)
        finally:
            app.destroy()


class CaptureDepuisLocalisation(unittest.TestCase):
    def interface(self, methode='Recherche large + ICP'):
        from test_recalage_capture import CaptureInterface
        a = CaptureInterface().interface(auto=False)   # Case Acquisition décochée.
        a.vars['loc_methode'] = Variable(methode)
        a.methodes_demandees = []
        def parametres(methode=None):
            a.methodes_demandees.append(methode)
            return (methode or 'Recherche large + ICP'), {}
        a.parametres_recalage = parametres
        a.dessiner_capture_localisation = MagicMock()
        return a

    def lancer(self, a, **kw):
        from app import Atelier
        class Thread:
            def __init__(self, target, **kw): self.target = target
            def start(self): self.target()
        r, m = demonstration(); a.scans = [r]; a.inclus = [True]; a.visibles = [True]
        m.suivi_recalage = dict(valide=True, etat='recalage', message='ok')
        with patch('app.threading.Thread', Thread), patch('acquisition.capturer', return_value=[m]), \
             patch('app.recaler_capture', return_value=[m]) as recaler:
            Atelier.lancer_capture(a, **kw)
        return r, m, recaler

    def test_localisation_force_le_recalage_sur_le_dernier_scan(self):
        a = self.interface()
        r, m, recaler = self.lancer(a, depuis_localisation=True)
        recaler.assert_called_once()
        self.assertEqual(recaler.call_args.args[1].pose, r.pose)            # Référence = dernier scan.
        self.assertEqual(recaler.call_args.kwargs['methode'], 'Recherche large + ICP')
        self.assertEqual(a.methodes_demandees, ['Recherche large + ICP'])
        self.assertTrue(a.capture_depuis_localisation)

    def test_methode_choisie_dans_localisation(self):
        a = self.interface('ICP local')
        _, _, recaler = self.lancer(a, depuis_localisation=True)
        self.assertEqual(recaler.call_args.kwargs['methode'], 'ICP local')

    def test_acquisition_classique_inchangee(self):
        a = self.interface()
        _, _, recaler = self.lancer(a)
        recaler.assert_not_called()          # Case décochée : pas de localisation.
        self.assertFalse(a.capture_depuis_localisation)
        self.assertEqual(a.methodes_demandees, [])

    def test_resultat_trace_dans_localisation_sans_changer_d_onglet(self):
        from app import Atelier
        a = self.interface()
        r, m, _ = self.lancer(a, depuis_localisation=True)
        type_, data = [x for x in list(a.messages.queue) if x[0] == 'capture_recalee'][0]
        a.onglets = MagicMock()
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.recevoir_capture_recalee(a, data)
        avertir.assert_not_called()
        a.dessiner_capture_localisation.assert_called_once()
        reference, nouveaux = a.dessiner_capture_localisation.call_args.args
        self.assertIs(reference, r); self.assertEqual(len(nouveaux), 1)
        a.onglets.select.assert_not_called()
        self.assertEqual(len(a.scans), 2)
        self.assertIn('réussie', a.info_capture.texte)

    def test_echec_trace_puis_avertit(self):
        from app import Atelier
        a = self.interface()
        r, m, _ = self.lancer(a, depuis_localisation=True)
        m.suivi_recalage = dict(valide=False, etat='non_recale', message='Recouvrement insuffisant')
        ordre = []
        a.dessiner_capture_localisation = MagicMock(side_effect=lambda *x: ordre.append('dessin'))
        with patch('app.messagebox.showwarning', side_effect=lambda *x, **k: ordre.append('alerte')):
            data = [x for x in list(a.messages.queue) if x[0] == 'capture_recalee'][0][1]
            Atelier.recevoir_capture_recalee(a, data)
        self.assertEqual(ordre, ['dessin', 'alerte'])


if __name__ == '__main__':
    unittest.main()
