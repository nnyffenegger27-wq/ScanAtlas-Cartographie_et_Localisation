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


class PeriodeDeVerification(unittest.TestCase):
    """Après une position retrouvée, la carte n'est enrichie qu'une fois le suivi redevenu normal."""
    def suite(self, c, depart, pas, n, seq0):
        sortie = []
        for k in range(n):
            time.sleep(.1)
            avant = len(c.cles)
            e = c.traiter(trame_pose([depart[0]+pas*(k+1), depart[1], depart[2]], seq0+k))
            sortie.append((e.accepte, len(c.cles)-avant, e.message))
        return sortie

    def test_position_360_puis_cartographie_reprend_sans_scan_clef_douteux(self):
        c = carte_suivie()
        c.relocaliser()                                        # bouton « Position 360° »
        vrai = [1.3, .5, 70.]
        e = None
        for k in range(10):
            time.sleep(.1)
            e = c.traiter(trame_pose(vrai, 8+k))
            if e.accepte:
                break
        suivant = 9+k
        self.assertTrue(e.accepte, e.message)
        self.assertIn('Position retrouvée', e.message)
        ep, ea = erreur_pose(c.pose, vrai)
        self.assertLess(ep, .1); self.assertLess(ea, 3)
        cles = len(c.cles)
        resultats = self.suite(c, vrai, .2, 8, suivant)             # le robot repart à 2 m/s (pire cas) : suivi normal
        self.assertTrue(all(a for a, _, _ in resultats), resultats)
        # Pendant la vérification : aucun scan clé, message explicite ; ensuite la carte s'enrichit de nouveau.
        self.assertTrue(all(n == 0 for _, n, _ in resultats[:3]), resultats)
        self.assertIn('non enrichie', resultats[0][2])
        self.assertGreater(len(c.cles), cles)

    def test_trou_de_liaison_aussi_surveille(self):
        c = carte_suivie()
        c.pose_cle = c.pose.copy()
        # Tour reçu après un trou de 0,9 s (liaison coupée un instant) : suivi accepté mais pas de scan clé.
        time.sleep(.1)
        e = c.traiter(trame_pose([.2, 0, 8], 8, fin=1_000_000+7*100000+900_000))
        if e.accepte:
            self.assertIn('non enrichie', e.message)

    def test_reprise_explicite_surveillee(self):
        c = carte_suivie()
        c.reprendre()
        time.sleep(.1)
        e = c.traiter(trame_pose(c.pose, 8))
        self.assertTrue(e.accepte, e.message)
        self.assertEqual(c.probation, 3)


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
                self.assertTrue(app.wifi_etat is not None and app.wifi_etat.accepte,
                                (app.wifi_info.get(), getattr(app.wifi_etat, 'message', None)))
                carte = app.wifi_carte
                app.wifi_robot.arret.set()                       # coupure subie (pas un clic sur Déconnecter)
                fin = time.monotonic()+3
                while time.monotonic() < fin and app.wifi_robot is not None:
                    app.update(); time.sleep(.01)
                self.assertIsNone(app.wifi_robot)
                self.assertIsNotNone(app.wifi_relance)           # une reconnexion est programmée
                self.assertIn('Reconnexion automatique', app.wifi_info.get())
                app.wifi_reconnecter()                           # (le délai de 3 s est court-circuité)
                fin = time.monotonic()+4                         # le calcul précédent peut finir encore un instant
                while time.monotonic() < fin and app.wifi_robot is None:
                    app.update(); time.sleep(.01)
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


def trame_en_rotation(pose_fin, omega, sequence, duree=.1):
    """Tour lidar réaliste d'un robot qui tourne : chaque rayon est mesuré à son instant, donc déformé."""
    import numpy as np
    from robot_wifi import TrameScan
    from test_wifi import salle
    relatif = salle()-np.asarray(pose_fin[:2])
    phi = np.degrees(np.arctan2(relatif[:, 1], relatif[:, 0])); r = np.linalg.norm(relatif, axis=1)
    f = ((phi-pose_fin[2]) % 360)/360
    for _ in range(8):
        angle = (phi-pose_fin[2]+omega*(1-f)*duree) % 360
        f = angle/360
    o = np.argsort(f)
    return TrameScan(sequence, 1_000_000+sequence*100000, int(duree*1e6),
                     np.column_stack([angle[o], r[o], np.full(len(r), 230.)]))


class RotationRapide(unittest.TestCase):
    def test_tour_redresse_et_suivi_conserve_a_150_degres_par_seconde(self):
        c = carte_suivie()
        yaw, pire, perdus = 7., 0., 0                         # cap de départ de carte_suivie()
        for k in range(20):
            w = 150*min(1., (k+1)/6)                      # montée en vitesse sur 0,6 s
            yaw = ((yaw+w*.1)+180) % 360-180
            time.sleep(.1)
            e = c.traiter(trame_en_rotation([.14, 0, yaw], w, 8+k))
            perdus += not e.accepte
            pire = max(pire, erreur_pose(c.pose, [0, 0, yaw])[1])
        self.assertEqual(perdus, 0)
        self.assertLess(pire, 4.)

    def test_correction_neutre_a_l_arret_et_inverse_du_mouvement(self):
        import numpy as np
        from suivi_lidar import corriger_mouvement
        m = np.column_stack([np.linspace(0, 359, 360), np.full(360, 2.), np.full(360, 200.)])
        np.testing.assert_allclose(corriger_mouvement(m, 0., np.zeros(2), .1), m, atol=1e-9)
        c = corriger_mouvement(m, 100., np.zeros(2), .1)
        self.assertAlmostEqual(c[-1, 0], m[-1, 0], places=6)          # le dernier point est à l'instant de référence
        self.assertAlmostEqual(abs((c[0, 0]-m[0, 0]+180) % 360-180), 10., places=6)  # le premier, 10° plus tôt
        np.testing.assert_allclose(c[:, 1], 2., atol=1e-9)             # une rotation pure ne change pas les distances


@unittest.skipUnless(os.environ.get('DISPLAY'), 'Écran Tk requis')
class PlafondDeRotation(unittest.TestCase):
    def test_la_rotation_est_plafonnee_par_defaut(self):
        from app import Atelier
        app = Atelier(); app.geometry('1500x950')
        try:
            app.onglets.select(app.wifi_cadre); app.update()
            self.assertEqual(app.wifi_yaw_max.get(), 60)
            app.wifi_pwm.set(80)
            app.wifi_actif.set(True); app.wifi_activer(); app.wifi_zone.focus_force(); app.update()
            for touche in ('z', 'a'):
                app.wifi_zone.event_generate(f'<KeyPress-{touche}>')
            app.update(); app.wifi_pilotage()
            self.assertEqual(app.wifi_encart._valeurs, (80, 0, 48))      # avance 80 %, rotation 60 % de 80 %
        finally:
            app.destroy()
