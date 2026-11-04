import copy
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from cartographie import demonstration
from localisation import ResultatICP, erreur_pose
from recalage_capture import recaler_capture


def resultat(pose, applicable=True, rmse=.02, recouvrement=.9):
    return ResultatICP(list(pose), [0,0,0], .2, rmse, recouvrement, 50, 5, .01,
                        applicable, applicable, 'résultat test')


class RecalageLot(unittest.TestCase):
    def test_premier_scan_ancre_sans_reference(self):
        r, m = demonstration()
        with patch('recalage_capture.recherche_icp', return_value=resultat(m.pose)) as calcul:
            lot = recaler_capture([r,m])
        self.assertEqual(lot[0].suivi_recalage['etat'], 'ancrage')
        self.assertTrue(lot[0].suivi_recalage['valide'])
        self.assertEqual(calcul.call_count,1)

    def test_chaine_references_et_non_mutation(self):
        r, m = demonstration(); n = copy.deepcopy(m); n.nom='suivant'
        p1, p2 = [.2,.3,5.], [.4,.6,10.]
        with patch('recalage_capture.recherche_icp', side_effect=[resultat(p1),resultat(p2)]) as calcul:
            lot = recaler_capture([m,n],r,mini=.05,maxi=12,intensite=0)
        self.assertEqual(calcul.call_args_list[0].kwargs['pose_initiale'],r.pose)
        self.assertEqual(calcul.call_args_list[1].kwargs['pose_initiale'],p1)
        self.assertIs(calcul.call_args_list[1].args[1],lot[0])
        self.assertEqual(lot[1].pose,p2)
        self.assertIsNone(m.suivi_recalage)
        self.assertIsNone(r.suivi_recalage)
        self.assertEqual(m.pose,[-.8,.4,15.])

    def test_echec_exception_ou_qualite_arrete_chaine(self):
        r,m=demonstration()
        for issue in [resultat([2,3,4],False),ValueError('trop peu de points')]:
            with self.subTest(issue=issue), patch('recalage_capture.recherche_icp',side_effect=[issue]) as calcul:
                lot=recaler_capture([m,copy.deepcopy(m)],r)
                self.assertEqual(calcul.call_count,1)
                self.assertTrue(all(not s.suivi_recalage['valide'] for s in lot))
                self.assertEqual(lot[0].pose,m.pose)

    def test_memes_criteres_que_localisation_manuelle(self):
        r,m=demonstration()
        for v in [resultat([.2,.3,4],rmse=.12),resultat([.2,.3,4],recouvrement=.55)]:
            with patch('recalage_capture.recherche_icp',return_value=v):
                lot=recaler_capture([m],r)
            self.assertTrue(lot[0].suivi_recalage['valide'])
            self.assertEqual(lot[0].pose,v.pose)

    def test_annulation_conserve_les_mesures(self):
        r,m=demonstration();e=threading.Event();e.set()
        with patch('recalage_capture.recherche_icp') as calcul:
            lot=recaler_capture([m],r,annuler=e)
        calcul.assert_not_called()
        self.assertEqual(len(lot),1)
        self.assertFalse(lot[0].suivi_recalage['valide'])

    def test_recalage_reel_sur_simulation(self):
        r,m=demonstration();vraie=list(m.pose);m.pose=[0,0,0]
        s=recaler_capture([m],r)[0]
        self.assertTrue(s.suivi_recalage['valide'])
        ep,ea=erreur_pose(s.pose,vraie)
        self.assertLess(ep,.01);self.assertLess(ea,.1)


