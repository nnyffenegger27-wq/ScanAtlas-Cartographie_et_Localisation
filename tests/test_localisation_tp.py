import copy
import queue
import threading
import unittest
from types import SimpleNamespace,MethodType
from unittest.mock import patch
import numpy as np
from cartographie import demonstration,Grille
from localisation_tp import ReferenceGrille,ReferenceVectorielle,ReferenceScan,localiser_sur_reference,LOCALE,MULTI
from localisation import erreur_pose
from evaluer_tp_jour2 import construire_references
from app import Atelier
from interface_tp import InterfaceTP
from test_interface_sans_ecran import Variable


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

class InterfaceReference(unittest.TestCase):
    def interface(self,type_ref='Grille'):
        r,m=demonstration();modeles,g,v=construire_references(r)
        class Choix:
            def current(self):return 0
        class Label:
            def configure(self,**kw):self.texte=kw['text']
        a=SimpleNamespace(scans=[r,m],inclus=[True,False],visibles=[True,True],grille=g,vecteurs=v,
            scans_grille={id(r)},scans_vecteurs={id(r)},choix_reference_tp=Choix(),references_tp=[r,m],
            vars={'tp_reference':Variable(type_ref),'tp_methode':Variable(MULTI)},info_tp=Label(),
            travail=False,annuler=threading.Event(),messages=queue.Queue(),statut=Variable(),resultat_tp=None)
        a.filtres=lambda:dict(mini=.05,maxi=12,intensite=0);a.indice=lambda:1
        a.annuler_geste=lambda:None;a.dessiner_tp=lambda *args:None;a.actualiser=lambda *args:None
        def invalider(**kw):a.resultat_tp=None
        a.invalider=invalider
        for nom in ['preparer_reference_tp','contexte_tp_valide','lancer_localisation_tp','recevoir_localisation_tp','appliquer_localisation_tp']:
            setattr(a,nom,MethodType(getattr(InterfaceTP,nom),a))
        return a

    def test_mobile_dans_reference_interdit(self):
        for type_ref,cle in [('Grille','scans_grille'),('Carte vectorielle','scans_vecteurs')]:
            a=self.interface(type_ref);getattr(a,cle).add(id(a.scans[1]))
            with self.assertRaisesRegex(ValueError,'mobile'):a.preparer_reference_tp()

    def test_reference_modifiee_ou_selection_mobile_invalide_resultat(self):
        for type_ref in ['Grille','Carte vectorielle','Scan']:
            a=self.interface(type_ref);c=a.preparer_reference_tp();self.assertTrue(a.contexte_tp_valide(c))
            if type_ref=='Grille':a.grille.log_odds[0,0]+=.1
            elif type_ref=='Carte vectorielle':a.vecteurs[0][0,0]+=.1
            else:a.scans[0].pose[0]+=.1
            self.assertFalse(a.contexte_tp_valide(c))
        a=self.interface();c=a.preparer_reference_tp();a.indice=lambda:0;self.assertFalse(a.contexte_tp_valide(c))

    def test_calcul_et_application_reels_sur_grille(self):
        a=self.interface();mesures=a.scans[1].mesures.copy();pose_ref=list(a.scans[0].pose)
        a.scans[1].pose=(np.array(a.scans[1].pose)+[.3,-.2,6]).tolist()
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('interface_tp.threading.Thread',Thread):a.lancer_localisation_tp()
        while not a.messages.empty():
            type_,data=a.messages.get()
            if type_=='tp_resultat':a.recevoir_localisation_tp(data)
            elif type_=='erreur':self.fail(data)
        self.assertIsNotNone(a.resultat_tp)
        a.appliquer_localisation_tp()
        self.assertEqual(a.scans[0].pose,pose_ref);np.testing.assert_array_equal(a.scans[1].mesures,mesures)
        self.assertLess(erreur_pose(a.scans[1].pose,[-.8,.4,15])[0],.1)

    def test_appliquer_refuse_echec_et_resultat_perime(self):
        a=self.interface();c=a.preparer_reference_tp()
        r=localiser_sur_reference(a.scans[1],c['modele'],LOCALE,pose_initiale=[100,100,90])
        a.resultat_tp=(c,r)
        with self.assertRaisesRegex(ValueError,'refusée'):a.appliquer_localisation_tp()
        a.scans[1].pose[0]+=1
        with self.assertRaisesRegex(ValueError,'périmé'):a.appliquer_localisation_tp()


class Evaluation(unittest.TestCase):
    def test_annulation_ne_remplace_pas_csv(self):
        from evaluer_tp_jour2 import evaluer
        import tempfile
        from pathlib import Path
        e=threading.Event();e.set()
        with tempfile.TemporaryDirectory() as dossier:
            p=Path(dossier)/'ancien.csv';p.write_text('ancien résultat')
            with self.assertRaises(InterruptedError):evaluer(p,annuler=e)
            self.assertEqual(p.read_text(),'ancien résultat')
