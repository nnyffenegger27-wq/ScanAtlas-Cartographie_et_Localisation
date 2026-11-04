"""Session directe sans interface : reconnexion automatique, démonstration quittable, consignes de pilotage."""
import time
import unittest
from unittest.mock import patch
import session_directe
from session_directe import SessionDirecte, Diffuseur, pourcentages
from document_carte import DocumentCarte
from robot_usb import RobotUsb
from test_usb_direct import FauxFirmware, FauxSerie


def attendre(predicat, delai=8.):
    fin = time.monotonic()+delai
    while time.monotonic() < fin:
        if predicat():
            return True
        time.sleep(.02)
    return False


class Pourcentages(unittest.TestCase):
    def test_puissance_et_rotation_max_sont_des_plafonds_independants(self):
        self.assertEqual(pourcentages(1, 0, 0, 60, 30), (60, 0, 0))
        self.assertEqual(pourcentages(0, 0, 1, 60, 30), (0, 0, 18))   # 30 % de la puissance
        self.assertEqual(pourcentages(-.5, .5, -1, 80, 50), (-40, 40, -40))
        self.assertEqual(pourcentages(0, 0, 0, 100, 100), (0, 0, 0))

    def test_valeurs_hors_limites_sont_ramenees(self):
        v = pourcentages(5, -5, 5, 60, 60)
        self.assertEqual(v, (60, -60, 36))


class Fixture(unittest.TestCase):
    def setUp(self):
        self.firmwares = []
        def fabrique(liaison, hote):
            fw = FauxFirmware(); self.firmwares.append(fw)
            return RobotUsb(hote, ouvrir=lambda port, s=FauxSerie(fw): s)
        self.doc = DocumentCarte()
        self.session = SessionDirecte(self.doc, Diffuseur(), fabrique_robot=fabrique)

    def tearDown(self):
        self.session.fermer()
        for fw in self.firmwares:
            fw.stop.set()


class Reconnexion(Fixture):
    def test_coupure_puis_reconnexion_avec_la_meme_carte(self):
        s = self.session
        s.connecter('usb', 'COM9')
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte), s.message)
        carte = s.carte
        with patch.object(session_directe, 'DELAI_RECONNEXION', .2):
            s.robot.arret.set()                                   # coupure subie, pas un clic sur Déconnecter
            self.assertTrue(attendre(lambda: s.robot is None))
            self.assertTrue(s.reconnexion_a is not None)         # une reconnexion est programmée
            self.assertIn('Reconnexion automatique', s.message)
            s.reconnexion_a = time.monotonic()                    # on court-circuite l'attente
            self.assertTrue(attendre(lambda: s.robot is not None))
        self.assertIs(s.carte, carte)                             # même carte de suivi
        s.deconnecter()                                           # un vrai clic annule tout
        self.assertEqual((s.tentatives, s.reconnexion_a, s.actif_demande), (0, None, False))

    def test_case_decochee_pas_de_reconnexion(self):
        s = self.session
        s.regler(reconnexion_auto=False)
        s.connecter('usb', 'COM9')
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte), s.message)
        s.robot.arret.set()
        self.assertTrue(attendre(lambda: s.robot is None))
        self.assertIsNone(s.reconnexion_a)
        self.assertFalse(s.actif_demande)

    def test_double_connexion_refusee(self):
        s = self.session
        s.connecter('usb', 'COM9')
        with self.assertRaises(ValueError):
            s.connecter('usb', 'COM9')


class Demonstration(Fixture):
    def test_on_peut_quitter_la_demonstration(self):
        s = self.session
        s.liaison, s.hote = 'usb', 'COM8'
        avant = self.doc.version
        s.demarrer_demo()
        self.assertIsNotNone(s.demo)
        self.assertEqual((s.liaison, s.hote), ('wifi', '127.0.0.1'))
        processus = s.demo['processus']
        # La démonstration utilise le vrai robot Wi-Fi simulé (fabrique par défaut), pas le faux firmware USB.
        s.fabrique_robot = SessionDirecte._fabrique_defaut
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte, 12), s.message)
        s.quitter_demo()
        self.assertIsNone(s.demo)
        self.assertIsNone(s.robot)
        self.assertEqual((s.liaison, s.hote), ('usb', 'COM8'))   # adresse d'avant rétablie
        self.assertEqual(len(self.doc.scans), 0)                  # la carte simulée ne reste pas
        processus.wait(timeout=5)                                 # le robot simulé est arrêté
        time.sleep(.6)
        self.assertIsNone(s.robot)                                # et ne se reconnecte pas tout seul


