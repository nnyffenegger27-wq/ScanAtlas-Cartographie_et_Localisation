import copy
import queue
import threading
import unittest
from types import SimpleNamespace,MethodType
from unittest.mock import patch
import numpy as np
from atlas.calcul.cartographie import demonstration,Grille
from atlas.calcul.localisation_tp import ReferenceGrille,ReferenceVectorielle,ReferenceScan,localiser_sur_reference,LOCALE,MULTI
from atlas.calcul.localisation import erreur_pose
from atlas.calcul.evaluer_tp_jour2 import construire_references


class DistancesReferences(unittest.TestCase):
    def test_segments_finis_pas_droites_infinies(self):
        v=ReferenceVectorielle([[[0,0],[1,0]]])
        p=np.array([[.5,.2],[2,0],[-1,1]],float)
        np.testing.assert_allclose(v.distance(p),[.2,1,np.sqrt(2)])
        for mauvais in [[],[[[0,0],[0,0]]],[[[0,0],[float('nan'),0]]]]:
            with self.assertRaises(ValueError):ReferenceVectorielle(mauvais)

    def test_champ_grille_depend_cellules_occupees(self):
        g=Grille(np.array([0.,0.]),.1,np.zeros((10,10)),np.zeros((10,10),bool))
        g.log_odds[4,5]=1;g.log_odds[4,6]=1;g.log_odds[4,7]=1;g.observe[4,5:8]=True
        r=ReferenceGrille(g)
        self.assertAlmostEqual(r.distance(np.array([[.55,.45]]))[0],0)
        self.assertGreater(r.distance(np.array([[-2.,-2.]]))[0],.5)
        g.log_odds[:]=0
        self.assertAlmostEqual(r.distance(np.array([[.55,.45]]))[0],0) # copie figée
        with self.assertRaises(ValueError):ReferenceGrille(g)

    def test_moins_de_douze_points_scan_refuse(self):
        r=demonstration()[0];r.mesures=r.mesures[:5]
        with self.assertRaises(ValueError):ReferenceScan(r)

class LocalisationTroisTypes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref,cls.mobile=demonstration();cls.modeles,_,_=construire_references(cls.ref)

    def test_six_combinaisons_retournent_pose_connue_sans_mutation(self):
        mesures=self.mobile.mesures.copy();pose=list(self.mobile.pose)
        for modele,_ in self.modeles:
            for methode in [LOCALE,MULTI]:
                with self.subTest(reference=modele.type,methode=methode):
                    r=localiser_sur_reference(self.mobile,modele,methode,pose_initiale=(np.array(pose)+[.1,-.1,2]).tolist())
                    self.assertTrue(r.applicable,r.message)
                    ep,ea=erreur_pose(r.pose,pose);self.assertLess(ep,.1);self.assertLess(ea,2)
                    self.assertGreater(r.duree,0)
        np.testing.assert_array_equal(self.mobile.mesures,mesures);self.assertEqual(self.mobile.pose,pose)

    def test_mauvaise_pose_et_annulation_ne_sont_pas_acceptees(self):
        modele=self.modeles[0][0];e=threading.Event();e.set()
        r=localiser_sur_reference(self.mobile,modele,annuler=e)
        self.assertFalse(r.applicable);self.assertEqual(r.pose,self.mobile.pose)
        r=localiser_sur_reference(self.mobile,modele,LOCALE,pose_initiale=[100,100,90])
        self.assertFalse(r.applicable)

    def test_une_seule_droite_ne_localise_pas_trois_etats(self):
        v=ReferenceVectorielle([[[-10,0],[10,0]]]);m=copy.deepcopy(self.mobile)
        x=np.linspace(-2,2,100);p=np.column_stack([x,np.ones(100)*.1]);a=np.rad2deg(np.arctan2(p[:,1],p[:,0]))
        m.mesures=np.column_stack([a,np.linalg.norm(p,axis=1),np.full(100,220)]);m.pose=[0,0,0]
        r=localiser_sur_reference(m,v,LOCALE)
        self.assertFalse(r.applicable)



class Evaluation(unittest.TestCase):
    def test_annulation_ne_remplace_pas_csv(self):
        from atlas.calcul.evaluer_tp_jour2 import evaluer
        import tempfile
        from pathlib import Path
        e=threading.Event();e.set()
        with tempfile.TemporaryDirectory() as dossier:
            p=Path(dossier)/'ancien.csv';p.write_text('ancien résultat')
            with self.assertRaises(InterruptedError):evaluer(p,annuler=e)
            self.assertEqual(p.read_text(),'ancien résultat')
