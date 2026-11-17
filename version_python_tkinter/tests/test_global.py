import copy
import threading
import unittest
from types import MethodType
from unittest.mock import patch
import numpy as np
from cartographie import Scan, demonstration
from localisation import ResultatICP, erreur_pose
from localisation_globale import localisation_globale, METHODE_GLOBALE
from assemblage_global import assembler_scans
from app import Atelier


def calcul(pose,ok=True):
    r=ResultatICP(list(pose),[0,0,0],.2,.02,.9,100,2,0,ok,ok,'test')
    r.accord_fin=.9 if ok else .1
    return r

class Global(unittest.TestCase):
    def test_demi_tour_et_depart_tres_lointain(self):
        r,m=demonstration()
        vraie=[m.pose[0],m.pose[1],180.]
        m.mesures[:,0]=(m.mesures[:,0]+m.pose[2]-180)%360
        m.pose=[100,-80,47]
        avant=m.mesures.copy()
        x=localisation_globale(m,r)
        self.assertTrue(x.applicable,x.message)
        ep,ea=erreur_pose(x.pose,vraie)
        self.assertLess(ep,.1);self.assertLess(ea,2)
        np.testing.assert_array_equal(m.mesures,avant)
        self.assertEqual(m.pose,[100,-80,47])

    def test_symetrie_carree_refusee(self):
        a=np.arange(360.);theta=np.deg2rad(a)
        d=2/np.maximum(abs(np.cos(theta)),abs(np.sin(theta)))
        r=Scan('carré',np.column_stack([a,d,np.full(360,220)]),[0,0,0],'SIMULATION',0.)
        x=localisation_globale(copy.deepcopy(r),r)
        self.assertFalse(x.applicable)
        self.assertIn('ambigu',x.message)

    def test_annulation_et_peu_de_points(self):
        r,m=demonstration();e=threading.Event();e.set()
        x=localisation_globale(m,r,annuler=e)
        self.assertFalse(x.applicable);self.assertIn('annul',x.message)
        m.mesures=m.mesures[:5]
        with self.assertRaises(ValueError): localisation_globale(m,r)

class Groupes(unittest.TestCase):
    def test_groupes_conserves_puis_fusion_rigide_par_pont(self):
        a,b=demonstration();c=copy.deepcopy(b);c.nom='C';d=copy.deepcopy(b);d.nom='pont'
        issues=[calcul([0,0,0],False),calcul([0,0,0],False),calcul([0,0,0],False),
                calcul([1,0,0]),calcul([10,2,90]),calcul([2,1,0])]
        with patch('assemblage_global.localisation_globale',side_effect=issues), patch('assemblage_global.plus_proches',side_effect=lambda pts,ref:(np.zeros(len(pts),int),np.zeros(len(pts)))):
            lot=assembler_scans([a,b,c,d])
        self.assertTrue(all(s.suivi_recalage['valide'] for s in lot))
        np.testing.assert_allclose(lot[1].pose,[11,0,90],atol=1e-8)
        np.testing.assert_allclose(lot[2].pose,[11,1,90],atol=1e-8)
        np.testing.assert_allclose(lot[3].pose,[10,2,90],atol=1e-8)
        self.assertEqual(lot[0].pose,a.pose)
        self.assertIsNone(b.suivi_recalage)

    def test_echec_ne_contamine_pas_carte_principale_et_persiste(self):
        a,b=demonstration()
        with patch('assemblage_global.localisation_globale',return_value=calcul([9,9,9],False)):
            lot=assembler_scans([a,b])
        self.assertFalse(lot[1].suivi_recalage['valide'])
        self.assertEqual(lot[1].suivi_recalage['groupe'],1)
        with patch('assemblage_global.localisation_globale',return_value=calcul([9,9,9],False)) as chercher:
            reprise=assembler_scans(lot,reprendre=True)
        self.assertEqual(reprise[1].suivi_recalage['groupe'],1)
        self.assertEqual(chercher.call_count,1)

    def test_changement_ancre_invalide_reprise_des_poses(self):
        a,b=demonstration()
        with patch('assemblage_global.localisation_globale',return_value=calcul([.2,.3,4])):
            lot=assembler_scans([a,b])
        lot[0].pose[0]=20
        with patch('assemblage_global.localisation_globale',return_value=calcul([20.2,.3,4])) as chercher:
            resultat=assembler_scans(lot,reprendre=True)
        self.assertEqual(chercher.call_count,1)
        self.assertEqual(resultat[1].pose,[20.2,.3,4])

