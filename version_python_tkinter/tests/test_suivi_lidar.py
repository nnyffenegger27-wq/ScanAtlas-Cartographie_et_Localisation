import unittest
import numpy as np
from suivi_lidar import composer,inverse,predire,ReferenceSuivi,icp_droites
from cartographie_direct import CarteDirecte
from robot_wifi import TrameScan
from localisation import erreur_pose
from simuler_robot_wifi import mesures_simulees


class SuiviAnalytique(unittest.TestCase):
    def test_composition_prediction_en_tournant_et_passage_180(self):
        a=np.array([1.,2.,179.]);delta=np.array([.1,0.,3.])
        b=composer(a,delta);attendu=composer(b,delta)
        np.testing.assert_allclose(composer(a,inverse(a)),[0,0,0],atol=1e-12)
        np.testing.assert_allclose(predire(a,b,1),attendu,atol=1e-12)
        np.testing.assert_allclose(predire(a,b,0),b,atol=1e-12)

    def test_mur_unique_ne_contraint_pas_translation_parallele(self):
        ref=ReferenceSuivi(np.column_stack([np.linspace(-3,3,200),np.ones(200)]))
        r=icp_droites(ref.fond,ref,[.2,.1,2.])
        self.assertFalse(r.applicable)

    def test_faux_points_isoles_normales_non_utilisees(self):
        p=np.array([[x,y] for x in range(4) for y in range(4)],float)
        ref=ReferenceSuivi(p)
        self.assertEqual(ref.valides.sum(),0)
        self.assertFalse(icp_droites(p,ref,[0,0,0]).applicable)

    def test_demi_tour_continu_et_translation(self):
        c=CarteDirecte();rng=np.random.default_rng(312)
        for i in range(105):
            vraie=[.004*i,.001*i,1.8*i]
            tr=TrameScan(i+1,1_000_000+i*100000,100000,mesures_simulees(vraie,rng))
            e=c.traiter(tr)
            self.assertTrue(e.accepte,e.message)
            ep,ea=erreur_pose(e.scan.pose,vraie)
            # Les tours simulés sont instantanés : la correction de mouvement les déforme de 1,8° au plus.
            self.assertLess(ep,.06);self.assertLess(ea,1.5)
        self.assertEqual(e.scans_cles[0].pose,[0.,0.,0.])
        self.assertEqual(len(c.historique_poses),2)

    def test_cache_reference_inchange_sans_nouveau_scan_cle(self):
        c=CarteDirecte();rng=np.random.default_rng(7)
        c.traiter(TrameScan(1,1_000_000,100000,mesures_simulees([0,0,0],rng)))
        ref=c.reference_locale
        e=c.traiter(TrameScan(2,1_100_000,100000,mesures_simulees([.01,0,.2],rng)))
        self.assertTrue(e.accepte,e.message)
        self.assertIs(c.reference_locale,ref)


if __name__=='__main__':unittest.main()
