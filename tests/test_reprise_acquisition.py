import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
from test_wifi import FauxRobot, trame_pose
from cartographie_direct import CarteDirecte
from robot_wifi import RobotWifi
from acquisition import capturer_wifi

class RepriseAcquisition(unittest.TestCase):
    def test_reprise_automatique_sans_contamination(self):
        c=CarteDirecte()
        with patch('cartographie_direct.perf_counter',return_value=10.):
            a=c.traiter(trame_pose([0,0,0],1))
            mauvais=trame_pose([0,0,0],2);mauvais.mesures[:,1]=0
            b=c.traiter(mauvais)
            attente=c.traiter(trame_pose([0,0,0],3))
        self.assertFalse(b.accepte);self.assertTrue(np.isnan(attente.concordance))
        np.testing.assert_array_equal(a.points,b.points)
        with patch('cartographie_direct.perf_counter',return_value=11.):
            r=c.traiter(trame_pose([.02,0,1],40))
        self.assertTrue(r.accepte,r.message);self.assertFalse(c.perdu)
        self.assertEqual(r.scans_cles[0].pose,[0.,0.,0.])

    def test_reprise_explicite_apres_redemarrage_horloge(self):
        c=CarteDirecte();c.traiter(trame_pose([0,0,0],100))
        c.reprendre();r=c.traiter(trame_pose([.1,0,2],1))
        self.assertTrue(r.accepte,r.message)

    def test_acquisition_wifi_brute_meme_sans_geometrie(self):
        f=FauxRobot();f.degrade=True
        try:
            scans=capturer_wifi('127.0.0.1',2,threading.Event(),lambda s:None,
                port_commande=f.udp.getsockname()[1],port_scans=f.tcp.getsockname()[1])
            self.assertEqual(len(scans),2)
            self.assertTrue(all(np.all(s.mesures[:,1]==0) for s in scans))
            self.assertTrue(all(cmd=='STOP' for _,cmd in f.commandes))
        finally:f.fermer()

    def test_acquittement_effectif_distinct_commande(self):
        f=FauxRobot(force_stop=True)
        r=RobotWifi('127.0.0.1',f.udp.getsockname()[1],f.tcp.getsockname()[1])
        try:
            r.demarrer();fin=time.monotonic()+3
            while time.monotonic()<fin:
                r.commander('FORWARD')
                d=r.diagnostic_commande()
                if d['envoyee']=='FORWARD' and d['effective']=='STOP':break
                time.sleep(.02)
            else:self.fail('Acquittement attendu absent')
        finally:r.fermer();f.fermer()
