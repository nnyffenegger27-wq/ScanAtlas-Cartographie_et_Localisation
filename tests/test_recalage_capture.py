import copy
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from cartographie import demonstration
from localisation import ResultatICP, erreur_pose
from recalage_capture import recaler_capture
from app import Atelier
from test_interface_sans_ecran import Variable


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


class CaptureInterface(unittest.TestCase):
    def interface(self, auto=True):
        class Label:
            def configure(self, **kw): self.texte=kw['text']
        a=SimpleNamespace(travail=False,scans=[],inclus=[],visibles=[],
            vars={'auto_icp':Variable('1' if auto else '0')},port=Variable('COM3'),
            annuler=threading.Event(),messages=queue.Queue(),statut=Variable(),
            info_capture=Label())
        a.nombre=lambda cle: {'baud':115200,'quantite':1}[cle]
        a.annuler_geste=lambda:None
        a.parametres_recalage=lambda:('Recherche large + ICP',{})
        a.filtres=lambda:dict(mini=.05,maxi=12,intensite=0)
        a.actualiser=lambda *args:None
        def ajouter(scans):
            a.scans.extend(scans);a.inclus.extend([True]*len(scans));a.visibles.extend([True]*len(scans))
        a.ajouter=ajouter
        return a

    def test_case_desactivee_ne_lance_pas_icp(self):
        a=self.interface(False)
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('app.threading.Thread',Thread),patch('acquisition.capturer',return_value=demonstration()),patch('app.recaler_capture') as recaler:
            Atelier.lancer_capture(a)
        recaler.assert_not_called()
        self.assertEqual(a.messages.get()[0],'scans')

    def test_case_active_utilise_dernier_scan(self):
        a=self.interface(True);r,m=demonstration();a.scans=[r]
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('app.threading.Thread',Thread),patch('acquisition.capturer',return_value=[m]),patch('app.recaler_capture',return_value=[m]) as recaler:
            Atelier.lancer_capture(a)
        self.assertEqual(recaler.call_args.args[1].pose,r.pose)
        self.assertIn('capture_recalee',[t for t,_ in list(a.messages.queue)])

    def test_resultat_perime_conserve_scan_et_decoche_carte(self):
        a=self.interface();r,m=demonstration();a.scans=[r];a.inclus=[True];a.visibles=[True]
        copie=copy.deepcopy(r);r.pose=[9,9,9]
        m.suivi_recalage=dict(valide=True,etat='recalage')
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.recevoir_capture_recalee(a,([m],r,copie,a.filtres()))
        avertir.assert_called_once()
        self.assertEqual(len(a.scans),2)
        self.assertEqual(a.scans[-1].pose,[0,0,0])
        self.assertFalse(a.inclus[-1]);self.assertTrue(a.visibles[-1])
        self.assertEqual(a.scans[-1].suivi_recalage['etat'],'perime')

    def test_echec_affiche_motif(self):
        a=self.interface();r,m=demonstration();a.scans=[r];a.inclus=[True];a.visibles=[True]
        m.suivi_recalage=dict(valide=False,etat='non_recale',message='Recouvrement insuffisant')
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.recevoir_capture_recalee(a,([m],r,copy.deepcopy(r),a.filtres()))
        self.assertIn('Recouvrement insuffisant',avertir.call_args.args[1])
        self.assertIn('Échec',a.info_capture.texte)

    def test_premiere_capture_explique_reference_sans_recalage(self):
        a=self.interface();r=demonstration()[0]
        r.suivi_recalage=dict(valide=True,etat='ancrage')
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.recevoir_capture_recalee(a,([r],None,None,a.filtres()))
        avertir.assert_not_called()
        self.assertIn('Aucun scan précédent',a.info_capture.texte)

    def test_du_flux_serie_a_la_pose_appliquee_et_vue_nuages(self):
        import numpy as np
        from types import MethodType
        a=self.interface();r,m=demonstration()
        a.scans=[r];a.inclus=[True];a.visibles=[True]
        vraie=list(m.pose);pose_ref=list(r.pose)
        lignes=['N,Angle,Distance,Intensity,x,y']
        lignes += [f'{i},{angle},{distance*1000},{intensite},0,0' for i,(angle,distance,intensite) in enumerate(m.mesures)]
        flux=('\n'.join(lignes)+'\n\n').encode()
        class Serial:
            def __init__(self,*args,**kwargs):self.data=flux
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def reset_input_buffer(self):pass
            @property
            def in_waiting(self):return len(self.data)
            def read(self,n):b,self.data=self.data[:n],self.data[n:];return b
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        class Onglets:
            selection=None
            def tabs(self):return ['usb','cloud']
            def tab(self,tab,opt):return 'Nuages' if tab=='cloud' else 'Acquisition USB'
            def select(self,tab):self.selection=tab
        a.onglets=Onglets();a.after=lambda *args:None
        a.poll=MethodType(Atelier.poll,a)
        a.recevoir_capture_recalee=MethodType(Atelier.recevoir_capture_recalee,a)
        with patch('app.threading.Thread',Thread),patch.dict('sys.modules',{'serial':SimpleNamespace(Serial=Serial)}):
            Atelier.lancer_capture(a)
        with patch('app.messagebox.showwarning') as avertir:
            Atelier.poll(a)
        avertir.assert_not_called()
        self.assertEqual(len(a.scans),2)
        ep,ea=erreur_pose(a.scans[-1].pose,vraie)
        self.assertLess(ep,.01);self.assertLess(ea,.1)
        self.assertEqual(r.pose,pose_ref)
        self.assertEqual(a.onglets.selection,'cloud')
        self.assertFalse(a.travail)
        self.assertIn('réussie',a.statut.get())
        np.testing.assert_allclose(a.scans[-1].mesures,m.mesures)

    def test_exception_traitement_ne_perd_pas_capture(self):
        a=self.interface();r,m=demonstration();a.scans=[r];a.inclus=[True];a.visibles=[True]
        class Thread:
            def __init__(self,target,**kw):self.target=target
            def start(self):self.target()
        with patch('app.threading.Thread',Thread),patch('acquisition.capturer',return_value=[m]),patch('app.recaler_capture',side_effect=RuntimeError('calcul impossible')):
            Atelier.lancer_capture(a)
        payload=next(data for type_,data in list(a.messages.queue) if type_=='capture_recalee')
        self.assertEqual(len(payload[0]),1)
        self.assertFalse(payload[0][0].suivi_recalage['valide'])
        self.assertIn('calcul impossible',payload[0][0].suivi_recalage['message'])
