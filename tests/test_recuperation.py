"""Perte de suivi : récupération automatique, nouvel essai d'ouverture du port, reconnexion automatique."""
import os
import time
import unittest
from unittest.mock import patch
from cartographie_direct import CarteDirecte
from localisation import erreur_pose
from robot_usb import RobotUsb
from test_wifi import trame_pose
from test_usb_direct import FauxFirmware, FauxSerie, attendre, messages


def carte_suivie():
    c = CarteDirecte()
    for i in range(1, 8):
        e = c.traiter(trame_pose([i*.02, 0, i], i))
    assert e.accepte, e.message
    return c


def rejouer(c, pose, tours, **options):
    """Tours à 10 Hz sur le PC (les limites de cadence de la carte suivent l'horloge réelle)."""
    resultats = []
    for k in range(tours):
        time.sleep(.1)
        resultats.append(c.traiter(trame_pose(pose, 8+k), **options))
        if resultats[-1].accepte and k > 2:
            break
    return resultats


class RecuperationAutomatique(unittest.TestCase):
    def test_saut_de_pose_retrouve_sans_action_de_l_utilisateur(self):
        c = carte_suivie()
        vrai = [1.3, .5, 70.]                                  # téléportation : le suivi local ne peut plus suivre
        resultats = rejouer(c, vrai, 120)
        self.assertTrue(resultats[-1].accepte, resultats[-1].message)
        self.assertFalse(resultats[0].accepte)                  # il a bien été perdu d'abord
        self.assertTrue(any('Perdu depuis' in r.message for r in resultats))
        self.assertTrue(any('Position retrouvée' in r.message for r in resultats))
        ep, ea = erreur_pose(c.pose, vrai)
        self.assertLess(ep, .1); self.assertLess(ea, 3)

    def test_desactivee_le_robot_reste_perdu(self):
        c = carte_suivie(); c.recup_auto = False
        resultats = rejouer(c, [1.3, .5, 70.], 22)
        self.assertFalse(any(r.accepte for r in resultats))

    def test_message_de_refus_avec_raison(self):
        c = carte_suivie()
        e = c.traiter(trame_pose([3., 2., 120.], 8))
        self.assertFalse(e.accepte)
        self.assertIn('Recalage refusé', e.message)


class OuverturePortEtReconnexion(unittest.TestCase):
    def test_port_pas_encore_disponible_nouvel_essai(self):
        firmware = FauxFirmware(); serie = FauxSerie(firmware)
        essais = []
        def ouvrir(port):
            essais.append(port)
            if len(essais) < 3:
                raise PermissionError(13, 'Accès refusé.', None, 5)    # le port revient après le redémarrage
            return serie
        robot = RobotUsb('COM9', ouvrir=ouvrir, attente_port=5.)
        try:
            robot.demarrer()
            self.assertTrue(attendre(robot.connecte.is_set, 8))
            self.assertEqual(len(essais), 3)
            self.assertTrue(any('nouvel essai' in m for m in messages(robot)))
        finally:
            robot.fermer(); firmware.stop.set()

    def test_port_toujours_refuse_apres_le_delai(self):
        def ouvrir(port):
            raise PermissionError(13, 'Accès refusé.', None, 5)
        robot = RobotUsb('COM9', ouvrir=ouvrir, attente_port=.6)
        robot.demarrer()
        self.assertTrue(attendre(robot.arret.is_set, 5))
        self.assertFalse(robot.connecte.is_set())
        robot.fermer()


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Écran Tk requis')
class ReconnexionAutomatique(unittest.TestCase):
    def test_coupure_puis_reconnexion_avec_la_meme_carte(self):
        from app import Atelier
        app = Atelier(); app.geometry('1500x950')
        firmwares = []
        def fabrique(hote):
            fw = FauxFirmware(); firmwares.append(fw)
            return RobotUsb(hote, ouvrir=lambda port, s=FauxSerie(fw): s)
        try:
            app.onglets.select(app.wifi_cadre); app.update()
            app.wifi_liaison.set('USB filaire'); app.wifi_liaison_changer(); app.wifi_hote.set('COM9')
            with patch('interface_wifi.RobotUsb', side_effect=fabrique):
                app.wifi_connecter()
                fin = time.monotonic()+6
                while time.monotonic() < fin and not (app.wifi_etat is not None and app.wifi_etat.accepte):
                    app.update(); time.sleep(.01)
                self.assertTrue(app.wifi_etat is not None and app.wifi_etat.accepte)
                carte = app.wifi_carte
                app.wifi_robot.arret.set()                       # coupure subie (pas un clic sur Déconnecter)
                fin = time.monotonic()+3
                while time.monotonic() < fin and app.wifi_robot is not None:
                    app.update(); time.sleep(.01)
                self.assertIsNone(app.wifi_robot)
                self.assertIsNotNone(app.wifi_relance)           # une reconnexion est programmée
                self.assertIn('Reconnexion automatique', app.wifi_info.get())
                app.wifi_reconnecter()                           # (le délai de 3 s est court-circuité)
                self.assertIsNotNone(app.wifi_robot)
                self.assertIs(app.wifi_carte, carte)             # même carte
                app.wifi_deconnecter()                           # un vrai clic annule tout
                self.assertEqual(app.wifi_tentatives, 0)
        finally:
            app.wifi_deconnecter(); app.destroy()
            for fw in firmwares:
                fw.stop.set()

    def test_case_de_reconnexion_desactivee(self):
        from app import Atelier
        app = Atelier()
        try:
            app.wifi_auto_connexion.set(False)
            app.wifi_robot = None
            app.wifi_reconnecter()
            self.assertIsNone(app.wifi_robot)
        finally:
            app.destroy()


if __name__ == '__main__':
    unittest.main()
