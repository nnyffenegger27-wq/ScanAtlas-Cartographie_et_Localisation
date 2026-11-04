"""Test Tk réel, optionnel : DISPLAY actif requis (Xvfb possible)."""
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch
from app import Atelier
from robot_wifi import RobotWifi
from test_wifi import FauxRobot


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Écran Tk requis')
class InterfaceWifiReelle(unittest.TestCase):
    def test_connexion_fleches_relachement_focus_onglet_deconnexion(self):
        fake=FauxRobot();app=Atelier();app.geometry('1500x950')
        def creer(hote):return RobotWifi('127.0.0.1',fake.udp.getsockname()[1],fake.tcp.getsockname()[1])
        def attendre(predicat,timeout=5.):
            fin=time.monotonic()+timeout
            while time.monotonic()<fin:
                app.update()
                if predicat():return
                time.sleep(.01)
            self.fail('Événement UI absent : '+app.wifi_info.get())
        def arme():
            app.wifi_actif.set(True);app.wifi_activer();app.wifi_zone.focus_force();app.update()
        try:
            titres=[app.onglets.tab(t,'text') for t in app.onglets.tabs()]
            self.assertEqual(titres.count('Localisation'),1)
            self.assertNotIn('TP Localisation',titres)
            self.assertEqual(titres,['Cartographie','Localisation','Robot en direct'])
            self.assertIn('Acquisition',[app.sous_onglets.tab(t,'text') for t in app.sous_onglets.tabs()])
            self.assertEqual(app.capture_source.get(),'USB')
            self.assertIn('tp_reference',app.vars)
            app.wifi_curseur_pwm.set(49)
            self.assertEqual(app.wifi_pwm.get(),49)
            with patch('interface_wifi.RobotWifi',side_effect=creer):
                app.onglets.select(app.wifi_cadre);app.update();app.wifi_connecter()
                attendre(lambda:app.wifi_etat is not None and app.wifi_etat.accepte)
                self.assertIn('%',app.wifi_metriques['concordance'].get())
                points=app.wifi_etat.points.copy()
                app.wifi_mode.set('Localisation seule');app.wifi_mode_changer()
                attendre(lambda:not app.wifi_etat.enrichissement)
                app.wifi_vue.set('Grille');app.wifi_actualiser_vue();app.update()
                self.assertTrue(app.wifi_image_grille.get_visible())
                self.assertGreater(app.wifi_canvas.get_tk_widget().winfo_width(),800)
                app.wifi_mode.set('Cartographier');app.wifi_mode_changer()
                fake.degrade=True
                attendre(lambda:not app.wifi_etat.accepte)
                arme();app.wifi_zone.event_generate('<KeyPress-Up>')
                attendre(lambda:fake.commandes and fake.commandes[-1][1]=='FORWARD')
                app.wifi_zone.event_generate('<KeyRelease-Up>')
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                fake.degrade=False
                attendre(lambda:app.wifi_etat.accepte)
                app.wifi_axes.set_xlim(-1,1);app.wifi_axes.set_ylim(-1,1)
                app.wifi_dessiner(app.wifi_etat)
                self.assertEqual(app.wifi_axes.get_xlim(),(-1,1))  # Le zoom n'est plus réinitialisé à chaque tour.
                arme();app.wifi_zone.event_generate('<KeyPress-Up>')
                attendre(lambda:any(c=='FORWARD' for _,c in fake.commandes))
                app.wifi_zone.event_generate('<KeyRelease-Up>')
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                arme();app.wifi_zone.event_generate('<KeyPress-Left>')
                attendre(lambda:fake.commandes[-1][1]=='LEFT')
                app.wifi_zone.event_generate('<FocusOut>');app.update()
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                self.assertTrue(app.wifi_actif.get())   # le robot s'arrête, la case reste cochée
                arme();app.wifi_zone.event_generate('<KeyPress-Down>')
                attendre(lambda:fake.commandes[-1][1]=='BACK')
                app.onglets.select(0);app.update()
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                app.onglets.select(app.wifi_cadre);app.update()
                app.wifi_centrer();app.update()
                if os.environ.get('SCANATLAS_SCREENSHOT'):
                    from PIL import ImageGrab
                    ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height()),xdisplay=os.environ['DISPLAY']).save(os.environ['SCANATLAS_SCREENSHOT'])
                app.wifi_deconnecter();self.assertIsNone(app.wifi_robot)
                self.assertIsNotNone(app.wifi_etat)
        finally:
            app.wifi_deconnecter();app.destroy();fake.fermer()


if __name__=='__main__':unittest.main()

