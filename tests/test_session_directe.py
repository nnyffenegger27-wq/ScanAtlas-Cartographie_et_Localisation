"""Session directe sans interface : reconnexion automatique, démonstration quittable, consignes de pilotage."""
import time
import unittest
import numpy as np
from unittest.mock import patch
from atlas.robot import session_directe
from atlas.robot.session_directe import SessionDirecte, Diffuseur, pourcentages
from atlas.application.document_carte import DocumentCarte
from atlas.robot.robot_usb import RobotUsb
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


class ScanManuel(Fixture):
    def prendre(self, delai=25.):
        """Roule doucement (le suivi d'un robot immobile dans la simulation parfaite est refusé : scène sans bruit) puis demande le scan."""
        s = self.session; fin = time.monotonic()+delai
        while time.monotonic() < fin:
            s.piloter(.5, 0., 0.)
            try:
                s.prendre_scan(); s.piloter(0., 0., 0.); return
            except ValueError:
                time.sleep(.1)
        self.fail('suivi jamais accepté : '+s.message)

    def test_refus_sans_robot(self):
        with self.assertRaises(ValueError):
            self.session.prendre_scan()

    def test_en_mode_localiser_la_carte_ne_grossit_que_sur_demande(self):
        s = self.session
        s.demarrer_demo('salle')
        s.fabrique_robot = SessionDirecte._fabrique_defaut       # vrai robot Wi-Fi simulé (processus + sockets), qui bouge vraiment
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte and s.pret(), 15), s.message)
        s.regler(mode='localiser')
        self.assertTrue(attendre(lambda: s.pret() and s.dernier_etat is not None and s.dernier_etat.accepte), s.message)
        cles = len(s.carte.cles)
        s.piloter(.5, 0., 0.); time.sleep(1.)
        self.assertEqual(len(s.carte.cles), cles)                 # localiser : rien n'est ajouté tout seul
        self.prendre()
        self.assertTrue(attendre(lambda: s.carte.nb_manuels == 1), s.message)
        self.assertEqual(len(s.carte.cles), cles+1)
        self.assertTrue(s.carte.cles[-1].nom.startswith('Manuel 1'), s.carte.cles[-1].nom)
        self.assertIn('Scan manuel 1 ajouté', ' '.join(m['texte'] for m in s.messages))
        self.prendre(); self.assertTrue(attendre(lambda: s.carte.nb_manuels == 2), s.message)
        self.assertEqual(len(s.carte.cles), cles+2)               # un scan par demande, même à l'arrêt
        s.quitter_demo()

    def test_demande_abandonnee_si_la_position_n_est_pas_suivie(self):
        s = self.session
        s.connecter('usb', 'COM9')
        self.assertTrue(attendre(lambda: s.dernier_etat is not None and s.dernier_etat.accepte), s.message)
        with patch('atlas.calcul.cartographie_direct.DELAI_SCAN_MANUEL', 0.):
            s.carte.demander_scan_manuel()
            time.sleep(.05)
            self.assertTrue(attendre(lambda: any('abandonné' in m['texte'] for m in s.messages)), s.messages[-3:])
        self.assertEqual(s.carte.nb_manuels, 0)


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


class ChoixDeLaSalle(Fixture):
    def test_salle_inconnue_refusee(self):
        with self.assertRaises(ValueError):
            self.session.demarrer_demo('palais')
        self.assertIsNone(self.session.demo)

    def test_etat_public_liste_les_salles(self):
        e = self.session.etat_public()
        self.assertIn('appartement', [x['id'] for x in e['salles']])
        self.assertIsNone(e['salle_demo'])

    def test_l_appartement_est_la_salle_par_defaut_et_le_robot_y_est(self):
        s = self.session
        s.demarrer_demo()
        s.fabrique_robot = SessionDirecte._fabrique_defaut
        self.assertEqual(s.etat_public()['salle_demo'], 'appartement')
        self.assertTrue(attendre(lambda: s.dernier_etat is not None, 15), s.message)
        scan = s.dernier_etat.scan
        angles = (scan.mesures[:, 0]-scan.angle_reference-180+180) % 360-180                # écart à la direction arrière
        derriere = scan.mesures[np.argmin(np.abs(angles))]                                   # mesure à 180° : mur ouest
        self.assertAlmostEqual(derriere[1], 2.0, delta=.1)           # départ en (2 ; 4,6) dans l'appartement (3 m dans la petite salle)
        s.quitter_demo()


class CoupuresDeLiaison(Fixture):
    """Trous de liaison Wi-Fi simulés (1,4 s toutes les 4 s) : le robot repart seul si la touche reste tenue, la pause est
    expliquée dans le journal (PC réactif ou bloqué) et le suivi n'est pas déclaré perdu pour longtemps."""
    def test_le_pilotage_reprend_seul_apres_chaque_trou(self):
        import os
        s = self.session
        with patch.dict(os.environ, {'SCANATLAS_SIM_COUPURES': '4,1.4'}):
            s.demarrer_demo('salle')
        s.fabrique_robot = SessionDirecte._fabrique_defaut
        try:
            self.assertTrue(attendre(lambda: s.pret(), 20), s.message)
            s.reglages['puissance'] = 40
            debut, positions = time.monotonic(), []
            while time.monotonic()-debut < 14:
                s.piloter(0, 1 if int(time.monotonic()-debut) % 8 < 4 else -1, 0)       # va-et-vient, touche toujours tenue
                time.sleep(.06)
                if s.dernier_etat is not None:
                    positions.append((time.monotonic()-debut, s.dernier_etat.scan.pose[1]))
            for t0 in (6., 10.):                         # après le deuxième et le troisième trou, le robot avance de nouveau
                fenetre = [y for t, y in positions if t0 <= t <= t0+2.]
                self.assertGreater(max(fenetre)-min(fenetre), .1, t0)
            journal = (s.journal.dossier/'evenements.log').read_text(encoding='utf-8')
            self.assertIn('PC réactif', journal)
            self.assertNotIn('Robot sans réponse', journal)
        finally:
            s.quitter_demo()


class LectureDuSignalWifi(unittest.TestCase):
    def test_netsh_en_francais_et_en_anglais(self):
        from atlas.robot.robot_wifi import lire_signal_wifi
        fr = "    Nom                    : Wi-Fi\n    SSID                   : ScanAtlas\n    Canal                  : 6\n    Signal                 : 74%\n"
        en = "    SSID                   : ScanAtlas\n    Channel                : 11\n    Signal                 : 100%\n"
        self.assertEqual(lire_signal_wifi(fr), (74, 6, 'ScanAtlas'))
        self.assertEqual(lire_signal_wifi(en), (100, 11, 'ScanAtlas'))
        self.assertIsNone(lire_signal_wifi('pas de réseau'))


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
        s.demarrer_demo('salle')                                  # la petite salle : l'exploration y tient en temps réel
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