class Pilotage(Fixture):
    def test_consigne_perimee_devient_un_arret(self):
        s = self.session
        s.connecter('usb', 'COM9')
        self.assertTrue(attendre(lambda: s.pret()), s.message)
        envoyes = []
        robot = s.robot
        vrai_conduire, vrai_commander = robot.conduire, robot.commander
        robot.conduire = lambda *v: (envoyes.append(('DRIVE', v)), vrai_conduire(*v))
        robot.commander = lambda *v: (envoyes.append(v), vrai_commander(*v))
        s.piloter(1., 0., 0.)
        self.assertTrue(attendre(lambda: ('DRIVE', (60, 0, 0)) in envoyes))
        n = len(envoyes)
        time.sleep(session_directe.VALIDITE_CONSIGNE+.3)          # la page ne répond plus : plus aucune consigne fraîche
        self.assertTrue(any(e == ('DRIVE', (0, 0, 0)) for e in envoyes[n:]), envoyes[n:][:5])

    def test_consigne_invalide_refusee(self):
        with self.assertRaises(ValueError):
            self.session.piloter(float('nan'), 0, 0)


class ExplorationDansLaSession(Fixture):
    def demarrer(self):
        s = self.session
        s.demarrer_demo()
        s.fabrique_robot = SessionDirecte._fabrique_defaut       # vrai robot Wi-Fi simulé (processus + sockets)
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte and s.pret(), 15), s.message)
        return s

    def test_exploration_complete_de_la_salle_de_demonstration(self):
        s = self.demarrer()
        s.demarrer_auto()
        self.assertTrue(s.explorateur.actif)
        self.assertTrue(attendre(lambda: not s.explorateur.actif, 120), s.explorateur.message)
        self.assertEqual(s.explorateur.etat, 'termine', s.explorateur.message)
        self.assertGreater(s.dernier_etat.cles, 3)
        self.assertEqual(s.consigne, (0., 0., 0.))
        s.quitter_demo()

    def test_pilotage_manuel_reprend_la_main(self):
        s = self.demarrer()
        s.demarrer_auto()
        s.piloter(1., 0., 0.)
        self.assertEqual(s.explorateur.etat, 'inactif')
        self.assertIn('manuel', s.message)
        s.quitter_demo()

    def test_arret_et_deconnexion_arretent_l_exploration(self):
        s = self.demarrer()
        s.demarrer_auto(); s.arreter()
        self.assertFalse(s.explorateur.actif)
        s.demarrer_auto(); s.quitter_demo()
        self.assertFalse(s.explorateur.actif)

    def test_conditions_de_demarrage(self):
        s = self.session
        with self.assertRaises(ValueError):
            s.demarrer_auto()                                       # pas connecté
        with self.assertRaises(ValueError):
            s.replacer(0, 0, 0)

    def test_mode_localiser_interdit_l_exploration(self):
        s = self.demarrer()
        s.regler(mode='localiser')
        with self.assertRaises(ValueError):
            s.demarrer_auto()
        s.quitter_demo()

    def test_replacer_pendant_la_demo(self):
        s = self.demarrer()
        carte = s.carte
        pose = s.dernier_etat.trajectoire[-1]
        s.replacer(pose[0]+.2, pose[1]-.2, pose[2]+10.)             # indice proche : doit être confirmé sans perdre la carte
        self.assertTrue(attendre(lambda: carte.indice is None, 10))
        self.assertIs(s.carte, carte)
        s.quitter_demo()


if __name__ == '__main__':
    unittest.main()
