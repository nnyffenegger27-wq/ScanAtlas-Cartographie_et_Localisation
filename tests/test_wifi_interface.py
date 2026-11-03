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
            with patch('interface_wifi.RobotWifi',side_effect=creer):
                app.onglets.select(app.wifi_cadre);app.update();app.wifi_connecter()
                attendre(lambda:app.wifi_etat is not None and app.wifi_etat.accepte)
                arme();app.wifi_zone.event_generate('<KeyPress-Up>')
                attendre(lambda:any(c=='FORWARD' for _,c in fake.commandes))
                app.wifi_zone.event_generate('<KeyRelease-Up>')
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                arme();app.wifi_zone.event_generate('<KeyPress-Left>')
                attendre(lambda:fake.commandes[-1][1]=='LEFT')
                app.wifi_zone.event_generate('<FocusOut>');app.update()
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                self.assertFalse(app.wifi_actif.get())
                arme();app.wifi_zone.event_generate('<KeyPress-Down>')
                attendre(lambda:fake.commandes[-1][1]=='BACK')
                app.onglets.select(0);app.update()
                attendre(lambda:fake.commandes[-1][1]=='STOP')
                app.onglets.select(app.wifi_cadre);app.update()
                if os.environ.get('SCANATLAS_SCREENSHOT'):
                    from PIL import ImageGrab
                    ImageGrab.grab(xdisplay=os.environ['DISPLAY']).save(os.environ['SCANATLAS_SCREENSHOT'])
                app.wifi_deconnecter();self.assertIsNone(app.wifi_robot)
                self.assertIsNotNone(app.wifi_etat)
        finally:
            app.wifi_deconnecter();app.destroy();fake.fermer()


if __name__=='__main__':unittest.main()
