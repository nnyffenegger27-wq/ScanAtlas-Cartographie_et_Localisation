import copy
import unittest
from unittest.mock import patch
import numpy as np
from cartographie import demonstration
from localisation import (ReferencePoints, sous_carte, valider_solution, ResultatICP, recherche_icp, erreur_pose)
from recalage_capture import recaler_lot


def resultat(pose, applicable=True):
    return ResultatICP(list(pose),list(pose),0,0,1,100,1,0,True,applicable,'test')

class Robustesse(unittest.TestCase):
    def test_sous_carte_equilibre_doublons_sans_modifier_mesures(self):
        r,m=demonstration();mesures=r.mesures.copy()
        a=sous_carte([r],dict(mini=.05,maxi=12,intensite=0))
        b=sous_carte([r,copy.deepcopy(r)],dict(mini=.05,maxi=12,intensite=0))
        np.testing.assert_allclose(a.points,b.points)
        np.testing.assert_array_equal(r.mesures,mesures)

    def test_glissement_murs_paralleles_refuse(self):
        x=np.linspace(-3,3,120)
        cible=np.vstack([np.column_stack([x,np.ones(120)]),np.column_stack([x,-np.ones(120)])])
        r=valider_solution(resultat([0,0,0]),cible,cible,.5)
        self.assertFalse(r.applicable)
        self.assertIn('parallèles',r.message)

    def test_accord_large_ne_suffit_pas(self):
        r,m=demonstration()
        from localisation import points_filtres
        p=points_filtres(r,dict(mini=.05,maxi=12,intensite=0))
        test=valider_solution(resultat([0,0,0]),p,p+[.3,.3],.5)
        self.assertFalse(test.applicable)

    def test_reference_lot_ne_contient_pas_scan_refuse(self):
        r,m=demonstration();n=copy.deepcopy(m);n.nom='troisième'
        with patch('recalage_capture.recaler_capture') as calcul:
            mauvais=copy.deepcopy(m);mauvais.suivi_recalage={'valide':False,'message':'échec'}
            bon=copy.deepcopy(n);bon.pose=[.2,.3,4];bon.suivi_recalage={'valide':True}
            calcul.side_effect=[[mauvais],[bon]]
            lot=recaler_lot([r,m,n])
        self.assertEqual(len(calcul.call_args_list[1].kwargs['historique']),1)
        self.assertEqual(lot[1].pose,m.pose)
        self.assertEqual(lot[2].pose,[.2,.3,4])
        self.assertIsNone(r.suivi_recalage)

    def test_grande_translation_rotation_acceptee(self):
        r,m=demonstration();vraie=list(m.pose)
        rcalc=recherche_icp(m,r,pose_initiale=(np.array(vraie)+[.7,.4,20]).tolist())
        self.assertTrue(rcalc.applicable,rcalc.message)
        ep,ea=erreur_pose(rcalc.pose,vraie)
        self.assertLess(ep,.1);self.assertLess(ea,2)

    def test_pose_connue_ne_guide_pas_calcul(self):
        r,m=demonstration();m.pose_connue=[500,500,90]
        avant=recherche_icp(m,r)
        m.pose_connue=[-500,-500,-90]
        apres=recherche_icp(m,r)
        np.testing.assert_allclose(avant.pose,apres.pose)


class Ambiguite(unittest.TestCase):
    def test_salle_carree_refuse_orientations_equivalentes(self):
        from cartographie import Scan
        angles=np.arange(360.);a=np.deg2rad(angles)
        d=2/np.maximum(abs(np.cos(a)),abs(np.sin(a)))
        r=Scan('carré',np.column_stack([angles,d,np.full(360,220)]),[0,0,0],'SIMULATION',0.)
        m=copy.deepcopy(r);m.pose=[0,0,90]
        calcul=recherche_icp(m,r,fenetre_angle=90)
        self.assertFalse(calcul.applicable)
        self.assertIn('ambigu',calcul.message)