class AcquisitionGlobale(unittest.TestCase):
    def interface(self):
        from test_recalage_capture import CaptureInterface
        a=CaptureInterface().interface()
        a.parametres_recalage=lambda:(METHODE_GLOBALE,{})
        a.recevoir_capture_globale=MethodType(Atelier.recevoir_capture_globale,a)
        a.after=lambda *args:None
        a.poll=MethodType(Atelier.poll,a)
        return a

    def test_case_active_global_thread_messages_application(self):
        a=self.interface();r,m=demonstration();a.scans=[r];a.inclus=[True];a.visibles=[True]
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('app.threading.Thread',Thread),patch('acquisition.capturer',return_value=[m]):
            Atelier.lancer_capture(a)
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.poll(a)
        avertir.assert_not_called()
        self.assertFalse(a.travail)
        self.assertEqual(len(a.scans),2)
        self.assertTrue(a.scans[1].suivi_recalage['valide'])
        ep,ea=erreur_pose(a.scans[1].pose,m.pose)
        self.assertLess(ep,.1);self.assertLess(ea,2)
        self.assertIn('concordance',a.info_capture.texte.lower())

    def test_resultat_perime_garde_capture_et_anciennes_poses(self):
        a=self.interface();r,m=demonstration();a.scans=[r];a.inclus=[True];a.visibles=[True]
        copies=copy.deepcopy(a.scans);lot=copy.deepcopy(a.scans+[m])
        for s in lot:s.suivi_recalage={'valide':True,'groupe':0,'message':'accepté'}
        r.pose=[5,5,0]
        with patch('app.messagebox.showwarning'):
            Atelier.recevoir_capture_globale(a,([r],copies,a.filtres(),lot,[m]))
        self.assertEqual(r.pose,[5,5,0]);self.assertFalse(a.inclus[1]);self.assertFalse(a.visibles[1])
        self.assertEqual(len(a.scans),2)
        self.assertEqual(a.scans[1].suivi_recalage['etat'],'perime')

    def test_dernier_scan_en_attente_ne_bloque_pas_capture_globale(self):
        a=self.interface();r,m=demonstration();r.suivi_recalage={'valide':False,'etat':'attente','groupe':1}
        a.scans=[r];a.inclus=[False];a.visibles=[False]
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('app.threading.Thread',Thread),patch('acquisition.capturer',return_value=[m]),patch('app.assembler_scans',return_value=[r,m]) as assembler:
            Atelier.lancer_capture(a)
        assembler.assert_called_once()

class PontsEtSessions(unittest.TestCase):
    def test_un_pont_insuffisant_ne_fusionne_pas_le_groupe(self):
        a,b=demonstration();pont=copy.deepcopy(b)
        issues=[calcul([0,0,0],False),calcul([10,2,90]),calcul([2,1,0]),calcul([0,0,0],False)]
        with patch('assemblage_global.localisation_globale',side_effect=issues),patch('assemblage_global.plus_proches',side_effect=lambda p,q:(np.zeros(len(p),int),np.ones(len(p)))):
            lot=assembler_scans([a,b,pont])
        self.assertFalse(lot[1].suivi_recalage['valide'])
        self.assertEqual(lot[1].suivi_recalage['groupe'],1)
        self.assertTrue(lot[2].suivi_recalage['valide'])

    def test_deux_recouvrements_partiels_constituent_un_pont(self):
        a,b=demonstration();pont=copy.deepcopy(b)
        direct=calcul([0,0,0],False);direct.accord_fin=.45
        x=calcul([10,2,90]);x.accord_fin=.45
        y=calcul([2,1,0]);y.accord_fin=.55
        appels=[]
        def distances(p,q):
            appels.append(1);d=np.ones(len(p))
            if len(appels)==1: d[:len(p)//2]=0
            else: d[len(p)//2:]=0
            return np.zeros(len(p),int),d
        with patch('assemblage_global.localisation_globale',side_effect=[calcul([0,0,0],False),direct,x,y]),patch('assemblage_global.plus_proches',side_effect=distances):
            lot=assembler_scans([a,b,pont])
        self.assertTrue(all(s.suivi_recalage['valide'] for s in lot))
        self.assertEqual(lot[-1].suivi_recalage['etat'],'pont')
        self.assertEqual(lot[-1].suivi_recalage['accord_fin'],1.)

    def test_session_conserve_groupes_et_active_mode_global(self):
        import tempfile
        from pathlib import Path
        from test_interface_sans_ecran import interface_factice,Variable
        a=interface_factice()
        a.vars['icp_methode']=Variable(METHODE_GLOBALE)
        a.scans[0].suivi_recalage={'valide':True,'etat':'ancrage','groupe':0,'methode':METHODE_GLOBALE,'pose_ancre':[0.,0.,0.]}
        a.scans[1].suivi_recalage={'valide':False,'etat':'attente','groupe':2,'methode':METHODE_GLOBALE,'accord_fin':.27,'message':'en attente'}
        a.inclus[1]=False;a.visibles[1]=False
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'session.json'
            with patch('app.filedialog.asksaveasfilename',return_value=str(p)): a.sauver_session()
            a.scans=[]
            with patch('app.filedialog.askopenfilename',return_value=str(p)): a.ouvrir_session()
        self.assertEqual(a.vars['icp_methode'].get(),METHODE_GLOBALE)
        self.assertEqual(a.scans[1].suivi_recalage['groupe'],2)
        self.assertFalse(a.inclus[1]);self.assertFalse(a.visibles[1])
